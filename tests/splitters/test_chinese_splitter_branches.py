"""\u4e2d\u6587\u5207\u5206\u5668\u5206\u652f\u56de\u5f52\u6d4b\u8bd5\u3002"""

from __future__ import annotations

from server.splitters.chinese_recursive_text_splitter import (
    ChineseRecursiveTextSplitter,
    _split_text_with_regex_from_end,
)
from server.splitters.chinese_text_splitter import ChineseTextSplitter


def test_split_text_with_regex_from_end_supports_plain_split_and_char_fallback() -> None:
    """\u9012\u5f52\u5207\u5206\u8f85\u52a9\u51fd\u6570\u5e94\u8986\u76d6\u666e\u901a\u5206\u5272\u4e0e\u7a7a\u5206\u9694\u7b26\u9010\u5b57\u56de\u9000\u3002"""

    assert _split_text_with_regex_from_end("a,b,c", ",", False) == ["a", "b", "c"]
    assert _split_text_with_regex_from_end("ABC", "", False) == ["A", "B", "C"]


def test_chinese_recursive_text_splitter_flushes_good_splits_and_long_segments() -> None:
    """\u9012\u5f52\u5207\u5206\u65f6\u5e94\u5148\u5237\u51fa\u77ed\u7247\u6bb5\uff0c\u518d\u4fdd\u7559\u8d85\u957f\u7247\u6bb5\u5e76\u7ee7\u7eed\u6536\u5c3e\u3002"""

    splitter = ChineseRecursiveTextSplitter(
        separators=[","],
        keep_separator=False,
        is_separator_regex=False,
        chunk_size=5,
        chunk_overlap=0,
    )

    chunks = splitter._split_text("a,bigsegment,b", splitter._separators)

    assert chunks == ["a", "bigsegment", "b"]


def test_chinese_recursive_text_splitter_handles_empty_separator_merge() -> None:
    """\u5f53\u4ec5\u5269\u7a7a\u5206\u9694\u7b26\u65f6\uff0c\u9012\u5f52\u5207\u5206\u5e94\u9000\u5316\u4e3a\u6309\u5b57\u7b26\u5408\u5e76\u3002"""

    splitter = ChineseRecursiveTextSplitter(
        separators=[""],
        keep_separator=False,
        is_separator_regex=False,
        chunk_size=2,
        chunk_overlap=0,
    )

    chunks = splitter._split_text("ABCD", splitter._separators)

    assert chunks == ["AB", "CD"]


def test_chinese_text_splitter_split_text1_normalizes_pdf_whitespace() -> None:
    """split_text1 \u5728 PDF \u6a21\u5f0f\u4e0b\u5e94\u5148\u505a\u7a7a\u767d\u5f52\u4e00\u5316\u518d\u6309\u53e5\u53f7\u5207\u5206\u3002"""

    splitter = ChineseTextSplitter(pdf=True, sentence_size=20)

    chunks = splitter.split_text1("\u7b2c\u4e00\u53e5\u3002\n\n\n\u7b2c\u4e8c\u53e5\uff01   \u7b2c\u4e09\u53e5\uff1f")

    assert chunks == ["\u7b2c\u4e00\u53e5\u3002", " \u7b2c\u4e8c\u53e5\uff01", " \u7b2c\u4e09\u53e5\uff1f"]


def test_chinese_text_splitter_split_text_breaks_long_sentences_by_space_and_comma() -> None:
    """\u957f\u53e5\u5e94\u7ee7\u7eed\u6309\u9017\u53f7\u3001\u53cc\u7a7a\u683c\u548c\u5355\u7a7a\u683c\u9012\u8fdb\u62c6\u5206\u3002"""

    splitter = ChineseTextSplitter(pdf=False, sentence_size=5)

    assert splitter.split_text("AAAAAA  BBBBBB CCCCCC") == ["AAAAAA  ", "BBBBBB ", "CCCCCC"]
    assert splitter.split_text("\u7532\u7532\u7532\u7532,\u4e59\u4e59\u4e59\u4e59,\u4e19\u4e19\u4e19\u4e19") == [
        "\u7532\u7532\u7532\u7532,",
        "\u4e59\u4e59\u4e59\u4e59,",
        "\u4e19\u4e19\u4e19\u4e19",
    ]
