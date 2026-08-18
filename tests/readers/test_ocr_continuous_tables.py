"""OCR 连续表格合并规则测试。"""

from __future__ import annotations

from server.readers.ocr_layout import merge_continuous_table_pages


def table(rows, centers=(20.0, 120.0)):
    """构造表格块。"""
    return {"type": "table", "rows": rows, "column_centers": list(centers)}


def paragraph(text):
    """构造普通段落块。"""
    return {"type": "paragraph", "text": text}


def test_adjacent_same_page_table_blocks_are_merged() -> None:
    """同页相邻且列结构一致的表格块应合并。"""
    result = merge_continuous_table_pages([
        {"page_number": 1, "blocks": [table([["名称", "数量"], ["大米", "10"]]), table([["小麦", "20"]])]},
    ])
    assert result["diagnostics"]["table_block_count"] == 2
    assert result["diagnostics"]["merged_block_count"] == 1
    assert result["text"].count("| --- | --- |") == 1
    assert "| 小麦 | 20 |" in result["text"]


def test_paragraph_is_a_hard_boundary() -> None:
    """普通段落必须阻断同页表格延续。"""
    result = merge_continuous_table_pages([
        {"page_number": 1, "blocks": [table([["A", "B"], ["1", "2"]]), paragraph("说明文字"), table([["A", "B"], ["3", "4"]])]},
    ])
    assert result["diagnostics"]["merged_block_count"] == 0
    assert result["text"].count("| --- | --- |") == 2


def test_column_count_or_center_drift_prevents_merge() -> None:
    """列数不同或列中心漂移过大时不得合并。"""
    result = merge_continuous_table_pages([
        {"page_number": 1, "blocks": [
            table([["A", "B"], ["1", "2"]]),
            table([["A", "B"], ["3", "4"]], centers=(20.0, 220.0)),
            table([["A", "B", "C"], ["5", "6", "7"]], centers=(20.0, 120.0, 220.0)),
        ]},
    ])
    assert result["diagnostics"]["merged_block_count"] == 0


def test_only_previous_tail_and_next_head_continue_across_pages() -> None:
    """跨页只允许上一页尾表和下一页首表延续。"""
    result = merge_continuous_table_pages([
        {"page_number": 1, "blocks": [paragraph("前言"), table([["A", "B"], ["1", "2"]])]},
        {"page_number": 2, "blocks": [table([["A", "B"], ["3", "4"]]), paragraph("结论"), table([["A", "B"], ["5", "6"]])]},
    ])
    assert result["diagnostics"]["continued_page_count"] == 1
    assert result["diagnostics"]["merged_block_count"] == 1
    assert result["text"].count("[Page 1]") == 1
    assert result["text"].count("[Page 2]") == 1
    assert result["text"].count("| --- | --- |") == 2


def test_repeated_header_is_removed_on_page_continuation() -> None:
    """下一页首表重复表头应去重，但页标记必须保留。"""
    result = merge_continuous_table_pages([
        {"page_number": 1, "blocks": [table([["名称", "数量"], ["大米", "10"]])]},
        {"page_number": 2, "blocks": [table([["名称", "数量"], ["小麦", "20"]])]},
    ])
    assert result["diagnostics"]["removed_repeated_header_count"] == 1
    page_two = result["text"].split("[Page 2]", 1)[1]
    assert "名称" not in page_two
    assert "| 小麦 | 20 |" in page_two
