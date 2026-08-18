"""图片 OCR 能力与运行时预热状态管理。"""

from __future__ import annotations

import importlib
import os
import re
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
_SUPPORTED_IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/bmp",
}
_SIGNATURE_SNIFF_FALLBACK_IMAGE_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}
_OCR_TIMING_FLOAT_FIELDS = (
    "ocr_init_ms",
    "ocr_load_image_ms",
    "ocr_predict_ms",
    "ocr_postprocess_ms",
    "ocr_total_ms",
)
_OCR_RUNTIME_CONFIG = {
    "lang": "ch",
    "use_doc_orientation_classify": False,
    "use_doc_unwarping": False,
    "use_textline_orientation": False,
}
_OCR_INSTANCE = None
_OCR_LOCK = threading.RLock()
_OCR_PREDICT_LOCK = threading.RLock()
_OCR_WARMUP_THREAD: threading.Thread | None = None
_OCR_WARMUP_STATUS: dict[str, Any] = {
    "state": "idle",
    "attempt_count": 0,
    "last_error": None,
    "last_duration_ms": None,
    "started_at": None,
    "finished_at": None,
}
_OCR_WARMUP_LOCK = threading.RLock()


def _configure_default_paddlex_model_source() -> None:
    """为国内本地环境设置更稳定的 PaddleX 模型下载默认源。"""
    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "modelscope")
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")


def _ensure_langchain_text_splitter_bridge() -> None:
    """预加载 LangChain 兼容桥，避免 PaddleX 覆盖同名模块。"""
    module = sys.modules.get("langchain.text_splitter")
    if module is not None and not hasattr(module, "TextSplitter"):
        sys.modules.pop("langchain.text_splitter", None)
    importlib.import_module("langchain.text_splitter")


def _utc_now_iso() -> str:
    """返回当前 UTC 时间的 ISO 8601 字符串。"""
    return datetime.now(timezone.utc).isoformat()


def _elapsed_ms(started_at: float) -> float:
    """根据 monotonic 起点计算已耗时毫秒数。"""
    return round(max(time.perf_counter() - started_at, 0.0) * 1000, 3)


def _new_ocr_timing_metrics() -> dict[str, Any]:
    """创建 OCR 细粒度耗时指标的默认结构。"""
    metrics = {field: 0.0 for field in _OCR_TIMING_FLOAT_FIELDS}
    metrics["ocr_instance_reused"] = False
    return metrics


def _finalize_ocr_timing_metrics(metrics: dict[str, Any], request_started_at: float) -> dict[str, Any]:
    """补齐请求级总耗时并返回新的 OCR 指标。"""
    finalized = dict(metrics)
    finalized["ocr_total_ms"] = _elapsed_ms(request_started_at)
    return finalized


def _build_ocr_result(
    *,
    status: str,
    attempted: bool,
    text: str,
    error: str | None,
    engine: str | None,
    timing_metrics: dict[str, Any],
    failure_category: str | None = None,
    missing_dependency: str | None = None,
    dependency_status: str | None = None,
    layout_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造统一的 OCR 结果结构，便于上层诊断。"""
    payload = {
        "status": status,
        "attempted": attempted,
        "text": text,
        "error": error,
        "engine": engine,
    }
    if missing_dependency:
        payload["missing_dependency"] = missing_dependency
        payload["failure_category"] = "dependency_missing"
        payload["dependency_status"] = "missing"
    else:
        if failure_category is not None:
            payload["failure_category"] = failure_category
        if dependency_status is not None:
            payload["dependency_status"] = dependency_status
    payload.update(timing_metrics)
    if layout_metadata:
        payload.update(layout_metadata)
    return payload



def _infer_missing_dependency(exc: Exception) -> str | None:
    """从 OCR 异常中推断缺失的依赖名。"""
    name = getattr(exc, "name", None)
    if isinstance(name, str) and name.strip():
        lowered = name.strip().lower()
    else:
        lowered = ""
    if lowered in {"paddleocr"}:
        return lowered

    message = str(exc or "")
    lowered_message = message.lower()
    if "paddleocr" in lowered_message:
        return "paddleocr"

    match = re.search(r'no module named [\'"]([^\'"]+)[\'"]', message, re.IGNORECASE)
    if match:
        dependency = match.group(1).strip().lower()
        if dependency == "paddleocr":
            return dependency
        return dependency
    return None



def get_ocr_warmup_status() -> dict[str, Any]:
    """返回 OCR 预热线程的当前状态快照。"""
    with _OCR_WARMUP_LOCK:
        status = dict(_OCR_WARMUP_STATUS)
    status["is_ready"] = _OCR_INSTANCE is not None
    return status


def _set_ocr_warmup_status(**kwargs: Any) -> None:
    """原子更新 OCR 预热状态字段。"""
    with _OCR_WARMUP_LOCK:
        _OCR_WARMUP_STATUS.update(kwargs)



def _run_ocr_dummy_inference() -> None:
    """执行一次轻量 OCR 预热推理，提前加载检测与识别模型。"""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    ocr = get_shared_ocr()
    canvas = Image.new("RGB", (1280, 720), color="white")
    draw = ImageDraw.Draw(canvas)
    font = None
    for candidate in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        try:
            if candidate.exists():
                font = ImageFont.truetype(str(candidate), size=36)
                break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    warmup_lines = [
        "ThinkRAG OCR warmup sample",
        "PDF fallback should hit detect and recognize",
        "Local knowledge base OCR warmup",
        "Shared OCR runtime for image and PDF",
    ]
    y = 72
    for line in warmup_lines:
        draw.text((72, y), line, fill="black", font=font)
        y += 140
    warmup_image = np.asarray(canvas, dtype="uint8")
    run_ocr_predict(ocr, warmup_image)


def _run_ocr_warmup() -> None:
    """执行后台 OCR 预热任务。"""
    global _OCR_WARMUP_THREAD
    started_at = time.perf_counter()
    try:
        _run_ocr_dummy_inference()
    except Exception as exc:
        _set_ocr_warmup_status(
            state="failed",
            last_error=str(exc),
            last_duration_ms=_elapsed_ms(started_at),
            finished_at=_utc_now_iso(),
        )
    else:
        _set_ocr_warmup_status(
            state="ready",
            last_error=None,
            last_duration_ms=_elapsed_ms(started_at),
            finished_at=_utc_now_iso(),
        )
    finally:
        with _OCR_WARMUP_LOCK:
            _OCR_WARMUP_THREAD = None


def start_ocr_warmup_in_background(force: bool = False) -> bool:
    """按需启动后台 OCR 预热线程。"""
    global _OCR_WARMUP_THREAD
    with _OCR_WARMUP_LOCK:
        if _OCR_INSTANCE is not None and not force:
            _OCR_WARMUP_STATUS.update(
                state="ready",
                last_error=None,
                last_duration_ms=0.0,
                started_at=_OCR_WARMUP_STATUS.get("started_at") or _utc_now_iso(),
                finished_at=_utc_now_iso(),
            )
            return False
        if _OCR_WARMUP_THREAD is not None and _OCR_WARMUP_THREAD.is_alive() and not force:
            return False
        _OCR_WARMUP_STATUS.update(
            state="warming",
            attempt_count=int(_OCR_WARMUP_STATUS.get("attempt_count") or 0) + 1,
            last_error=None,
            last_duration_ms=None,
            started_at=_utc_now_iso(),
            finished_at=None,
        )
        thread = threading.Thread(target=_run_ocr_warmup, name="thinkrag-ocr-warmup", daemon=True)
        _OCR_WARMUP_THREAD = thread
    thread.start()
    return True


def _reset_ocr_runtime_state_for_tests() -> None:
    """重置 OCR 运行时状态，便于测试隔离。"""
    global _OCR_INSTANCE, _OCR_WARMUP_THREAD
    with _OCR_LOCK:
        _OCR_INSTANCE = None
    with _OCR_WARMUP_LOCK:
        _OCR_WARMUP_THREAD = None
        _OCR_WARMUP_STATUS.clear()
        _OCR_WARMUP_STATUS.update(
            {
                "state": "idle",
                "attempt_count": 0,
                "last_error": None,
                "last_duration_ms": None,
                "started_at": None,
                "finished_at": None,
            }
        )


def _get_ocr(timing_metrics: dict[str, Any] | None = None):
    """获取或初始化 PaddleOCR 实例，并记录初始化耗时。"""
    global _OCR_INSTANCE
    with _OCR_LOCK:
        reused = _OCR_INSTANCE is not None
        if timing_metrics is not None:
            timing_metrics["ocr_instance_reused"] = reused
        if reused:
            return _OCR_INSTANCE

        init_started_at = time.perf_counter()
        try:
            _configure_default_paddlex_model_source()
            _ensure_langchain_text_splitter_bridge()
            from paddleocr import PaddleOCR

            _OCR_INSTANCE = PaddleOCR(**_OCR_RUNTIME_CONFIG)
            return _OCR_INSTANCE
        finally:
            if timing_metrics is not None:
                timing_metrics["ocr_init_ms"] += _elapsed_ms(init_started_at)



def get_shared_ocr(timing_metrics: dict[str, Any] | None = None):
    """获取共享 PaddleOCR 实例，供图片 OCR 与 PDF OCR 共同复用。"""
    return _get_ocr(timing_metrics)


def run_ocr_predict(ocr: Any, image: Any):
    """串行执行 OCR predict，避免共享运行时并发调用不稳定。"""
    with _OCR_PREDICT_LOCK:
        return ocr.predict(image)


def _normalize_ocr_text(text: str) -> str:
    """规范化 OCR 输出文本，清理多余空白与噪声。"""
    normalized_lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    normalized = "\n".join(normalized_lines).strip()
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def _has_meaningful_text(text: str) -> bool:
    """判断 OCR 文本是否包含可用于入库的有效内容。"""
    if not text:
        return False
    visible_chars = [char for char in text if not char.isspace()]
    if len(visible_chars) < 2:
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z0-9]", text))


def _coerce_ocr_box(raw_box: Any) -> tuple[float, float, float, float] | None:
    """把 rec_boxes 或 dt_polys 统一转换为矩形边界。"""
    if hasattr(raw_box, "tolist"):
        raw_box = raw_box.tolist()
    if not isinstance(raw_box, (list, tuple)):
        return None
    try:
        if len(raw_box) == 4 and all(isinstance(value, (int, float)) for value in raw_box):
            x1, y1, x2, y2 = (float(value) for value in raw_box)
            return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
        points = []
        for point in raw_box:
            if hasattr(point, "tolist"):
                point = point.tolist()
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                points.append((float(point[0]), float(point[1])))
        if points:
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            return min(xs), min(ys), max(xs), max(ys)
    except (TypeError, ValueError):
        return None
    return None


def _collect_ocr_items(result: Any) -> list[dict[str, Any]]:
    """提取文本、几何框和置信度，保留原始序号作为稳定回退。"""
    items: list[dict[str, Any]] = []
    sequence = 0
    for ocr_item in result or []:
        payload = getattr(ocr_item, "json", None)
        if not isinstance(payload, dict):
            continue
        res_payload = payload.get("res") or {}
        if not isinstance(res_payload, dict):
            continue
        texts = res_payload.get("rec_texts")
        boxes = res_payload.get("rec_boxes")
        if boxes is None:
            boxes = res_payload.get("dt_polys")
        scores = res_payload.get("rec_scores")
        texts = texts.tolist() if hasattr(texts, "tolist") else (texts if texts is not None else [])
        boxes = boxes.tolist() if hasattr(boxes, "tolist") else (boxes if boxes is not None else [])
        scores = scores.tolist() if hasattr(scores, "tolist") else (scores if scores is not None else [])
        for index, raw_text in enumerate(texts):
            text = str(raw_text or "").strip()
            if not text:
                continue
            box = _coerce_ocr_box(boxes[index]) if index < len(boxes) else None
            score = None
            if index < len(scores):
                try:
                    score = float(scores[index])
                except (TypeError, ValueError):
                    score = None
            item = {"text": text, "box": box, "confidence": score, "sequence": sequence}
            if box:
                x1, y1, x2, y2 = box
                item.update(x1=x1, y1=y1, x2=x2, y2=y2, x_center=(x1 + x2) / 2, y_center=(y1 + y2) / 2, height=max(y2 - y1, 1.0))
            items.append(item)
            sequence += 1
    return items


def _cluster_ocr_rows(items: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """按 y 聚类为行，再按 x 排序；无 box 时回退原始顺序。"""
    boxed = [item for item in items if item.get("box")]
    if len(boxed) != len(items):
        return [[item] for item in sorted(items, key=lambda item: item["sequence"])]
    heights = sorted(float(item["height"]) for item in boxed)
    median_height = heights[len(heights) // 2] if heights else 12.0
    tolerance = max(median_height * 0.6, 4.0)
    rows: list[list[dict[str, Any]]] = []
    row_centers: list[float] = []
    for item in sorted(boxed, key=lambda current: (current["y_center"], current["x_center"], current["sequence"])):
        if not rows or abs(float(item["y_center"]) - row_centers[-1]) > tolerance:
            rows.append([item])
            row_centers.append(float(item["y_center"]))
        else:
            rows[-1].append(item)
            row_centers[-1] = sum(float(cell["y_center"]) for cell in rows[-1]) / len(rows[-1])
    for row in rows:
        row.sort(key=lambda item: (item["x_center"], item["sequence"]))
    return rows


def _escape_markdown_cell(text: str) -> str:
    """转义 Markdown 表格单元格。"""
    return text.replace("|", r"\|").replace("\n", " ").strip()


def extract_ocr_layout(result: Any) -> dict[str, Any]:
    """从 OCR 几何结果恢复阅读顺序，并输出可跨页合并的结构化块。"""
    from server.readers.ocr_layout import build_layout_blocks, render_layout_blocks

    items = _collect_ocr_items(result)
    rows = _cluster_ocr_rows(items)
    blocks = build_layout_blocks(rows)
    table_blocks = [block for block in blocks if block.get("type") == "table"]
    paragraph_blocks = [block for block in blocks if block.get("type") == "paragraph"]
    table_column_count = max(
        (len((block.get("rows") or [[]])[0]) for block in table_blocks if block.get("rows")),
        default=0,
    )
    if table_blocks and paragraph_blocks:
        layout_mode = "mixed"
    elif table_blocks:
        layout_mode = "table"
    else:
        layout_mode = "geometry_lines" if items and all(item.get("box") for item in items) else "sequence"

    confidences = [float(item["confidence"]) for item in items if item.get("confidence") is not None]
    return {
        "text": render_layout_blocks(blocks),
        "blocks": blocks,
        "layout_mode": layout_mode,
        "line_count": len(rows),
        "table_detected": bool(table_blocks),
        "table_row_count": sum(len(block.get("rows") or []) for block in table_blocks),
        "table_column_count": table_column_count,
        "table_block_count": len(table_blocks),
        "merged_block_count": 0,
        "continued_page_count": 0,
        "removed_repeated_header_count": 0,
        "mean_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
    }


def _collect_rec_texts(result: Any) -> list[str]:
    """从 PaddleOCR 返回结果中提取识别文本列表。"""
    texts: list[str] = []
    for ocr_item in result or []:
        payload = getattr(ocr_item, "json", None)
        if not isinstance(payload, dict):
            continue
        res_payload = payload.get("res") or {}
        if isinstance(res_payload, dict):
            rec_texts = res_payload.get("rec_texts") or []
        else:
            rec_texts = []
        for raw_text in rec_texts:
            value = str(raw_text or "").strip()
            if value:
                texts.append(value)
    return texts


def _has_supported_image_signature(path: Path) -> bool:
    """基于文件头识别当前 OCR 能处理的图片格式。"""
    try:
        with path.open("rb") as handle:
            sample = handle.read(32)
    except OSError:
        return False

    if sample.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if sample.startswith(b"\xff\xd8\xff"):
        return True
    if sample.startswith(b"BM"):
        return True
    if len(sample) >= 12 and sample[:4] == b"RIFF" and sample[8:12] == b"WEBP":
        return True
    return False


def _is_supported_image_input(path: Path, content_type: str) -> bool:
    """判断当前输入是否属于可进入 OCR 流程的图片。"""
    suffix = path.suffix.lower()
    mime_type = str(content_type or "").strip().lower()
    if suffix in _SUPPORTED_IMAGE_SUFFIXES or mime_type in _SUPPORTED_IMAGE_MIME_TYPES:
        return True
    if suffix:
        return False
    if mime_type not in _SIGNATURE_SNIFF_FALLBACK_IMAGE_MIME_TYPES:
        return False
    return _has_supported_image_signature(path)


def extract_image_ocr_result(file_path: str | Path, *, content_type: str = "") -> dict[str, Any]:
    """对图片执行 OCR，并返回稳定的诊断结果。"""
    request_started_at = time.perf_counter()
    timing_metrics = _new_ocr_timing_metrics()
    path = Path(file_path).resolve()
    if not _is_supported_image_input(path, content_type):
        return _build_ocr_result(
            status="skipped",
            attempted=False,
            text="",
            error=None,
            engine=None,
            timing_metrics=_finalize_ocr_timing_metrics(timing_metrics, request_started_at),
        )

    try:
        load_started_at = time.perf_counter()
        import numpy as np
        from PIL import Image

        with Image.open(path) as image:
            rgb_image = image.convert("RGB")
            img_array = np.asarray(rgb_image)
        timing_metrics["ocr_load_image_ms"] += _elapsed_ms(load_started_at)

        ocr = _get_ocr(timing_metrics)
        predict_started_at = time.perf_counter()
        result = run_ocr_predict(ocr, img_array)
        timing_metrics["ocr_predict_ms"] += _elapsed_ms(predict_started_at)
    except Exception as exc:
        missing_dependency = _infer_missing_dependency(exc)
        return _build_ocr_result(
            status="failed",
            attempted=True,
            text="",
            error=str(exc),
            engine="paddleocr",
            timing_metrics=_finalize_ocr_timing_metrics(timing_metrics, request_started_at),
            failure_category="ocr_runtime_error",
            missing_dependency=missing_dependency,
            dependency_status="missing" if missing_dependency else "unknown",
        )

    postprocess_started_at = time.perf_counter()
    layout = extract_ocr_layout(result)
    normalized_text = _normalize_ocr_text(layout.pop("text"))
    layout.pop("blocks", None)
    timing_metrics["ocr_postprocess_ms"] += _elapsed_ms(postprocess_started_at)
    finalized_metrics = _finalize_ocr_timing_metrics(timing_metrics, request_started_at)
    if not _has_meaningful_text(normalized_text):
        return _build_ocr_result(
            status="no_text",
            attempted=True,
            text="",
            error=None,
            engine="paddleocr",
            timing_metrics=finalized_metrics,
            layout_metadata=layout,
        )

    return _build_ocr_result(
        status="success",
        attempted=True,
        text=normalized_text,
        error=None,
        engine="paddleocr",
        timing_metrics=finalized_metrics,
        layout_metadata=layout,
    )
