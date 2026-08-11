"""跨知识库与跨领域真实问答诊断脚本。"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import uuid
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_API_BASE = "http://127.0.0.1:18080"
DEFAULT_TIMEOUT = 120.0
DEFAULT_SLOW_THRESHOLD_MS = 5000.0

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
    except TimeoutError as exc:
        return {"code": -1, "_http_status": -1, "message": str(exc)}
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


def _expected_any_term_groups(case: dict[str, Any]) -> list[list[str]]:
    """规整任一命中关键词组。"""
    expected_any_term_groups: list[list[str]] = []
    for group in case.get("expected_any_term_groups") or []:
        group_terms = _as_list(group)
        if group_terms:
            expected_any_term_groups.append(group_terms)
    return expected_any_term_groups


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


def _extract_source_files(data: dict[str, Any]) -> list[str]:
    """从 sources 和 evidence 中抽取可读来源文件名。"""
    records = _extract_records(data, "sources") + _extract_records(data, "evidence")
    files: list[str] = []
    for item in records:
        for key in ("file", "source", "title", "doc_id"):
            value = item.get(key)
            if isinstance(value, str) and value:
                files.append(value)
                break
    return files


def _source_file_terms_hit(source_files: list[str], terms: list[str]) -> bool:
    """检查每个期望来源文件片段都能命中至少一个来源。"""
    return all(any(term in source_file for source_file in source_files) for term in terms)


def _source_file_terms_clean(source_files: list[str], terms: list[str]) -> bool:
    """检查来源文件名不包含禁止片段。"""
    return not any(term in source_file for source_file in source_files for term in terms)


def _source_payload_text(data: dict[str, Any]) -> str:
    """合并 sources 和 evidence 正文，用于证据文本检查。"""
    sources = _extract_records(data, "sources")
    evidence = _extract_records(data, "evidence")
    return json.dumps({"sources": sources, "evidence": evidence}, ensure_ascii=False)


def _payload_text(data: dict[str, Any]) -> str:
    """合并 answer、sources 和 evidence，用于精确泄漏词检测。"""
    answer = str(data.get("answer") or "")
    return answer + "\n" + _source_payload_text(data)


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


def _new_session_id(case: dict[str, Any], case_id: str) -> str:
    """生成本次评测专用 session，避免历史记录串扰。"""
    configured = str(case.get("session_id") or "").strip()
    if configured:
        return configured
    return f"cross-domain-eval::{case_id}::{uuid.uuid4().hex}"


def _elapsed_ms(started_at: float) -> float:
    """计算耗时毫秒，保留 3 位小数。"""
    return round((time.perf_counter() - started_at) * 1000, 3)


def _evaluate_single_turn(
    *,
    case: dict[str, Any],
    api_base: str,
    timeout: float,
    case_id: str,
    session_id: str,
    turn_index: int | None = None,
    turn_id: str | None = None,
) -> dict[str, Any]:
    """执行一次问答请求并计算该轮检查结果。"""
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

    started_at = time.perf_counter()
    response = _post_json(
        api_base,
        "/api/chat/query",
        {
            "question": question,
            "session_id": session_id,
            "kb_ids": kb_ids,
            "top_k": int(case.get("top_k") or 5),
        },
        timeout,
    )
    duration_ms = _elapsed_ms(started_at)

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
    expected_any_term_groups = _expected_any_term_groups(case)
    forbidden_terms = _as_list(case.get("forbidden_terms"))
    expected_error_terms = _as_list(case.get("expected_error_terms"))
    allowed_source_kb_ids = set(_as_list(case.get("allowed_source_kb_ids")))
    required_source_kb_ids = set(_as_list(case.get("required_source_kb_ids")))
    forbidden_source_kb_ids = set(_as_list(case.get("forbidden_source_kb_ids")))
    required_source_files = _as_list(case.get("required_source_files"))
    forbidden_source_files = _as_list(case.get("forbidden_source_files"))
    required_source_text_terms = _as_list(case.get("required_source_text_terms"))
    forbidden_source_text_terms = _as_list(case.get("forbidden_source_text_terms"))

    answer = str(data.get("answer") or "")
    combined_text = _payload_text(data)
    source_text = _source_payload_text(data)
    source_kb_ids, source_record_count = _extract_source_kb_ids(data)
    source_files = _extract_source_files(data)
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
            "required_source_file_hit": True,
            "forbidden_source_file_clean": True,
            "required_source_text_hit": True,
            "forbidden_source_text_clean": True,
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
        required_source_file_hit = (
            _source_file_terms_hit(source_files, required_source_files) if required_source_files else True
        )
        forbidden_source_file_clean = (
            _source_file_terms_clean(source_files, forbidden_source_files) if forbidden_source_files else True
        )
        required_source_text_hit = (
            _contains_all(source_text, required_source_text_terms) if required_source_text_terms else True
        )
        forbidden_source_text_clean = (
            not _contains_any(source_text, forbidden_source_text_terms) if forbidden_source_text_terms else True
        )

        checks = {
            "http_status_ok": status_ok,
            "expected_terms_hit": expected_terms_hit,
            "forbidden_terms_clean": forbidden_terms_clean,
            "source_presence_ok": source_presence_ok,
            "source_kb_known": source_kb_known,
            "source_kb_allowed": source_kb_allowed,
            "required_source_kb_hit": required_source_kb_hit,
            "forbidden_source_kb_clean": forbidden_source_kb_clean,
            "required_source_file_hit": required_source_file_hit,
            "forbidden_source_file_clean": forbidden_source_file_clean,
            "required_source_text_hit": required_source_text_hit,
            "forbidden_source_text_clean": forbidden_source_text_clean,
        }
        passed = all(checks.values())

    result = {
        "id": case_id,
        "kind": kind,
        "focus": focus,
        "tags": tags,
        "case_source": str(case.get("case_source") or ""),
        "kb_ids": kb_ids,
        "session_id": session_id,
        "question": question,
        "expected_terms": expected_terms,
        "expected_any_term_groups": expected_any_term_groups,
        "expected_error_terms": expected_error_terms,
        "expected_http_status": expected_http_status,
        "forbidden_terms": forbidden_terms,
        "allowed_source_kb_ids": sorted(allowed_source_kb_ids),
        "required_source_kb_ids": sorted(required_source_kb_ids),
        "forbidden_source_kb_ids": sorted(forbidden_source_kb_ids),
        "required_source_files": required_source_files,
        "forbidden_source_files": forbidden_source_files,
        "required_source_text_terms": required_source_text_terms,
        "forbidden_source_text_terms": forbidden_source_text_terms,
        "answer_preview": answer[:240],
        "source_text_preview": source_text[:240],
        "duration_ms": duration_ms,
        "source_record_count": source_record_count,
        "source_kb_ids": source_kb_ids,
        "source_files": source_files,
        "source_kb_id_missing_count": source_kb_id_missing_count,
        "http_status": http_status,
        "response_message": response_message,
        "checks": checks,
        "passed": passed,
        "error": error,
        "note": case.get("note"),
    }
    if turn_index is not None:
        result["case_id"] = str(case.get("case_id") or case_id)
        result["turn_index"] = turn_index
        result["turn_id"] = turn_id or f"turn-{turn_index}"
    return result


def _merge_turn_case(case: dict[str, Any], turn: dict[str, Any], index: int) -> dict[str, Any]:
    """把 case 默认字段和单轮字段合并为可评测结构。"""
    merged = {key: value for key, value in case.items() if key != "turns"}
    turn_id = str(turn.get("id") or f"turn-{index}")
    merged.update(turn)
    merged["case_id"] = str(case.get("id") or "case")
    merged["id"] = f"{merged['case_id']}::{turn_id}"
    merged.setdefault("kind", case.get("kind") or "positive")
    merged.setdefault("focus", case.get("focus") or "uncategorized")
    merged.setdefault("tags", _as_list(case.get("tags")))
    merged.setdefault("case_source", case.get("case_source") or "")
    return merged


def _evaluate_multi_turn_case(case: dict[str, Any], api_base: str, timeout: float) -> dict[str, Any]:
    """按同一 session 顺序执行多轮追问用例。"""
    case_id = str(case.get("id") or "case")
    turns = case.get("turns")
    if not isinstance(turns, list) or not turns:
        raise ValueError(f"{case_id}: turns must be a non-empty list")
    turn_items = [item for item in turns if isinstance(item, dict)]
    if len(turn_items) != len(turns):
        raise ValueError(f"{case_id}: every turn must be an object")

    session_id = _new_session_id(case, case_id)
    started_at = time.perf_counter()
    results: list[dict[str, Any]] = []
    for index, turn in enumerate(turn_items, start=1):
        turn_id = str(turn.get("id") or f"turn-{index}")
        turn_case = _merge_turn_case(case, turn, index)
        results.append(
            _evaluate_single_turn(
                case=turn_case,
                api_base=api_base,
                timeout=timeout,
                case_id=case_id,
                session_id=session_id,
                turn_index=index,
                turn_id=turn_id,
            )
        )

    failed_turns = [item for item in results if not item.get("passed")]
    kind = str(case.get("kind") or "positive")
    focus = str(case.get("focus") or "uncategorized")
    tags = _as_list(case.get("tags"))
    kb_ids = _as_list(case.get("kb_ids"))
    source_kb_ids: list[str] = []
    source_files: list[str] = []
    source_kb_id_missing_count = 0
    source_record_count = 0
    for item in results:
        source_kb_ids.extend(_as_list(item.get("source_kb_ids")))
        source_files.extend(_as_list(item.get("source_files")))
        source_kb_id_missing_count += int(item.get("source_kb_id_missing_count") or 0)
        source_record_count += int(item.get("source_record_count") or 0)

    return {
        "id": case_id,
        "kind": kind,
        "focus": focus,
        "tags": tags,
        "case_source": str(case.get("case_source") or ""),
        "kb_ids": kb_ids,
        "session_id": session_id,
        "is_multi_turn": True,
        "turn_count": len(results),
        "passed_turn_count": sum(1 for item in results if item.get("passed")),
        "failed_turn_ids": [str(item.get("turn_id")) for item in failed_turns],
        "duration_ms": _elapsed_ms(started_at),
        "turn_duration_total_ms": round(sum(float(item.get("duration_ms") or 0.0) for item in results), 3),
        "source_record_count": source_record_count,
        "source_kb_ids": source_kb_ids,
        "source_files": source_files,
        "source_kb_id_missing_count": source_kb_id_missing_count,
        "checks": {
            "turns_passed": not failed_turns,
            "turn_count_ok": len(results) == len(turn_items),
            "source_kb_known": source_kb_id_missing_count == 0,
        },
        "passed": not failed_turns,
        "turns": results,
        "note": case.get("note"),
    }


def evaluate_case(case: dict[str, Any], api_base: str, timeout: float) -> dict[str, Any]:
    """执行单条跨领域用例并计算通过状态，支持单轮和多轮追问。"""
    case_id = str(case.get("id") or "case")
    if "turns" in case:
        return _evaluate_multi_turn_case(case, api_base, timeout)
    return _evaluate_single_turn(
        case=case,
        api_base=api_base,
        timeout=timeout,
        case_id=case_id,
        session_id=_new_session_id(case, case_id),
    )


def _failed_check_names(item: dict[str, Any]) -> list[str]:
    """提取单条结果中失败的检查项名称。"""
    checks = item.get("checks")
    if not isinstance(checks, dict):
        return []
    return sorted(str(name) for name, passed in checks.items() if passed is False)


def _iter_check_results(item: dict[str, Any]) -> list[tuple[str, str, list[str]]]:
    """返回 case/turn 粒度的失败检查项，用于汇总诊断。"""
    case_id = str(item.get("id") or "case")
    rows: list[tuple[str, str, list[str]]] = []
    if item.get("is_multi_turn"):
        for turn in item.get("turns") or []:
            if not isinstance(turn, dict):
                continue
            check_names = _failed_check_names(turn)
            if check_names:
                turn_id = str(turn.get("turn_id") or turn.get("id") or "turn")
                rows.append((case_id, turn_id, check_names))
        parent_checks = [name for name in _failed_check_names(item) if name != "turns_passed"]
        if parent_checks:
            rows.append((case_id, "", parent_checks))
    else:
        check_names = _failed_check_names(item)
        if check_names:
            rows.append((case_id, "", check_names))
    return rows


def _summarize_failures(results: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """按失败检查项和失败 case 生成诊断摘要。"""
    check_groups: dict[str, list[dict[str, str]]] = {}
    case_groups: dict[str, dict[str, Any]] = {}
    for item in results:
        for case_id, turn_id, check_names in _iter_check_results(item):
            case_entry = case_groups.setdefault(case_id, {"id": case_id, "failed_checks": [], "failed_turns": []})
            for check_name in check_names:
                check_groups.setdefault(check_name, []).append({"id": case_id, "turn_id": turn_id})
                if check_name not in case_entry["failed_checks"]:
                    case_entry["failed_checks"].append(check_name)
            if turn_id and turn_id not in case_entry["failed_turns"]:
                case_entry["failed_turns"].append(turn_id)

    check_summary = {
        check_name: {
            "total": len(rows),
            "case_ids": sorted({row["id"] for row in rows}),
            "turn_ids": sorted({row["turn_id"] for row in rows if row["turn_id"]}),
        }
        for check_name, rows in sorted(check_groups.items())
    }
    case_summary = [
        {
            "id": item["id"],
            "failed_checks": sorted(item["failed_checks"]),
            "failed_turns": sorted(item["failed_turns"]),
        }
        for item in sorted(case_groups.values(), key=lambda row: row["id"])
    ]
    return check_summary, case_summary


def _as_float(value: Any) -> float | None:
    """把数值字段转换为 float。"""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _summarize_durations(results: list[dict[str, Any]], slow_threshold_ms: float) -> dict[str, Any]:
    """汇总 case/turn 耗时，便于定位慢用例。"""
    case_rows: list[dict[str, Any]] = []
    turn_rows: list[dict[str, Any]] = []
    for item in results:
        case_id = str(item.get("id") or "case")
        duration_ms = _as_float(item.get("duration_ms"))
        if duration_ms is not None:
            case_rows.append({"id": case_id, "duration_ms": duration_ms})
        if item.get("is_multi_turn"):
            for turn in item.get("turns") or []:
                if not isinstance(turn, dict):
                    continue
                turn_duration_ms = _as_float(turn.get("duration_ms"))
                if turn_duration_ms is None:
                    continue
                turn_rows.append(
                    {
                        "id": case_id,
                        "turn_id": str(turn.get("turn_id") or turn.get("id") or "turn"),
                        "duration_ms": turn_duration_ms,
                    }
                )
        elif duration_ms is not None:
            turn_rows.append({"id": case_id, "turn_id": "", "duration_ms": duration_ms})

    def _total(rows: list[dict[str, Any]]) -> float:
        return round(sum(float(row["duration_ms"]) for row in rows), 3)

    def _avg(rows: list[dict[str, Any]]) -> float | None:
        return round(_total(rows) / len(rows), 3) if rows else None

    slow_cases = [row for row in case_rows if float(row["duration_ms"]) >= slow_threshold_ms]
    slow_turns = [row for row in turn_rows if float(row["duration_ms"]) >= slow_threshold_ms]
    max_case = max(case_rows, key=lambda row: float(row["duration_ms"]), default=None)
    max_turn = max(turn_rows, key=lambda row: float(row["duration_ms"]), default=None)
    return {
        "slow_threshold_ms": slow_threshold_ms,
        "case_total_ms": _total(case_rows),
        "case_avg_ms": _avg(case_rows),
        "case_max_ms": round(float(max_case["duration_ms"]), 3) if max_case else None,
        "case_max_id": str(max_case["id"]) if max_case else "",
        "slow_case_ids": [str(row["id"]) for row in sorted(slow_cases, key=lambda row: str(row["id"]))],
        "turn_total_ms": _total(turn_rows),
        "turn_avg_ms": _avg(turn_rows),
        "turn_max_ms": round(float(max_turn["duration_ms"]), 3) if max_turn else None,
        "turn_max_id": str(max_turn["id"]) if max_turn else "",
        "turn_max_turn_id": str(max_turn["turn_id"]) if max_turn else "",
        "slow_turns": [
            {"id": str(row["id"]), "turn_id": str(row["turn_id"]), "duration_ms": round(float(row["duration_ms"]), 3)}
            for row in sorted(slow_turns, key=lambda row: (str(row["id"]), str(row["turn_id"])))
        ],
    }


def summarize(results: list[dict[str, Any]], slow_threshold_ms: float = DEFAULT_SLOW_THRESHOLD_MS) -> dict[str, Any]:
    """汇总跨领域用例结果。"""
    total = len(results)
    passed = [item for item in results if item.get("passed")]
    positive = [item for item in results if item.get("kind") == "positive"]
    negative = [item for item in results if item.get("kind") == "negative"]
    contract = [item for item in results if item.get("kind") == "contract"]
    failed = [item for item in results if not item.get("passed")]
    multi_turn = [item for item in results if item.get("is_multi_turn")]
    turn_total = sum(int(item.get("turn_count") or 1) for item in results)
    turn_passed = 0
    for item in results:
        if item.get("is_multi_turn"):
            turn_passed += int(item.get("passed_turn_count") or 0)
        elif item.get("passed"):
            turn_passed += 1
    focus_groups: dict[str, list[dict[str, Any]]] = {}
    case_source_groups: dict[str, list[dict[str, Any]]] = {}
    tag_groups: dict[str, list[dict[str, Any]]] = {}
    failure_check_summary, failure_case_summary = _summarize_failures(results)
    duration_summary = _summarize_durations(results, slow_threshold_ms)
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
        "multi_turn_total": len(multi_turn),
        "turn_total": turn_total,
        "turn_passed": turn_passed,
        "turn_failed": max(turn_total - turn_passed, 0),
        "turn_pass_rate": round(turn_passed / turn_total, 4) if turn_total else 0.0,
        "failed_case_ids": [str(item.get("id")) for item in failed],
        "failure_check_summary": failure_check_summary,
        "failure_case_summary": failure_case_summary,
        "duration_summary": duration_summary,
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


def build_report(
    *, cases: list[dict[str, Any]], api_base: str, timeout: float, slow_threshold_ms: float = DEFAULT_SLOW_THRESHOLD_MS
) -> dict[str, Any]:
    """执行全部用例并构造报告。"""
    results = [evaluate_case(case, api_base, timeout) for case in cases]
    return {
        "generated_at": _now_iso(),
        "api_base": api_base.rstrip("/"),
        "timeout": timeout,
        "slow_threshold_ms": slow_threshold_ms,
        "summary": summarize(results, slow_threshold_ms=slow_threshold_ms),
        "cases": results,
    }


def run_evaluation(
    *,
    api_base: str,
    timeout: float,
    output: str,
    cases_path: str | None = None,
    extra_cases_paths: list[str] | None = None,
    slow_threshold_ms: float = DEFAULT_SLOW_THRESHOLD_MS,
) -> tuple[dict[str, Any], int]:
    """执行跨领域评测并写出报告。"""
    cases = load_cases(cases_path, extra_cases_paths)
    if not cases:
        return {"summary": {"total": 0, "passed": 0, "failed": 0}}, 2
    report = build_report(cases=cases, api_base=api_base, timeout=timeout, slow_threshold_ms=slow_threshold_ms)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report, 0 if report["summary"]["failed"] == 0 else 1


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="跨知识库、跨领域真实问答诊断")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="API 根地址")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="单条问答超时秒数")
    parser.add_argument(
        "--slow-threshold-ms",
        type=float,
        default=DEFAULT_SLOW_THRESHOLD_MS,
        help="慢用例阈值毫秒数，用于 duration_summary",
    )
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
        slow_threshold_ms=args.slow_threshold_ms,
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
