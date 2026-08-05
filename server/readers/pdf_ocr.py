"""
PDF 文本提取器：优先使用 PyMuPDF 提取文字层；当文字层为空或疑似无效时，自动回退到 PaddleOCR。
"""

import copy
import os
import re
import time

import numpy as np
from llama_index.core.readers.base import BasePydanticReader
from llama_index.core.schema import Document


PDF_INDEX_EXCLUDED_METADATA_KEYS = (
    "file_path",
    "source_type",
    "ocr_attempted",
    "ocr_status",
    "ocr_text_length",
    "ocr_error",
    "indexed_from_ocr",
    "ocr_engine",
    "ocr_init_ms",
    "ocr_load_image_ms",
    "ocr_predict_ms",
    "ocr_postprocess_ms",
    "ocr_total_ms",
    "ocr_instance_reused",
    "failure_category",
    "missing_dependency",
    "dependency_status",
)


class PDFOCRReader(BasePydanticReader):
    """PDF 读取器，支持扫描件 OCR 回退。"""

    is_remote: bool = False
    lang: str = "ch"
    use_textline_orientation: bool = True
    ocr_kw: dict = {}

    @staticmethod
    def _collect_rec_texts(result) -> list[str]:
        """提取 PaddleOCR 多批次返回中的识别文本，并过滤空字符串。"""
        texts: list[str] = []
        for ocr_res in result or []:
            payload = getattr(ocr_res, "json", None)
            if not isinstance(payload, dict):
                continue
            res_payload = payload.get("res") or {}
            if not isinstance(res_payload, dict):
                continue
            for raw_text in res_payload.get("rec_texts") or []:
                value = str(raw_text or "").strip()
                if value:
                    texts.append(value)
        return texts

    def __init__(self, lang="ch", use_textline_orientation=True, **ocr_kw):
        super().__init__(lang=lang, use_textline_orientation=use_textline_orientation, ocr_kw=ocr_kw)
        self._ocr = None
        self._last_diagnostics = None

    def _set_last_diagnostics(self, diagnostics: dict | None) -> None:
        """缓存最近一次 PDF 解析诊断，供上游导入回执消费。"""
        self._last_diagnostics = copy.deepcopy(diagnostics) if isinstance(diagnostics, dict) else None

    def consume_last_diagnostics(self) -> dict | None:
        """消费最近一次 PDF 解析诊断，避免跨文件串味。"""
        payload = copy.deepcopy(self._last_diagnostics) if isinstance(self._last_diagnostics, dict) else None
        self._last_diagnostics = None
        return payload

    @classmethod
    def class_name(cls) -> str:
        return "PDFOCRReader"

    def _lazy_ocr(self, timing_metrics: dict | None = None):
        """懒加载共享 OCR 运行时，确保 PDF OCR 与图片 OCR 复用同一实例。"""
        if self._ocr is None:
            from server.readers.image_ocr import get_shared_ocr

            self._ocr = get_shared_ocr(timing_metrics=timing_metrics)
        return self._ocr

    @staticmethod
    def _text_is_garbled(text: str) -> bool:
        """判断 PyMuPDF 提取文本是否像正文，而不是页码、水印或碎片。"""
        text = text.strip()
        if not text:
            return True

        visible_chars = [char for char in text if not char.isspace()]
        visible_len = len(visible_chars)
        if visible_len == 0:
            return True

        cjk_chars = len(re.findall(r"[一-鿿]", text))
        latin_chars = len(re.findall(r"[A-Za-z]", text))
        digit_chars = len(re.findall(r"\d", text))
        readable_ratio = (cjk_chars + latin_chars + digit_chars) / visible_len
        if readable_ratio < 0.3:
            return True

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        unique_lines = list(dict.fromkeys(lines))
        longest_line_length = max((len(line) for line in unique_lines), default=0)

        # 仅有极短碎片且行数很少时，仍视为无效文字层，避免页码或水印误判为正文。
        if len(unique_lines) <= 2 and visible_len < 30 and longest_line_length < 20:
            return True

        return False

    def _try_pymupdf(self, file_path):
        try:
            import fitz

            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            if text and text.strip() and not self._text_is_garbled(text):
                return text, True
        except Exception:
            pass
        return "", False

    @staticmethod
    def _build_page_matrix(page) -> object:
        """按页面长边自适应缩放渲染尺寸，控制扫描件 OCR 的输入分辨率。"""
        import fitz

        long_side = max(float(page.rect.width), float(page.rect.height), 1.0)
        target_long_side = 1280.0
        scale = max(min(target_long_side / long_side, 1.5), 1.0)
        return fitz.Matrix(scale, scale)

    def _ocr_pdf(self, file_path):
        try:
            import fitz
        except ImportError as exc:
            raise ImportError("缺少 PyMuPDF（fitz），无法执行 PDF OCR。") from exc

        ocr_timing_metrics = {
            "ocr_init_ms": 0.0,
            "ocr_load_image_ms": 0.0,
            "ocr_predict_ms": 0.0,
            "ocr_postprocess_ms": 0.0,
            "ocr_total_ms": 0.0,
            "ocr_instance_reused": False,
        }
        ocr_started_at = time.perf_counter()
        ocr = self._lazy_ocr(timing_metrics=ocr_timing_metrics)
        doc = fitz.open(file_path)
        pages_text: list[str] = []
        try:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                render_started_at = time.perf_counter()
                pix = page.get_pixmap(matrix=self._build_page_matrix(page))
                img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                if img_array.shape[2] == 4:
                    img_array = img_array[:, :, :3]
                render_elapsed_ms = round(max(time.perf_counter() - render_started_at, 0.0) * 1000, 3)
                ocr_timing_metrics["ocr_load_image_ms"] += render_elapsed_ms

                from server.readers.image_ocr import run_ocr_predict

                predict_started_at = time.perf_counter()
                result = run_ocr_predict(ocr, img_array)
                predict_elapsed_ms = round(max(time.perf_counter() - predict_started_at, 0.0) * 1000, 3)
                ocr_timing_metrics["ocr_predict_ms"] += predict_elapsed_ms

                postprocess_started_at = time.perf_counter()
                page_text = "\n".join(self._collect_rec_texts(result)).strip()
                postprocess_elapsed_ms = round(max(time.perf_counter() - postprocess_started_at, 0.0) * 1000, 3)
                ocr_timing_metrics["ocr_postprocess_ms"] += postprocess_elapsed_ms
                pages_text.append(page_text)
                print(
                    f"  OCR 页 {page_num + 1}/{len(doc)} → {len(page_text)} 字 | "
                    f"render={render_elapsed_ms:.1f}ms predict={predict_elapsed_ms:.1f}ms "
                    f"post={postprocess_elapsed_ms:.1f}ms"
                )
        finally:
            doc.close()

        ocr_timing_metrics["ocr_total_ms"] = round(max(time.perf_counter() - ocr_started_at, 0.0) * 1000, 3)
        self._set_last_diagnostics({**(self._last_diagnostics or {}), **ocr_timing_metrics})
        return "\n\n".join(text for text in pages_text if text)
    def load_data(self, file_path, **kwargs):
        resolved_path = os.fspath(file_path)
        filename = os.path.basename(resolved_path)
        self._set_last_diagnostics(None)

        text, ok = self._try_pymupdf(file_path)
        if ok:
            print(f"  PyMuPDF 文本层命中: {filename}，提取 {len(text)} 字")
            self._set_last_diagnostics(
                {
                    "file_name": filename,
                    "file_path": resolved_path,
                    "source_type": "pdf_text_layer",
                    "ocr_attempted": False,
                    "ocr_status": None,
                    "ocr_text_length": 0,
                    "ocr_error": None,
                    "indexed_from_ocr": False,
                    "ocr_engine": None,
                }
            )
        else:
            print(f"  PDF 文字层不可用，回退 PaddleOCR: {filename}")
            text = self._ocr_pdf(file_path)
            stripped_text = text.strip()
            existing_diagnostics = self._last_diagnostics or {}
            self._set_last_diagnostics(
                {
                    **existing_diagnostics,
                    "file_name": filename,
                    "file_path": resolved_path,
                    "source_type": "pdf_ocr_fallback",
                    "ocr_attempted": True,
                    "ocr_status": "success" if stripped_text else "no_text",
                    "ocr_text_length": len(stripped_text),
                    "ocr_error": None,
                    "indexed_from_ocr": bool(stripped_text),
                    "ocr_engine": "paddleocr",
                }
            )

        if not text.strip():
            return []

        metadata = {
            "file_name": filename,
            "file_path": resolved_path,
            **(self._last_diagnostics or {}),
        }
        excluded_keys = [key for key in PDF_INDEX_EXCLUDED_METADATA_KEYS if key in metadata]
        doc = Document(
            text=text,
            metadata=metadata,
            excluded_embed_metadata_keys=excluded_keys,
            excluded_llm_metadata_keys=excluded_keys,
        )
        return [doc]
