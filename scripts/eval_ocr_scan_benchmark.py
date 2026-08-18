"""评估 OCR 扫描件基准的文字、顺序、单元格与连续表格指标。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OCRExecutor = Callable[[Path], dict[str, Any]]


def _character_recall(expected: str, observed: str) -> float:
    """按字符多重集计算召回率，忽略空白。"""
    expected_counter = Counter(char for char in expected if not char.isspace())
    observed_counter = Counter(char for char in observed if not char.isspace())
    total = sum(expected_counter.values())
    return 1.0 if total == 0 else sum(min(count, observed_counter[char]) for char, count in expected_counter.items()) / total


def _normalize_line(line: str) -> str:
    """统一普通文本和 Markdown 表格行，避免格式符影响阅读顺序指标。"""
    value = str(line or "").strip()
    if re.fullmatch(r"\|?(?:\s*:?-{3,}:?\s*\|)+\s*", value):
        return ""
    if "|" in value:
        value = " ".join(part.strip() for part in value.strip("|").split("|") if part.strip())
    return " ".join(value.split())


def _line_order(expected: str, observed: str) -> float:
    """计算期望非空行按顺序出现在观测文本中的比例。"""
    expected_lines = [_normalize_line(line) for line in expected.splitlines()]
    expected_lines = [line for line in expected_lines if line]
    observed_lines = [_normalize_line(line) for line in observed.splitlines()]
    observed_lines = [line for line in observed_lines if line]
    cursor = 0
    matched = 0
    for line in expected_lines:
        while cursor < len(observed_lines) and observed_lines[cursor] != line:
            cursor += 1
        if cursor < len(observed_lines):
            matched += 1
            cursor += 1
    return 1.0 if not expected_lines else matched / len(expected_lines)


def _runtime_cells(expected_cells: list[Any], observed_text: str) -> list[str]:
    """从真实 OCR 文本中恢复命中的金标单元格，供严格召回统计。"""
    compact_observed = " ".join(_normalize_line(line) for line in observed_text.splitlines()).casefold()
    return [str(cell) for cell in expected_cells if str(cell).casefold() in compact_observed]


def _default_runtime_executor(asset_path: Path) -> dict[str, Any]:
    """使用项目真实图片/PDF OCR 链路执行单个基准资产。"""
    if asset_path.suffix.lower() == ".pdf":
        from server.readers.pdf_ocr import PDFOCRReader

        reader = PDFOCRReader()
        documents = reader.load_data(str(asset_path))
        diagnostics = dict(getattr(reader, "_last_diagnostics", None) or {})
        diagnostics.update(
            status="success" if documents else "no_text",
            text="\n\n".join(str(document.text or "") for document in documents),
            engine="paddleocr",
        )
        return diagnostics

    from server.readers.image_ocr import extract_image_ocr_result

    return extract_image_ocr_result(asset_path)


def _observed_item(
    item: dict[str, Any],
    *,
    manifest_dir: Path,
    mode: str,
    ocr_executor: OCRExecutor | None,
) -> dict[str, Any]:
    """为一个样本选择固定观测或真实 OCR 观测。"""
    if mode == "recorded":
        return {
            "status": "recorded",
            "text": str(item.get("observed_text") or ""),
            "cells": [str(value) for value in item.get("observed_cells") or []],
            "header_continuation": item.get("observed_header_continuation"),
            "continuous_merge": item.get("observed_continuous_merge"),
        }

    executor = ocr_executor or _default_runtime_executor
    result = dict(executor((manifest_dir / str(item["asset"])).resolve()) or {})
    observed_text = str(result.get("text") or "")
    return {
        "status": str(result.get("status") or "unknown"),
        "text": observed_text,
        "cells": _runtime_cells(item.get("expected_cells") or [], observed_text),
        "header_continuation": int(result.get("removed_repeated_header_count") or 0) > 0,
        "continuous_merge": (
            int(result.get("continued_page_count") or 0) > 0
            or int(result.get("merged_block_count") or 0) > 0
        ),
        "diagnostics": {
            key: result.get(key)
            for key in (
                "engine",
                "layout_mode",
                "table_block_count",
                "merged_block_count",
                "continued_page_count",
                "removed_repeated_header_count",
                "ocr_total_ms",
                "error",
            )
            if key in result
        },
    }


def evaluate_manifest(
    manifest_path: Path,
    *,
    mode: str = "recorded",
    ocr_executor: OCRExecutor | None = None,
) -> dict[str, Any]:
    """读取 manifest，以固定结果或真实 OCR runtime 返回聚合指标。"""
    if mode not in {"recorded", "runtime"}:
        raise ValueError("mode must be 'recorded' or 'runtime'")
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = manifest.get("items") or []
    char_scores: list[float] = []
    order_scores: list[float] = []
    expected_cells: list[str] = []
    observed_cells: list[str] = []
    header_scores: list[bool] = []
    merge_scores: list[bool] = []
    item_reports: list[dict[str, Any]] = []

    for item in items:
        observed = _observed_item(
            item,
            manifest_dir=manifest_path.parent,
            mode=mode,
            ocr_executor=ocr_executor,
        )
        expected_text = str(item.get("expected_text") or "")
        observed_text = observed["text"]
        char_score = _character_recall(expected_text, observed_text)
        order_score = _line_order(expected_text, observed_text)
        char_scores.append(char_score)
        order_scores.append(order_score)
        expected_cells.extend(str(value) for value in item.get("expected_cells") or [])
        observed_cells.extend(observed["cells"])
        if "expected_header_continuation" in item:
            header_scores.append(item.get("expected_header_continuation") == observed["header_continuation"])
        if "expected_continuous_merge" in item:
            merge_scores.append(item.get("expected_continuous_merge") == observed["continuous_merge"])
        item_reports.append(
            {
                "id": item.get("id"),
                "asset": item.get("asset"),
                "status": observed["status"],
                "character_recall": round(char_score, 6),
                "line_order_accuracy": round(order_score, 6),
                "observed_text": observed_text,
                "diagnostics": observed.get("diagnostics") or {},
            }
        )

    observed_cell_counter = Counter(observed_cells)
    matched_cells = 0
    for cell in expected_cells:
        if observed_cell_counter[cell] > 0:
            matched_cells += 1
            observed_cell_counter[cell] -= 1
    metrics = {
        "character_recall": sum(char_scores) / len(char_scores) if char_scores else 1.0,
        "line_order_accuracy": sum(order_scores) / len(order_scores) if order_scores else 1.0,
        "cell_recall": matched_cells / len(expected_cells) if expected_cells else 1.0,
        "header_continuation_accuracy": sum(header_scores) / len(header_scores) if header_scores else 1.0,
        "continuous_table_merge_accuracy": sum(merge_scores) / len(merge_scores) if merge_scores else 1.0,
    }
    rounded_metrics = {key: round(value, 6) for key, value in metrics.items()}
    return {
        "schema_version": 1,
        "manifest": str(manifest_path),
        "mode": mode,
        "item_count": len(items),
        "metrics": rounded_metrics,
        "overall_score": round(sum(metrics.values()) / len(metrics), 6),
        "items": item_reports,
    }


def _markdown_report(report: dict[str, Any]) -> str:
    """把 JSON 报告转换为便于评审的 Markdown 摘要。"""
    lines = [
        "# OCR Benchmark Report",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Items: {report['item_count']}",
        f"- Overall score: {report['overall_score']:.6f}",
        "",
        "## Metrics",
        "",
        "| Metric | Score |",
        "|---|---:|",
    ]
    lines.extend(f"| {name} | {score:.6f} |" for name, score in report["metrics"].items())
    lines.extend(["", "## Items", "", "| ID | Status | Character recall | Line order |", "|---|---|---:|---:|"])
    for item in report.get("items") or []:
        lines.append(
            f"| {item.get('id')} | {item.get('status')} | "
            f"{item.get('character_recall', 0):.6f} | {item.get('line_order_accuracy', 0):.6f} |"
        )
    return "\n".join(lines) + "\n"


def _write_reports(output: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    """兼容 JSON 文件路径或报告目录，并始终生成 JSON/Markdown。"""
    if output.suffix.lower() == ".json":
        json_path = output
        markdown_path = output.with_suffix(".md")
    else:
        json_path = output / "report.json"
        markdown_path = output / "report.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown_report(report), encoding="utf-8")
    return json_path, markdown_path


def main(argv: list[str] | None = None) -> int:
    """命令行入口，低于阈值或真实运行失败时返回 1。"""
    parser = argparse.ArgumentParser(description="评估 OCR 扫描件基准")
    parser.add_argument("manifest_positional", nargs="?", help="兼容旧命令的 manifest 路径")
    parser.add_argument("--manifest", dest="manifest_named")
    parser.add_argument("--mode", choices=("recorded", "runtime"), default="recorded")
    parser.add_argument("--output", default="docs/20260817-kb-migration-agent-ocr-cache/artifacts/ocr-benchmark")
    parser.add_argument("--min-score", type=float, default=0.8)
    args = parser.parse_args(argv)
    manifest = args.manifest_named or args.manifest_positional or "tests/fixtures/ocr_real_scan/manifest.json"
    report = evaluate_manifest(Path(manifest), mode=args.mode)
    _write_reports(Path(args.output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    runtime_failed = args.mode == "runtime" and any(item.get("status") not in {"success", "recorded"} for item in report["items"])
    return 0 if report["overall_score"] >= args.min_score and not runtime_failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
