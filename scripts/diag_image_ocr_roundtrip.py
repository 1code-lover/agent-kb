"""真实运行时图片 OCR 导入/问答回归诊断脚本。"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont

from server.utils.font_fallbacks import OCR_FONT_CANDIDATES, load_first_available_font

try:
    from scripts.diag_roundtrip_support import DEFAULT_LOCAL_API_PORT, resolve_api_base_url, wait_for_runtime_ready
except ModuleNotFoundError:
    from diag_roundtrip_support import DEFAULT_LOCAL_API_PORT, resolve_api_base_url, wait_for_runtime_ready

DEFAULT_BASE_URL = f"http://127.0.0.1:{DEFAULT_LOCAL_API_PORT}"
DEFAULT_RELATIVE_PATH = "images/diag-ocr.png"
IMAGE_LINES = [
    "Image OCR diagnostic",
    "Folder is organization only",
    "Knowledge Base is the authorization boundary",
    "Preview should resolve to OCR chunk",
]
QUESTION = "In the OCR diagnostic image, what is the authorization boundary?"
EXPECTED_TERMS = ["knowledge base", "authorization boundary"]
FONT_CANDIDATES = OCR_FONT_CANDIDATES


def _sha256_bytes(payload: bytes) -> str:
    """计算字节内容的 SHA256。"""
    return hashlib.sha256(payload).hexdigest()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """读取命令行参数。"""
    parser = argparse.ArgumentParser(description="诊断图片 OCR 真实导入与问答链路")
    parser.add_argument(
        "--base-url",
        default=resolve_api_base_url(),
        help="本地 API 地址；优先读取 KB_API_BASE_URL，未设置时回退到 KB_API_PORT（默认 18080）",
    )
    parser.add_argument("--kb-id", default=None, help="可选；指定知识库 ID")
    parser.add_argument(
        "--source-path",
        default=str(Path("temp") / "diag-ocr.png"),
        help="本地临时诊断图片路径",
    )
    parser.add_argument("--relative-path", default=DEFAULT_RELATIVE_PATH, help="导入到知识库内的相对路径")
    parser.add_argument("--timeout", type=float, default=240.0, help="HTTP 超时时间（秒）")
    parser.add_argument("--output-path", default=None, help="write JSON report directly to file in UTF-8")
    return parser.parse_args(argv)


def _request_json(method: str, url: str, *, timeout: float, **kwargs: Any) -> dict[str, Any]:
    """发起 HTTP 请求并返回 JSON 结果。"""
    response = requests.request(method, url, timeout=timeout, **kwargs)
    response.raise_for_status()
    return response.json()


def _ensure_kb(base_url: str, kb_id: str, timeout: float) -> dict[str, Any]:
    """创建诊断知识库；若已存在则直接复用。"""
    response = requests.post(
        base_url.rstrip("/") + "/api/kb",
        json={"kb_id": kb_id, "kb_name": "Image OCR Diagnostic"},
        timeout=timeout,
    )
    if response.status_code == 200:
        return response.json()
    if response.status_code == 409:
        return {"code": 409, "message": "kb_exists", "data": {"kb_id": kb_id}}
    response.raise_for_status()
    return response.json()


def _pick_font(size: int = 30) -> tuple[ImageFont.ImageFont, str]:
    """选择可用字体，若都不存在则回退到默认字体。"""
    return load_first_available_font(size=size, candidates=FONT_CANDIDATES)


def _create_image(path: Path) -> dict[str, Any]:
    """创建内含 OCR 文本的诊断图片。"""
    font, font_label = _pick_font(size=30)
    image = Image.new("RGB", (1280, 720), color="white")
    draw = ImageDraw.Draw(image)
    y = 60
    for line in IMAGE_LINES:
        draw.text((60, y), line, fill="black", font=font)
        y += 110
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    payload = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "sha256": _sha256_bytes(payload),
        "size": len(payload),
        "text_preview": "\n".join(IMAGE_LINES),
        "font": font_label,
    }


def _import_image(base_url: str, kb_id: str, source_path: Path, relative_path: str, timeout: float) -> dict[str, Any]:
    """通过真实文件上传接口导入图片并触发 OCR。"""
    with source_path.open("rb") as handle:
        response = requests.post(
            base_url.rstrip("/") + "/api/kb/file/import",
            files={"files": (source_path.name, handle, "image/png")},
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
    """调用真实问答接口验证 OCR 问答。"""
    return _request_json(
        "POST",
        base_url.rstrip("/") + "/api/chat/query",
        timeout=timeout,
        json={"question": QUESTION, "kb_ids": [kb_id]},
    )


def _preview(base_url: str, kb_id: str, evidence_id: str, timeout: float) -> dict[str, Any]:
    """根据 evidence_id 读取 preview。"""
    return _request_json(
        "POST",
        base_url.rstrip("/") + "/api/kb/preview",
        timeout=timeout,
        json={"kb_id": kb_id, "evidence_id": evidence_id},
    )


def _contains_all(text: str, terms: list[str]) -> bool:
    """判断文本是否包含所有关键词。"""
    lowered = (text or "").lower()
    return all(term.lower() in lowered for term in terms)


def _emit_report(report: dict[str, Any], output_path: str | None) -> None:
    """输出 JSON 报告，并在需要时直接落盘为 UTF-8 文件。"""
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
    print(payload)


def main() -> int:
    """执行完整诊断并输出 JSON 报告。"""
    args = _parse_args()
    base_url = args.base_url.rstrip("/")
    kb_id = args.kb_id or f"diag-image-ocr-{int(time.time())}"
    source_path = Path(args.source_path)

    health = wait_for_runtime_ready(base_url, timeout=args.timeout, require_ocr=True)
    source_info = _create_image(source_path)
    _ensure_kb(base_url, kb_id, args.timeout)
    import_resp = _import_image(base_url, kb_id, source_path, args.relative_path, args.timeout)

    saved_path = Path("data") / kb_id / Path(args.relative_path)
    saved_payload = saved_path.read_bytes()

    chat_resp = _chat_query(base_url, kb_id, args.timeout)
    chat_payload = chat_resp.get("data", {})
    answer = str(chat_payload.get("answer") or "")
    first_source = (chat_payload.get("sources") or [{}])[0]
    first_evidence = (chat_payload.get("evidence") or [{}])[0]
    preview_payload = None
    if first_evidence.get("id"):
        preview_payload = _preview(base_url, kb_id, str(first_evidence["id"]), args.timeout).get("data")

    report = {
        "base_url": base_url,
        "kb_id": kb_id,
        "question": QUESTION,
        "health": health.get("data", health),
        "source": source_info,
        "saved": {
            "path": str(saved_path.resolve()),
            "sha256": _sha256_bytes(saved_payload),
            "size": len(saved_payload),
        },
        "checks": {
            "source_saved_hash_match": source_info["sha256"] == _sha256_bytes(saved_payload),
            "chat_answer_has_expected_terms": _contains_all(answer, EXPECTED_TERMS),
            "chat_source_has_expected_terms": _contains_all(str(first_source.get("text") or ""), ["knowledge base"]),
            "chat_evidence_has_expected_terms": _contains_all(str(first_evidence.get("excerpt") or ""), ["knowledge base"]),
            "preview_has_expected_terms": _contains_all(str((preview_payload or {}).get("excerpt") or ""), ["knowledge base"]),
            "ocr_attempted": bool(import_resp.get("data", {}).get("file_results", [{}])[0].get("diagnostics", {}).get("ocr_attempted")),
            "indexed_from_ocr": bool(import_resp.get("data", {}).get("file_results", [{}])[0].get("diagnostics", {}).get("indexed_from_ocr")),
        },
        "import_summary": import_resp.get("data", {}),
        "chat_summary": {
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
        },
    }
    _emit_report(report, args.output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
