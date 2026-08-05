"""\u8bca\u65ad PDF text-layer \u5bfc\u5165\u3001\u843d\u76d8\u4e0e\u95ee\u7b54\u94fe\u8def\u3002"""

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

try:
    import fitz  # type: ignore
except ModuleNotFoundError:
    fitz = None

DEFAULT_BASE_URL = "http://127.0.0.1:18081"
DEFAULT_RELATIVE_PATH = "pdf/diag-text-layer.pdf"
PDF_LINES = [
    "PDF diagnostic note.",
    "Folder is an organization object.",
    "Knowledge Base remains the authorization boundary.",
    "Evidence preview should resolve to the original PDF chunk.",
]
QUESTION = "In the diagnostic PDF, what remains the authorization boundary."
EXPECTED_TERMS = ["knowledge base", "authorization boundary"]


def _sha256_bytes(payload: bytes) -> str:
    """\u8ba1\u7b97\u5b57\u8282\u5185\u5bb9\u7684 SHA256\uff0c\u4fbf\u4e8e\u6821\u9a8c\u6e90\u6587\u4ef6\u4e0e\u843d\u76d8\u6587\u4ef6\u4e00\u81f4\u6027\u3002"""
    return hashlib.sha256(payload).hexdigest()


def _parse_args() -> argparse.Namespace:
    """\u89e3\u6790\u547d\u4ee4\u884c\u53c2\u6570\u3002"""
    parser = argparse.ArgumentParser(description="\u8bca\u65ad PDF text-layer \u5bfc\u5165\u3001\u843d\u76d8\u4e0e\u95ee\u7b54\u94fe\u8def")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="\u76ee\u6807 API \u57fa\u5730\u5740")
    parser.add_argument("--kb-id", default=None, help="\u53ef\u9009\u7684\u8bca\u65ad\u77e5\u8bc6\u5e93 ID")
    parser.add_argument(
        "--source-path",
        default=str(Path("temp") / "diag-text-layer.pdf"),
        help="\u672c\u5730\u4e34\u65f6 PDF \u6587\u4ef6\u8def\u5f84",
    )
    parser.add_argument("--relative-path", default=DEFAULT_RELATIVE_PATH, help="\u5bfc\u5165\u5230\u77e5\u8bc6\u5e93\u5185\u7684\u76f8\u5bf9\u8def\u5f84")
    parser.add_argument("--timeout", type=float, default=180.0, help="HTTP \u8bf7\u6c42\u8d85\u65f6\u65f6\u95f4\uff08\u79d2\uff09")
    parser.add_argument("--output-path", default=None, help="\u53ef\u9009\u7684 JSON \u62a5\u544a\u8f93\u51fa\u8def\u5f84")
    return parser.parse_args()


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


def _ensure_kb(base_url: str, kb_id: str, timeout: float) -> dict[str, Any]:
    """\u786e\u4fdd\u8bca\u65ad\u77e5\u8bc6\u5e93\u5b58\u5728\uff1b\u82e5\u5df2\u5b58\u5728\u5219\u8fd4\u56de\u517c\u5bb9\u7ed3\u679c\u3002"""
    response = requests.post(
        base_url.rstrip("/") + "/api/kb",
        json={"kb_id": kb_id, "kb_name": "PDF Diagnostic"},
        timeout=timeout,
    )
    if response.status_code == 200:
        return response.json()
    if response.status_code == 409:
        return {"code": 409, "message": "kb_exists", "data": {"kb_id": kb_id}}
    response.raise_for_status()
    return response.json()


def _escape_pdf_text(text: str) -> str:
    """\u8f6c\u4e49 PDF \u6587\u672c\u5bf9\u8c61\u4e2d\u9700\u8981\u7279\u6b8a\u5904\u7406\u7684\u5b57\u7b26\u3002"""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_minimal_pdf_bytes(lines: list[str]) -> bytes:
    """\u6784\u9020\u4e00\u4e2a\u5305\u542b\u6587\u672c\u5c42\u7684\u6700\u5c0f PDF\uff0c\u907f\u514d\u811a\u672c\u4fa7\u5f3a\u4f9d\u8d56 PyMuPDF\u3002"""
    content_lines = ["BT", "/F1 16 Tf", "50 760 Td"]
    for index, line in enumerate(lines):
        if index:
            content_lines.append("0 -24 Td")
        content_lines.append(f"({_escape_pdf_text(line)}) Tj")
    content_lines.append("ET")
    stream_data = ("\n".join(content_lines) + "\n").encode("utf-8")

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Count 1 /Kids [3 0 R] >>\nendobj\n",
        (
            "3 0 obj\n"
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\n"
            "endobj\n"
        ).encode("utf-8"),
        (
            f"4 0 obj\n<< /Length {len(stream_data)} >>\nstream\n".encode("utf-8")
            + stream_data
            + b"endstream\nendobj\n"
        ),
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    output = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = [0]
    for obj in objects:
        offsets.append(len(output))
        output.extend(obj)

    xref_start = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def _extract_pdf_text_if_possible(path: Path) -> dict[str, Any]:
    """\u82e5\u672c\u673a\u5b89\u88c5\u4e86 PyMuPDF\uff0c\u5219\u63d0\u53d6\u6587\u672c\u9884\u89c8\uff1b\u5426\u5219\u8fd4\u56de\u7f3a\u4f9d\u8d56\u8bf4\u660e\u3002"""
    if fitz is None:
        return {
            "text_preview": None,
            "extractor": None,
            "extract_error": "fitz_not_installed",
        }

    document = fitz.open(path)
    try:
        extracted = "\n".join(page.get_text("text") for page in document).strip()
    finally:
        document.close()
    return {
        "text_preview": extracted,
        "extractor": "fitz",
        "extract_error": None,
    }


def _create_pdf(path: Path) -> dict[str, Any]:
    """\u751f\u6210\u8bca\u65ad PDF \u6587\u4ef6\uff0c\u5e76\u8fd4\u56de\u6e90\u6587\u4ef6\u6458\u8981\u4fe1\u606f\u3002"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _build_minimal_pdf_bytes(PDF_LINES)
    path.write_bytes(payload)
    extracted = _extract_pdf_text_if_possible(path)
    return {
        "path": str(path.resolve()),
        "sha256": _sha256_bytes(payload),
        "size": len(payload),
        "expected_text_preview": "\n".join(PDF_LINES),
        **extracted,
    }


def _import_pdf(base_url: str, kb_id: str, source_path: Path, relative_path: str, timeout: float) -> dict[str, Any]:
    """\u8c03\u7528\u5bfc\u5165\u63a5\u53e3\u4e0a\u4f20\u8bca\u65ad PDF\u3002"""
    with source_path.open("rb") as handle:
        response = requests.post(
            base_url.rstrip("/") + "/api/kb/file/import",
            files={"files": (source_path.name, handle, "application/pdf")},
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


def _preview(base_url: str, kb_id: str, evidence_id: str, timeout: float) -> dict[str, Any]:
    """\u6309 evidence_id \u8bf7\u6c42\u8bc1\u636e\u9884\u89c8\u3002"""
    return _request_json(
        "POST",
        base_url.rstrip("/") + "/api/kb/preview",
        timeout=timeout,
        json={"kb_id": kb_id, "evidence_id": evidence_id},
    )


def _contains_all(text: str, terms: list[str]) -> bool:
    """\u5224\u65ad\u6587\u672c\u662f\u5426\u540c\u65f6\u5305\u542b\u6240\u6709\u76ee\u6807\u5173\u952e\u8bcd\u3002"""
    lowered = (text or "").lower()
    return all(term.lower() in lowered for term in terms)


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
    kb_id = args.kb_id or f"diag-pdf-text-{int(time.time())}"
    source_path = Path(args.source_path)

    health = wait_for_runtime_ready(base_url, timeout=args.timeout, require_ocr=False)
    source_info = _create_pdf(source_path)
    _ensure_kb(base_url, kb_id, args.timeout)
    import_resp = _import_pdf(base_url, kb_id, source_path, args.relative_path, args.timeout)

    import_file_result = find_file_result(import_resp, relative_path=args.relative_path) or {}
    saved_path = resolve_saved_file_path(import_resp, kb_id=kb_id, relative_path=args.relative_path)
    saved_payload = saved_path.read_bytes() if saved_path is not None else None
    saved_text_info = _extract_pdf_text_if_possible(saved_path) if saved_path is not None else {
        "text_preview": None,
        "extractor": None,
        "extract_error": None,
    }

    import_status = str(import_file_result.get("status") or "unknown")
    should_attempt_chat = import_status == "indexed"
    chat_attempted = False
    chat_executed = False
    chat_payload: dict[str, Any] = {}
    answer = ""
    first_source: dict[str, Any] = {}
    first_evidence: dict[str, Any] = {}
    preview_payload = None
    preview_error = None
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
            if first_evidence.get("id"):
                try:
                    preview_payload = _preview(base_url, kb_id, str(first_evidence["id"]), args.timeout).get("data")
                except requests.RequestException as exc:
                    preview_error = _build_request_error(exc)
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
            "text_preview": saved_text_info.get("text_preview"),
            "text_extractor": saved_text_info.get("extractor"),
            "text_extract_error": saved_text_info.get("extract_error"),
            "import_status": import_status,
            "import_message": import_file_result.get("message"),
            "import_diagnostics": import_file_result.get("diagnostics"),
        },
        "checks": {
            "source_saved_hash_match": source_info["sha256"] == _sha256_bytes(saved_payload) if saved_payload is not None else None,
            "saved_text_has_expected_terms": _contains_all(str(saved_text_info.get("text_preview") or ""), EXPECTED_TERMS) if saved_path is not None else None,
            "chat_answer_has_expected_terms": _contains_all(answer, EXPECTED_TERMS) if chat_executed else None,
            "chat_source_has_expected_terms": _contains_all(str(first_source.get("text") or ""), ["knowledge base"]) if chat_executed else None,
            "chat_evidence_has_expected_terms": _contains_all(str(first_evidence.get("excerpt") or ""), ["knowledge base"]) if chat_executed else None,
            "preview_has_expected_terms": _contains_all(str((preview_payload or {}).get("excerpt") or ""), ["knowledge base"]) if preview_payload is not None else None,
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
            "preview": preview_payload,
            "preview_error": preview_error,
        },
    }
    _emit_report(report, args.output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

