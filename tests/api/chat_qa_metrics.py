from __future__ import annotations

from collections import Counter
import math
import re
from typing import Any


def _normalize_string_list(values: list[Any] | None) -> list[str]:
    return [str(value) for value in list(values or [])]


def _contains_case_insensitive(haystack: str, needle: str) -> bool:
    haystack_text = str(haystack or "")
    needle_text = str(needle or "")
    if not needle_text:
        return False

    haystack_lower = haystack_text.lower()
    needle_lower = needle_text.lower()
    if needle_lower not in haystack_lower:
        return False

    if any(char.isascii() and (char.isalnum() or char == "_") for char in needle_text):
        boundary_pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(needle_text)}(?![A-Za-z0-9_])", re.IGNORECASE)
        return boundary_pattern.search(haystack_text) is not None

    return True


def _iter_case_insensitive_matches(haystack: str, needle: str) -> list[re.Match[str]]:
    haystack_text = str(haystack or "")
    needle_text = str(needle or "")
    if not needle_text:
        return []

    if any(char.isascii() and (char.isalnum() or char == "_") for char in needle_text):
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(needle_text)}(?![A-Za-z0-9_])", re.IGNORECASE)
    else:
        pattern = re.compile(re.escape(needle_text), re.IGNORECASE)
    return list(pattern.finditer(haystack_text))


def _blocked_term_is_contextually_negated(answer: str, blocked_term: str) -> bool:
    answer_text = str(answer or "")
    blocked_text = str(blocked_term or "")
    if not answer_text or not blocked_text:
        return False

    safe_before_hints = (
        "not ",
        "never ",
        "don't ",
        "do not ",
        "must not ",
        "should not ",
        "cannot ",
        "can't ",
        "instead of ",
        "rather than ",
        "legacy ",
        "retired ",
    )
    safe_after_hints = (
        " is retired",
        " retired",
        " is deprecated",
        " deprecated",
        " is obsolete",
        " is legacy",
        " is wrong",
        " is incorrect",
        " is not valid",
        " is not the live answer",
        " must not be used",
        " should not be used",
        " should be ignored",
        " should be avoided",
        " should be replaced",
        " must be ignored",
        " must be avoided",
        " must be replaced",
        " is retired and must not be used",
        " is retired and should not be used",
    )

    for match in _iter_case_insensitive_matches(answer_text, blocked_text):
        start, end = match.span()
        before = answer_text[max(0, start - 32):start].lower()
        after = answer_text[end:min(len(answer_text), end + 64)].lower()
        if any(before.endswith(hint) for hint in safe_before_hints):
            continue
        if any(hint in after for hint in safe_after_hints):
            continue
        return False
    return True


def _confidence_interval_wilson(successes: int, total: int, *, z: float = 1.96) -> dict[str, float]:
    if total <= 0:
        return {"low": 0.0, "high": 0.0}

    proportion = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    center = (proportion + z2 / (2.0 * total)) / denominator
    margin = (z / denominator) * math.sqrt((proportion * (1.0 - proportion) / total) + (z2 / (4.0 * total * total)))
    return {"low": max(0.0, center - margin), "high": min(1.0, center + margin)}


def _collect_returned_titles(payload: dict[str, Any]) -> set[str]:
    titles: set[str] = set()
    for item in payload.get("sources", []):
        file_name = item.get("file")
        if file_name:
            titles.add(str(file_name))
    for item in payload.get("evidence", []):
        for field in ("title", "source"):
            value = item.get(field)
            if value:
                titles.add(str(value))
    return titles


def build_chat_case_report(
    case: dict[str, Any],
    payload: dict[str, Any],
    *,
    expected_kb_ids: list[str],
    expected_scope_type: str = "single_kb",
    expected_effective_scope_type: str = "single_kb",
    expected_default_deny: bool = False,
    expected_isolation_level: str | None = None,
    preview_payload: dict[str, Any] | None = None,
    required_evidence_docs: list[str] | None = None,
    preview_required: bool | None = None,
) -> dict[str, Any]:
    """根据单个问答 case 构建结构化质量报告。"""
    answer = str(payload.get("answer", ""))
    expected_keypoints = _normalize_string_list(case.get("expected_keypoints"))
    matched_keypoints = [item for item in expected_keypoints if _contains_case_insensitive(answer, item)]

    blocked_terms = _normalize_string_list(case.get("must_not_contain"))
    blocked_hits = [
        item
        for item in blocked_terms
        if _contains_case_insensitive(answer, item) and not _blocked_term_is_contextually_negated(answer, item)
    ]

    sources = list(payload.get("sources", []))
    evidence = list(payload.get("evidence", []))
    expected_source_count = int(case.get("expected_source_count", len(case.get("source_nodes", []))))
    actual_source_count = len(sources)
    actual_evidence_count = len(evidence)

    returned_titles = _collect_returned_titles(payload)
    required_docs = _normalize_string_list(required_evidence_docs)
    expected_doc = case.get("expected_doc")
    if required_docs:
        evidence_hit = all(item in returned_titles for item in required_docs)
    elif expected_doc is None:
        evidence_hit = expected_source_count == 0 and actual_source_count == 0 and actual_evidence_count == 0
    else:
        evidence_hit = str(expected_doc) in returned_titles

    preview_terms = _normalize_string_list(case.get("preview_terms"))
    preview_excerpt = "" if preview_payload is None else str(preview_payload.get("excerpt", ""))
    preview_term_hits = [item for item in preview_terms if _contains_case_insensitive(preview_excerpt, item)]
    resolved_preview_required = bool(preview_required) if preview_required is not None else expected_source_count > 0 and bool(preview_terms)
    if resolved_preview_required:
        if preview_terms:
            preview_resolvable = preview_payload is not None and len(preview_term_hits) == len(preview_terms)
            preview_term_coverage = len(preview_term_hits) / len(preview_terms)
        else:
            preview_resolvable = preview_payload is not None
            preview_term_coverage = 1.0 if preview_payload is not None else 0.0
    else:
        preview_resolvable = True
        preview_term_coverage = 1.0

    scope_passed = (
        payload.get("requested_scope_type") == expected_scope_type
        and payload.get("requested_kb_ids") == expected_kb_ids
        and payload.get("effective_scope_type") == expected_effective_scope_type
        and payload.get("effective_kb_ids") == expected_kb_ids
        and payload.get("is_default_deny_applied") is expected_default_deny
    )
    if expected_isolation_level is not None:
        scope_passed = scope_passed and payload.get("isolation_level") == expected_isolation_level

    keypoint_coverage = len(matched_keypoints) / len(expected_keypoints) if expected_keypoints else 1.0
    source_count_match = actual_source_count == expected_source_count and actual_evidence_count == expected_source_count
    blocked_term_clean = not blocked_hits

    passed = all(
        [
            scope_passed,
            keypoint_coverage == 1.0,
            blocked_term_clean,
            source_count_match,
            evidence_hit,
            preview_resolvable,
        ]
    )

    return {
        "case_id": case.get("case_id", "<unknown>"),
        "category": case.get("category") or case.get("type") or "uncategorized",
        "answer": answer,
        "preview_excerpt": preview_excerpt,
        "scope_passed": scope_passed,
        "expected_kb_ids": list(expected_kb_ids),
        "keypoint_total": len(expected_keypoints),
        "keypoint_hits": matched_keypoints,
        "keypoint_missed": [item for item in expected_keypoints if item not in matched_keypoints],
        "keypoint_coverage": keypoint_coverage,
        "blocked_term_total": len(blocked_terms),
        "blocked_term_hits": blocked_hits,
        "blocked_term_clean": blocked_term_clean,
        "forbidden_term_clean_rate": 1.0 if blocked_term_clean else 0.0,
        "expected_source_count": expected_source_count,
        "actual_source_count": actual_source_count,
        "actual_evidence_count": actual_evidence_count,
        "source_count_match": source_count_match,
        "expected_doc": expected_doc,
        "required_evidence_docs": required_docs,
        "returned_titles": sorted(returned_titles),
        "evidence_hit": evidence_hit,
        "preview_required": resolved_preview_required,
        "preview_resolvable": preview_resolvable,
        "preview_term_total": len(preview_terms),
        "preview_term_hits": preview_term_hits,
        "preview_term_coverage": preview_term_coverage,
        "passed": passed,
    }


def summarize_chat_case_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """聚合多个问答 case 报告并输出 suite 级摘要。"""
    total_cases = len(reports)
    if total_cases == 0:
        return {
            "total_cases": 0,
            "passed_cases": 0,
            "failed_cases": 0,
            "pass_rate": 0.0,
            "pass_rate_ci95": {"low": 0.0, "high": 0.0},
            "scope_pass_rate": 0.0,
            "average_keypoint_coverage": 0.0,
            "total_keypoints": 0,
            "matched_keypoints": 0,
            "missing_keypoints": 0,
            "keypoint_hit_rate": 0.0,
            "evidence_expected_cases": 0,
            "evidence_hit_cases": 0,
            "evidence_hit_rate": 0.0,
            "preview_required_cases": 0,
            "preview_resolved_cases": 0,
            "preview_resolvable_rate": 0.0,
            "preview_term_total": 0,
            "preview_term_hits": 0,
            "preview_term_hit_rate": 0.0,
            "source_count_match_rate": 0.0,
            "blocked_term_hit_cases": 0,
            "forbidden_term_clean_rate": 0.0,
            "category_breakdown": {},
        }

    passed_cases = sum(1 for item in reports if item["passed"])
    scope_passed_cases = sum(1 for item in reports if item["scope_passed"])
    total_keypoints = sum(int(item.get("keypoint_total") or 0) for item in reports)
    matched_keypoints = sum(len(item.get("keypoint_hits") or []) for item in reports)
    evidence_expected_cases = [
        item
        for item in reports
        if item.get("required_evidence_docs") or item["expected_doc"] is not None or item["expected_source_count"] > 0
    ]
    evidence_hit_cases = sum(1 for item in evidence_expected_cases if item["evidence_hit"])
    preview_required_cases = [item for item in reports if item["preview_required"]]
    preview_resolved_cases = sum(1 for item in preview_required_cases if item["preview_resolvable"])
    preview_term_total = sum(int(item.get("preview_term_total") or 0) for item in preview_required_cases)
    preview_term_hits = sum(len(item.get("preview_term_hits") or []) for item in preview_required_cases)
    source_count_match_cases = sum(1 for item in reports if item["source_count_match"])
    blocked_term_clean_cases = sum(1 for item in reports if item["blocked_term_clean"])
    blocked_term_hit_cases = total_cases - blocked_term_clean_cases

    category_counter = Counter(str(item.get("category", "uncategorized")) for item in reports)
    category_breakdown: dict[str, dict[str, Any]] = {}
    for category, count in sorted(category_counter.items()):
        category_reports = [item for item in reports if str(item.get("category", "uncategorized")) == category]
        category_passed = sum(1 for item in category_reports if item["passed"])
        category_breakdown[category] = {
            "count": count,
            "passed": category_passed,
            "pass_rate": category_passed / count,
            "pass_rate_ci95": _confidence_interval_wilson(category_passed, count),
        }

    return {
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": total_cases - passed_cases,
        "pass_rate": passed_cases / total_cases,
        "pass_rate_ci95": _confidence_interval_wilson(passed_cases, total_cases),
        "scope_pass_rate": scope_passed_cases / total_cases,
        "average_keypoint_coverage": sum(item["keypoint_coverage"] for item in reports) / total_cases,
        "total_keypoints": total_keypoints,
        "matched_keypoints": matched_keypoints,
        "missing_keypoints": total_keypoints - matched_keypoints,
        "keypoint_hit_rate": matched_keypoints / total_keypoints if total_keypoints else 1.0,
        "evidence_expected_cases": len(evidence_expected_cases),
        "evidence_hit_cases": evidence_hit_cases,
        "evidence_hit_rate": evidence_hit_cases / len(evidence_expected_cases) if evidence_expected_cases else 1.0,
        "preview_required_cases": len(preview_required_cases),
        "preview_resolved_cases": preview_resolved_cases,
        "preview_resolvable_rate": preview_resolved_cases / len(preview_required_cases) if preview_required_cases else 1.0,
        "preview_term_total": preview_term_total,
        "preview_term_hits": preview_term_hits,
        "preview_term_hit_rate": preview_term_hits / preview_term_total if preview_term_total else 1.0,
        "source_count_match_rate": source_count_match_cases / total_cases,
        "blocked_term_hit_cases": blocked_term_hit_cases,
        "forbidden_term_clean_rate": blocked_term_clean_cases / total_cases,
        "category_breakdown": category_breakdown,
    }
