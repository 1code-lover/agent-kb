"""\u8bca\u65ad UTF-8 Markdown \u5bfc\u5165\u3001\u843d\u76d8\u4e0e\u95ee\u7b54\u94fe\u8def\u3002"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import requests

try:
    from scripts.diag_roundtrip_support import (
        DEFAULT_LOCAL_API_PORT,
        find_file_result,
        resolve_api_base_url,
        resolve_saved_file_path,
    )
except ModuleNotFoundError:
    from diag_roundtrip_support import DEFAULT_LOCAL_API_PORT, find_file_result, resolve_api_base_url, resolve_saved_file_path

DEFAULT_BASE_URL = f"http://127.0.0.1:{DEFAULT_LOCAL_API_PORT}"
DEFAULT_RELATIVE_PATH = "diag/diag-import-utf8.md"
UTF8_TEXT = (
    "# UTF-8 \u8bca\u65ad\u77e5\u8bc6\u5e93\n\n"
    "\u8fd9\u662f\u4e00\u4efd\u7528\u4e8e\u9a8c\u8bc1\u672c\u5730\u77e5\u8bc6\u5e93\u5bfc\u5165\u94fe\u8def\u7684 Markdown \u8bca\u65ad\u6587\u6863\u3002\n\n"
    "\u6587\u6863\u660e\u786e\u8bf4\u660e\uff1a\u77e5\u8bc6\u5e93\u4ecd\u7136\u662f\u6388\u6743\u8fb9\u754c\uff0c\u6587\u4ef6\u5939\u53ea\u627f\u62c5\u7ec4\u7ec7\u4f5c\u7528\uff0c\u4e0d\u627f\u62c5\u6743\u9650\u9694\u79bb\u3002\n"
)
QUESTION = "\u8bca\u65ad\u6587\u6863\u91cc\uff0c\u4ec0\u4e48\u5bf9\u8c61\u4ecd\u7136\u662f\u6388\u6743\u8fb9\u754c\u3002"
EXPECTED_SNIPPET = "\u77e5\u8bc6\u5e93\u4ecd\u7136\u662f\u6388\u6743\u8fb9\u754c"
EXPECTED_ANSWER_ANCHORS = ("\u77e5\u8bc6\u5e93",)


def _contains_all(text: str, terms: tuple[str, ...] | list[str]) -> bool:
    """\u5224\u65ad\u6587\u672c\u662f\u5426\u5305\u542b\u7ed9\u5b9a\u7684\u6240\u6709\u5173\u952e\u77ed\u8bed\u3002"""
    normalized = str(text or "")
    return all(term in normalized for term in terms)


def _answer_meets_minimum_contract(
    answer: str,
    *,
    source_text: str = "",
    evidence_excerpt: str = "",
) -> bool:
    """
    UTF-8 \u8bca\u65ad\u53ea\u8981\u6c42\u56de\u7b54\u6ee1\u8db3\u201c\u6700\u5c0f\u53ef\u7528\u7ed3\u8bba\u201d\uff0c\u800c\u4e0d\u662f\u9010\u5b57\u590d\u8ff0\u6574\u53e5\u3002

    \u7ea6\u675f\uff1a
    1. \u82e5\u56de\u7b54\u5df2\u5305\u542b\u5b8c\u6574\u76ee\u6807\u77ed\u8bed\uff0c\u5219\u76f4\u63a5\u89c6\u4e3a\u901a\u8fc7\u3002
    2. \u82e5\u56de\u7b54\u53ea\u7ed9\u51fa\u6838\u5fc3\u5bf9\u8c61\uff08\u5982\u201c\u77e5\u8bc6\u5e93\u201d\uff09\uff0c\u5219\u8981\u6c42 source / evidence \u4e2d\u80fd\u627e\u5230\u5b8c\u6574\u8bc1\u636e\u77ed\u8bed\uff0c
       \u8bc1\u660e\u95ee\u7b54\u94fe\u8def\u662f\u201c\u56de\u7b54\u7b80\u77ed\u4f46\u6709\u8bc1\u636e\u652f\u6491\u201d\uff0c\u800c\u4e0d\u662f\u5bfc\u5165\u6216\u68c0\u7d22\u4e22\u5931\u3002
    """
    if EXPECTED_SNIPPET in str(answer or ""):
        return True

    support_blob = "\n".join(part for part in (str(source_text or ""), str(evidence_excerpt or "")) if part)
    return _contains_all(answer, EXPECTED_ANSWER_ANCHORS) and EXPECTED_SNIPPET in support_blob


def _sha256_bytes(payload: bytes) -> str:
    """\u8ba1\u7b97\u5b57\u8282\u5185\u5bb9\u7684 SHA256\uff0c\u4fbf\u4e8e\u6821\u9a8c\u6e90\u6587\u4ef6\u4e0e\u843d\u76d8\u6587\u4ef6\u4e00\u81f4\u6027\u3002"""
    return hashlib.sha256(payload).hexdigest()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """\u89e3\u6790\u547d\u4ee4\u884c\u53c2\u6570\u3002"""
    parser = argparse.ArgumentParser(description="\u8bca\u65ad UTF-8 Markdown \u5bfc\u5165\u3001\u843d\u76d8\u4e0e\u95ee\u7b54\u94fe\u8def")
    parser.add_argument(
        "--base-url",
        default=resolve_api_base_url(),
        help="目标 API 基地址；优先读取 KB_API_BASE_URL，未设置时回退到 KB_API_PORT（默认 18080）",
    )
    parser.add_argument("--kb-id", default=None, help="\u53ef\u9009\u7684\u8bca\u65ad\u77e5\u8bc6\u5e93 ID")
    parser.add_argument(
        "--source-path",
        default=str(Path("temp") / "diag-import-utf8.md"),
        help="\u672c\u5730\u4e34\u65f6 Markdown \u6587\u4ef6\u8def\u5f84",
    )
    parser.add_argument("--relative-path", default=DEFAULT_RELATIVE_PATH, help="\u5bfc\u5165\u5230\u77e5\u8bc6\u5e93\u5185\u7684\u76f8\u5bf9\u8def\u5f84")
    parser.add_argument("--timeout", type=float, default=180.0, help="HTTP \u8bf7\u6c42\u8d85\u65f6\u65f6\u95f4\uff08\u79d2\uff09")
    parser.add_argument("--output-path", default=None, help="\u53ef\u9009\u7684 JSON \u62a5\u544a\u8f93\u51fa\u8def\u5f84")
    return parser.parse_args(argv)


def _request_json(method: str, url: str, *, timeout: float, **kwargs: Any) -> dict[str, Any]:
    """\u53d1\u9001 HTTP \u8bf7\u6c42\u5e76\u8fd4\u56de JSON \u54cd\u5e94\u3002"""
    response = requests.request(method, url, timeout=timeout, **kwargs)
    response.raise_for_status()
    return response.json()


def _build_request_error(exc: requests.RequestException) -> dict[str, Any]:
    """\u628a requests \u5f02\u5e38\u6574\u7406\u4e3a\u53ef\u5e8f\u5217\u5316\u7684\u7ed3\u6784\u5316\u9519\u8bef\u4fe1\u606f\u3002"""
    response = getattr(exc, "response", None)
    payload: dict[str, Any] | None = None
    if response is not None:
        try:
            payload = response.json()
        except ValueError:
            payload = None
    return {
        "type": type(exc).__name__,
        "status_code": getattr(response, "status_code", None),
        "payload": payload,
        "text": getattr(response, "text", None),
        "message": str(exc),
    }


def _write_source_markdown(path: Path) -> dict[str, Any]:
    """\u5199\u5165 UTF-8 \u8bca\u65ad Markdown \u6587\u4ef6\uff0c\u5e76\u8fd4\u56de\u6e90\u6587\u4ef6\u6458\u8981\u4fe1\u606f\u3002"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(UTF8_TEXT, encoding="utf-8", newline="\n")
    payload = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "sha256": _sha256_bytes(payload),
        "size": len(payload),
        "text_preview": path.read_text(encoding="utf-8"),
    }


def _ensure_kb(base_url: str, kb_id: str, timeout: float) -> dict[str, Any]:
    """\u786e\u4fdd\u8bca\u65ad\u77e5\u8bc6\u5e93\u5b58\u5728\uff1b\u82e5\u5df2\u5b58\u5728\u5219\u8fd4\u56de\u517c\u5bb9\u7ed3\u679c\u3002"""
    response = requests.post(
        base_url.rstrip("/") + "/api/kb",
        json={"kb_id": kb_id, "kb_name": "UTF8 Diagnostic"},
        timeout=timeout,
    )
    if response.status_code == 200:
        return response.json()
    if response.status_code == 409:
        return {"code": 409, "message": "kb_exists", "data": {"kb_id": kb_id}}
    response.raise_for_status()
    return response.json()


def _import_markdown(base_url: str, kb_id: str, source_path: Path, relative_path: str, timeout: float) -> dict[str, Any]:
    """\u8c03\u7528\u5bfc\u5165\u63a5\u53e3\u4e0a\u4f20\u8bca\u65ad Markdown\u3002"""
    with source_path.open("rb") as handle:
        response = requests.post(
            base_url.rstrip("/") + "/api/kb/file/import",
            files={"files": (source_path.name, handle, "text/markdown")},
            data={
                "kb_id": kb_id,
                "chunk_size": "128",
                "chunk_overlap": "16",
                "relative_paths": relative_path,
                "import_mode": "preserve_tree",
            },
            timeout=timeout,
        )
    response.raise_for_status()
    return response.json()


def _chat_query(base_url: str, kb_id: str, timeout: float) -> dict[str, Any]:
    """\u5728\u5355\u77e5\u8bc6\u5e93\u8303\u56f4\u5185\u53d1\u8d77\u8bca\u65ad\u95ee\u7b54\u3002"""
    return _request_json(
        "POST",
        base_url.rstrip("/") + "/api/chat/query",
        timeout=timeout,
        json={"question": QUESTION, "kb_ids": [kb_id]},
    )


def _emit_report(report: dict[str, Any], output_path: str | None) -> None:
    """\u8f93\u51fa JSON \u62a5\u544a\uff0c\u5e76\u5728\u9700\u8981\u65f6\u5199\u5165 UTF-8 \u6587\u4ef6\u3002"""
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
    print(payload)


def main() -> int:
    """\u6267\u884c\u8bca\u65ad\u6d41\u7a0b\u5e76\u8f93\u51fa\u7ed3\u6784\u5316\u7ed3\u679c\u3002"""
    args = _parse_args()
    base_url = args.base_url.rstrip("/")
    kb_id = args.kb_id or f"diag-kb-utf8-{int(time.time())}"
    source_path = Path(args.source_path)

    health = _request_json("GET", base_url + "/api/health", timeout=args.timeout)
    source_info = _write_source_markdown(source_path)
    _ensure_kb(base_url, kb_id, args.timeout)
    import_resp = _import_markdown(base_url, kb_id, source_path, args.relative_path, args.timeout)

    import_file_result = find_file_result(import_resp, relative_path=args.relative_path) or {}
    saved_path = resolve_saved_file_path(import_resp, kb_id=kb_id, relative_path=args.relative_path)
    saved_payload = saved_path.read_bytes() if saved_path is not None else None
    saved_text = saved_path.read_text(encoding="utf-8") if saved_path is not None else None

    import_status = str(import_file_result.get("status") or "unknown")
    should_attempt_chat = import_status == "indexed"
    chat_attempted = False
    chat_executed = False
    chat_payload: dict[str, Any] = {}
    answer = ""
    first_source: dict[str, Any] = {}
    first_evidence: dict[str, Any] = {}
    chat_skipped_reason = None
    chat_error = None
    if should_attempt_chat:
        chat_attempted = True
        try:
            chat_resp = _chat_query(base_url, kb_id, args.timeout)
            chat_payload = chat_resp.get("data", {})
            answer = str(chat_payload.get("answer") or "")
            first_source = (chat_payload.get("sources") or [{}])[0]
            first_evidence = (chat_payload.get("evidence") or [{}])[0]
            chat_executed = True
        except requests.RequestException as exc:
            chat_error = _build_request_error(exc)
    else:
        chat_skipped_reason = f"import_status={import_status}"

    report = {
        "base_url": base_url,
        "kb_id": kb_id,
        "question": QUESTION,
        "health": health.get("data", health),
        "source": source_info,
        "saved": {
            "requested_relative_path": args.relative_path,
            "path": str(saved_path) if saved_path is not None else import_file_result.get("path"),
            "exists": saved_path is not None,
            "sha256": _sha256_bytes(saved_payload) if saved_payload is not None else None,
            "size": len(saved_payload) if saved_payload is not None else None,
            "text_preview": saved_text,
            "import_status": import_status,
            "import_message": import_file_result.get("message"),
            "import_diagnostics": import_file_result.get("diagnostics"),
        },
        "checks": {
            "source_saved_hash_match": source_info["sha256"] == _sha256_bytes(saved_payload) if saved_payload is not None else None,
            "saved_text_contains_expected_snippet": EXPECTED_SNIPPET in (saved_text or "") if saved_text is not None else None,
            "chat_answer_contains_expected_snippet": EXPECTED_SNIPPET in answer if chat_executed else None,
            "chat_answer_has_expected_anchor": _contains_all(answer, EXPECTED_ANSWER_ANCHORS) if chat_executed else None,
            "chat_answer_meets_minimum_contract": _answer_meets_minimum_contract(
                answer,
                source_text=str(first_source.get("text") or ""),
                evidence_excerpt=str(first_evidence.get("excerpt") or ""),
            )
            if chat_executed
            else None,
            "chat_source_contains_expected_snippet": EXPECTED_SNIPPET[:8] in str(first_source.get("text") or "") if chat_executed else None,
            "chat_evidence_contains_expected_snippet": EXPECTED_SNIPPET[:8] in str(first_evidence.get("excerpt") or "") if chat_executed else None,
        },
        "import_summary": import_resp.get("data", {}),
        "chat_summary": {
            "attempted": chat_attempted,
            "executed": chat_executed,
            "skipped_reason": chat_skipped_reason,
            "error": chat_error,
            "answer": answer,
            "requested_scope_type": chat_payload.get("requested_scope_type"),
            "requested_kb_ids": chat_payload.get("requested_kb_ids"),
            "effective_scope_type": chat_payload.get("effective_scope_type"),
            "effective_kb_ids": chat_payload.get("effective_kb_ids"),
            "is_default_deny_applied": chat_payload.get("is_default_deny_applied"),
            "isolation_level": chat_payload.get("isolation_level"),
            "first_source": first_source,
            "first_evidence": first_evidence,
        },
    }

    _emit_report(report, args.output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

