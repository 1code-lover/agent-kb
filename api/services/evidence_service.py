"""证据归一化与最小预览契约辅助。"""

from __future__ import annotations

import base64
import json
from typing import Any, Sequence

from server.kb_errors import KBValidationError

_MAX_EXCERPT_CHARS = 600


def _trim_excerpt(text: Any) -> str:
    value = str(text or "")
    return value[:_MAX_EXCERPT_CHARS]


def _extract_doc_id(content_node: Any, metadata: dict[str, Any]) -> str | None:
    """尽量从节点对象或 metadata 中恢复 ref_doc_id。"""
    candidates = (
        metadata.get("doc_id"),
        metadata.get("ref_doc_id"),
        getattr(content_node, "ref_doc_id", None),
        getattr(content_node, "doc_id", None),
    )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def build_preview_locator(metadata: dict[str, Any], content_node: Any | None = None) -> dict[str, Any] | None:
    """生成最小 preview locator，P0 先覆盖页码与节点定位。"""
    locator: dict[str, Any] = {}

    page = metadata.get("page_label") or metadata.get("page")
    if page not in (None, "", "N/A"):
        locator["page"] = str(page)

    node_id = getattr(content_node, "node_id", None) if content_node is not None else None
    if isinstance(node_id, str) and node_id.strip():
        locator["node_id"] = node_id

    return locator or None


def build_evidence_id(
    *,
    kb_id: str,
    doc_id: str | None,
    preview_locator: dict[str, Any] | None,
    fallback_index: int,
) -> str:
    """构造可反解的 evidence_id；无 doc_id 时退回顺序号。"""
    if not doc_id:
        return f"ev-{fallback_index}"

    payload = {
        "kb_id": kb_id or "default",
        "doc_id": doc_id,
        "preview_locator": preview_locator or None,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    return "ev:" + encoded.rstrip("=")


def parse_evidence_id(evidence_id: str) -> dict[str, Any]:
    """解析 evidence_id，失败时要求调用方改用 doc_id。"""
    if not isinstance(evidence_id, str) or not evidence_id.startswith("ev:"):
        raise KBValidationError("证据标识无法解析，请改用 doc_id 或重新发起问答")

    encoded = evidence_id[3:]
    padding = "=" * (-len(encoded) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode((encoded + padding).encode("ascii")).decode("utf-8"))
    except Exception as exc:
        raise KBValidationError("证据标识无法解析，请改用 doc_id 或重新发起问答") from exc

    if not isinstance(payload, dict) or not payload.get("doc_id"):
        raise KBValidationError("证据标识缺少 doc_id，请改用 doc_id 直接预览")
    return payload


def normalize_source_nodes(response: Any) -> list[dict[str, Any]]:
    """把 query response.source_nodes 归一成兼容 sources 结构。"""
    sources: list[dict[str, Any]] = []
    for index, node in enumerate(getattr(response, "source_nodes", []) or [], start=1):
        content_node = getattr(node, "node", None)
        metadata = getattr(content_node, "metadata", {}) if content_node is not None else {}
        file_name = metadata.get("file_name") or metadata.get("title") or "N/A"
        doc_id = _extract_doc_id(content_node, metadata)
        preview_locator = build_preview_locator(metadata, content_node)
        sources.append(
            {
                "id": build_evidence_id(
                    kb_id=metadata.get("kb_id", "default"),
                    doc_id=doc_id,
                    preview_locator=preview_locator,
                    fallback_index=index,
                ),
                "file": file_name,
                "page": metadata.get("page_label", "N/A"),
                "score": getattr(node, "score", None),
                "text": getattr(content_node, "text", "") if content_node is not None else "",
                "kb_id": metadata.get("kb_id", "default"),
                "doc_id": doc_id,
                "preview_locator": preview_locator,
            }
        )
    return sources


def normalize_evidence(sources: Sequence[dict[str, Any]] | None, receipt_id: str | None = None) -> list[dict[str, Any]]:
    """把 sources 映射成正式 evidence 对象。"""
    evidence: list[dict[str, Any]] = []
    for index, source in enumerate(sources or [], start=1):
        if not isinstance(source, dict):
            source = dict(source)
        title = source.get("file") or source.get("title") or "Knowledge Source"
        locator = source.get("preview_locator") if isinstance(source.get("preview_locator"), dict) else None
        doc_id = source.get("doc_id") if isinstance(source.get("doc_id"), str) else None
        evidence.append(
            {
                "id": source.get("id")
                or build_evidence_id(
                    kb_id=source.get("kb_id", "default"),
                    doc_id=doc_id,
                    preview_locator=locator,
                    fallback_index=index,
                ),
                "title": title,
                "source": source.get("source") or title,
                "page": source.get("page"),
                "score": source.get("score"),
                "excerpt": _trim_excerpt(source.get("text") or source.get("excerpt")),
                "receipt_id": receipt_id if receipt_id is not None else source.get("receipt_id"),
                "kb_id": source.get("kb_id", "default"),
                "doc_id": doc_id,
                "preview_locator": locator,
            }
        )
    return evidence
