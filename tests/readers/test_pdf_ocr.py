"""
PDF OCR 读取器测试：覆盖文字层直取、乱码回退、多批 OCR 聚合与中文扫描锚点。
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from llama_index.core import Document

from server.readers import image_ocr
from server.readers.pdf_ocr import PDFOCRReader
from server.utils.font_fallbacks import OCR_FONT_CANDIDATES, load_first_available_font
from server.text_splitter import create_text_splitter


FONT_CANDIDATES = OCR_FONT_CANDIDATES


def _create_text_pdf(path: Path, text: str) -> None:
    """创建带真实文字层的 PDF fixture。"""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in text.splitlines():
        page.insert_text((72, y), line, fontsize=11, fontname="china-s")
        y += 18
    doc.save(path)
    doc.close()


def _create_blank_pdf(path: Path) -> None:
    """创建没有文字层的空白 PDF fixture。"""
    import fitz

    doc = fitz.open()
    doc.new_page()
    doc.save(path)
    doc.close()


def _pick_font(size: int = 28):
    """优先选择支持中文的系统字体，避免扫描件 fixture 出现方块字。"""
    font, _ = load_first_available_font(size=size, candidates=FONT_CANDIDATES)
    return font


def _create_scanned_pdf(path: Path, lines: list[str]) -> None:
    """创建只包含图片页的扫描件 PDF fixture。"""
    import fitz
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1400, 900), color="white")
    draw = ImageDraw.Draw(image)
    font = _pick_font(28)
    y = 80
    for line in lines:
        draw.text((72, y), line, fill="black", font=font)
        y += 42

    image_path = path.with_suffix(".png")
    image.save(image_path)

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(36, 36, 559, 806), filename=str(image_path))
    doc.save(path)
    doc.close()
    image_path.unlink(missing_ok=True)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Page 1", True),
        ("Confidential", True),
        ("Product Overview\nLocal KB import keeps a clean text layer.", False),
        ("系统架构说明\n当前 PDF 文本层可直接进入知识库索引。", False),
    ],
)
def test_text_is_garbled_heuristic(text: str, expected: bool) -> None:
    """短碎片文本应判为无效文字层，正常中英文正文不应被误判。"""
    assert PDFOCRReader._text_is_garbled(text) is expected


def test_text_layer_pdf_uses_pymupdf_without_ocr(tmp_path: Path) -> None:
    """带有效文字层的 PDF 应直接使用 PyMuPDF，不应触发 OCR。"""
    expected_text = "\n".join(
        [
            "PDFOCRReader 文本层直取测试。",
            "本文件用于验证 PyMuPDF 分支。",
            "关键词：文本层成功、无需 OCR、稳定导入。",
        ]
        * 20
    )
    pdf_path = tmp_path / "text-layer.pdf"
    _create_text_pdf(pdf_path, expected_text)

    reader = PDFOCRReader()

    def fail_if_ocr_called(_file_path: str) -> str:
        raise AssertionError("带有效文字层的 PDF 不应该触发 OCR")

    reader._ocr_pdf = fail_if_ocr_called  # type: ignore[method-assign]

    docs = reader.load_data(str(pdf_path))

    assert len(docs) == 1
    assert "PDFOCRReader 文本层直取测试" in docs[0].text
    assert "稳定导入" in docs[0].text


def test_garbled_text_layer_pdf_falls_back_to_ocr(tmp_path: Path) -> None:
    """只有页码或水印碎片的文字层 PDF 应回退到 OCR。"""
    pdf_path = tmp_path / "garbled-layer.pdf"
    _create_text_pdf(pdf_path, "Page 1\nConfidential")

    reader = PDFOCRReader()
    reader._ocr_pdf = lambda _file_path: 'OCR 回退成功\n系统架构图说明'  # type: ignore[method-assign]

    docs = reader.load_data(str(pdf_path))

    assert len(docs) == 1
    assert docs[0].text == 'OCR 回退成功\n系统架构图说明'
    assert docs[0].metadata["file_name"] == "garbled-layer.pdf"


def test_blank_pdf_returns_no_documents(tmp_path: Path) -> None:
    """无文字内容的 PDF 应返回空文档列表。"""
    pdf_path = tmp_path / "blank.pdf"
    _create_blank_pdf(pdf_path)

    reader = PDFOCRReader()
    reader._ocr_pdf = lambda _file_path: ""  # type: ignore[method-assign]

    assert reader.load_data(str(pdf_path)) == []
    diagnostics = reader.consume_last_diagnostics()
    assert diagnostics is not None
    assert diagnostics["source_type"] == "pdf_ocr_fallback"
    assert diagnostics["ocr_attempted"] is True
    assert diagnostics["ocr_status"] == "no_text"
    assert diagnostics["indexed_from_ocr"] is False
    assert diagnostics["ocr_engine"] == "paddleocr"


def test_pdf_reader_lazy_ocr_reuses_shared_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """PDF OCR 应复用 image_ocr 的共享运行时，而不是重复初始化 PaddleOCR。"""
    shared_ocr = object()
    shared_calls: list[str] = []

    def fake_get_shared_ocr(timing_metrics=None):
        shared_calls.append("called")
        return shared_ocr

    class BombPaddleOCR:
        def __init__(self, *args, **kwargs):
            raise AssertionError("PDFOCRReader 不应重复初始化 PaddleOCR")

    monkeypatch.setattr(image_ocr, "get_shared_ocr", fake_get_shared_ocr, raising=False)
    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PaddleOCR=BombPaddleOCR))

    reader = PDFOCRReader()

    assert reader._lazy_ocr() is shared_ocr
    assert reader._lazy_ocr() is shared_ocr
    assert shared_calls == ["called"]


def test_pdf_ocr_fallback_uses_shared_predict_wrapper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """扫描件 PDF 回退到 OCR 时，应复用共享 predict 包装器。"""
    pdf_path = tmp_path / "shared-predict.pdf"
    _create_scanned_pdf(pdf_path, ["Shared OCR predict wrapper", "PDF fallback must reuse it"])

    shared_ocr = object()
    predict_calls: list[tuple[object, tuple[int, ...]]] = []

    def fake_run_ocr_predict(ocr, img_array):
        predict_calls.append((ocr, tuple(img_array.shape)))
        return [SimpleNamespace(json={"res": {"rec_texts": ["共享 OCR 结果", "扫描 PDF 文本"]}})]

    reader = PDFOCRReader()
    monkeypatch.setattr(reader, "_lazy_ocr", lambda timing_metrics=None: shared_ocr)
    monkeypatch.setattr(image_ocr, "run_ocr_predict", fake_run_ocr_predict, raising=False)

    text = reader._ocr_pdf(str(pdf_path))

    assert "共享 OCR 结果" in text
    assert predict_calls
    assert predict_calls[0][0] is shared_ocr
    assert len(predict_calls[0][1]) == 3


@pytest.mark.slow
def test_scanned_pdf_falls_back_to_ocr_and_accumulates_all_predict_batches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """扫描件 PDF 应走 OCR 回退，且不能丢失 PaddleOCR 多批次返回的文本。"""
    pdf_path = tmp_path / "scanned.pdf"
    _create_scanned_pdf(
        pdf_path,
        [
            "Rice quality control sheet",
            "Scanned PDF fixture for OCR fallback",
            "This page intentionally has no text layer",
        ],
    )

    class FakeOCR:
        def predict(self, _img_array):
            return [
                SimpleNamespace(json={"res": {"rec_texts": ["稻谷质量标准", "出糙率不低于 75%"]}}),
                SimpleNamespace(json={"res": {"rec_texts": ["整精米率不低于 45%", "杂质含量应受控"]}}),
            ]

    reader = PDFOCRReader()
    monkeypatch.setattr(reader, "_lazy_ocr", lambda timing_metrics=None: FakeOCR())

    docs = reader.load_data(str(pdf_path))

    assert len(docs) == 1
    text = docs[0].text
    for term in ["稻谷", "出糙率", "整精米率", "杂质"]:
        assert term in text
    assert text.count("\n") >= 3
    assert docs[0].metadata["file_name"] == "scanned.pdf"


def test_scanned_pdf_preserves_mixed_chinese_and_anchor_tokens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """中文扫描件 OCR 回退应保留中文正文和英文锚点，供 semireal 检索使用。"""
    pdf_path = tmp_path / "scanned-zh-anchor.pdf"
    _create_scanned_pdf(
        pdf_path,
        [
            "交接窗口 handover window",
            "扫描件页面需要 OCR fallback",
            "merge every predict batch 后写回索引",
        ],
    )

    class FakeOCR:
        def predict(self, _img_array):
            return [
                SimpleNamespace(
                    json={
                        "res": {
                            "rec_texts": [
                                "handover window 扫描页没有文字层时",
                                "OCR fallback must merge every predict batch for the same page",
                            ]
                        }
                    }
                ),
                SimpleNamespace(
                    json={
                        "res": {
                            "rec_texts": [
                                "中文流程说明也要写回当前知识库",
                                "避免导入后只剩图片像素",
                            ]
                        }
                    }
                ),
            ]

    reader = PDFOCRReader()
    monkeypatch.setattr(reader, "_lazy_ocr", lambda timing_metrics=None: FakeOCR())

    docs = reader.load_data(str(pdf_path))

    assert len(docs) == 1
    text = docs[0].text
    for term in ["handover window", "merge every predict batch", "中文流程说明", "当前知识库"]:
        assert term in text
    assert docs[0].metadata["file_name"] == "scanned-zh-anchor.pdf"


def test_pdf_load_data_merges_ocr_timing_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    """load_data 应保留 _ocr_pdf 写入的 OCR 耗时指标，不能被回退元数据覆盖。"""
    reader = PDFOCRReader()

    monkeypatch.setattr(reader, "_try_pymupdf", lambda _file_path: ("", False))

    def fake_ocr_pdf(_file_path: str) -> str:
        reader._set_last_diagnostics(
            {
                "ocr_init_ms": 11.0,
                "ocr_load_image_ms": 22.0,
                "ocr_predict_ms": 33.0,
                "ocr_postprocess_ms": 4.0,
                "ocr_total_ms": 70.0,
                "ocr_instance_reused": True,
            }
        )
        return "OCR 识别正文"

    monkeypatch.setattr(reader, "_ocr_pdf", fake_ocr_pdf)

    docs = reader.load_data("demo.pdf")

    assert len(docs) == 1
    metadata = docs[0].metadata
    assert metadata["source_type"] == "pdf_ocr_fallback"
    assert metadata["ocr_status"] == "success"
    assert metadata["ocr_total_ms"] == pytest.approx(70.0)
    assert metadata["ocr_predict_ms"] == pytest.approx(33.0)
    assert metadata["ocr_instance_reused"] is True



def test_pdf_ocr_document_excludes_internal_metadata_from_chunk_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PDF OCR 文档应排除路径型与 OCR 运行时 metadata，避免 128 chunk_size 下切块失败。"""
    pdf_path = tmp_path / "very" / "deep" / "nested" / "pdf" / "assets" / "for" / "chunk" / "budget" / "scan.pdf"
    reader = PDFOCRReader()

    monkeypatch.setattr(reader, "_try_pymupdf", lambda _file_path: ("", False))

    def fake_ocr_pdf(_file_path: str) -> str:
        reader._set_last_diagnostics(
            {
                "ocr_init_ms": 11.0,
                "ocr_load_image_ms": 22.0,
                "ocr_predict_ms": 33.0,
                "ocr_postprocess_ms": 4.0,
                "ocr_total_ms": 70.0,
                "ocr_instance_reused": True,
            }
        )
        return "知识库的授权范围需要显式声明。"

    monkeypatch.setattr(reader, "_ocr_pdf", fake_ocr_pdf)

    docs = reader.load_data(str(pdf_path))

    assert len(docs) == 1
    document = docs[0]
    assert "file_path" in document.excluded_embed_metadata_keys
    assert "source_type" in document.excluded_embed_metadata_keys
    assert "ocr_total_ms" in document.excluded_embed_metadata_keys
    assert "ocr_instance_reused" in document.excluded_llm_metadata_keys

    splitter = create_text_splitter(chunk_size=128, chunk_overlap=16)
    raw_document = Document(text=document.text, metadata=dict(document.metadata))
    with pytest.raises(ValueError, match="Metadata length"):
        splitter.get_nodes_from_documents([raw_document])

    nodes = splitter.get_nodes_from_documents([document])
    assert len(nodes) == 1
    assert nodes[0].metadata["file_name"] == "scan.pdf"
    assert nodes[0].metadata["source_type"] == "pdf_ocr_fallback"
    assert nodes[0].metadata["ocr_status"] == "success"


def test_short_english_text_layer_pdf_uses_pymupdf_without_ocr(tmp_path: Path) -> None:
    """短英文正文型文字层 PDF 也应保留文字层，不应误触发 OCR。"""
    expected_text = "Product Overview\nThis PDF keeps a clean text layer for local knowledge base import."
    pdf_path = tmp_path / "english-short.pdf"
    _create_text_pdf(pdf_path, expected_text)

    reader = PDFOCRReader()

    def fail_if_ocr_called(_file_path: str) -> str:
        raise AssertionError("短英文正文型文字层 PDF 不应该触发 OCR")

    reader._ocr_pdf = fail_if_ocr_called  # type: ignore[method-assign]

    docs = reader.load_data(str(pdf_path))

    assert len(docs) == 1
    assert "Product Overview" in docs[0].text
    assert "clean text layer" in docs[0].text


def test_pdf_ocr_preserves_page_markers_and_layout_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """扫描 PDF 应保留页边界，并汇总版面与表格诊断元数据。"""
    import fitz

    pdf_path = tmp_path / "layout-pages.pdf"
    fixture = fitz.open()
    fixture.new_page()
    fixture.new_page()
    fixture.save(pdf_path)
    fixture.close()
    page_results = iter(
        [
            [SimpleNamespace(json={"res": {"rec_texts": ["标题", "正文"], "rec_boxes": [[10, 10, 80, 30], [10, 40, 80, 60]]}})],
            [SimpleNamespace(json={"res": {"rec_texts": ["名称", "数量", "大米", "10"], "rec_boxes": [[10, 10, 80, 30], [120, 10, 170, 30], [10, 40, 80, 60], [120, 40, 170, 60]]}})],
        ]
    )
    reader = PDFOCRReader()
    monkeypatch.setattr(reader, "_lazy_ocr", lambda timing_metrics=None: object())
    monkeypatch.setattr(image_ocr, "run_ocr_predict", lambda ocr, image: next(page_results))

    docs = reader.load_data(str(pdf_path))

    assert "[Page 1]\n标题\n正文" in docs[0].text
    assert "[Page 2]\n| 名称 | 数量 |" in docs[0].text
    assert docs[0].metadata["layout_mode"] == "mixed"
    assert docs[0].metadata["page_count"] == 2
    assert docs[0].metadata["table_detected"] is True
    assert docs[0].metadata["table_row_count"] == 2
    assert docs[0].metadata["table_column_count"] == 2
