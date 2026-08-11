"""跨知识库与跨领域真实问答诊断脚本。"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_API_BASE = "http://127.0.0.1:18080"
DEFAULT_TIMEOUT = 120.0

DEFAULT_CASES: list[dict[str, Any]] = [
    {
        "id": "grain-positive-safety-policy",
        "focus": "grain",
        "kind": "positive",
        "kb_ids": ["grain-knowledge-base"],
        "question": "《粮油安全储存守则》制定的安全储粮方针是什么？",
        "expected_terms": ["预防为主", "综合防治"],
        "allowed_source_kb_ids": ["grain-knowledge-base"],
        "required_source_kb_ids": ["grain-knowledge-base"],
    },
    {
        "id": "grain-positive-safety-production",
        "focus": "grain",
        "kind": "positive",
        "kb_ids": ["grain-knowledge-base"],
        "question": "《粮库安全生产守则》遵循什么安全生产理念和方针？",
        "expected_terms": ["以人为本", "生命至上", "安全发展", "安全第一", "预防为主", "综合治理"],
        "allowed_source_kb_ids": ["grain-knowledge-base"],
        "required_source_kb_ids": ["grain-knowledge-base"],
    },
    {
        "id": "desktop-positive-passcode",
        "focus": "desktop",
        "kind": "positive",
        "kb_ids": ["diag-desktop-e2e-1786353063"],
        "question": "What is the unique desktop workflow passcode in the diagnostic document?",
        "expected_terms": ["northagent-desktop-e2e-1786353063"],
        "allowed_source_kb_ids": ["diag-desktop-e2e-1786353063"],
        "required_source_kb_ids": ["diag-desktop-e2e-1786353063"],
    },
    {
        "id": "desktop-positive-passcode-older",
        "focus": "desktop",
        "kind": "positive",
        "kb_ids": ["diag-desktop-e2e-1786352564"],
        "question": "What is the unique desktop workflow passcode in the older diagnostic document?",
        "expected_terms": ["northagent-desktop-e2e-1786352564"],
        "allowed_source_kb_ids": ["diag-desktop-e2e-1786352564"],
        "required_source_kb_ids": ["diag-desktop-e2e-1786352564"],
    },
    {
        "id": "desktop-positive-preview",
        "focus": "desktop",
        "kind": "positive",
        "kb_ids": ["diag-desktop-e2e-1786353063"],
        "question": "What should evidence preview resolve after chat returns sources?",
        "expected_terms": ["resolve this file after chat returns sources"],
        "allowed_source_kb_ids": ["diag-desktop-e2e-1786353063"],
        "required_source_kb_ids": ["diag-desktop-e2e-1786353063"],
    },
    {
        "id": "utf8-positive-boundary",
        "focus": "utf8",
        "kind": "positive",
        "kb_ids": ["diag-kb-utf8-1785505921"],
        "question": "这份 UTF-8 诊断文档如何描述知识库和文件夹的边界？",
        "expected_terms": ["知识库", "授权边界", "组织作用"],
        "allowed_source_kb_ids": ["diag-kb-utf8-1785505921"],
        "required_source_kb_ids": ["diag-kb-utf8-1785505921"],
    },
    {
        "id": "image-positive-boundary",
        "focus": "image-ocr",
        "kind": "positive",
        "kb_ids": ["diag-image-ocr-20260807-r2"],
        "question": "What does the OCR diagnostic document say about folder and knowledge base boundaries?",
        "expected_terms": ["folder is for organization only", "knowledge base is the authorization boundary"],
        "allowed_source_kb_ids": ["diag-image-ocr-20260807-r2"],
        "required_source_kb_ids": ["diag-image-ocr-20260807-r2"],
    },
    {
        "id": "pdf-positive-fallback",
        "focus": "pdf-scan",
        "kind": "positive",
        "kb_ids": ["diag-pdf-scan-20260807-r2"],
        "question": "What does the scanned PDF diagnostic say about OCR fallback?",
        "expected_terms": ["OCR fallback must merge every predict batch per page"],
        "allowed_source_kb_ids": ["diag-pdf-scan-20260807-r2"],
        "required_source_kb_ids": ["diag-pdf-scan-20260807-r2"],
    },
    {
        "id": "mixed-positive-rollback",
        "focus": "mixed-batch",
        "kind": "positive",
        "kb_ids": ["diag-mixed-batch-20260807-r2"],
        "question": "Who gives the final rollback approval in the Friday release cutover note?",
        "expected_any_term_groups": [
            ["平台值班主管", "最终的回滚批准"],
            ["platform duty lead", "final rollback approval"],
        ],
        "allowed_source_kb_ids": ["diag-mixed-batch-20260807-r2"],
        "required_source_kb_ids": ["diag-mixed-batch-20260807-r2"],
    },
    {
        "id": "mixed-positive-preview",
        "focus": "mixed-batch",
        "kind": "positive",
        "kb_ids": ["diag-mixed-batch-20260807-r2"],
        "question": "What should every evidence preview include?",
        "expected_terms": ["doc_id", "preview_locator"],
        "allowed_source_kb_ids": ["diag-mixed-batch-20260807-r2"],
        "required_source_kb_ids": ["diag-mixed-batch-20260807-r2"],
    },
    {
        "id": "boundary-negative-manual-structure",
        "focus": "boundary",
        "kind": "negative",
        "kb_ids": ["diag-boundary-1785495036"],
        "question": "What exact sentence does the manual use to describe the authorization boundary?",
        "forbidden_terms": ["Knowledge Base remains the authorization boundary", "Folder is organization only"],
        "allowed_source_kb_ids": ["diag-boundary-1785495036"],
        "forbidden_source_kb_ids": ["diag-exttext-readme-utf8-1785506464", "diag-exttext-readme-utf16-1785506468"],
    },
    {
        "id": "exttext-positive-readme-utf8",
        "focus": "exttext",
        "kind": "positive",
        "kb_ids": ["diag-exttext-readme-utf8-1785506464"],
        "question": "What exact sentence does the README use to describe the authorization boundary?",
        "expected_terms": ["Knowledge Base remains the authorization boundary"],
        "allowed_source_kb_ids": ["diag-exttext-readme-utf8-1785506464"],
        "required_source_kb_ids": ["diag-exttext-readme-utf8-1785506464"],
    },
    {
        "id": "exttext-positive-extensionless-utf8-folder",
        "focus": "exttext",
        "kind": "positive",
        "kb_ids": ["diag-kb-extensionless-text-readme-utf8-1785506975"],
        "question": "What does the extensionless UTF-8 README say about the folder?",
        "expected_any_term_groups": [
            ["organization object only"],
            ["organization only"],
        ],
        "allowed_source_kb_ids": ["diag-kb-extensionless-text-readme-utf8-1785506975"],
        "required_source_kb_ids": ["diag-kb-extensionless-text-readme-utf8-1785506975"],
    },
    {
        "id": "exttext-positive-readme-utf16",
        "focus": "exttext",
        "kind": "positive",
        "kb_ids": ["diag-exttext-readme-utf16-1785506468"],
        "question": "What exact sentence does the UTF-16 README use to describe the authorization boundary?",
        "expected_terms": ["Knowledge Base remains the authorization boundary"],
        "allowed_source_kb_ids": ["diag-exttext-readme-utf16-1785506468"],
        "required_source_kb_ids": ["diag-exttext-readme-utf16-1785506468"],
    },
    {
        "id": "utf16-positive-folder-boundary",
        "focus": "exttext",
        "kind": "positive",
        "kb_ids": ["diag-kb-extensionless-text-readme-utf16-1785506975"],
        "question": "What does the UTF-16 README say about the authorization boundary?",
        "expected_any_term_groups": [
            ["authorization boundary remains the base"],
            ["authorization boundary remains the knowledge base"],
        ],
        "allowed_source_kb_ids": ["diag-kb-extensionless-text-readme-utf16-1785506975"],
        "required_source_kb_ids": ["diag-kb-extensionless-text-readme-utf16-1785506975"],
    },
    {
        "id": "desktop-negative-grain-question",
        "focus": "cross-domain",
        "kind": "negative",
        "kb_ids": ["diag-desktop-e2e-1786353063"],
        "question": "《粮油安全储存守则》制定的安全储粮方针是什么？",
        "forbidden_terms": ["预防为主", "综合防治"],
        "allowed_source_kb_ids": ["diag-desktop-e2e-1786353063"],
        "forbidden_source_kb_ids": ["grain-knowledge-base"],
    },
    {
        "id": "desktop-negative-older-passcode",
        "focus": "cross-domain",
        "kind": "negative",
        "kb_ids": ["diag-desktop-e2e-1786353063"],
        "question": "What is the unique desktop workflow passcode in the 1786352564 diagnostic document?",
        "forbidden_terms": ["northagent-desktop-e2e-1786352564"],
        "allowed_source_kb_ids": ["diag-desktop-e2e-1786353063"],
        "forbidden_source_kb_ids": ["diag-desktop-e2e-1786352564"],
    },
    {
        "id": "grain-negative-desktop-passcode",
        "focus": "cross-domain",
        "kind": "negative",
        "kb_ids": ["grain-knowledge-base"],
        "question": "What is the unique desktop workflow passcode in the diagnostic document?",
        "forbidden_terms": ["northagent-desktop-e2e-1786353063"],
        "allowed_source_kb_ids": ["grain-knowledge-base"],
        "forbidden_source_kb_ids": ["diag-desktop-e2e-1786353063"],
    },
    {
        "id": "grain-negative-utf8-exact-boundary",
        "focus": "cross-domain",
        "kind": "negative",
        "kb_ids": ["grain-knowledge-base"],
        "question": "这份 UTF-8 诊断文档如何描述知识库和文件夹的边界？",
        "forbidden_terms": ["文件夹只承担组织作用", "不承担权限隔离"],
        "allowed_source_kb_ids": ["grain-knowledge-base"],
        "forbidden_source_kb_ids": ["diag-kb-utf8-1785505921"],
        "note": "允许 grain KB 回答相似的授权边界概念，但不能泄漏 UTF-8 诊断文档的精确证据短语。",
    },
    {
        "id": "image-negative-pdf-fallback",
        "focus": "cross-domain",
        "kind": "negative",
        "kb_ids": ["diag-image-ocr-20260807-r2"],
        "question": "What does the scanned PDF diagnostic say about OCR fallback?",
        "forbidden_terms": ["OCR fallback must merge every predict batch per page"],
        "allowed_source_kb_ids": ["diag-image-ocr-20260807-r2"],
        "forbidden_source_kb_ids": ["diag-pdf-scan-20260807-r2"],
    },
    {
        "id": "pdf-negative-image-boundary",
        "focus": "cross-domain",
        "kind": "negative",
        "kb_ids": ["diag-pdf-scan-20260807-r2"],
        "question": "What does the OCR diagnostic document say about folder and knowledge base boundaries?",
        "forbidden_terms": ["folder is organization only", "knowledge base is the authorization boundary"],
        "allowed_source_kb_ids": ["diag-pdf-scan-20260807-r2"],
        "forbidden_source_kb_ids": ["diag-image-ocr-20260807-r2"],
    },
    {
        "id": "mixed-negative-grain-policy",
        "focus": "cross-domain",
        "kind": "negative",
        "kb_ids": ["diag-mixed-batch-20260807-r2"],
        "question": "《粮油安全储存守则》制定的安全储粮方针是什么？",
        "forbidden_terms": ["预防为主", "综合防治"],
        "allowed_source_kb_ids": ["diag-mixed-batch-20260807-r2"],
        "forbidden_source_kb_ids": ["grain-knowledge-base"],
    },
    {
        "id": "multi-kb-contract-rejected",
        "focus": "contract",
        "kind": "contract",
        "kb_ids": ["grain-knowledge-base", "diag-image-ocr-20260807-r2"],
        "question": "Please compare the grain safety policy and the OCR boundary rule.",
        "expected_http_status": 400,
        "expected_error_terms": ["不支持多知识库查询"],
    },
]


def _now_iso() -> str:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc).isoformat()


def _copy_case(item: dict[str, Any], source: str) -> dict[str, Any]:
    """复制用例并补充来源标记。"""
    copied = dict(item)
    copied.setdefault("case_source", source)
    return copied


def _read_cases_file(path: str | Path) -> list[dict[str, Any]]:
    """读取外部 JSON 用例文件。"""
    source_path = Path(path)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("cases")
    if not isinstance(payload, list):
        raise ValueError("cross-domain cases file must be a JSON list or an object with a cases list")
    return [_copy_case(item, str(source_path)) for item in payload if isinstance(item, dict)]


def _ensure_unique_case_ids(cases: list[dict[str, Any]]) -> None:
    """确保用例 id 唯一，避免追加真实样本时误覆盖。"""
    seen: set[str] = set()
    duplicates: list[str] = []
    for item in cases:
        case_id = str(item.get("id") or "case")
        if case_id in seen:
            duplicates.append(case_id)
        seen.add(case_id)
    if duplicates:
        raise ValueError(f"duplicate cross-domain case ids: {', '.join(sorted(set(duplicates)))}")


def load_cases(path: str | Path | None = None, extra_paths: list[str | Path] | None = None) -> list[dict[str, Any]]:
    """读取 JSON 用例；未传路径时返回内置诊断用例，可追加外部真实样本。"""
    if path is None:
        cases = [_copy_case(item, "default") for item in DEFAULT_CASES]
    else:
        cases = _read_cases_file(path)
    for extra_path in extra_paths or []:
        cases.extend(_read_cases_file(extra_path))
    _ensure_unique_case_ids(cases)
    return cases


def _post_json(api_base: str, path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    """向 API 发送 JSON 请求并解析响应。"""
    url = api_base.rstrip("/") + path
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if isinstance(payload, dict):
                payload["_http_status"] = response.status
            return payload
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"code": exc.code, "_http_status": exc.code, "message": detail}
    except urllib.error.URLError as exc:
        return {"code": -1, "_http_status": -1, "message": str(exc)}


def _as_list(value: Any) -> list[str]:
    """把用例字段规整为字符串列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [str(value)] if str(value) else []


def _contains_all(haystack: str, terms: list[str]) -> bool:
    """检查文本是否包含全部关键词。"""
    return all(term in haystack for term in terms)


def _contains_expected_terms(haystack: str, terms: list[str], term_groups: list[list[str]]) -> bool:
    """检查固定关键词或任一同义关键词组是否命中。"""
    required_hit = _contains_all(haystack, terms) if terms else True
    if not term_groups:
        return required_hit
    return required_hit and any(_contains_all(haystack, group) for group in term_groups)


def _contains_any(haystack: str, terms: list[str]) -> bool:
    """检查文本是否包含任一关键词。"""
    return any(term in haystack for term in terms)


def _extract_records(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """从 data 中读取 sources/evidence 记录。"""
    value = data.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _extract_source_kb_ids(data: dict[str, Any]) -> tuple[list[str], int]:
    """从 sources 和 evidence 中抽取 kb_id。"""
    records = _extract_records(data, "sources") + _extract_records(data, "evidence")
    kb_ids: list[str] = []
    for item in records:
        kb_id = item.get("kb_id")
        if isinstance(kb_id, str) and kb_id:
            kb_ids.append(kb_id)
    return kb_ids, len(records)


def _payload_text(data: dict[str, Any]) -> str:
    """合并 answer、sources 和 evidence，用于精确泄漏词检测。"""
    answer = str(data.get("answer") or "")
    sources = _extract_records(data, "sources")
    evidence = _extract_records(data, "evidence")
    return answer + "\n" + json.dumps({"sources": sources, "evidence": evidence}, ensure_ascii=False)


def _resolve_http_status(response: dict[str, Any]) -> int:
    """兼容不同响应形态，提取 HTTP 状态码。"""
    if "_http_status" in response and response["_http_status"] is not None:
        try:
            return int(response["_http_status"])
        except Exception:
            return -1
    code = response.get("code")
    if code == 0:
        return 200
    try:
        return int(code)
    except Exception:
        return -1


def evaluate_case(case: dict[str, Any], api_base: str, timeout: float) -> dict[str, Any]:
    """执行单条跨领域用例并计算通过状态。"""
    case_id = str(case.get("id") or "case")
    kind = str(case.get("kind") or "positive")
    focus = str(case.get("focus") or "uncategorized")
    tags = _as_list(case.get("tags"))
    kb_ids = _as_list(case.get("kb_ids"))
    if not kb_ids:
        raise ValueError(f"{case_id}: kb_ids is required")
    question = str(case.get("question") or "").strip()
    if not question:
        raise ValueError(f"{case_id}: question is required")
    expected_http_status = int(case.get("expected_http_status") or 200)

    response = _post_json(
        api_base,
        "/api/chat/query",
        {
            "question": question,
            "session_id": f"cross-domain-eval::{case_id}",
            "kb_ids": kb_ids,
            "top_k": int(case.get("top_k") or 5),
        },
        timeout,
    )

    data: dict[str, Any] = {}
    response_message = str(response.get("message") or "")
    http_status = _resolve_http_status(response)
    status_ok = http_status == expected_http_status
    error: str | None = None
    if http_status == 200 and isinstance(response.get("data"), dict):
        data = response["data"]
    else:
        error = None if status_ok else response_message or str(response)

    expected_terms = _as_list(case.get("expected_terms"))
    expected_any_term_groups: list[list[str]] = []
    for group in case.get("expected_any_term_groups") or []:
        group_terms = _as_list(group)
        if group_terms:
            expected_any_term_groups.append(group_terms)
    forbidden_terms = _as_list(case.get("forbidden_terms"))
    expected_error_terms = _as_list(case.get("expected_error_terms"))
    allowed_source_kb_ids = set(_as_list(case.get("allowed_source_kb_ids")))
    required_source_kb_ids = set(_as_list(case.get("required_source_kb_ids")))
    forbidden_source_kb_ids = set(_as_list(case.get("forbidden_source_kb_ids")))

    answer = str(data.get("answer") or "")
    combined_text = _payload_text(data)
    source_kb_ids, source_record_count = _extract_source_kb_ids(data)
    source_kb_set = set(source_kb_ids)
    source_kb_id_missing_count = max(source_record_count - len(source_kb_ids), 0)

    if expected_http_status != 200:
        expected_error_terms_hit = _contains_all(response_message, expected_error_terms) if expected_error_terms else True
        checks = {
            "http_status_ok": status_ok,
            "expected_error_terms_hit": expected_error_terms_hit,
            "source_presence_ok": True,
            "source_kb_known": True,
            "source_kb_allowed": True,
            "required_source_kb_hit": True,
            "forbidden_source_kb_clean": True,
            "expected_terms_hit": True,
            "forbidden_terms_clean": True,
        }
        passed = status_ok and expected_error_terms_hit
    else:
        require_sources = bool(case.get("require_sources", kind == "positive"))
        source_presence_ok = (source_record_count > 0) if require_sources else True
        source_kb_known = source_record_count == len(source_kb_ids)
        source_kb_allowed = (
            True
            if not allowed_source_kb_ids
            else source_kb_known and all(kb_id in allowed_source_kb_ids for kb_id in source_kb_ids)
        )
        required_source_kb_hit = required_source_kb_ids.issubset(source_kb_set)
        forbidden_source_kb_clean = not bool(source_kb_set & forbidden_source_kb_ids)
        expected_terms_hit = _contains_expected_terms(answer, expected_terms, expected_any_term_groups)
        forbidden_terms_clean = not _contains_any(combined_text, forbidden_terms)

        checks = {
            "http_status_ok": status_ok,
            "expected_terms_hit": expected_terms_hit,
            "forbidden_terms_clean": forbidden_terms_clean,
            "source_presence_ok": source_presence_ok,
            "source_kb_known": source_kb_known,
            "source_kb_allowed": source_kb_allowed,
            "required_source_kb_hit": required_source_kb_hit,
            "forbidden_source_kb_clean": forbidden_source_kb_clean,
        }
        passed = all(checks.values())

    return {
        "id": case_id,
        "kind": kind,
        "focus": focus,
        "tags": tags,
        "case_source": str(case.get("case_source") or ""),
        "kb_ids": kb_ids,
        "question": question,
        "expected_terms": expected_terms,
        "expected_any_term_groups": expected_any_term_groups,
        "expected_error_terms": expected_error_terms,
        "expected_http_status": expected_http_status,
        "forbidden_terms": forbidden_terms,
        "allowed_source_kb_ids": sorted(allowed_source_kb_ids),
        "required_source_kb_ids": sorted(required_source_kb_ids),
        "forbidden_source_kb_ids": sorted(forbidden_source_kb_ids),
        "answer_preview": answer[:240],
        "source_record_count": source_record_count,
        "source_kb_ids": source_kb_ids,
        "source_kb_id_missing_count": source_kb_id_missing_count,
        "http_status": http_status,
        "response_message": response_message,
        "checks": checks,
        "passed": passed,
        "error": error,
        "note": case.get("note"),
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总跨领域用例结果。"""
    total = len(results)
    passed = [item for item in results if item.get("passed")]
    positive = [item for item in results if item.get("kind") == "positive"]
    negative = [item for item in results if item.get("kind") == "negative"]
    contract = [item for item in results if item.get("kind") == "contract"]
    failed = [item for item in results if not item.get("passed")]
    focus_groups: dict[str, list[dict[str, Any]]] = {}
    case_source_groups: dict[str, list[dict[str, Any]]] = {}
    tag_groups: dict[str, list[dict[str, Any]]] = {}
    for item in results:
        focus_groups.setdefault(str(item.get("focus") or "uncategorized"), []).append(item)
        case_source_groups.setdefault(str(item.get("case_source") or "unknown"), []).append(item)
        for tag in _as_list(item.get("tags")):
            tag_groups.setdefault(tag, []).append(item)

    def _rate(rows: list[dict[str, Any]]) -> float | None:
        if not rows:
            return None
        return round(sum(1 for item in rows if item.get("passed")) / len(rows), 4)

    return {
        "total": total,
        "passed": len(passed),
        "failed": len(failed),
        "pass_rate": _rate(results) if results else 0.0,
        "positive_total": len(positive),
        "positive_pass_rate": _rate(positive),
        "negative_total": len(negative),
        "negative_pass_rate": _rate(negative),
        "contract_total": len(contract),
        "contract_pass_rate": _rate(contract),
        "failed_case_ids": [str(item.get("id")) for item in failed],
        "focus_summary": {
            focus: {
                "total": len(rows),
                "passed": sum(1 for item in rows if item.get("passed")),
                "failed": sum(1 for item in rows if not item.get("passed")),
                "pass_rate": _rate(rows),
            }
            for focus, rows in sorted(focus_groups.items())
        },
        "case_source_summary": {
            source: {
                "total": len(rows),
                "passed": sum(1 for item in rows if item.get("passed")),
                "failed": sum(1 for item in rows if not item.get("passed")),
                "pass_rate": _rate(rows),
            }
            for source, rows in sorted(case_source_groups.items())
        },
        "tag_summary": {
            tag: {
                "total": len(rows),
                "passed": sum(1 for item in rows if item.get("passed")),
                "failed": sum(1 for item in rows if not item.get("passed")),
                "pass_rate": _rate(rows),
            }
            for tag, rows in sorted(tag_groups.items())
        },
    }


def build_report(*, cases: list[dict[str, Any]], api_base: str, timeout: float) -> dict[str, Any]:
    """执行全部用例并构造报告。"""
    results = [evaluate_case(case, api_base, timeout) for case in cases]
    return {
        "generated_at": _now_iso(),
        "api_base": api_base.rstrip("/"),
        "timeout": timeout,
        "summary": summarize(results),
        "cases": results,
    }


def run_evaluation(
    *,
    api_base: str,
    timeout: float,
    output: str,
    cases_path: str | None = None,
    extra_cases_paths: list[str] | None = None,
) -> tuple[dict[str, Any], int]:
    """执行跨领域评测并写出报告。"""
    cases = load_cases(cases_path, extra_cases_paths)
    if not cases:
        return {"summary": {"total": 0, "passed": 0, "failed": 0}}, 2
    report = build_report(cases=cases, api_base=api_base, timeout=timeout)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report, 0 if report["summary"]["failed"] == 0 else 1


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="跨知识库、跨领域真实问答诊断")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="API 根地址")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="单条问答超时秒数")
    parser.add_argument("--cases", default=None, help="可选；JSON list 或 {cases: [...]} 格式用例文件；传入后替换内置基线")
    parser.add_argument(
        "--extra-cases",
        action="append",
        default=[],
        help="可重复；在当前用例集后追加 JSON list 或 {cases: [...]} 格式真实样本文件",
    )
    parser.add_argument(
        "--output",
        default="docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report.json",
        help="评测报告输出路径",
    )
    args = parser.parse_args()

    report, exit_code = run_evaluation(
        api_base=args.api_base,
        timeout=args.timeout,
        output=args.output,
        cases_path=args.cases,
        extra_cases_paths=args.extra_cases,
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"报告已写入: {Path(args.output)}")
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("评测已中断", file=sys.stderr)
        raise SystemExit(130)
