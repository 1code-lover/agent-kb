"""粮仓检索实验脚本测试。"""

from __future__ import annotations

from scripts import run_grain_retrieval_experiments as exp


def test_normalize_file_name_strips_hash_and_parentheses() -> None:
    """文件名归一化应剥离导入 hash 并统一全角括号。"""
    assert exp.normalize_file_name("17空调控温（试行）_a1b2c3d4.docx") == "17空调控温(试行).docx"


def test_dedupe_source_files_uses_normalized_name() -> None:
    """source 文件去重应基于归一化文件名。"""
    assert exp.dedupe_source_files(
        [
            "06稻谷控温储藏技术规程t6_7a0554a1.docx",
            "06稻谷控温储藏技术规程t6_5a8d3dae.docx",
            "20超高大平房仓安全储粮技术规程_c802a581.docx",
        ]
    ) == ["06稻谷控温储藏技术规程t6.docx", "20超高大平房仓安全储粮技术规程.docx"]


def test_hit_rank_matches_top5_only() -> None:
    """hit_rank 只统计 Top5 内首个相关来源。"""
    relevant = {"target.docx"}
    assert exp.hit_rank(["noise.docx", "target.docx"], relevant) == 2
    assert exp.hit_rank(["a", "b", "c", "d", "e", "target.docx"], relevant) is None


def test_evaluate_sources_computes_recall_mrr_and_noise() -> None:
    """单条结果应计算 recall、mrr 与 source_noise。"""
    case = {
        "id": "case-1",
        "query": "q",
        "answerable": True,
        "relevant_documents": [{"file_name": "target.docx"}],
    }
    result = exp.evaluate_sources(
        case=case,
        source_files=["a.docx", "b.docx", "target.docx", "c.docx"],
    )

    assert result["recall_at_5"] == 1
    assert result["mrr_at_5"] == 0.3333
    assert result["source_noise"] == 1


def test_summarize_results_counts_failure_groups() -> None:
    """汇总应统计 retrieval_miss、rank_miss 与 source_noise。"""
    summary = exp.summarize_results(
        [
            {"id": "ok", "answerable": True, "recall_at_5": 1, "mrr_at_5": 1.0, "source_noise": 0},
            {"id": "rank", "answerable": True, "recall_at_5": 1, "mrr_at_5": 0.5, "source_noise": 1},
            {"id": "miss", "answerable": True, "recall_at_5": 0, "mrr_at_5": 0.0, "source_noise": 1},
            {"id": "no", "answerable": False, "recall_at_5": 0, "mrr_at_5": 0.0, "source_noise": 0},
        ]
    )

    assert summary["answerable_total"] == 3
    assert summary["recall_at_5"] == 0.6667
    assert summary["retrieval_miss_count"] == 1
    assert summary["rank_miss_count"] == 1
    assert summary["source_noise_count"] == 2
