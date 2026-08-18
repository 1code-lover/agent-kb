"""OCR 扫描件基准集与评估脚本测试。"""

from __future__ import annotations

import hashlib
import json

import pytest
from pathlib import Path

from scripts.build_ocr_scan_benchmark import build_benchmark
from scripts.eval_ocr_scan_benchmark import evaluate_manifest, main


def test_benchmark_manifest_has_six_project_authored_assets(tmp_path: Path) -> None:
    """基准必须覆盖 captured/synthetic_degradation，并校验资产哈希。"""
    manifest_path = build_benchmark(tmp_path / "fixture")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = manifest["items"]
    assert len(items) >= 6
    assert {item["source_type"] for item in items} == {"captured", "synthetic_degradation"}
    assert {item["category"] for item in items} >= {
        "paragraph", "single_page_table", "continuous_table", "cross_page_table",
        "double_column", "table_with_paragraph", "skew", "low_contrast", "noise"
    }
    for item in items:
        assert item["source_note"]
        assert item["license"] == "project-authored"
        asset = manifest_path.parent / item["asset"]
        assert hashlib.sha256(asset.read_bytes()).hexdigest() == item["sha256"]


def test_evaluator_reports_required_metrics_deterministically(tmp_path: Path) -> None:
    """评估输出应包含字符、行序、单元格、表头和连续表格指标。"""
    manifest_path = build_benchmark(tmp_path / "fixture")
    first = evaluate_manifest(manifest_path)
    second = evaluate_manifest(manifest_path)
    assert first == second
    assert set(first["metrics"]) == {
        "character_recall", "line_order_accuracy", "cell_recall", "header_continuation_accuracy", "continuous_table_merge_accuracy"
    }
    assert all(0 <= value <= 1 for value in first["metrics"].values())


def test_threshold_failure_returns_nonzero(tmp_path: Path) -> None:
    """阈值高于当前得分时命令行必须以非零退出码阻断。"""
    manifest_path = build_benchmark(tmp_path / "fixture")
    report_path = tmp_path / "report.json"
    assert main([str(manifest_path), "--output", str(report_path), "--min-score", "1.01"]) == 1
    assert report_path.exists()


def test_runtime_mode_uses_ocr_executor_instead_of_recorded_observations(tmp_path: Path) -> None:
    """真实运行模式必须从资产执行 OCR，不能继续消费 manifest 的固定观测值。"""
    manifest_path = build_benchmark(tmp_path / "fixture")
    calls: list[Path] = []

    def fake_executor(asset_path: Path) -> dict:
        calls.append(asset_path)
        return {
            "status": "success",
            "text": "runtime output",
            "merged_block_count": 0,
            "continued_page_count": 0,
            "removed_repeated_header_count": 0,
        }

    report = evaluate_manifest(manifest_path, mode="runtime", ocr_executor=fake_executor)

    assert len(calls) == report["item_count"]
    assert report["mode"] == "runtime"
    assert all(item["observed_text"] == "runtime output" for item in report["items"])
    assert report["metrics"]["character_recall"] < 1.0


def test_cli_accepts_named_manifest_and_writes_json_and_markdown(tmp_path: Path) -> None:
    """CLI 应与实施计划一致支持 --manifest，并在目录中生成双格式报告。"""
    manifest_path = build_benchmark(tmp_path / "fixture")
    output_dir = tmp_path / "reports"

    assert main(["--manifest", str(manifest_path), "--output", str(output_dir), "--min-score", "0"]) == 0
    assert (output_dir / "report.json").exists()
    assert (output_dir / "report.md").exists()


def test_benchmark_assets_are_byte_stable_across_rebuilds(tmp_path: Path) -> None:
    """确定性生成资产重复构建后哈希必须稳定，避免基准自身漂移。"""
    first_path = build_benchmark(tmp_path / "first")
    second_path = build_benchmark(tmp_path / "second")
    first = json.loads(first_path.read_text(encoding="utf-8"))
    second = json.loads(second_path.read_text(encoding="utf-8"))
    assert [(item["id"], item["sha256"]) for item in first["items"]] == [
        (item["id"], item["sha256"]) for item in second["items"]
    ]


def test_cross_page_gold_is_attached_to_a_pdf_asset(tmp_path: Path) -> None:
    """跨页表头和连续合并金标必须落在真实多页资产，而不是单页截图。"""
    manifest_path = build_benchmark(tmp_path / "fixture")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cross_page = next(item for item in manifest["items"] if item["category"] == "cross_page_table")
    assert cross_page["asset"].endswith(".pdf")
    assert cross_page["expected_header_continuation"] is True
    assert cross_page["expected_continuous_merge"] is True


def _paddle_ocr_cache_available() -> bool:
    root = Path.home() / ".paddlex" / "official_models"
    return (root / "PP-OCRv6_medium_det").is_dir() and (root / "PP-OCRv6_medium_rec").is_dir()


@pytest.mark.slow
def test_real_paddleocr_runtime_benchmark_passes_when_cache_exists() -> None:
    """本地模型缓存存在时，真实 PaddleOCR 链路应通过完整基准门槛。"""
    if not _paddle_ocr_cache_available():
        pytest.skip("PaddleOCR model cache is unavailable")
    report = evaluate_manifest(
        Path("tests/fixtures/ocr_real_scan/manifest.json"),
        mode="runtime",
    )
    assert report["overall_score"] >= 0.8
    assert all(item["status"] == "success" for item in report["items"] )
    cross_page = next(item for item in report["items"] if item["id"] == "synthetic-cross-page-table")
    assert cross_page["diagnostics"]["continued_page_count"] == 1
    assert cross_page["diagnostics"]["removed_repeated_header_count"] == 1
