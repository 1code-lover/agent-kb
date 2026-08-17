"""知识库 Folder 服务。"""

from __future__ import annotations

from typing import Any

from api.runtime import runtime_state
from server.folder_registry import KBFolderRegistry, resolve_relative_path_from_metadata
from server.utils.file import validate_kb_id

_folder_registry: KBFolderRegistry | None = None


def _get_folder_registry() -> KBFolderRegistry:
    global _folder_registry
    if _folder_registry is None:
        _folder_registry = KBFolderRegistry()
    return _folder_registry


def _normalize_doc_kb_id(metadata: dict[str, Any]) -> str:
    return metadata.get("kb_id") or "default"


def list_folders(kb_id: str) -> list[dict[str, Any]]:
    """列出指定知识库的 folder 节点，并按当前文档集合刷新 registry。"""
    from api.services import kb_service

    safe_kb_id = validate_kb_id(kb_id)
    kb_service._ensure_kb_active(safe_kb_id)

    manager = runtime_state.get_index_manager(safe_kb_id)
    doc_store = manager.storage_context.docstore
    ref_doc_info = doc_store.get_all_ref_doc_info() if len(doc_store.docs) > 0 else {}
    relative_paths: list[str] = []
    for ref_doc in ref_doc_info.values():
        metadata = ref_doc.metadata
        if _normalize_doc_kb_id(metadata) != safe_kb_id:
            continue
        relative_path = resolve_relative_path_from_metadata(metadata, safe_kb_id)
        if relative_path is not None:
            relative_paths.append(relative_path)

    registry = _get_folder_registry()
    registry.replace_from_relative_paths(safe_kb_id, relative_paths)
    return registry.list_folders(safe_kb_id)
