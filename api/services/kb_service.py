"""知识库服务：处理 KB CRUD、文件/URL 导入与文档管理。"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from api.runtime import runtime_state
from api.services.evidence_service import build_evidence_id, parse_evidence_id
from api.schemas import DeleteDocsRequest, PreviewRequest
from server.kb_errors import (
    KBConflictError,
    KBConsistencyError,
    KBNotFoundError,
    KBUnavailableError,
    KBValidationError,
)
from server.folder_registry import folder_path_from_relative_path, normalize_relative_path, resolve_relative_path_from_metadata
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


def _build_import_receipt_id(prefix: str) -> str:
    """生成导入回执 ID，便于前后端串联一次导入批次。"""
    return f"{prefix}-{uuid4().hex}"


def _build_file_result(
    *,
    kb_id: str,
    filename: str,
    content_type: str,
    size: int,
    path: Path | None,
    status: str,
    indexed_chunks: int,
    relative_path: str | None = None,
    folder_path: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """构造单文件导入结果，统一补齐路径与统计字段。"""
    result = {
        "name": filename,
        "type": content_type,
        "size": size,
        "path": str(path.resolve()) if path is not None else None,
        "kb_id": kb_id,
        "status": status,
        "indexed_chunks": indexed_chunks,
        "relative_path": relative_path,
        "folder_path": folder_path,
    }
    if message is not None:
        result["message"] = message
    return result



def _validate_import_mode(import_mode: str) -> str:
    """校验导入模式，仅允许 preserve_tree 或 flatten。"""
    value = (import_mode or "preserve_tree").strip()
    if value not in {"preserve_tree", "flatten"}:
        raise KBValidationError(f"不支持的导入模式: {import_mode}")
    return value



def _normalize_import_relative_paths(files: list[Any], relative_paths: list[str] | None) -> list[str | None]:
    """标准化 relative_paths，并确保数量与上传文件一一对应。"""
    if relative_paths is None:
        return [None] * len(files)
    if len(relative_paths) != len(files):
        raise KBValidationError("relative_paths 数量必须与 files 数量一致")
    return [normalize_relative_path(path) for path in relative_paths]


def _build_url_result(*, kb_id: str, url: str, status: str, indexed_chunks: int, message: str | None = None) -> dict[str, Any]:
    """构造单 URL 导入结果。"""
    result = {
        "url": url,
        "kb_id": kb_id,
        "status": status,
        "indexed_chunks": indexed_chunks,
    }
    if message is not None:
        result["message"] = message
    return result


# ===== 知识库 CRUD =====

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


def import_files(
    files: list[Any],
    chunk_size: int,
    chunk_overlap: int,
    kb_id: str = "default",
    relative_paths: list[str] | None = None,
    import_mode: str = "preserve_tree",
) -> dict[str, Any]:
    """导入本地文件到知识库，并根据模式决定是否保留目录树。"""
    _ensure_kb_active(kb_id)
    runtime_state.ensure_models_ready(require_llm=False)
    manager = runtime_state.get_index_manager()
    kb_dir = get_kb_data_dir(kb_id, create=True)
    safe_import_mode = _validate_import_mode(import_mode)
    normalized_relative_paths = _normalize_import_relative_paths(files, relative_paths)

    receipt_id = _build_import_receipt_id("kb-file-import")
    retained_files: list[dict[str, Any]] = []
    file_results: list[dict[str, Any]] = []
    indexed_chunks = 0
    success_count = 0
    failed_count = 0
    empty_count = 0

    for file, relative_path in zip(files, normalized_relative_paths):
        original_name = getattr(file, "filename", "") or "unnamed"
        content_type = getattr(file, "content_type", "") or ""
        file_size = 0
        target_path: Path | None = None
        stored_filename = FilenameSanitizer.sanitize(original_name)
        folder_path = folder_path_from_relative_path(relative_path) if relative_path is not None else None

        try:
            file_content = file.file.read()
            file_size = len(file_content)
            if file_size > MAX_FILE_SIZE:
                raise KBValidationError(f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE})")
            if hasattr(file.file, "seek"):
                file.file.seek(0)

            if safe_import_mode == "preserve_tree" and relative_path is not None:
                target_path = ensure_path_within(kb_dir, kb_dir / relative_path)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                stored_filename = target_path.name
            else:
                stored_filename = FilenameSanitizer.generate_unique_filename(stored_filename)
                target_path = ensure_path_within(kb_dir, kb_dir / stored_filename)

            with target_path.open("wb") as buffer:
                buffer.write(file_content)

            nodes = manager.load_files([target_path.resolve()], chunk_size, chunk_overlap, kb_id=kb_id) or []
            chunk_count = len(nodes)
            file_record = _build_file_result(
                kb_id=kb_id,
                filename=stored_filename,
                content_type=content_type,
                size=file_size,
                path=target_path,
                status="indexed" if chunk_count > 0 else "empty",
                indexed_chunks=chunk_count,
                relative_path=relative_path,
                folder_path=folder_path,
            )
            retained_files.append(
                {k: file_record[k] for k in ("name", "type", "size", "path", "kb_id", "relative_path", "folder_path")}
            )
            file_results.append(file_record)
            indexed_chunks += chunk_count
            if chunk_count > 0:
                success_count += 1
            else:
                empty_count += 1
        except Exception as exc:
            if target_path is not None:
                try:
                    if target_path.exists() and target_path.is_file():
                        target_path.unlink()
                except OSError:
                    pass
            failed_count += 1
            file_results.append(
                _build_file_result(
                    kb_id=kb_id,
                    filename=stored_filename,
                    content_type=content_type,
                    size=file_size,
                    path=target_path,
                    status="failed",
                    indexed_chunks=0,
                    relative_path=relative_path,
                    folder_path=folder_path,
                    message=str(exc),
                )
            )

    if success_count > 0:
        _safe_add_doc_count(kb_id, success_count)

    return {
        "receipt_id": receipt_id,
        "files": retained_files,
        "file_results": file_results,
        "indexed_chunks": indexed_chunks,
        "success_count": success_count,
        "failed_count": failed_count,
        "empty_count": empty_count,
        "kb_id": kb_id,
        "import_mode": safe_import_mode,
    }



def import_urls(urls: list[str], chunk_size: int, chunk_overlap: int, kb_id: str = "default") -> dict[str, Any]:
    """逐项导入 URL，区分 indexed / empty / failed 三种结果。"""
    _ensure_kb_active(kb_id)
    runtime_state.ensure_models_ready(require_llm=False)
    manager = runtime_state.get_index_manager()

    receipt_id = _build_import_receipt_id("kb-url-import")
    url_results: list[dict[str, Any]] = []
    indexed_chunks = 0
    success_count = 0
    failed_count = 0
    empty_count = 0

    for url in urls:
        try:
            nodes = manager.load_websites([url], chunk_size, chunk_overlap, kb_id=kb_id) or []
            chunk_count = len(nodes)
            url_results.append(
                _build_url_result(
                    kb_id=kb_id,
                    url=url,
                    status="indexed" if chunk_count > 0 else "empty",
                    indexed_chunks=chunk_count,
                )
            )
            indexed_chunks += chunk_count
            if chunk_count > 0:
                success_count += 1
            else:
                empty_count += 1
        except Exception as exc:
            failed_count += 1
            url_results.append(
                _build_url_result(
                    kb_id=kb_id,
                    url=url,
                    status="failed",
                    indexed_chunks=0,
                    message=str(exc),
                )
            )

    if success_count > 0:
        _safe_add_doc_count(kb_id, success_count)

    return {
        "receipt_id": receipt_id,
        "urls": urls,
        "url_results": url_results,
        "indexed_chunks": indexed_chunks,
        "success_count": success_count,
        "failed_count": failed_count,
        "empty_count": empty_count,
        "kb_id": kb_id,
    }


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
        relative_path = resolve_relative_path_from_metadata(metadata, doc_kb_id) if file_path else None
        folder_path = folder_path_from_relative_path(relative_path) if relative_path is not None else None
        docs.append(
            {
                "id": ref_doc_id,
                "name": metadata.get("file_name") or metadata.get("title", "N/A"),
                "path": path_or_url,
                "type": "file" if file_path else "url",
                "date": metadata.get("creation_date", ""),
                "kb_id": doc_kb_id,
                "relative_path": relative_path,
                "folder_path": folder_path,
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


def _get_preview_docstore():
    """获取 preview 所需的 docstore。"""
    manager = runtime_state.get_index_manager()
    return manager.storage_context.docstore


def _fetch_preview_nodes(doc_store, node_ids: list[str]) -> list[Any]:
    """按节点 ID 从 docstore 读取节点列表。"""
    if not node_ids:
        return []
    if hasattr(doc_store, "get_nodes"):
        try:
            return list(doc_store.get_nodes(node_ids=node_ids, raise_error=False) or [])
        except TypeError:
            return list(doc_store.get_nodes(node_ids) or [])

    docs = getattr(doc_store, "docs", {}) or {}
    return [docs[node_id] for node_id in node_ids if node_id in docs]


def _select_preview_node(nodes: list[Any], locator: dict[str, Any] | None) -> Any | None:
    """根据 locator 选择最匹配的预览节点。"""
    if not nodes:
        return None
    if not locator:
        return nodes[0]

    target_node_id = locator.get("node_id")
    if isinstance(target_node_id, str) and target_node_id:
        for node in nodes:
            if getattr(node, "node_id", None) == target_node_id:
                return node

    target_page = locator.get("page")
    if target_page not in (None, ""):
        for node in nodes:
            metadata = getattr(node, "metadata", {}) or {}
            page = metadata.get("page_label") or metadata.get("page")
            if page is not None and str(page) == str(target_page):
                return node

    return nodes[0]


def _build_preview_locator_from_node(node: Any | None, locator: dict[str, Any] | None) -> dict[str, Any] | None:
    """合并 locator 并补齐节点级定位信息。"""
    merged = dict(locator or {})
    if node is None:
        return merged or None

    metadata = getattr(node, "metadata", {}) or {}
    page = metadata.get("page_label") or metadata.get("page")
    if page not in (None, "", "N/A"):
        merged["page"] = str(page)

    node_id = getattr(node, "node_id", None)
    if isinstance(node_id, str) and node_id:
        merged["node_id"] = node_id

    return merged or None


def preview_document(request: PreviewRequest) -> dict[str, Any]:
    """按 doc_id / evidence_id 返回最小预览对象。"""
    safe_kb_id = validate_kb_id(request.kb_id)
    _ensure_kb_active(safe_kb_id)

    if not request.doc_id and not request.evidence_id:
        raise KBValidationError("预览请求必须提供 doc_id 或 evidence_id")

    doc_id = request.doc_id
    locator = dict(request.preview_locator or {}) if request.preview_locator else None
    evidence_id = request.evidence_id

    if evidence_id:
        payload = parse_evidence_id(evidence_id)
        payload_kb_id = payload.get("kb_id")
        if payload_kb_id and payload_kb_id != safe_kb_id:
            raise KBValidationError("evidence_id 与请求的 kb_id 不一致")
        doc_id = doc_id or payload.get("doc_id")
        if locator is None and isinstance(payload.get("preview_locator"), dict):
            locator = payload.get("preview_locator")

    if not isinstance(doc_id, str) or not doc_id.strip():
        raise KBValidationError("预览请求缺少有效 doc_id")
    doc_id = doc_id.strip()

    runtime_state.ensure_index_loaded()
    doc_store = _get_preview_docstore()
    ref_doc = doc_store.get_ref_doc_info(doc_id) if hasattr(doc_store, "get_ref_doc_info") else None
    if ref_doc is None:
        raise KBNotFoundError(f"文档不存在或不属于该知识库: {doc_id}")

    ref_metadata = getattr(ref_doc, "metadata", {}) or {}
    if not _doc_belongs_to_request(ref_metadata, safe_kb_id):
        raise KBNotFoundError(f"文档不存在或不属于该知识库: {doc_id}")

    node_ids = list(getattr(ref_doc, "node_ids", []) or [])
    nodes = _fetch_preview_nodes(doc_store, node_ids)
    preview_node = _select_preview_node(nodes, locator)
    preview_text = getattr(preview_node, "text", "") if preview_node is not None else ""
    effective_locator = _build_preview_locator_from_node(preview_node, locator)
    title = ref_metadata.get("file_name") or ref_metadata.get("title") or doc_id
    if preview_node is not None:
        node_metadata = getattr(preview_node, "metadata", {}) or {}
        title = node_metadata.get("file_name") or node_metadata.get("title") or title

    return {
        "title": title,
        "kb_id": safe_kb_id,
        "doc_id": doc_id,
        "excerpt": str(preview_text or "")[:600],
        "locator": effective_locator,
        "preview_type": "text_excerpt",
        "evidence_id": evidence_id
        or build_evidence_id(
            kb_id=safe_kb_id,
            doc_id=doc_id,
            preview_locator=effective_locator,
            fallback_index=1,
        ),
    }
