"""知识库服务：处理 KB CRUD、文件/网页导入和文档管理。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from api.runtime import runtime_state
from api.schemas import DeleteDocsRequest
from server.kb_errors import (
    KBConflictError,
    KBConsistencyError,
    KBNotFoundError,
    KBUnavailableError,
    KBValidationError,
)
from server.kb_registry import KBRegistry
from server.security.filename_sanitizer import FilenameSanitizer
from server.utils.file import ensure_path_within, get_data_root, get_kb_data_dir, validate_kb_id

# 上传文件大小上限：100MB。
MAX_FILE_SIZE = 100 * 1024 * 1024

# 延迟初始化 registry，便于测试替换工作目录。
_registry: KBRegistry | None = None


def _get_registry() -> KBRegistry:
    global _registry
    if _registry is None:
        _registry = KBRegistry(storage_path=Path("storage/kb_registry.json"))
    return _registry


def _registry_snapshot(registry: KBRegistry) -> list[dict]:
    """复制 registry 当前数据，用于失败回滚。"""
    return [dict(item) for item in registry.list_kbs()]


def _restore_registry(registry: KBRegistry, snapshot: list[dict]) -> None:
    """按快照恢复 registry。"""
    registry.replace_all(snapshot)


def _ensure_kb_active(kb_id: str) -> dict:
    """校验 KB 已登记且处于 active 状态。"""
    safe_kb_id = validate_kb_id(kb_id)
    kb = _get_registry().get_kb(safe_kb_id)
    if kb is None:
        raise KBNotFoundError(f"知识库不存在: {safe_kb_id}")
    if kb.get("status", "active") != "active":
        raise KBUnavailableError(f"知识库不可用: {safe_kb_id}")
    return kb


def _normalize_doc_kb_id(metadata: dict[str, Any]) -> str:
    """解析文档归属；旧无标签节点统一归入 default。"""
    return metadata.get("kb_id") or "default"


def _doc_belongs_to_request(metadata: dict[str, Any], request_kb_id: str | None) -> bool:
    """判断文档是否属于本次请求的 KB 范围。"""
    if request_kb_id is None:
        return True
    doc_kb_id = _normalize_doc_kb_id(metadata)
    return doc_kb_id == request_kb_id


def _safe_add_doc_count(kb_id: str, delta: int) -> None:
    """安全更新 doc_count；删除旧索引遗留记录时兼容 registry 缺失。"""
    try:
        _get_registry().add_doc_count(kb_id, delta)
    except ValueError:
        return


# ?? KB CRUD ??

def create_kb(kb_id: str, kb_name: str) -> dict:
    """创建知识库，并同步创建 data/{kb_id}/ 目录。"""
    safe_kb_id = validate_kb_id(kb_id)
    registry = _get_registry()
    snapshot = _registry_snapshot(registry)
    try:
        result = registry.create_kb(safe_kb_id, kb_name)
    except ValueError as exc:
        raise KBConflictError(str(exc)) from exc

    try:
        get_kb_data_dir(safe_kb_id, create=True)
    except Exception as exc:
        try:
            _restore_registry(registry, snapshot)
        except Exception as restore_exc:
            raise KBConsistencyError(
                f"创建 KB 后回滚 registry 失败: {safe_kb_id}; 原因: {restore_exc}"
            ) from restore_exc
        raise KBConsistencyError(f"创建 KB 目录失败，已回滚 registry: {safe_kb_id}; 原因: {exc}") from exc
    return result


def list_kbs() -> list[dict]:
    """列出全部知识库。"""
    return _get_registry().list_kbs()


def get_kb(kb_id: str) -> dict | None:
    """获取知识库详情。"""
    safe_kb_id = validate_kb_id(kb_id)
    return _get_registry().get_kb(safe_kb_id)


def update_kb(kb_id: str, kb_name: str) -> dict:
    """更新知识库名称。"""
    safe_kb_id = validate_kb_id(kb_id)
    try:
        return _get_registry().update_kb(safe_kb_id, kb_name)
    except ValueError as exc:
        raise KBNotFoundError(str(exc)) from exc


def delete_kb(kb_id: str) -> bool:
    """删除空知识库；default 和非空知识库禁止删除。"""
    safe_kb_id = validate_kb_id(kb_id)
    if safe_kb_id == "default":
        raise KBConflictError("禁止删除 default 知识库")

    registry = _get_registry()
    kb = registry.get_kb(safe_kb_id)
    if kb is None:
        raise KBNotFoundError(f"知识库不存在: {safe_kb_id}")

    if int(kb.get("doc_count", 0)) > 0:
        raise KBConflictError(f"知识库非空，禁止删除: {safe_kb_id}")

    try:
        docs = list_docs(kb_id=safe_kb_id)
    except RuntimeError:
        docs = []
    if docs:
        raise KBConflictError(f"知识库仍有关联文档，禁止删除: {safe_kb_id}")

    kb_dir = get_kb_data_dir(safe_kb_id, create=False)
    if kb_dir.exists() and any(kb_dir.iterdir()):
        raise KBConflictError(f"知识库目录非空，禁止删除: {safe_kb_id}")

    snapshot = _registry_snapshot(registry)
    try:
        registry.delete_kb(safe_kb_id)
    except ValueError as exc:
        raise KBNotFoundError(str(exc)) from exc

    try:
        if kb_dir.exists():
            kb_dir.rmdir()
    except Exception as exc:
        try:
            _restore_registry(registry, snapshot)
        except Exception as restore_exc:
            raise KBConsistencyError(
                f"删除 KB 后恢复 registry 失败: {safe_kb_id}; 原因: {restore_exc}"
            ) from restore_exc
        raise KBConsistencyError(f"删除 KB 目录失败，已恢复 registry: {safe_kb_id}; 原因: {exc}") from exc
    return True


def import_files(files: list[Any], chunk_size: int, chunk_overlap: int, kb_id: str = "default") -> dict[str, Any]:
    """导入本地文件，先校验 KB，再落盘到 data/{kb_id}/。"""
    _ensure_kb_active(kb_id)
    runtime_state.ensure_models_ready(require_llm=False)
    manager = runtime_state.get_index_manager()
    kb_dir = get_kb_data_dir(kb_id, create=True)

    uploaded_files: list[dict[str, Any]] = []
    file_paths: list[Path] = []
    try:
        for file in files:
            file_content = file.file.read()
            if len(file_content) > MAX_FILE_SIZE:
                raise KBValidationError(f"File too large: {len(file_content)} bytes (max: {MAX_FILE_SIZE})")
            file.file.seek(0)

            safe_filename = FilenameSanitizer.sanitize(file.filename)
            unique_filename = FilenameSanitizer.generate_unique_filename(safe_filename)
            target_path = ensure_path_within(kb_dir, kb_dir / unique_filename)

            with target_path.open("wb") as buffer:
                buffer.write(file_content)

            file_paths.append(target_path)
            uploaded_files.append(
                {
                    "name": unique_filename,
                    "type": getattr(file, "content_type", ""),
                    "size": len(file_content),
                    "path": str(target_path.resolve()),
                    "kb_id": kb_id,
                }
            )

        nodes = manager.load_files(file_paths, chunk_size, chunk_overlap, kb_id=kb_id)
    except Exception:
        for path in file_paths:
            try:
                if path.exists() and path.is_file():
                    path.unlink()
            except OSError:
                pass
        raise

    _get_registry().add_doc_count(kb_id, len(uploaded_files))
    return {"files": uploaded_files, "indexed_chunks": len(nodes or []), "kb_id": kb_id}


def import_urls(urls: list[str], chunk_size: int, chunk_overlap: int, kb_id: str = "default") -> dict[str, Any]:
    """导入网页 URL。"""
    _ensure_kb_active(kb_id)
    runtime_state.ensure_models_ready(require_llm=False)
    manager = runtime_state.get_index_manager()
    nodes = manager.load_websites(urls, chunk_size, chunk_overlap, kb_id=kb_id)
    _get_registry().add_doc_count(kb_id, len(urls))
    return {"urls": urls, "indexed_chunks": len(nodes or []), "kb_id": kb_id}


def list_docs(kb_id: str | None = None) -> list[dict[str, Any]]:
    """列出知识库文档。

    Args:
        kb_id: 可选知识库 ID；为空时返回全部文档。
    """
    safe_kb_id = validate_kb_id(kb_id) if kb_id is not None else None
    manager = runtime_state.get_index_manager()
    doc_store = manager.storage_context.docstore
    ref_doc_info = doc_store.get_all_ref_doc_info() if len(doc_store.docs) > 0 else {}

    docs: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for ref_doc_id, ref_doc in ref_doc_info.items():
        metadata = ref_doc.metadata
        doc_kb_id = _normalize_doc_kb_id(metadata)
        if not _doc_belongs_to_request(metadata, safe_kb_id):
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
                "kb_id": doc_kb_id,
            }
        )
        if file_path:
            seen_paths.add(file_path)
    return docs


def _path_matches(candidate: str | None, targets: set[str]) -> bool:
    """删除指定文档并同步维护索引与源文件。"""
    if not candidate:
        return False
    if candidate in targets:
        return True
    try:
        resolved = str(Path(candidate).resolve())
        return resolved in targets or any(Path(target).resolve() == Path(candidate).resolve() for target in targets)
    except OSError:
        return False


def _is_legacy_default_root_file(path: Path, metadata: dict[str, Any]) -> bool:
    """判断路径是否为 data/ 根目录直属旧文件。"""
    data_root = get_data_root()
    expected_name = metadata.get("file_name")
    return (
        _normalize_doc_kb_id(metadata) == "default"
        and path.parent == data_root
        and path.is_file()
        and (not expected_name or expected_name == path.name)
    )


def _delete_local_file_for_doc(metadata: dict[str, Any], request_kb_id: str) -> str:
    """按 KB 边界安全删除源文件，返回 deleted/skipped/none。"""
    file_path = metadata.get("file_path")
    if not file_path:
        return "none"

    path = Path(file_path).resolve()
    if not path.exists() or not path.is_file():
        return "skipped"

    allowed = False
    if request_kb_id == "default":
        default_dir = get_kb_data_dir("default", create=False)
        try:
            ensure_path_within(default_dir, path)
            allowed = True
        except KBValidationError:
            allowed = _is_legacy_default_root_file(path, metadata)
    else:
        kb_dir = get_kb_data_dir(request_kb_id, create=False)
        try:
            ensure_path_within(kb_dir, path)
            allowed = True
        except KBValidationError:
            allowed = False

    if not allowed:
        return "skipped"

    try:
        path.unlink()
    except OSError as exc:
        raise KBConsistencyError(f"删除源文件失败: {path}; 原因: {exc}") from exc
    return "deleted"


def delete_docs(request: DeleteDocsRequest) -> dict[str, int]:
    """判断 doc_id 是否属于本次删除请求的候选范围。"""
    safe_kb_id = validate_kb_id(request.kb_id)
    manager = runtime_state.get_index_manager()
    runtime_state.ensure_index_loaded()
    doc_store = manager.storage_context.docstore
    ref_doc_info = doc_store.get_all_ref_doc_info() if len(doc_store.docs) > 0 else {}
    deleted = 0
    files_deleted = 0
    files_skipped = 0

    path_targets = set(request.paths)
    id_targets = set(request.doc_ids)
    for ref_doc_id, ref_doc in list(ref_doc_info.items()):
        metadata = ref_doc.metadata
        if not _doc_belongs_to_request(metadata, safe_kb_id):
            continue
        path = metadata.get("file_path") or metadata.get("url_source")
        if ref_doc_id in id_targets or _path_matches(path, path_targets):
            file_status = _delete_local_file_for_doc(metadata, safe_kb_id)
            manager.delete_ref_doc(ref_doc_id)
            deleted += 1
            if file_status == "deleted":
                files_deleted += 1
            elif file_status == "skipped":
                files_skipped += 1
            _safe_add_doc_count(_normalize_doc_kb_id(metadata), -1)

    return {"deleted": deleted, "files_deleted": files_deleted, "files_skipped": files_skipped}
