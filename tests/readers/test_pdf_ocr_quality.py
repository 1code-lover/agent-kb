"""
PDF OCR 解析质量评估测试：验证关键词召回统计逻辑。
"""
from __future__ import annotations

from scripts.pdf_ocr_quality import evaluate_keyword_recall


def test_evaluate_keyword_recall_counts_hits_and_misses() -> None:
    """关键词召回评估应统计命中词、未命中词和召回率。"""
    result = evaluate_keyword_recall(
        text="稻谷质量标准包含出糙率、水分和杂质要求。",
        keywords=["稻谷", "出糙率", "整精米率", "水分"],
    )

    assert result.total == 4
    assert result.hit_count == 3
    assert result.miss_count == 1
    assert result.hit_terms == ["稻谷", "出糙率", "水分"]
    assert result.missed_terms == ["整精米率"]
    assert result.recall == 0.75


def test_evaluate_keyword_recall_handles_empty_keyword_list() -> None:
    """没有配置关键词时召回率应为 0，避免除零错误。"""
    result = evaluate_keyword_recall(text="任意文本", keywords=[])

    assert result.total == 0
    assert result.hit_count == 0
    assert result.miss_count == 0
    assert result.hit_terms == []
    assert result.missed_terms == []
    assert result.recall == 0.0
