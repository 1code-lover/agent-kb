"""中文分句与递归切分器回归测试。"""

from __future__ import annotations

from server.splitters.chinese_recursive_text_splitter import ChineseRecursiveTextSplitter
from server.splitters.chinese_text_splitter import ChineseTextSplitter


def test_chinese_recursive_text_splitter_respects_english_punctuation_with_spaces() -> None:
    """英文句号/问号后跟空格时，应能继续按句切分。"""

    splitter = ChineseRecursiveTextSplitter(chunk_size=12, chunk_overlap=0)

    chunks = splitter._split_text("Alpha done. Beta ships? Gamma closes!", splitter._separators)

    assert chunks == ["Alpha done.", "Beta ships?", "Gamma closes!"]


def test_chinese_text_splitter_pdf_mode_normalizes_whitespace_before_sentence_split() -> None:
    """PDF 模式应先归一化空白，再稳定按句切分。"""

    splitter = ChineseTextSplitter(pdf=True, sentence_size=80)

    chunks = splitter.split_text("\u7b2c\u4e00\u6bb5\u3002\n\n\n\u7b2c\u4e8c\u6bb5\uff01   \u7b2c\u4e09\u6bb5\uff1f")

    assert chunks == ["\u7b2c\u4e00\u6bb5\u3002", " \u7b2c\u4e8c\u6bb5\uff01", " \u7b2c\u4e09\u6bb5\uff1f"]
