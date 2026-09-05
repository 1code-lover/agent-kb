from __future__ import annotations

from typing import Any, Iterable

from tests.api.chat_qa_metrics import _contains_case_insensitive


def _category_name(item: dict[str, Any]) -> str:
    return str(item.get("category") or "uncategorized")


def _case_id(item: dict[str, Any]) -> str:
    return str(item.get("case_id") or "")


def _modality_name(item: dict[str, Any]) -> str:
    return str(item.get("modality") or "unknown")


def _required_modalities(schema: dict[str, Any], *, quality_gate_key: str) -> list[str]:
    allowed_modalities = [str(item) for item in list(schema.get("allowed_modalities") or [])]
    quality_gates = dict(schema.get("quality_gates") or {})
    minimum_cases = int(quality_gates.get(quality_gate_key) or 0)
    if not allowed_modalities or minimum_cases <= 0:
        return []
    return allowed_modalities


def _build_required_marker_hits(
    passed_reports: Iterable[dict[str, Any]],
    required_markers: Iterable[str],
) -> tuple[dict[str, dict[str, Any]], bool]:
    marker_hits: dict[str, dict[str, Any]] = {}
    all_markers_covered = True
    for marker in required_markers:
        matched_case_ids = [
            _case_id(item)
            for item in passed_reports
            if _contains_case_insensitive(str(item.get("answer") or ""), marker)
        ]
        covered = len(matched_case_ids) > 0
        marker_hits[str(marker)] = {
            "covered": covered,
            "hit_cases": len(matched_case_ids),
            "case_ids": matched_case_ids,
        }
        all_markers_covered = all_markers_covered and covered
    return marker_hits, all_markers_covered


def _build_modality_summary(
    reports: Iterable[dict[str, Any]],
    *,
    required_modalities: Iterable[str],
) -> dict[str, Any]:
    report_list = list(reports)
    required_modality_list = [str(item) for item in required_modalities]
    required_modality_set = set(required_modality_list)
    modality_names = sorted({_modality_name(item) for item in report_list} | required_modality_set)

    modality_breakdown: dict[str, dict[str, Any]] = {}
    missing_required_modalities: list[str] = []
    required_modalities_without_passed_cases: list[str] = []
    modality_counts: dict[str, tuple[int, int]] = {}

    for modality in modality_names:
        modality_reports = [item for item in report_list if _modality_name(item) == modality]
        passed = sum(1 for item in modality_reports if item.get("passed"))
        modality_counts[modality] = (len(modality_reports), passed)
        modality_breakdown[modality] = {
            "count": len(modality_reports),
            "passed": passed,
            "failed": len(modality_reports) - passed,
            "pass_rate": passed / len(modality_reports) if modality_reports else 0.0,
        }

    for modality in required_modality_list:
        count, passed = modality_counts.get(modality, (0, 0))
        if count == 0:
            missing_required_modalities.append(modality)
        elif passed == 0:
            required_modalities_without_passed_cases.append(modality)

    return {
        "required_modalities": required_modality_list,
        "missing_required_modalities": missing_required_modalities,
        "required_modalities_without_passed_cases": required_modalities_without_passed_cases,
        "required_modalities_passed": not missing_required_modalities and not required_modalities_without_passed_cases,
        "modality_breakdown": modality_breakdown,
    }



def _build_modality_marker_coverage_summary(
    reports: Iterable[dict[str, Any]],
    *,
    marker_mapping: dict[str, list[str]],
    required_modalities: Iterable[str],
) -> dict[str, Any]:
    report_list = list(reports)
    tracked_categories = set(marker_mapping)
    modality_names = sorted({_modality_name(item) for item in report_list} | {str(item) for item in required_modalities})

    modality_category_breakdown: dict[str, dict[str, Any]] = {}
    missing_required_markers_by_modality: dict[str, dict[str, list[str]]] = {}
    required_marker_total = 0
    covered_marker_total = 0

    for modality in modality_names:
        modality_reports = [item for item in report_list if _modality_name(item) == modality]
        passed_modality_reports = [item for item in modality_reports if item.get("passed")]
        category_names = sorted({_category_name(item) for item in passed_modality_reports} & tracked_categories)
        if not category_names:
            continue

        modality_category_breakdown[modality] = {}
        modality_missing: dict[str, list[str]] = {}
        for category in category_names:
            category_reports = [item for item in modality_reports if _category_name(item) == category]
            passed_category_reports = [item for item in passed_modality_reports if _category_name(item) == category]
            required_markers = marker_mapping.get(category, [])
            marker_hits, _ = _build_required_marker_hits(passed_category_reports, required_markers)
            missing_markers = [marker for marker, item in marker_hits.items() if not bool(item.get("covered"))]
            required_marker_total += len(required_markers)
            covered_marker_total += sum(1 for item in marker_hits.values() if bool(item.get("covered")))
            modality_category_breakdown[modality][category] = {
                "count": len(category_reports),
                "passed": len(passed_category_reports),
                "failed": len(category_reports) - len(passed_category_reports),
                "required_markers": marker_hits,
            }
            if missing_markers:
                modality_missing[category] = missing_markers

        if modality_missing:
            missing_required_markers_by_modality[modality] = modality_missing

    return {
        "modality_category_breakdown": modality_category_breakdown,
        "missing_required_markers_by_modality": missing_required_markers_by_modality,
        "required_modality_marker_coverage_passed": not missing_required_markers_by_modality,
        "required_modality_marker_required_count": required_marker_total,
        "required_modality_marker_covered_count": covered_marker_total,
    }


def build_refusal_summary(reports: Iterable[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
    """聚合 refusal case 的运行期覆盖摘要。"""
    refusal_reports = [item for item in reports if str(item.get("answer_style") or "") == "refusal"]
    required_categories = [str(item) for item in list(schema.get("required_refusal_categories") or [])]
    marker_mapping = {
        str(category): [str(marker) for marker in list(markers or [])]
        for category, markers in dict(schema.get("required_refusal_markers_by_category") or {}).items()
    }
    category_names = sorted(
        {_category_name(item) for item in refusal_reports} | set(required_categories) | set(marker_mapping)
    )

    category_breakdown: dict[str, dict[str, Any]] = {}
    missing_required_categories: list[str] = []
    required_categories_without_passed_cases: list[str] = []
    marker_coverage_passed = True

    for category in category_names:
        category_reports = [item for item in refusal_reports if _category_name(item) == category]
        passed_category_reports = [item for item in category_reports if item.get("passed")]
        passed = len(passed_category_reports)
        required_markers = marker_mapping.get(category, [])
        marker_hits, category_marker_coverage_passed = _build_required_marker_hits(
            passed_category_reports,
            required_markers,
        )
        marker_coverage_passed = marker_coverage_passed and category_marker_coverage_passed

        if category in required_categories:
            if not category_reports:
                missing_required_categories.append(category)
            elif not passed_category_reports:
                required_categories_without_passed_cases.append(category)

        category_breakdown[category] = {
            "count": len(category_reports),
            "passed": passed,
            "failed": len(category_reports) - passed,
            "pass_rate": passed / len(category_reports) if category_reports else 0.0,
            "required_markers": marker_hits,
        }

    passed_refusal_cases = sum(1 for item in refusal_reports if item.get("passed"))
    failed_refusal_cases = sum(1 for item in refusal_reports if not item.get("passed"))
    required_modalities = _required_modalities(
        schema,
        quality_gate_key="minimum_refusal_cases_per_modality",
    )
    modality_summary = _build_modality_summary(
        refusal_reports,
        required_modalities=required_modalities,
    )
    modality_marker_summary = _build_modality_marker_coverage_summary(
        refusal_reports,
        marker_mapping=marker_mapping,
        required_modalities=required_modalities,
    )
    return {
        "refusal_case_count": len(refusal_reports),
        "passed_refusal_cases": passed_refusal_cases,
        "failed_refusal_cases": failed_refusal_cases,
        "refusal_pass_rate": (passed_refusal_cases / len(refusal_reports)) if refusal_reports else 1.0,
        "required_categories": required_categories,
        "missing_required_categories": missing_required_categories,
        "required_categories_without_passed_cases": required_categories_without_passed_cases,
        "required_categories_passed": not missing_required_categories and not required_categories_without_passed_cases,
        "required_marker_coverage_passed": marker_coverage_passed,
        "category_breakdown": category_breakdown,
        **modality_summary,
        **modality_marker_summary,
    }


def build_negative_contract_summary(reports: Iterable[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
    """聚合 negative contract / boundary case 的运行期覆盖摘要。"""
    required_categories = [str(item) for item in list(schema.get("required_negative_contract_categories") or [])]
    marker_mapping = {
        str(category): [str(marker) for marker in list(markers or [])]
        for category, markers in dict(schema.get("required_negative_contract_markers_by_category") or {}).items()
    }
    required_category_set = set(required_categories)
    negative_contract_reports = [item for item in reports if _category_name(item) in required_category_set]
    category_names = sorted(
        {_category_name(item) for item in negative_contract_reports} | required_category_set | set(marker_mapping)
    )

    category_breakdown: dict[str, dict[str, Any]] = {}
    missing_required_categories: list[str] = []
    required_categories_without_passed_cases: list[str] = []
    marker_coverage_passed = True

    for category in category_names:
        category_reports = [item for item in negative_contract_reports if _category_name(item) == category]
        passed_category_reports = [item for item in category_reports if item.get("passed")]
        passed = len(passed_category_reports)
        required_markers = marker_mapping.get(category, [])
        marker_hits, category_marker_coverage_passed = _build_required_marker_hits(
            passed_category_reports,
            required_markers,
        )
        marker_coverage_passed = marker_coverage_passed and category_marker_coverage_passed

        if category in required_category_set:
            if not category_reports:
                missing_required_categories.append(category)
            elif passed == 0:
                required_categories_without_passed_cases.append(category)
        category_breakdown[category] = {
            "count": len(category_reports),
            "passed": passed,
            "failed": len(category_reports) - passed,
            "pass_rate": passed / len(category_reports) if category_reports else 0.0,
            "required_markers": marker_hits,
        }

    passed_cases = sum(1 for item in negative_contract_reports if item.get("passed"))
    total_cases = len(negative_contract_reports)
    required_modalities = _required_modalities(
        schema,
        quality_gate_key="minimum_negative_contract_cases_per_modality",
    )
    modality_summary = _build_modality_summary(
        negative_contract_reports,
        required_modalities=required_modalities,
    )
    modality_marker_summary = _build_modality_marker_coverage_summary(
        negative_contract_reports,
        marker_mapping=marker_mapping,
        required_modalities=required_modalities,
    )
    return {
        "negative_contract_case_count": total_cases,
        "passed_negative_contract_cases": passed_cases,
        "failed_negative_contract_cases": total_cases - passed_cases,
        "negative_contract_pass_rate": (passed_cases / total_cases) if total_cases else 1.0,
        "required_categories": required_categories,
        "missing_required_categories": missing_required_categories,
        "required_categories_without_passed_cases": required_categories_without_passed_cases,
        "required_categories_passed": not missing_required_categories and not required_categories_without_passed_cases,
        "required_marker_coverage_passed": marker_coverage_passed,
        "category_breakdown": category_breakdown,
        **modality_summary,
        **modality_marker_summary,
    }


def _build_required_presence_gate(
    *,
    metric: str,
    required_values: list[str],
    missing_values: list[str],
    values_without_passed_cases: list[str],
    without_passed_field: str,
) -> dict[str, Any]:
    covered_count = len(required_values) - len(missing_values) - len(values_without_passed_cases)
    gate_passed = not missing_values and not values_without_passed_cases
    return {
        "metric": metric,
        "actual": 1.0 if gate_passed else 0.0,
        "minimum": 1.0,
        "passed": gate_passed,
        "required_count": len(required_values),
        "covered_count": max(0, covered_count),
        "missing": missing_values,
        without_passed_field: values_without_passed_cases,
        "detail": {
            "missing": missing_values,
            without_passed_field: values_without_passed_cases,
        },
    }


def _build_required_category_gate(
    *,
    required_categories: list[str],
    missing_categories: list[str],
    categories_without_passed_cases: list[str],
) -> dict[str, Any]:
    return _build_required_presence_gate(
        metric="required_categories_passed",
        required_values=required_categories,
        missing_values=missing_categories,
        values_without_passed_cases=categories_without_passed_cases,
        without_passed_field="required_categories_without_passed_cases",
    )


def _build_required_modality_gate(
    *,
    required_modalities: list[str],
    missing_modalities: list[str],
    modalities_without_passed_cases: list[str],
) -> dict[str, Any]:
    return _build_required_presence_gate(
        metric="required_modalities_passed",
        required_values=required_modalities,
        missing_values=missing_modalities,
        values_without_passed_cases=modalities_without_passed_cases,
        without_passed_field="required_modalities_without_passed_cases",
    )


def evaluate_contract_gates(
    refusal_summary: dict[str, Any] | None,
    negative_contract_summary: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """把 refusal / negative contract 覆盖摘要规整为统一 gate 结果。"""
    refusal_summary = dict(refusal_summary or {})
    negative_contract_summary = dict(negative_contract_summary or {})
    gate_results: dict[str, dict[str, Any]] = {}

    refusal_required_categories = [str(item) for item in list(refusal_summary.get("required_categories") or [])]
    if refusal_required_categories:
        missing_categories = [str(item) for item in list(refusal_summary.get("missing_required_categories") or [])]
        categories_without_passed_cases = [
            str(item)
            for item in list(refusal_summary.get("required_categories_without_passed_cases") or [])
        ]
        gate_results["required_refusal_categories"] = _build_required_category_gate(
            required_categories=refusal_required_categories,
            missing_categories=missing_categories,
            categories_without_passed_cases=categories_without_passed_cases,
        )

    refusal_required_modalities = [str(item) for item in list(refusal_summary.get("required_modalities") or [])]
    if refusal_required_modalities:
        missing_modalities = [str(item) for item in list(refusal_summary.get("missing_required_modalities") or [])]
        modalities_without_passed_cases = [
            str(item)
            for item in list(refusal_summary.get("required_modalities_without_passed_cases") or [])
        ]
        gate_results["required_refusal_modalities"] = _build_required_modality_gate(
            required_modalities=refusal_required_modalities,
            missing_modalities=missing_modalities,
            modalities_without_passed_cases=modalities_without_passed_cases,
        )

    refusal_category_breakdown = dict(refusal_summary.get("category_breakdown") or {})
    required_refusal_markers_by_category = {
        category: list(dict(item.get("required_markers") or {}).keys())
        for category, item in refusal_category_breakdown.items()
        if dict(item.get("required_markers") or {})
    }
    missing_refusal_markers = {
        category: [
            marker
            for marker, marker_item in dict(item.get("required_markers") or {}).items()
            if not bool(dict(marker_item).get("covered"))
        ]
        for category, item in refusal_category_breakdown.items()
        if dict(item.get("required_markers") or {})
    }
    missing_refusal_markers = {
        category: markers for category, markers in missing_refusal_markers.items() if markers
    }
    if required_refusal_markers_by_category:
        total_required_markers = sum(len(markers) for markers in required_refusal_markers_by_category.values())
        missing_marker_count = sum(len(markers) for markers in missing_refusal_markers.values())
        gate_results["required_refusal_markers"] = {
            "metric": "required_marker_coverage_passed",
            "actual": 1.0 if not missing_refusal_markers else 0.0,
            "minimum": 1.0,
            "passed": not missing_refusal_markers,
            "required_count": total_required_markers,
            "covered_count": total_required_markers - missing_marker_count,
            "missing": missing_refusal_markers,
            "detail": missing_refusal_markers,
        }


    refusal_modality_marker_required_count = int(refusal_summary.get("required_modality_marker_required_count") or 0)
    refusal_missing_modality_markers = dict(refusal_summary.get("missing_required_markers_by_modality") or {})
    refusal_modality_marker_covered_count = int(refusal_summary.get("required_modality_marker_covered_count") or 0)
    if refusal_modality_marker_required_count > 0:
        gate_results["required_refusal_modality_markers"] = {
            "metric": "required_modality_marker_coverage_passed",
            "actual": 1.0 if not refusal_missing_modality_markers else 0.0,
            "minimum": 1.0,
            "passed": not refusal_missing_modality_markers,
            "required_count": refusal_modality_marker_required_count,
            "covered_count": refusal_modality_marker_covered_count,
            "missing": refusal_missing_modality_markers,
            "detail": refusal_missing_modality_markers,
        }

    negative_required_categories = [str(item) for item in list(negative_contract_summary.get("required_categories") or [])]
    if negative_required_categories:
        missing_categories = [str(item) for item in list(negative_contract_summary.get("missing_required_categories") or [])]
        categories_without_passed_cases = [
            str(item)
            for item in list(negative_contract_summary.get("required_categories_without_passed_cases") or [])
        ]
        gate_results["required_negative_contract_categories"] = _build_required_category_gate(
            required_categories=negative_required_categories,
            missing_categories=missing_categories,
            categories_without_passed_cases=categories_without_passed_cases,
        )

    negative_required_modalities = [str(item) for item in list(negative_contract_summary.get("required_modalities") or [])]
    if negative_required_modalities:
        missing_modalities = [
            str(item) for item in list(negative_contract_summary.get("missing_required_modalities") or [])
        ]
        modalities_without_passed_cases = [
            str(item)
            for item in list(negative_contract_summary.get("required_modalities_without_passed_cases") or [])
        ]
        gate_results["required_negative_contract_modalities"] = _build_required_modality_gate(
            required_modalities=negative_required_modalities,
            missing_modalities=missing_modalities,
            modalities_without_passed_cases=modalities_without_passed_cases,
        )

    negative_category_breakdown = dict(negative_contract_summary.get("category_breakdown") or {})
    required_negative_markers_by_category = {
        category: list(dict(item.get("required_markers") or {}).keys())
        for category, item in negative_category_breakdown.items()
        if dict(item.get("required_markers") or {})
    }
    missing_negative_markers = {
        category: [
            marker
            for marker, marker_item in dict(item.get("required_markers") or {}).items()
            if not bool(dict(marker_item).get("covered"))
        ]
        for category, item in negative_category_breakdown.items()
        if dict(item.get("required_markers") or {})
    }
    missing_negative_markers = {
        category: markers for category, markers in missing_negative_markers.items() if markers
    }
    if required_negative_markers_by_category:
        total_required_markers = sum(len(markers) for markers in required_negative_markers_by_category.values())
        missing_marker_count = sum(len(markers) for markers in missing_negative_markers.values())
        gate_results["required_negative_contract_markers"] = {
            "metric": "required_marker_coverage_passed",
            "actual": 1.0 if not missing_negative_markers else 0.0,
            "minimum": 1.0,
            "passed": not missing_negative_markers,
            "required_count": total_required_markers,
            "covered_count": total_required_markers - missing_marker_count,
            "missing": missing_negative_markers,
            "detail": missing_negative_markers,
        }


    negative_modality_marker_required_count = int(
        negative_contract_summary.get("required_modality_marker_required_count") or 0
    )
    negative_missing_modality_markers = dict(
        negative_contract_summary.get("missing_required_markers_by_modality") or {}
    )
    negative_modality_marker_covered_count = int(
        negative_contract_summary.get("required_modality_marker_covered_count") or 0
    )
    if negative_modality_marker_required_count > 0:
        gate_results["required_negative_contract_modality_markers"] = {
            "metric": "required_modality_marker_coverage_passed",
            "actual": 1.0 if not negative_missing_modality_markers else 0.0,
            "minimum": 1.0,
            "passed": not negative_missing_modality_markers,
            "required_count": negative_modality_marker_required_count,
            "covered_count": negative_modality_marker_covered_count,
            "missing": negative_missing_modality_markers,
            "detail": negative_missing_modality_markers,
        }

    return gate_results


def _all_gates_passed(gates: dict[str, Any] | None) -> bool:
    """判断一组 gate 是否全部通过。"""
    return all(bool(item.get("passed")) for item in dict(gates or {}).values())


def evaluate_report_run_passed(
    *,
    evaluation_mode: str,
    suite_summary: dict[str, Any] | None,
    run_gates: dict[str, Any] | None,
    contract_gates: dict[str, Any] | None = None,
    diagnostic_gates: dict[str, Any] | None = None,
) -> bool:
    """统一计算 semireal 运行是否通过，避免不同入口出现 gate 漏判。"""
    if not _all_gates_passed(run_gates) or not _all_gates_passed(contract_gates):
        return False
    if evaluation_mode == "diagnostic":
        return _all_gates_passed(diagnostic_gates)
    return int(dict(suite_summary or {}).get("failed_cases") or 0) == 0


__all__ = [
    "build_negative_contract_summary",
    "build_refusal_summary",
    "evaluate_contract_gates",
    "evaluate_report_run_passed",
]
