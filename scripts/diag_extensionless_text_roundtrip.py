"""诊断无后缀文本在 octet-stream 下的真实导入与问答链路。"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import requests

try:
    from scripts.diag_roundtrip_support import find_file_result, resolve_saved_file_path, wait_for_runtime_ready
except ModuleNotFoundError:
    from diag_roundtrip_support import find_file_result, resolve_saved_file_path, wait_for_runtime_ready

DEFAULT_BASE_URL = "http://127.0.0.1:18081"
DEFAULT_TIMEOUT = 180.0
CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "README-utf8",
        "filename": "README",
        "relative_path": "docs/README",
        "encoding": "utf-8",
        "content_type": "application/octet-stream",
        "text": (
            "Extensionless diagnostic note.\n"
            "Knowledge Base remains the authorization boundary.\n"
            "Folder stays an organization object only.\n"
        ),
        "question": "In the extensionless UTF-8 note, what remains the authorization boundary?",
        "expected_terms": ("knowledge base", "authorization boundary"),
        "answer_anchor_terms": ("knowledge base",),
    },
    {
        "case_id": "README-utf16",
        "filename": "README",
        "relative_path": "docs/README",
        "encoding": "utf-16",
        "content_type": "application/octet-stream",
        "text": (
            "Extensionless UTF-16 diagnostic note.\n"
            "The authorization boundary remains the knowledge base.\n"
            "Folder remains organization only.\n"
        ),
        "question": "In the extensionless UTF-16 note, what remains the authorization boundary?",
        "expected_terms": ("knowledge base", "authorization boundary"),
        "answer_anchor_terms": ("knowledge base",),
    },
)


def _normalize_text(text: str | None) -> str:
    """归一化文本，便于大小写不敏感的片段判断。"""
    return " ".join(str(text or "").strip().lower().split())



def _contains_terms(text: str | None, terms: tuple[str, ...] | list[str]) -> bool:
    """判断文本是否包含全部期望关键词。"""
    normalized = _normalize_text(text)
    return all(_normalize_text(term) in normalized for term in terms)



def _answer_meets_minimum_contract(
    answer: str | None,
    *,
    expected_terms: tuple[str, ...] | list[str],
    answer_anchor_terms: tuple[str, ...] | list[str] = (),
    source_text: str = "",
    evidence_excerpt: str = "",
) -> bool:
    """允许“简短回答 + source/evidence 充分支撑”的最小可用结论。"""
    if _contains_terms(answer, expected_terms):
        return True

    anchors = tuple(answer_anchor_terms) or tuple(expected_terms[:1])
    support_blob = "\n".join(part for part in (str(source_text or ""), str(evidence_excerpt or "")) if part)
    return _contains_terms(answer, anchors) and _contains_terms(support_blob, expected_terms)



def _sha256_bytes(payload: bytes) -> str:
    """计算字节内容的 SHA256。"""
    return hashlib.sha256(payload).hexdigest()



def _parse_args() -> argparse.Namespace:
    """读取命令行参数。"""
    parser = argparse.ArgumentParser(description="诊断无后缀文本在 octet-stream 下的真实导入与问答链路")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="本地 API 地址")
    parser.add_argument("--kb-prefix", default="diag-kb-extensionless-text", help="诊断知识库 ID 前缀")
    parser.add_argument(
        "--source-dir",
        default=str(Path("temp") / "diag-extensionless-text"),
        help="本地临时诊断文件目录",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="HTTP 超时时间（秒）")
    parser.add_argument("--output-path", default=None, help="可选；把 JSON 报告写入指定 UTF-8 文件")
    return parser.parse_args()



def _request_json(method: str, url: str, *, timeout: float, **kwargs: Any) -> dict[str, Any]:
    """发起 HTTP 请求并返回 JSON 结果。"""
    response = requests.request(method, url, timeout=timeout, **kwargs)
    response.raise_for_status()
    return response.json()



def _build_request_error(exc: requests.RequestException) -> dict[str, Any]:
    """把 requests 异常转换成可序列化结构。"""
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



def _write_source_file(path: Path, text: str, encoding: str) -> dict[str, Any]:
    """写入无后缀源文件，并返回源文件摘要。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding=encoding)
    payload = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "encoding": encoding,
        "sha256": _sha256_bytes(payload),
        "size": len(payload),
        "text_preview": path.read_text(encoding=encoding),
    }



def _ensure_kb(base_url: str, kb_id: str, timeout: float) -> dict[str, Any]:
    """确保诊断知识库存在；若已存在则兼容返回。"""
    response = requests.post(
        base_url.rstrip("/") + "/api/kb",
        json={"kb_id": kb_id, "kb_name": f"Extensionless Diagnostic {kb_id}"},
        timeout=timeout,
    )
    if response.status_code == 200:
        return response.json()
    if response.status_code == 409:
        return {"code": 409, "message": "kb_exists", "data": {"kb_id": kb_id}}
    response.raise_for_status()
    return response.json()



def _import_file(
    base_url: str,
    *,
    kb_id: str,
    source_path: Path,
    relative_path: str,
    content_type: str,
    timeout: float,
) -> dict[str, Any]:
    """上传无后缀文本文件。"""
    with source_path.open("rb") as handle:
        response = requests.post(
            base_url.rstrip("/") + "/api/kb/file/import",
            files={"files": (source_path.name, handle, content_type)},
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



def _chat_query(base_url: str, *, kb_id: str, question: str, timeout: float) -> dict[str, Any]:
    """在单知识库范围内发起诊断问答。"""
    return _request_json(
        "POST",
        base_url.rstrip("/") + "/api/chat/query",
        timeout=timeout,
        json={"question": question, "kb_ids": [kb_id]},
    )



def _read_saved_text(saved_path: Path | None, encoding: str) -> tuple[str | None, str | None]:
    """按目标编码读取落盘文本，并保留解码错误信息。"""
    if saved_path is None:
        return None, None
    try:
        return saved_path.read_text(encoding=encoding), None
    except UnicodeError as exc:
        return None, f"{type(exc).__name__}: {exc}"



def _build_case_report(
    *,
    base_url: str,
    kb_prefix: str,
    source_dir: Path,
    timeout: float,
    case: dict[str, Any],
    timestamp: int,
) -> dict[str, Any]:
    """执行单个 extensionless 文本案例并输出结构化结果。"""
    case_id = str(case["case_id"])
    kb_id = f"{kb_prefix}-{case_id.lower()}-{timestamp}"
    source_path = source_dir / str(timestamp) / case_id / str(case["filename"])
    source_info = _write_source_file(source_path, str(case["text"]), str(case["encoding"]))
    _ensure_kb(base_url, kb_id, timeout)
    import_resp = _import_file(
        base_url,
        kb_id=kb_id,
        source_path=source_path,
        relative_path=str(case["relative_path"]),
        content_type=str(case["content_type"]),
        timeout=timeout,
    )

    import_file_result = find_file_result(import_resp, relative_path=str(case["relative_path"])) or {}
    saved_path = resolve_saved_file_path(import_resp, kb_id=kb_id, relative_path=str(case["relative_path"]))
    saved_payload = saved_path.read_bytes() if saved_path is not None else None
    saved_text, saved_text_error = _read_saved_text(saved_path, str(case["encoding"]))

    import_status = str(import_file_result.get("status") or "unknown")
    diagnostics = import_file_result.get("diagnostics") if isinstance(import_file_result.get("diagnostics"), dict) else {}
    should_attempt_chat = import_status == "indexed"
    chat_attempted = False
    chat_executed = False
    chat_error: dict[str, Any] | None = None
    chat_payload: dict[str, Any] = {}
    answer = ""
    first_source: dict[str, Any] = {}
    first_evidence: dict[str, Any] = {}
    if should_attempt_chat:
        chat_attempted = True
        try:
            chat_resp = _chat_query(base_url, kb_id=kb_id, question=str(case["question"]), timeout=timeout)
            chat_payload = chat_resp.get("data", {})
            answer = str(chat_payload.get("answer") or "")
            first_source = (chat_payload.get("sources") or [{}])[0]
            first_evidence = (chat_payload.get("evidence") or [{}])[0]
            chat_executed = True
        except requests.RequestException as exc:
            chat_error = _build_request_error(exc)

    expected_terms = tuple(str(item) for item in case.get("expected_terms", ()))
    answer_anchor_terms = tuple(str(item) for item in case.get("answer_anchor_terms", ()))
    checks = {
        "import_indexed": import_status == "indexed",
        "file_kind_text": diagnostics.get("file_kind") == "text",
        "saved_exists": saved_path is not None,
        "source_saved_hash_match": source_info["sha256"] == _sha256_bytes(saved_payload) if saved_payload is not None else None,
        "saved_text_contains_expected_terms": _contains_terms(saved_text, expected_terms) if saved_text is not None else None,
        "chat_answer_contains_expected_terms": _contains_terms(answer, expected_terms) if chat_executed else None,
        "chat_answer_meets_minimum_contract": _answer_meets_minimum_contract(
            answer,
            expected_terms=expected_terms,
            answer_anchor_terms=answer_anchor_terms,
            source_text=str(first_source.get("text") or ""),
            evidence_excerpt=str(first_evidence.get("excerpt") or ""),
        )
        if chat_executed
        else None,
        "chat_source_contains_expected_terms": _contains_terms(str(first_source.get("text") or ""), expected_terms) if chat_executed else None,
        "chat_evidence_contains_expected_terms": _contains_terms(str(first_evidence.get("excerpt") or ""), expected_terms) if chat_executed else None,
    }
    run_passed = all(value is True for value in checks.values() if value is not None)

    return {
        "case_id": case_id,
        "kb_id": kb_id,
        "question": case["question"],
        "expected_terms": list(expected_terms),
        "source": source_info,
        "saved": {
            "requested_relative_path": case["relative_path"],
            "path": str(saved_path) if saved_path is not None else import_file_result.get("path"),
            "exists": saved_path is not None,
            "encoding": case["encoding"],
            "sha256": _sha256_bytes(saved_payload) if saved_payload is not None else None,
            "size": len(saved_payload) if saved_payload is not None else None,
            "text_preview": saved_text,
            "text_decode_error": saved_text_error,
            "import_status": import_status,
            "import_message": import_file_result.get("message"),
            "import_diagnostics": diagnostics,
        },
        "checks": checks,
        "run_gates": {"run_passed": run_passed},
        "import_summary": import_resp.get("data", {}),
        "chat_summary": {
            "attempted": chat_attempted,
            "executed": chat_executed,
            "error": chat_error,
            "answer": answer,
            "requested_scope_type": chat_payload.get("requested_scope_type"),
            "requested_kb_ids": chat_payload.get("requested_kb_ids"),
            "effective_scope_type": chat_payload.get("effective_scope_type"),
            "effective_kb_ids": chat_payload.get("effective_kb_ids"),
            "is_default_deny_applied": chat_payload.get("is_default_deny_applied"),
            "isolation_level": chat_payload.get("isolation_level"),
            "source_count": len(chat_payload.get("sources") or []),
            "evidence_count": len(chat_payload.get("evidence") or []),
            "first_source": first_source,
            "first_evidence": first_evidence,
        },
    }



def _emit_report(report: dict[str, Any], output_path: str | None) -> None:
    """打印 JSON 报告，并在需要时写入 UTF-8 文件。"""
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
    print(payload)



def main() -> int:
    """执行无后缀文本诊断并输出结构化结果。"""
    args = _parse_args()
    base_url = args.base_url.rstrip("/")
    source_dir = Path(args.source_dir)
    timestamp = int(time.time())
    health = wait_for_runtime_ready(base_url, timeout=args.timeout, poll_interval=2.0, require_ocr=False)
    case_reports = [
        _build_case_report(
            base_url=base_url,
            kb_prefix=args.kb_prefix,
            source_dir=source_dir,
            timeout=args.timeout,
            case=case,
            timestamp=timestamp,
        )
        for case in CASES
    ]
    report = {
        "base_url": base_url,
        "generated_at_epoch": timestamp,
        "health": health.get("data", health),
        "cases": case_reports,
        "summary": {
            "case_count": len(case_reports),
            "passed_case_count": sum(1 for item in case_reports if item["run_gates"]["run_passed"]),
            "all_checks_passed": all(item["run_gates"]["run_passed"] for item in case_reports),
        },
    }
    _emit_report(report, args.output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
