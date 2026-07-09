"""知识库服务，封装 KB CRUD、文件/网页导入和文档管理。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from api.runtime import runtime_state
from api.schemas import DeleteDocsRequest
from server.kb_registry import KBRegistry
from server.utils.file import get_save_dir
from server.security.filename_sanitizer import FilenameSanitizer

# 文件大小限制（100MB）
MAX_FILE_SIZE = 100 * 1024 * 1024

# 全局 registry 实例
_registry: KBRegistry | None = None


def _get_registry() -> KBRegistry:
    global _registry
    if _registry is None:
        _registry = KBRegistry(storage_path=Path("storage/kb_registry.json"))
    return _registry


# ── KB CRUD ──

def create_kb(kb_id: str, kb_name: str) -> dict:
    """创建知识库"""
    return _get_registry().create_kb(kb_id, kb_name)


def list_kbs() -> list[dict]:
    """获取全部知识库列表"""
    return _get_registry().list_kbs()


def get_kb(kb_id: str) -> dict | None:
    """获取指定知识库"""
    return _get_registry().get_kb(kb_id)


def update_kb(kb_id: str, kb_name: str) -> dict:
    """更新知识库名称"""
    return _get_registry().update_kb(kb_id, kb_name)


def delete_kb(kb_id: str) -> bool:
    """删除知识库（含级联删除关联文档）"""
    return _get_registry().delete_kb(kb_id)


def import_files(files: list[Any], chunk_size: int, chunk_overlap: int, kb_id: str = "default") -> dict[str, Any]:
    """导入文件并构建索引（带文件名清理）。"""
    runtime_state.ensure_models_ready(require_llm=False)
    manager = runtime_state.get_index_manager()
    save_dir = get_save_dir()
    os.makedirs(save_dir, exist_ok=True)
    uploaded_files: list[dict[str, Any]] = []
    for file in files:
        # 1. 检查文件大小
        file_content = file.file.read()
        if len(file_content) > MAX_FILE_SIZE:
            raise ValueError(f"File too large: {len(file_content)} bytes (max: {MAX_FILE_SIZE})")
        file.file.seek(0)
        
        # 2. 清理文件名
        safe_filename = FilenameSanitizer.sanitize(file.filename)
        
        # 3. 生成唯一文件名（避免并发竞态条件）
        unique_filename = FilenameSanitizer.generate_unique_filename(safe_filename)
        target_path = os.path.join(save_dir, unique_filename)
        
        # 4. 写入文件
        with open(target_path, "wb") as buffer:
            buffer.write(file_content)
        uploaded_files.append({"name": unique_filename, "type": file.content_type, "size": len(file_content)})

    nodes = manager.load_files(uploaded_files, chunk_size, chunk_overlap, kb_id=kb_id)
    return {"files": uploaded_files, "indexed_chunks": len(nodes or []), "kb_id": kb_id}


def import_urls(urls: list[str], chunk_size: int, chunk_overlap: int, kb_id: str = "default") -> dict[str, Any]:
    """导入网页并构建索引。"""
    runtime_state.ensure_models_ready(require_llm=False)
    manager = runtime_state.get_index_manager()
    nodes = manager.load_websites(urls, chunk_size, chunk_overlap, kb_id=kb_id)
    return {"urls": urls, "indexed_chunks": len(nodes or []), "kb_id": kb_id}


def list_docs(kb_id: str | None = None) -> list[dict[str, Any]]:
    """列出知识库文档。

    Args:
        kb_id: 可选，按知识库 ID 过滤。不传则返回全部。
    """
    manager = runtime_state.get_index_manager()
    doc_store = manager.storage_context.docstore
    ref_doc_info = doc_store.get_all_ref_doc_info() if len(doc_store.docs) > 0 else {}

    docs: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for ref_doc_id, ref_doc in ref_doc_info.items():
        metadata = ref_doc.metadata
        # 按 kb_id 过滤
        if kb_id is not None and metadata.get("kb_id") is not None and metadata["kb_id"] != kb_id:
            continue
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
                "kb_id": metadata.get("kb_id", "default"),
            }
        )
        if file_path:
            seen_paths.add(file_path)
    return docs


def delete_docs(request: DeleteDocsRequest) -> dict[str, int]:
    """按 doc_id 或路径删除文档（可选限知识库范围）。"""
    manager = runtime_state.get_index_manager()
    runtime_state.ensure_index_loaded()
    doc_store = manager.storage_context.docstore
    ref_doc_info = doc_store.get_all_ref_doc_info() if len(doc_store.docs) > 0 else {}
    deleted = 0

    path_targets = set(request.paths)
    id_targets = set(request.doc_ids)
    for ref_doc_id, ref_doc in ref_doc_info.items():
        metadata = ref_doc.metadata
        # kb_id 范围限制：如果请求指定了 kb_id，只操作该知识库的文档
        if request.kb_id != "default":
            doc_kb_id = metadata.get("kb_id")
            if doc_kb_id is not None and doc_kb_id != request.kb_id:
                continue
        path = metadata.get("file_path") or metadata.get("url_source")
        if ref_doc_id in id_targets or (path and path in path_targets):
            manager.delete_ref_doc(ref_doc_id)
            deleted += 1
    return {"deleted": deleted}
