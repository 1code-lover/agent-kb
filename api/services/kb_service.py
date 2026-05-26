"""知识库服务，封装文件/网页导入和列表、删除。"""

from __future__ import annotations

import os
from typing import Any

from api.runtime import runtime_state
from api.schemas import DeleteDocsRequest
from server.utils.file import get_save_dir


def import_files(files: list[Any], chunk_size: int, chunk_overlap: int) -> dict[str, Any]:
    """导入文件并构建索引。"""
    runtime_state.ensure_models_ready(require_llm=False)
    manager = runtime_state.get_index_manager()
    save_dir = get_save_dir()
    os.makedirs(save_dir, exist_ok=True)
    uploaded_files: list[dict[str, Any]] = []
    for file in files:
        target_path = os.path.join(save_dir, file.filename)
        with open(target_path, "wb") as buffer:
            buffer.write(file.file.read())
        uploaded_files.append({"name": file.filename, "type": file.content_type, "size": os.path.getsize(target_path)})

    nodes = manager.load_files(uploaded_files, chunk_size, chunk_overlap)
    return {"files": uploaded_files, "indexed_chunks": len(nodes or [])}


def import_urls(urls: list[str], chunk_size: int, chunk_overlap: int) -> dict[str, Any]:
    """导入网页并构建索引。"""
    runtime_state.ensure_models_ready(require_llm=False)
    manager = runtime_state.get_index_manager()
    nodes = manager.load_websites(urls, chunk_size, chunk_overlap)
    return {"urls": urls, "indexed_chunks": len(nodes or [])}


def list_docs() -> list[dict[str, Any]]:
    """列出知识库文档。"""
    manager = runtime_state.get_index_manager()
    doc_store = manager.storage_context.docstore
    ref_doc_info = doc_store.get_all_ref_doc_info() if len(doc_store.docs) > 0 else {}

    docs: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for ref_doc_id, ref_doc in ref_doc_info.items():
        metadata = ref_doc.metadata
        file_path = metadata.get("file_path")
        if file_path and file_path in seen_paths:
            continue
        path_or_url = file_path or metadata.get("url_source", "")
        docs.append(
            {
                "id": ref_doc_id,
                "name": metadata.get("file_name") or metadata.get("title", "N/A"),
                "path": path_or_url,
                "type": "file" if file_path else "url",
                "date": metadata.get("creation_date", ""),
            }
        )
        if file_path:
            seen_paths.add(file_path)
    return docs


def delete_docs(request: DeleteDocsRequest) -> dict[str, int]:
    """按 doc_id 或路径删除文档。"""
    manager = runtime_state.get_index_manager()
    runtime_state.ensure_index_loaded()
    doc_store = manager.storage_context.docstore
    ref_doc_info = doc_store.get_all_ref_doc_info() if len(doc_store.docs) > 0 else {}
    deleted = 0

    path_targets = set(request.paths)
    id_targets = set(request.doc_ids)
    for ref_doc_id, ref_doc in ref_doc_info.items():
        metadata = ref_doc.metadata
        path = metadata.get("file_path") or metadata.get("url_source")
        if ref_doc_id in id_targets or (path and path in path_targets):
            manager.delete_ref_doc(ref_doc_id)
            deleted += 1
    return {"deleted": deleted}
