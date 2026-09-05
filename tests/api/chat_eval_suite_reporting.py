from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LAYERED_SUITE_PATH = REPO_ROOT / "tests" / "fixtures" / "rag_quality" / "eval_layered_suite.json"


def _resolve_repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (REPO_ROOT / candidate).resolve()


def load_eval_suite_manifest(path: str | Path = DEFAULT_LAYERED_SUITE_PATH) -> dict[str, Any]:
    """读取并归一化分层评测 manifest。"""
    suite_path = _resolve_repo_path(path)
    manifest = json.loads(suite_path.read_text(encoding="utf-8"))
    layers = list(manifest.get("layers") or [])
    if not layers:
        raise ValueError(f"eval suite manifest has no layers: {suite_path}")

    normalized_layers: list[dict[str, Any]] = []
    for layer in layers:
        layer_name = str(layer.get("name") or "").strip()
        if not layer_name:
            raise ValueError(f"eval suite manifest layer missing name: {suite_path}")
        normalized_layer = dict(layer)
        normalized_layer["cases_path"] = str(_resolve_repo_path(layer["cases_path"]))
        normalized_layer["schema_path"] = str(_resolve_repo_path(layer["schema_path"]))
        normalized_layers.append(normalized_layer)

    manifest = dict(manifest)
    manifest["suite_path"] = str(suite_path)
    manifest["layers"] = normalized_layers
    return manifest


def _failed_gate_names(gates: dict[str, Any] | None) -> list[str]:
    return [name for name, item in dict(gates or {}).items() if not bool(item.get("passed"))]


def _failed_gate_details(gates: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for name, item in dict(gates or {}).items():
        gate = dict(item or {})
        if bool(gate.get("passed")):
            continue
        detail: dict[str, Any] = {}
        if gate.get("metric"):
            detail["metric"] = str(gate.get("metric"))
        if "actual" in gate:
            detail["actual"] = gate.get("actual")
        if "minimum" in gate:
            detail["minimum"] = gate.get("minimum")
        if "required_count" in gate:
            detail["required_count"] = gate.get("required_count")
        if "covered_count" in gate:
            detail["covered_count"] = gate.get("covered_count")
        for key in (
            "missing",
            "required_categories_without_passed_cases",
            "required_modalities_without_passed_cases",
            "detail",
        ):
            value = gate.get(key)
            if value not in (None, "", [], {}):
                detail[key] = value
        details[str(name)] = detail
    return details


def _summarize_weakest_categories(summary: dict[str, Any], *, limit: int = 3) -> list[dict[str, Any]]:
    category_breakdown = dict(summary.get("category_breakdown") or {})
    weakest = sorted(
        (
            {
                "category": category,
                "count": int(item.get("count") or 0),
                "passed": int(item.get("passed") or 0),
                "pass_rate": float(item.get("pass_rate") or 0.0),
            }
            for category, item in category_breakdown.items()
        ),
        key=lambda item: (item["pass_rate"], item["count"], item["category"]),
    )
    return weakest[:limit]


def build_eval_suite_layer_summary(layer: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    """把单层 semireal report 规整成 suite 级 layer summary。"""
    summary = dict(report.get("suite_summary") or {})
    failures = list(report.get("failures") or [])
    return {
        "name": str(layer.get("name") or ""),
        "purpose": str(layer.get("purpose") or ""),
        "dataset_name": str(report.get("dataset_name") or layer.get("dataset_name") or ""),
        "evaluation_mode": str(report.get("evaluation_mode") or "healthy"),
        "target_case_count": int(layer.get("target_case_count") or summary.get("total_cases") or 0),
        "actual_case_count": int(summary.get("total_cases") or 0),
        "passed_cases": int(summary.get("passed_cases") or 0),
        "failed_cases": int(summary.get("failed_cases") or 0),
        "pass_rate": float(summary.get("pass_rate") or 0.0),
        "run_passed": bool(report.get("run_passed")),
        "failed_run_gates": _failed_gate_names(report.get("run_gates")),
        "failed_run_gate_details": _failed_gate_details(report.get("run_gates")),
        "failed_contract_gates": _failed_gate_names(report.get("contract_gates")),
        "failed_contract_gate_details": _failed_gate_details(report.get("contract_gates")),
        "failed_diagnostic_gates": _failed_gate_names(report.get("diagnostic_gates")),
        "failed_diagnostic_gate_details": _failed_gate_details(report.get("diagnostic_gates")),
        "weakest_categories": _summarize_weakest_categories(summary),
        "failure_case_ids": [str(item.get("case_id") or "") for item in failures[:5]],
        "failure_stage_breakdown": dict(report.get("failure_stage_breakdown") or {}),
        "cases_path": str(layer.get("cases_path") or ""),
        "schema_path": str(layer.get("schema_path") or ""),
        "artifacts": dict(report.get("artifacts") or {}),
    }


__all__ = [
    "build_eval_suite_layer_summary",
    "load_eval_suite_manifest",
]
