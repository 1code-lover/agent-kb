"""????????????/?? roundtrip ?????"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import fitz
import requests
from PIL import Image, ImageDraw, ImageFont

try:
    from scripts.diag_roundtrip_support import wait_for_runtime_ready
except ModuleNotFoundError:
    from diag_roundtrip_support import wait_for_runtime_ready

DEFAULT_BASE_URL = "http://127.0.0.1:18080"
DEFAULT_TIMEOUT = 240.0
DEFAULT_CHUNK_SIZE = 256
DEFAULT_CHUNK_OVERLAP = 16
FONT_CANDIDATES = [
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/System/Library/Fonts/Supplemental/Verdana.ttf"),
    Path("/System/Library/Fonts/Helvetica.ttc"),
    Path("/Library/Fonts/Arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("C:/Windows/Fonts/calibri.ttf"),
    Path("C:/Windows/Fonts/msyh.ttc"),
]
IMPORT_ORDER = [
    "cutover.md",
    "escalation-board.png",
    "vendor-cutover.pdf",
    "preview-board.png",
]
RELATIVE_PATHS = {
    "cutover.md": "playbooks/release/cutover.md",
    "escalation-board.png": "playbooks/release/images/escalation-board.png",
    "vendor-cutover.pdf": "reports/vendor-cutover.pdf",
    "preview-board.png": "boards/preview-board.png",
}
CONTENT_TYPES = {
    "cutover.md": "text/markdown",
    "escalation-board.png": "image/png",
    "vendor-cutover.pdf": "application/pdf",
    "preview-board.png": "image/png",
}
QUESTION_CASES = [
    {
        "case_id": "mixed-markdown-rollback-owner",
        "question": "Who gives the final rollback approval after the deployment coordinator summarizes the evidence?",
        "expected_terms": ["platform duty lead"],
        "preview_terms": ["platform duty lead"],
        "expected_source_count": 1,
        "expected_doc": "cutover.md",
        "strict_zero_evidence": False,
    },
    {
        "case_id": "mixed-pdf-checklist-signer",
        "question": "Who signs the cutover checklist before traffic moves to the vendor stack?",
        "expected_terms": ["customer success lead"],
        "preview_terms": ["customer success lead"],
        "expected_source_count": 1,
        "expected_doc": "vendor-cutover.pdf",
        "strict_zero_evidence": False,
    },
    {
        "case_id": "mixed-embedded-image-boundary",
        "question": "According to the escalation board image, what is the authorization boundary?",
        "expected_terms": ["knowledge base", "authorization boundary"],
        "preview_terms": ["authorization boundary"],
        "expected_source_count": 1,
        "expected_doc": "escalation-board.png",
        "strict_zero_evidence": False,
    },
    {
        "case_id": "mixed-standalone-image-preview-fields",
        "question": "Which two fields must every evidence preview include?",
        "expected_terms": ["doc_id", "preview_locator"],
        "preview_terms": ["doc_id", "preview_locator"],
        "expected_source_count": 1,
        "expected_doc": "preview-board.png",
        "strict_zero_evidence": False,
    },
    {
        "case_id": "mixed-no-evidence-refusal",
        "question": "What is the GPU memory requirement for the mobile build?",
        "expected_terms": ["no confirmable information is available"],
        "preview_terms": [],
        "expected_source_count": 0,
        "expected_doc": None,
        "strict_zero_evidence": True,
    },
]


def _sha256_bytes(payload: bytes) -> str:
    """??????? SHA256??????????????"""
    return hashlib.sha256(payload).hexdigest()



def _pick_font(size: int = 30) -> ImageFont.ImageFont:
    """?????? TrueType ????????????? OCR?"""
    for candidate in FONT_CANDIDATES:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()



def _parse_args() -> argparse.Namespace:
    """????????"""
    parser = argparse.ArgumentParser(description="???????????????? roundtrip?")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="?? API ??")
    parser.add_argument("--kb-id", default=None, help="?????????? ID")
    parser.add_argument(
        "--workspace-dir",
        default=str(Path("temp") / "diag-mixed-batch"),
        help="????????????",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="HTTP ???????")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE, help="?? chunk_size")
    parser.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP, help="?? chunk_overlap")
    parser.add_argument("--output-path", default=None, help="???? JSON ??? UTF-8 ??")
    return parser.parse_args()



def _request_json(method: str, url: str, *, timeout: float, **kwargs: Any) -> dict[str, Any]:
    """?? HTTP ????? JSON ???"""
    response = requests.request(method, url, timeout=timeout, **kwargs)
    response.raise_for_status()
    return response.json()



def _ensure_kb(base_url: str, kb_id: str, timeout: float) -> dict[str, Any]:
    """??????????????????"""
    response = requests.post(
        base_url.rstrip("/") + "/api/kb",
        json={"kb_id": kb_id, "kb_name": "Mixed Batch Diagnostic"},
        timeout=timeout,
    )
    if response.status_code == 200:
        return response.json()
    if response.status_code == 409:
        return {"code": 409, "message": "kb_exists", "data": {"kb_id": kb_id}}
    response.raise_for_status()
    return response.json()



def _create_text_image(path: Path, lines: list[str]) -> dict[str, Any]:
    """??????????????? OCR ????"""
    font = _pick_font(size=30)
    image = Image.new("RGB", (1440, 900), color="white")
    draw = ImageDraw.Draw(image)
    y = 70
    for line in lines:
        draw.text((70, y), line, fill="black", font=font)
        y += 120
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    payload = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "sha256": _sha256_bytes(payload),
        "size": len(payload),
        "text_preview": "\n".join(lines),
    }



def _create_text_pdf(path: Path, text: str) -> dict[str, Any]:
    """??????? PDF ???"""
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(fitz.Rect(48, 48, 560, 780), text)
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(path)
    document.close()
    payload = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "sha256": _sha256_bytes(payload),
        "size": len(payload),
        "text_preview": text,
    }



def _create_workspace(base_dir: Path) -> dict[str, dict[str, Any]]:
    """??????????????????????"""
    source_dir = base_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_info: dict[str, dict[str, Any]] = {}

    markdown_path = source_dir / RELATIVE_PATHS["cutover.md"]
    markdown_text = (
        "# Friday release cutover\n\n"
        "The Friday release cutover note explains who can approve rollback decisions.\n"
        "The platform duty lead gives the final rollback approval after the deployment coordinator summarizes the evidence.\n"
        "The team also keeps an escalation board image next to the runbook for scope reminders.\n\n"
        "![Escalation board](./images/escalation-board.png)\n"
    )
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown_text, encoding="utf-8", newline="\n")
    markdown_payload = markdown_path.read_bytes()
    source_info["cutover.md"] = {
        "path": str(markdown_path.resolve()),
        "sha256": _sha256_bytes(markdown_payload),
        "size": len(markdown_payload),
        "text_preview": markdown_text,
    }

    source_info["escalation-board.png"] = _create_text_image(
        source_dir / RELATIVE_PATHS["escalation-board.png"],
        [
            "Escalation board reminder",
            "Knowledge Base is the authorization boundary",
            "Folder remains organization only",
        ],
    )
    source_info["vendor-cutover.pdf"] = _create_text_pdf(
        source_dir / RELATIVE_PATHS["vendor-cutover.pdf"],
        (
            "Vendor cutover checklist. "
            "The customer success lead signs the cutover checklist before traffic moves to the vendor stack. "
            "The duty SRE confirms rollback readiness afterwards."
        ),
    )
    source_info["preview-board.png"] = _create_text_image(
        source_dir / RELATIVE_PATHS["preview-board.png"],
        [
            "Evidence preview checklist",
            "Every evidence preview must include doc_id and preview_locator",
        ],
    )
    return source_info



def _import_batch(
    base_url: str,
    kb_id: str,
    source_info: dict[str, dict[str, Any]],
    timeout: float,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> dict[str, Any]:
    """?????????????????"""
    handles = []
    files = []
    data: list[tuple[str, str]] = [
        ("kb_id", kb_id),
        ("chunk_size", str(chunk_size)),
        ("chunk_overlap", str(chunk_overlap)),
        ("import_mode", "preserve_tree"),
    ]
    try:
        for name in IMPORT_ORDER:
            path = Path(source_info[name]["path"])
            handle = path.open("rb")
            handles.append(handle)
            files.append(("files", (name, handle, CONTENT_TYPES[name])))
            data.append(("relative_paths", RELATIVE_PATHS[name]))

        response = requests.post(
            base_url.rstrip("/") + "/api/kb/file/import",
            files=files,
            data=data,
            timeout=timeout,
        )
    finally:
        for handle in handles:
            handle.close()

    response.raise_for_status()
    return response.json()



def _list_assets(base_url: str, kb_id: str, timeout: float) -> dict[str, Any]:
    """??????????????"""
    return _request_json(
        "GET",
        base_url.rstrip("/") + "/api/kb/assets",
        timeout=timeout,
        params={"kb_id": kb_id},
    )



def _preview(base_url: str, kb_id: str, evidence_id: str, timeout: float) -> dict[str, Any]:
    """?? evidence_id ?????????"""
    return _request_json(
        "POST",
        base_url.rstrip("/") + "/api/kb/preview",
        timeout=timeout,
        json={"kb_id": kb_id, "evidence_id": evidence_id},
    )



def _contains_all(text: str, terms: list[str]) -> bool:
    """??????????????"""
    lowered = (text or "").lower()
    return all(term.lower() in lowered for term in terms)



def _pick_doc_label(source: dict[str, Any], evidence: dict[str, Any]) -> str:
    """??? source / evidence ????????????"""
    candidates = [
        source.get("file"),
        source.get("title"),
        source.get("source"),
        evidence.get("title"),
        evidence.get("source"),
    ]
    return " | ".join(str(item) for item in candidates if isinstance(item, str) and item.strip())



def _matches_expected_doc(expected_doc: str | None, sources: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> bool:
    """???? source / evidence ?????????"""
    if not expected_doc:
        return True
    expected = expected_doc.lower()
    for source_item in sources:
        if expected in _pick_doc_label(source_item, {}).lower():
            return True
    for evidence_item in evidence:
        if expected in _pick_doc_label({}, evidence_item).lower():
            return True
    return False



def _answer_is_refusal_like(answer: str) -> bool:
    """?????????????????????????"""
    lowered = (answer or "").lower()
    refusal_markers = [
        "no confirmable information is available",
        "does not mention",
        "cannot be determined",
        "insufficient information",
        "not specified",
    ]
    return any(marker in lowered for marker in refusal_markers)



def _run_question_case(base_url: str, kb_id: str, case: dict[str, Any], timeout: float) -> dict[str, Any]:
    """?????? case???? answer/source/evidence/preview ???"""
    response = _request_json(
        "POST",
        base_url.rstrip("/") + "/api/chat/query",
        timeout=timeout,
        json={"question": case["question"], "kb_ids": [kb_id]},
    )
    payload = response.get("data", {})
    answer = str(payload.get("answer") or "")
    sources = list(payload.get("sources") or [])
    evidence = list(payload.get("evidence") or [])
    first_source = sources[0] if sources else {}
    first_evidence = evidence[0] if evidence else {}

    preview_payload = None
    if first_evidence.get("id"):
        preview_payload = _preview(base_url, kb_id, str(first_evidence["id"]), timeout).get("data")

    checks = {
        "scope_echo_ok": (
            payload.get("requested_scope_type") == "single_kb"
            and payload.get("requested_kb_ids") == [kb_id]
            and payload.get("effective_scope_type") == "single_kb"
            and payload.get("effective_kb_ids") == [kb_id]
            and payload.get("is_default_deny_applied") is False
            and payload.get("isolation_level") == "physical_isolated"
        ),
        "answer_has_expected_terms": _contains_all(answer, list(case["expected_terms"])),
        "answer_is_refusal_like": True,
        "source_count_match": len(sources) == int(case["expected_source_count"]),
        "evidence_count_match": len(evidence) == int(case["expected_source_count"]),
        "source_count_nonzero": len(sources) >= 1,
        "evidence_count_nonzero": len(evidence) >= 1,
        "evidence_fields_present": True,
        "source_doc_match": True,
        "preview_has_expected_terms": True,
        "strict_zero_evidence_contract": True,
    }

    if int(case["expected_source_count"]) > 0:
        checks["evidence_fields_present"] = bool(first_evidence.get("doc_id")) and isinstance(
            first_evidence.get("preview_locator"),
            dict,
        )
        checks["source_doc_match"] = _matches_expected_doc(case.get("expected_doc"), sources, evidence)
        checks["preview_has_expected_terms"] = _contains_all(
            str((preview_payload or {}).get("excerpt") or ""),
            list(case["preview_terms"]),
        )
        checks["strict_zero_evidence_contract"] = True
    else:
        checks["answer_is_refusal_like"] = _answer_is_refusal_like(answer)
        checks["answer_has_expected_terms"] = checks["answer_has_expected_terms"] or checks["answer_is_refusal_like"]
        checks["source_count_nonzero"] = len(sources) == 0
        checks["evidence_count_nonzero"] = len(evidence) == 0
        checks["evidence_fields_present"] = len(evidence) == 0
        checks["source_doc_match"] = len(sources) == 0
        checks["preview_has_expected_terms"] = preview_payload is None
        checks["strict_zero_evidence_contract"] = len(sources) == 0 and len(evidence) == 0 and preview_payload is None

    return {
        "case_id": case["case_id"],
        "question": case["question"],
        "expected_terms": list(case["expected_terms"]),
        "expected_source_count": int(case["expected_source_count"]),
        "expected_doc": case.get("expected_doc"),
        "checks": checks,
        "answer": answer,
        "sources": sources,
        "evidence": evidence,
        "preview": preview_payload,
    }



def _summarize_assets(items: list[dict[str, Any]]) -> dict[str, Any]:
    """? embedded / standalone ?????????"""
    by_role: dict[str, list[dict[str, Any]]] = {"embedded": [], "standalone": []}
    for item in items:
        role = str(item.get("asset_role") or "unknown")
        by_role.setdefault(role, []).append(item)
    return {
        "total": len(items),
        "embedded_count": len(by_role.get("embedded", [])),
        "standalone_count": len(by_role.get("standalone", [])),
        "items": items,
    }



def _emit_report(report: dict[str, Any], output_path: str | None) -> None:
    """?? JSON ????????????? UTF-8 ???"""
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
    print(payload)



def main() -> int:
    """????????? JSON ???"""
    args = _parse_args()
    base_url = args.base_url.rstrip("/")
    kb_id = args.kb_id or f"diag-mixed-batch-{int(time.time())}"
    workspace_dir = Path(args.workspace_dir)

    health = wait_for_runtime_ready(base_url, timeout=args.timeout, require_ocr=True)
    source_info = _create_workspace(workspace_dir)
    kb_create = _ensure_kb(base_url, kb_id, args.timeout)
    import_resp = _import_batch(
        base_url,
        kb_id,
        source_info,
        args.timeout,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    assets_resp = _list_assets(base_url, kb_id, args.timeout)
    case_reports = [_run_question_case(base_url, kb_id, case, args.timeout) for case in QUESTION_CASES]

    saved_files = {}
    all_saved_hash_match = True
    for name in IMPORT_ORDER:
        saved_path = Path("data") / kb_id / Path(RELATIVE_PATHS[name])
        saved_payload = saved_path.read_bytes()
        source_hash = str(source_info[name]["sha256"])
        saved_hash = _sha256_bytes(saved_payload)
        matches_source = saved_hash == source_hash
        saved_files[name] = {
            "path": str(saved_path.resolve()),
            "sha256": saved_hash,
            "size": len(saved_payload),
            "matches_source": matches_source,
        }
        all_saved_hash_match = all_saved_hash_match and matches_source

    import_data = import_resp.get("data", {})
    diagnostics = import_data.get("diagnostics", {})
    asset_items = list(assets_resp.get("data", {}).get("items") or [])
    asset_summary = _summarize_assets(asset_items)
    import_checks = {
        "saved_hashes_match": all_saved_hash_match,
        "success_empty_counts_expected": (
            import_data.get("success_count") == 3
            and import_data.get("failed_count") == 0
            and import_data.get("empty_count") == 1
        ),
        "embedded_shadowing_expected": (
            diagnostics.get("embedded_asset_ready_count") == 1
            and diagnostics.get("skip_standalone_asset_count") == 1
            and diagnostics.get("empty_reason_counts", {}).get("shadowed_by_embedded_asset") == 1
        ),
        "ocr_and_asset_counts_expected": (
            diagnostics.get("ocr_success_count") == 1
            and diagnostics.get("embedded_ocr_success_count") == 1
            and diagnostics.get("indexed_from_ocr_count") == 1
            and diagnostics.get("embedded_indexed_from_ocr_count") == 1
            and diagnostics.get("asset_registered_count") == 2
        ),
        "asset_list_expected": (
            asset_summary["total"] == 2
            and asset_summary["embedded_count"] == 1
            and asset_summary["standalone_count"] == 1
        ),
    }

    positive_cases = [item for item in case_reports if not next(case for case in QUESTION_CASES if case["case_id"] == item["case_id"])["strict_zero_evidence"]]
    no_evidence_case = next(item for item in case_reports if next(case for case in QUESTION_CASES if case["case_id"] == item["case_id"])["strict_zero_evidence"])
    qa_gates = {
        "positive_cases_passed": all(
            item["checks"]["scope_echo_ok"]
            and item["checks"]["answer_has_expected_terms"]
            and item["checks"]["source_count_nonzero"]
            and item["checks"]["evidence_count_nonzero"]
            and item["checks"]["evidence_fields_present"]
            and item["checks"]["source_doc_match"]
            and item["checks"]["preview_has_expected_terms"]
            for item in positive_cases
        ),
        "strict_no_evidence_contract_passed": no_evidence_case["checks"]["strict_zero_evidence_contract"],
        "no_evidence_answer_refusal_like": no_evidence_case["checks"]["answer_is_refusal_like"],
    }
    run_gates = {
        "core_ingestion_passed": all(import_checks.values()),
        "core_positive_qa_passed": qa_gates["positive_cases_passed"],
        "strict_no_evidence_contract_passed": qa_gates["strict_no_evidence_contract_passed"],
        "no_evidence_answer_refusal_like": qa_gates["no_evidence_answer_refusal_like"],
    }
    run_gates["run_passed"] = all(run_gates.values())

    report = {
        "base_url": base_url,
        "kb_id": kb_id,
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
        "kb_create": kb_create,
        "health": health.get("data", health),
        "source_files": source_info,
        "saved_files": saved_files,
        "import_checks": import_checks,
        "qa_gates": qa_gates,
        "run_gates": run_gates,
        "import_summary": import_data,
        "assets": asset_summary,
        "qa_cases": case_reports,
    }
    _emit_report(report, args.output_path)
    return 0 if run_gates["run_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
