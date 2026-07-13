"""
PDF OCR 读取器测试：验证文本层直取、扫描件 OCR 回退和空文档处理。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from server.readers.pdf_ocr import PDFOCRReader


PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


def test_text_layer_pdf_uses_pymupdf_without_ocr(tmp_path: Path) -> None:
    """带有效文字层的 PDF 应直接使用 PyMuPDF，不应启动 OCR。"""
    expected_text = "\n".join([
        "PDFOCRReader 文本层直取测试",
        "本文件用于验证 PyMuPDF 分支。",
        "关键词：文本层成功、无需OCR、稻谷标准。",
    ] * 20)
    pdf_path = tmp_path / "text-layer.pdf"
    _create_text_pdf(pdf_path, expected_text)

    reader = PDFOCRReader()

    def fail_if_ocr_called(_file_path: str) -> str:
        raise AssertionError("有效文字层 PDF 不应该触发 OCR")

    reader._ocr_pdf = fail_if_ocr_called  # type: ignore[method-assign]

    docs = reader.load_data(str(pdf_path))

    assert len(docs) == 1
    assert "文本层成功" in docs[0].text
    assert docs[0].metadata["file_name"] == "text-layer.pdf"


def test_blank_pdf_returns_no_documents(tmp_path: Path) -> None:
    """无文字内容的 PDF 应返回空文档列表。"""
    pdf_path = tmp_path / "blank.pdf"
    _create_blank_pdf(pdf_path)

    reader = PDFOCRReader()
    reader._ocr_pdf = lambda _file_path: ""  # type: ignore[method-assign]

    assert reader.load_data(str(pdf_path)) == []


@pytest.mark.slow
def test_scanned_pdf_falls_back_to_ocr_and_recalls_key_terms() -> None:
    """扫描件 PDF 应走 OCR，并召回国标文档中的关键信息。"""
    pdf_path = PROJECT_ROOT / "data" / "rice_standard_3885c3dc.pdf"
    if not pdf_path.exists():
        pytest.skip(f"缺少本地扫描件测试 PDF: {pdf_path}")

    reader = PDFOCRReader()
    docs = reader.load_data(str(pdf_path))

    assert len(docs) == 1
    text = docs[0].text
    assert len(text) >= 500
    expected_terms = ["稻谷", "出糙率", "整精米率"]
    recalled_terms = [term for term in expected_terms if term in text]
    assert len(recalled_terms) >= 2, f"召回关键词不足: {recalled_terms}; 文本前200字: {text[:200]!r}"
