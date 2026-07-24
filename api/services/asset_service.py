"""知识库资产服务。"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from server.asset_registry import KBAssetRegistry
from server.kb_errors import KBNotFoundError, KBUnavailableError, KBValidationError
from server.kb_registry import KBRegistry
from server.utils.file import get_kb_data_dir, validate_kb_id

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}
_MARKDOWN_SUFFIXES = {".md", ".markdown", ".mdown", ".mdx"}

_registry: KBAssetRegistry | None = None


def _get_registry() -> KBAssetRegistry:
    global _registry
    if _registry is None:
        _registry = KBAssetRegistry()
    return _registry


def _get_kb_registry() -> KBRegistry:
    return KBRegistry(storage_path=Path("storage") / "kb_registry.json")


def _ensure_kb_active(kb_id: str) -> str:
    safe_kb_id = validate_kb_id(kb_id)
    kb = _get_kb_registry().get_kb(safe_kb_id)
    if kb is None:
        raise KBNotFoundError(f"知识库不存在: {safe_kb_id}")
    if kb.get("status", "active") != "active":
        raise KBUnavailableError(f"知识库不可用: {safe_kb_id}")
    return safe_kb_id


def _is_markdown_result(file_result: dict[str, Any]) -> bool:
    relative_path = file_result.get("relative_path")
    if isinstance(relative_path, str) and Path(relative_path).suffix.lower() in _MARKDOWN_SUFFIXES:
        return True
    content_type = str(file_result.get("type") or "").lower()
    return content_type.startswith("text/markdown")


def _is_image_result(file_result: dict[str, Any]) -> bool:
    relative_path = file_result.get("relative_path")
    if isinstance(relative_path, str) and Path(relative_path).suffix.lower() in _IMAGE_SUFFIXES:
        return True
    content_type = str(file_result.get("type") or "").lower()
    return content_type.startswith("image/")


def _build_standalone_asset_id(kb_id: str, relative_path: str | None, path: str | None, filename: str | None) -> str:
    raw = relative_path or path or filename or "standalone"
    digest = hashlib.sha1(f"{kb_id}:standalone:{raw}".encode("utf-8")).hexdigest()[:16]
    return f"asset-standalone-{digest}"


def _build_standalone_asset(kb_id: str, file_result: dict[str, Any]) -> dict[str, Any] | None:
    if not _is_image_result(file_result):
        return None

    relative_path = file_result.get("relative_path")
    path = file_result.get("path")
    filename = file_result.get("name")
    if not isinstance(path, str) or not path:
        return None

    return {
        "asset_id": _build_standalone_asset_id(kb_id, relative_path, path, filename),
        "kb_id": kb_id,
        "source_doc_id": None,
        "source_doc_path": path,
        "source_doc_relative_path": relative_path,
        "asset_type": "image",
        "asset_role": "standalone",
        "title": Path(relative_path or filename or path).name,
        "path": path,
        "relative_path": relative_path,
        "mime_type": file_result.get("type") or "application/octet-stream",
        "locator": None,
        "status": "active",
    }


def _build_embedded_asset(kb_id: str, source_file: dict[str, Any], embedded_item: dict[str, Any]) -> dict[str, Any] | None:
    if embedded_item.get("status") == "invalid":
        return None

    source_doc_path = source_file.get("path")
    source_doc_relative_path = source_file.get("relative_path")
    resolved_relative_path = embedded_item.get("resolved_relative_path")
    if not isinstance(source_doc_path, str) or not source_doc_path:
        return None
    if not isinstance(source_doc_relative_path, str) or not source_doc_relative_path:
        return None
    if not isinstance(resolved_relative_path, str) or not resolved_relative_path:
        return None

    asset_path = str((get_kb_data_dir(kb_id, create=True) / resolved_relative_path).resolve())
    referenced_path = embedded_item.get("referenced_path")
    title_seed = resolved_relative_path or referenced_path or embedded_item.get("asset_id") or "embedded-asset"
    return {
        "asset_id": embedded_item.get("asset_id"),
        "kb_id": kb_id,
        "source_doc_id": None,
        "source_doc_path": source_doc_path,
        "source_doc_relative_path": source_doc_relative_path,
        "asset_type": embedded_item.get("asset_type") or "image",
        "asset_role": embedded_item.get("asset_role") or "embedded",
        "title": Path(title_seed).name,
        "path": asset_path,
        "relative_path": resolved_relative_path,
        "mime_type": embedded_item.get("mime_type") or "application/octet-stream",
        "locator": {
            "referenced_path": referenced_path,
            "occurrence_index": embedded_item.get("occurrence_index"),
            "source_type": embedded_item.get("source_type"),
        },
        "status": "active" if embedded_item.get("status") == "ready" else "missing",
    }


def _resolve_asset_status(asset: dict[str, Any]) -> str:
    asset_path = asset.get("path")
    source_doc_path = asset.get("source_doc_path")
    role = asset.get("asset_role")

    if role == "embedded":
        if isinstance(source_doc_path, str) and source_doc_path and not Path(source_doc_path).exists():
            return "orphaned"
        if not isinstance(asset_path, str) or not asset_path or not Path(asset_path).exists():
            return "missing"
        return "active"

    if not isinstance(asset_path, str) or not asset_path or not Path(asset_path).exists():
        return "missing"
    return "active"


def _refresh_runtime_statuses(kb_id: str) -> list[dict[str, Any]]:
    safe_kb_id = _ensure_kb_active(kb_id)
    registry = _get_registry()
    items = registry.list_assets(safe_kb_id)
    refreshed: list[dict[str, Any]] = []
    changed = False

    for item in items:
        current = dict(item)
        status = _resolve_asset_status(current)
        if current.get("status") != status:
            current["status"] = status
            changed = True
        refreshed.append(current)

    if changed:
        registry.upsert_assets(safe_kb_id, refreshed)
        return registry.list_assets(safe_kb_id)
    return refreshed


def register_imported_assets(kb_id: str, file_results: list[dict[str, Any]]) -> dict[str, int]:
    """把导入回执中的独立图片与 embedded 图片注册为资产对象。"""
    safe_kb_id = validate_kb_id(kb_id)
    registry = _get_registry()

    standalone_assets: list[dict[str, Any]] = []
    embedded_assets: list[dict[str, Any]] = []
    embedded_source_docs: set[str] = set()

    for file_result in file_results:
        status = file_result.get("status")
        if status not in {"indexed", "empty"}:
            continue

        if _is_image_result(file_result):
            standalone_asset = _build_standalone_asset(safe_kb_id, file_result)
            if standalone_asset is not None:
                standalone_assets.append(standalone_asset)

        if _is_markdown_result(file_result):
            source_relative_path = file_result.get("relative_path")
            if isinstance(source_relative_path, str) and source_relative_path:
                embedded_source_docs.add(source_relative_path)
            for embedded_item in file_result.get("embedded_assets") or []:
                embedded_asset = _build_embedded_asset(safe_kb_id, file_result, embedded_item)
                if embedded_asset is not None:
                    embedded_assets.append(embedded_asset)

    if embedded_source_docs:
        registry.replace_embedded_assets(safe_kb_id, embedded_source_docs, embedded_assets)
    if standalone_assets:
        registry.upsert_assets(safe_kb_id, standalone_assets)

    return {
        "standalone_count": len(standalone_assets),
        "embedded_count": len(embedded_assets),
    }


def list_assets(kb_id: str) -> list[dict[str, Any]]:
    """列出指定知识库的全部资产。"""
    return _refresh_runtime_statuses(kb_id)


def get_asset_preview(kb_id: str, asset_id: str) -> dict[str, Any]:
    """返回单个资产的最小预览数据。"""
    safe_kb_id = _ensure_kb_active(kb_id)
    if not isinstance(asset_id, str) or not asset_id.strip():
        raise KBValidationError("asset_id 不能为空")

    for item in _refresh_runtime_statuses(safe_kb_id):
        if item.get("asset_id") == asset_id:
            return dict(item)
    raise KBNotFoundError(f"资产不存在: {asset_id}")


def delete_kb_assets(kb_id: str) -> None:
    """删除指定知识库的资产注册表文件。"""
    safe_kb_id = validate_kb_id(kb_id)
    _get_registry().delete_kb(safe_kb_id)
