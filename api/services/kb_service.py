"""知识库服务：处理 KB CRUD、文件/URL 导入与文档管理。"""

from __future__ import annotations

import copy
import re
import time

from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from llama_index.core import Document

from api.runtime import runtime_state
from api.services import asset_service, kb_import_receipt_store
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
from server.markdown_asset_extractor import extract_markdown_embedded_assets_from_file
from server.security.filename_sanitizer import FilenameSanitizer
from server.utils.file import ensure_path_within, get_data_root, get_kb_data_dir, validate_kb_id

# 上传文件大小上限：100MB。
MAX_FILE_SIZE = 100 * 1024 * 1024

# 需要做内嵌资产解析的 Markdown 后缀。
MARKDOWN_SUFFIXES = {".md", ".markdown", ".mdown", ".mdx"}

# 需要识别为图片资产候选的常见图片后缀。
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}

# 允许尝试 OCR 的图片后缀。
OCR_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

# OCR 细粒度性能诊断字段，供导入回执与资产对象透传。
OCR_RUNTIME_FLOAT_KEYS = (
    "ocr_init_ms",
    "ocr_load_image_ms",
    "ocr_predict_ms",
    "ocr_postprocess_ms",
    "ocr_total_ms",
)

_TEXT_CONTROL_CHAR_BYTES = {9, 10, 12, 13}
_TEXT_CONTROL_CHARS = {"\t", "\n", "\f", "\r"}
_CONTENT_SNIFF_FALLBACK_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}


# OCR 派生文本入索引时，不应让路径/内部标识耗尽 chunk budget。
OCR_INDEX_EXCLUDED_METADATA_KEYS = (
    "kb_id",
    "asset_id",
    "source_type",
    "file_path",
    "relative_path",
    "mime_type",
    "ocr_engine",
    "source_doc_path",
    "source_doc_relative_path",
    "referenced_path",
    "occurrence_index",
)

# 延迟初始化 registry，便于测试替换工作目录。
_registry: KBRegistry | None = None


def _get_registry() -> KBRegistry:
    global _registry
    if _registry is None:
        _registry = KBRegistry(storage_path=Path("storage/kb_registry.json"))
    return _registry


def _new_import_stage_timings() -> dict[str, float]:
    """创建批次级 stage_timings 初始结构，便于累计导入耗时。"""
    return {
        "ensure_models_ready_ms": 0.0,
        "get_index_manager_ms": 0.0,
        "file_save_ms": 0.0,
        "persist_ms": 0.0,
        "standalone_ocr_ms": 0.0,
        "primary_index_ms": 0.0,
        "embedded_asset_extract_ms": 0.0,
        "embedded_asset_ocr_ms": 0.0,
        "embedded_asset_index_ms": 0.0,
        "index_storage_persist_ms": 0.0,
        "doc_count_update_ms": 0.0,
        "register_assets_ms": 0.0,
        "receipt_store_ms": 0.0,
        "result_build_ms": 0.0,
        "total_ms": 0.0,
    }


def _new_file_stage_timings() -> dict[str, float]:
    """创建单文件 stage_timings 初始结构。"""
    return {
        "file_save_ms": 0.0,
        "persist_ms": 0.0,
        "standalone_ocr_ms": 0.0,
        "primary_index_ms": 0.0,
        "embedded_asset_extract_ms": 0.0,
        "embedded_asset_ocr_ms": 0.0,
        "embedded_asset_index_ms": 0.0,
        "total_ms": 0.0,
    }


INDEX_STAGE_TIMING_KEYS = (
    "document_load_ms",
    "chunking_ms",
    "embedding_ms",
    "title_extract_ms",
    "vector_store_ms",
    "docstore_ms",
    "index_insert_ms",
    "total_ms",
)


def _new_index_stage_timings() -> dict[str, float]:
    """创建索引阶段耗时结构，覆盖 embedding 等细分步骤。"""
    return {key: 0.0 for key in INDEX_STAGE_TIMING_KEYS}


def _new_ingestion_diagnostics_summary() -> dict[str, Any]:
    """创建导入诊断聚合结构，用于汇总文件级 ingestion 信息。"""
    return {
        "document_count": 0,
        "empty_document_count": 0,
        "input_text_chars": 0,
        "node_count": 0,
        "nodes_with_embedding_count": 0,
        "nodes_without_embedding_count": 0,
        "index_stage_timings": _new_index_stage_timings(),
    }


def _merge_ingestion_diagnostics(target: dict[str, Any], source: dict[str, Any] | None) -> None:
    """把 IndexManager 返回的 ingestion diagnostics 合并进目标汇总。"""
    if not isinstance(target, dict) or not isinstance(source, dict):
        return

    for key in (
        "document_count",
        "empty_document_count",
        "input_text_chars",
        "node_count",
        "nodes_with_embedding_count",
        "nodes_without_embedding_count",
    ):
        try:
            target[key] = int(target.get(key) or 0) + int(source.get(key) or 0)
        except (TypeError, ValueError):
            continue

    source_stage_timings = source.get("index_stage_timings") or source.get("stage_timings") or {}
    target_stage_timings = target.setdefault("index_stage_timings", _new_index_stage_timings())
    for key in INDEX_STAGE_TIMING_KEYS:
        try:
            target_stage_timings[key] = round(
                float(target_stage_timings.get(key) or 0.0) + float(source_stage_timings.get(key) or 0.0),
                3,
            )
        except (TypeError, ValueError):
            continue


def _consume_manager_ingestion_diagnostics(manager: Any, *targets: dict[str, Any] | None) -> dict[str, Any] | None:
    """从 manager 消费一次 ingestion diagnostics，并同步写入多个目标。"""
    consumer = getattr(manager, "consume_last_ingestion_diagnostics", None)
    if not callable(consumer):
        return None
    diagnostics = consumer()
    for target in targets:
        if isinstance(target, dict):
            _merge_ingestion_diagnostics(target, diagnostics)
    return diagnostics


def _elapsed_ms(started_at: float) -> float:
    """基于 monotonic 时钟计算阶段耗时，统一返回毫秒值。"""
    return round(max(time.perf_counter() - started_at, 0.0) * 1000, 3)


def _add_stage_elapsed(stage_targets: tuple[dict[str, float], ...], key: str, started_at: float) -> float:
    """把某个阶段耗时累计写入多个 timing 容器。"""
    elapsed_ms = _elapsed_ms(started_at)
    for target in stage_targets:
        target[key] = round(float(target.get(key, 0.0)) + elapsed_ms, 3)
    return elapsed_ms


def _sync_stage_timing_aliases(*stage_timings_list: dict[str, float] | None) -> None:
    """同步阶段耗时别名字段，保证兼容 persist_ms 旧字段。"""
    for stage_timings in stage_timings_list:
        if not isinstance(stage_timings, dict):
            continue
        if "file_save_ms" in stage_timings:
            stage_timings["persist_ms"] = round(float(stage_timings.get("file_save_ms") or 0.0), 3)


def _record_file_save_elapsed(stage_targets: tuple[dict[str, float], ...], started_at: float) -> float:
    """记录文件保存耗时，并同步 persist_ms 兼容别名。"""
    elapsed_ms = _add_stage_elapsed(stage_targets, "file_save_ms", started_at)
    _sync_stage_timing_aliases(*stage_targets)
    return elapsed_ms


def _refresh_import_result_stage_timings(result: dict[str, Any], stage_timings: dict[str, float]) -> None:
    """把最新批次级阶段耗时回写到结果 diagnostics。"""
    diagnostics = result.get("diagnostics")
    if isinstance(diagnostics, dict):
        diagnostics["stage_timings"] = dict(stage_timings)


def _finalize_stage_total(stage_timings: dict[str, float]) -> None:
    """汇总阶段耗时并回填 total_ms，避免重复累计别名字段。"""
    _sync_stage_timing_aliases(stage_timings)
    excluded_keys = {"total_ms"}
    if "file_save_ms" in stage_timings:
        excluded_keys.add("persist_ms")
    stage_timings["total_ms"] = round(
        sum(float(value) for key, value in stage_timings.items() if key not in excluded_keys),
        3,
    )


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


def _is_embedded_asset_doc(metadata: dict[str, Any]) -> bool:
    """判断索引节点是否表示 Markdown 内嵌资产派生出来的影子文档。"""
    return bool(metadata.get("source_doc_relative_path") or metadata.get("source_doc_path"))


def _safe_add_doc_count(kb_id: str, delta: int) -> None:
    """安全更新 doc_count；删除旧索引遗留记录时兼容 registry 缺失。"""
    try:
        _get_registry().add_doc_count(kb_id, delta)
    except ValueError:
        return


def _collect_existing_ref_docs_for_import(
    manager: Any,
    *,
    kb_id: str,
    target_path: Path,
    relative_path: str | None,
) -> list[dict[str, Any]]:
    """收集与当前导入目标绑定的旧 ref_doc，供成功重导入后替换。"""
    storage_context = getattr(manager, "storage_context", None)
    doc_store = getattr(storage_context, "docstore", None)
    raw_docs = getattr(doc_store, "docs", {}) if doc_store is not None else {}
    get_all_ref_doc_info = getattr(doc_store, "get_all_ref_doc_info", None) if doc_store is not None else None
    if not raw_docs or not callable(get_all_ref_doc_info):
        return []

    resolved_target = str(target_path.resolve())
    target_set = {resolved_target}
    ref_doc_info = get_all_ref_doc_info() or {}
    matches: list[dict[str, Any]] = []
    seen_ref_doc_ids: set[str] = set()

    for ref_doc_id, ref_doc in ref_doc_info.items():
        if not isinstance(ref_doc_id, str) or not ref_doc_id or ref_doc_id in seen_ref_doc_ids:
            continue

        metadata = getattr(ref_doc, "metadata", {}) or {}
        if not _doc_belongs_to_request(metadata, kb_id):
            continue

        file_path = metadata.get("file_path")
        source_doc_path = metadata.get("source_doc_path")
        same_target = _path_matches(file_path, target_set) or _path_matches(source_doc_path, target_set)
        same_source_doc = bool(relative_path) and metadata.get("source_doc_relative_path") == relative_path
        if not (same_target or same_source_doc):
            continue

        seen_ref_doc_ids.add(ref_doc_id)
        matches.append(
            {
                "ref_doc_id": ref_doc_id,
                "counts_doc": not _is_embedded_asset_doc(metadata),
            }
        )
    return matches


def _restore_reimport_backup_file(target_path: Path | None, backup_bytes: bytes | None) -> None:
    """重导入未成功落库时恢复旧文件字节，避免磁盘内容与旧索引脱节。"""
    if target_path is None or backup_bytes is None:
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("wb") as buffer:
        buffer.write(backup_bytes)



def _get_manager_docstore(manager: Any) -> Any | None:
    """读取索引管理器上的 docstore，供导入期回滚逻辑复用。"""
    storage_context = getattr(manager, "storage_context", None)
    return getattr(storage_context, "docstore", None) if storage_context is not None else None



def _get_manager_ref_doc_info(manager: Any) -> dict[str, Any]:
    """读取当前 docstore 中全部 ref_doc 信息，异常时返回空映射。"""
    doc_store = _get_manager_docstore(manager)
    get_all_ref_doc_info = getattr(doc_store, "get_all_ref_doc_info", None) if doc_store is not None else None
    if not callable(get_all_ref_doc_info):
        return {}
    try:
        raw_info = get_all_ref_doc_info() or {}
    except Exception:
        return {}
    return raw_info if isinstance(raw_info, dict) else {}



def _capture_ref_doc_ids(manager: Any) -> set[str]:
    """抓取当前索引中的 ref_doc_id 集合，用于识别本批新增对象。"""
    return {str(ref_doc_id) for ref_doc_id in _get_manager_ref_doc_info(manager) if isinstance(ref_doc_id, str) and ref_doc_id}



def _collect_new_ref_doc_ids(manager: Any, before_ref_doc_ids: set[str] | None) -> list[str]:
    """根据导入前快照识别当前步骤新增的 ref_doc。"""
    previous = before_ref_doc_ids or set()
    current = _capture_ref_doc_ids(manager)
    return sorted(ref_doc_id for ref_doc_id in current - previous if ref_doc_id)



def _snapshot_ref_doc_payloads(manager: Any, ref_doc_ids: list[str] | None) -> list[dict[str, Any]]:
    """备份待替换 ref_doc 的节点与元数据，供 persist 失败时恢复。"""
    if not ref_doc_ids:
        return []

    doc_store = _get_manager_docstore(manager)
    if doc_store is None:
        return []

    all_ref_doc_info = _get_manager_ref_doc_info(manager)
    get_ref_doc_info = getattr(doc_store, "get_ref_doc_info", None)
    get_document = getattr(doc_store, "get_document", None)
    docs_dict = getattr(doc_store, "docs", None)

    snapshots: list[dict[str, Any]] = []
    for ref_doc_id in ref_doc_ids:
        if not isinstance(ref_doc_id, str) or not ref_doc_id:
            continue
        ref_doc_info = None
        if callable(get_ref_doc_info):
            try:
                ref_doc_info = get_ref_doc_info(ref_doc_id)
            except Exception:
                ref_doc_info = None
        if ref_doc_info is None:
            ref_doc_info = all_ref_doc_info.get(ref_doc_id)
        if ref_doc_info is None:
            continue

        nodes: list[Any] = []
        for node_id in list(getattr(ref_doc_info, "node_ids", []) or []):
            node = None
            if callable(get_document):
                try:
                    node = get_document(node_id, raise_error=False)
                except TypeError:
                    try:
                        node = get_document(node_id)
                    except Exception:
                        node = None
                except Exception:
                    node = None
            if node is None and isinstance(docs_dict, dict):
                node = docs_dict.get(node_id)
            if node is not None:
                nodes.append(copy.deepcopy(node))

        snapshots.append(
            {
                "ref_doc_id": ref_doc_id,
                "ref_doc_info": copy.deepcopy(ref_doc_info),
                "nodes": nodes,
            }
        )
    return snapshots



def _delete_ref_doc_with_optional_persist(manager: Any, ref_doc_id: str, *, persist: bool) -> bool:
    """删除 ref_doc，并兼容旧测试替身上不支持 persist 参数的签名。"""
    if not isinstance(ref_doc_id, str) or not ref_doc_id:
        return False

    current_ref_doc_info = _get_manager_ref_doc_info(manager)
    if ref_doc_id not in current_ref_doc_info:
        return False

    delete_ref_doc = getattr(manager, "delete_ref_doc", None)
    if not callable(delete_ref_doc):
        return False

    try:
        delete_ref_doc(ref_doc_id, persist=persist)
    except TypeError:
        delete_ref_doc(ref_doc_id)
    return True



def _restore_ref_doc_snapshots(manager: Any, snapshots: list[dict[str, Any]] | None) -> int:
    """在批量 persist 失败后恢复被替换掉的旧 ref_doc。"""
    if not snapshots:
        return 0

    nodes_to_restore: list[Any] = []
    for item in snapshots:
        for node in item.get("nodes") or []:
            nodes_to_restore.append(copy.deepcopy(node))

    insert_nodes = getattr(manager, "insert_nodes", None)
    if nodes_to_restore and callable(insert_nodes):
        try:
            insert_nodes(nodes_to_restore, persist=False)
        except TypeError:
            insert_nodes(nodes_to_restore)
        return len(snapshots)

    doc_store = _get_manager_docstore(manager)
    docs_dict = getattr(doc_store, "docs", None) if doc_store is not None else None
    legacy_ref_docs = getattr(doc_store, "_ref_docs", None) if doc_store is not None else None
    alt_ref_docs = getattr(doc_store, "ref_docs", None) if doc_store is not None else None
    if doc_store is None:
        return 0

    restored_count = 0
    for item in snapshots:
        ref_doc_id = item.get("ref_doc_id")
        ref_doc_info = item.get("ref_doc_info")
        if not isinstance(ref_doc_id, str) or not ref_doc_id or ref_doc_info is None:
            continue
        if isinstance(docs_dict, dict):
            for node in item.get("nodes") or []:
                node_copy = copy.deepcopy(node)
                node_id = getattr(node_copy, "node_id", None)
                if isinstance(node_id, str) and node_id:
                    docs_dict[node_id] = node_copy
        if isinstance(legacy_ref_docs, dict):
            legacy_ref_docs[ref_doc_id] = copy.deepcopy(ref_doc_info)
        elif isinstance(alt_ref_docs, dict):
            alt_ref_docs[ref_doc_id] = copy.deepcopy(ref_doc_info)
        restored_count += 1
    return restored_count



def _rollback_import_batch_after_persist_failure(manager: Any, *, kb_id: str, pending_items: list[dict[str, Any]]) -> None:
    """在批量 persist 失败后回滚新写入内容，并尽量恢复被替换的 ref_doc。"""
    restored_doc_count = 0
    for item in pending_items:
        status = item.get("status")
        if status == "failed":
            continue

        for ref_doc_id in item.get("embedded_created_ref_doc_ids") or []:
            _delete_ref_doc_with_optional_persist(manager, ref_doc_id, persist=False)
        for ref_doc_id in item.get("created_ref_doc_ids") or []:
            _delete_ref_doc_with_optional_persist(manager, ref_doc_id, persist=False)

        replacement_snapshots = item.get("replacement_snapshots") or []
        replacement_refs = item.get("replacement_refs") or []
        if replacement_snapshots:
            _restore_ref_doc_snapshots(manager, replacement_snapshots)
            _restore_reimport_backup_file(item.get("path"), item.get("replacement_backup_bytes"))
            restored_doc_count += int(item.get("replacement_deleted_doc_count") or 0)
            continue

        if replacement_refs:
            _restore_reimport_backup_file(item.get("path"), item.get("replacement_backup_bytes"))
            continue

        target_path = item.get("path")
        if isinstance(target_path, Path):
            try:
                if target_path.exists() and target_path.is_file():
                    target_path.unlink()
            except OSError:
                pass

    if restored_doc_count > 0:
        _safe_add_doc_count(kb_id, restored_doc_count)



def _commit_reimport_replacements(
    manager: Any,
    *,
    kb_id: str,
    replacement_refs: list[dict[str, Any]] | None,
    persist: bool = True,
) -> dict[str, int]:
    """提交重导入替换操作，删除旧 ref_doc 并同步修正 doc_count。"""
    if not replacement_refs:
        return {"deleted_ref_doc_count": 0, "deleted_counted_doc_count": 0}

    deleted_ref_doc_count = 0
    deleted_counted_doc_count = 0
    seen_ref_doc_ids: set[str] = set()
    for item in replacement_refs:
        ref_doc_id = item.get("ref_doc_id")
        if not isinstance(ref_doc_id, str) or not ref_doc_id or ref_doc_id in seen_ref_doc_ids:
            continue
        seen_ref_doc_ids.add(ref_doc_id)
        if _delete_ref_doc_with_optional_persist(manager, ref_doc_id, persist=persist):
            deleted_ref_doc_count += 1
            if bool(item.get("counts_doc", False)):
                deleted_counted_doc_count += 1

    if deleted_counted_doc_count > 0:
        _safe_add_doc_count(kb_id, -deleted_counted_doc_count)
    return {
        "deleted_ref_doc_count": deleted_ref_doc_count,
        "deleted_counted_doc_count": deleted_counted_doc_count,
    }



def _build_import_receipt_id(prefix: str) -> str:
    """生成导入回执 ID，便于前后端串联一次导入批次。"""
    return f"{prefix}-{uuid4().hex}"


def get_latest_import_receipt(kb_id: str) -> dict[str, Any] | None:
    """读取指定知识库最近一次导入回执，并补齐展示摘要。"""
    safe_kb_id = validate_kb_id(kb_id)
    _ensure_kb_active(safe_kb_id)
    receipt = kb_import_receipt_store.load_latest_import_receipt(safe_kb_id)
    if not isinstance(receipt, dict):
        return receipt

    payload = dict(receipt)
    result = payload.get("result")
    if isinstance(result, dict):
        payload["result"] = _ensure_import_display_summary(dict(result))
    return payload



def _safe_int(value: Any, default: int = 0) -> int:
    """把任意值尽量稳定转换为 int，失败时返回默认值。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default



def _rank_count_items(
    counts: dict[str, Any] | None,
    *,
    name_key: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """把计数字典整理为按数量降序的展示列表。"""
    if not isinstance(counts, dict):
        return []

    items: list[dict[str, Any]] = []
    for raw_name, raw_count in counts.items():
        name = str(raw_name).strip()
        count = _safe_int(raw_count)
        if not name or count <= 0:
            continue
        items.append({name_key: name, "count": count})
    items.sort(key=lambda item: (-item["count"], item[name_key]))
    return items[:limit]



def _build_display_action(action: str, label: str, **extra: Any) -> dict[str, Any]:
    """构造导入回执中的建议操作项。"""
    payload = {"action": action, "label": label}
    payload.update({key: value for key, value in extra.items() if value is not None})
    return payload



def _build_file_import_display_summary(result: dict[str, Any]) -> dict[str, Any]:
    """构造文件导入结果的展示摘要，供前端回执直接渲染。"""
    file_results = result.get("file_results") or []
    diagnostics = result.get("diagnostics") or {}

    total_items = _safe_int(diagnostics.get("total_files"), len(file_results))
    indexed_items = _safe_int(diagnostics.get("indexed_files"), _safe_int(result.get("success_count")))
    empty_items = _safe_int(diagnostics.get("empty_files"), _safe_int(result.get("empty_count")))
    failed_items = _safe_int(diagnostics.get("failed_files"), _safe_int(result.get("failed_count")))
    asset_registered_count = _safe_int(diagnostics.get("asset_registered_count"))
    asset_warning_count = _safe_int(diagnostics.get("asset_warning_count"))
    asset_registered_but_not_indexed_count = sum(
        1
        for item in file_results
        if item.get("status") != "indexed" and bool((item.get("diagnostics") or {}).get("asset_registered"))
    )
    dependency_missing_count = _safe_int(diagnostics.get("dependency_missing_count"))
    top_missing_dependencies = _rank_count_items(
        diagnostics.get("missing_dependency_counts"),
        name_key="dependency",
    )
    top_empty_reasons = _rank_count_items(diagnostics.get("empty_reason_counts"), name_key="reason")

    has_dependency_issues = dependency_missing_count > 0 or bool(top_missing_dependencies)
    has_blockers = has_dependency_issues or failed_items > 0
    has_warnings = asset_warning_count > 0 or empty_items > 0 or asset_registered_but_not_indexed_count > 0

    if has_dependency_issues:
        affected_count = dependency_missing_count or sum(item["count"] for item in top_missing_dependencies)
        headline = f"{affected_count} 个文件因依赖缺失未完成导入"
        user_message = "请先安装缺失依赖后重试；详情可查看缺失依赖列表和失败项。"
    elif failed_items > 0:
        headline = f"{failed_items} 个文件导入失败"
        user_message = "请检查失败项中的错误信息，修复后重新导入。"
    elif asset_registered_but_not_indexed_count > 0:
        headline = f"{asset_registered_but_not_indexed_count} 个图片资产已入库但未索引"
        user_message = "图片资产已登记，但 OCR 尚未提取到可索引文本；可稍后补装 OCR 依赖或人工补录。"
    elif indexed_items == total_items and total_items > 0:
        headline = f"成功导入 {indexed_items} 个文件"
        user_message = "文件已完成解析并写入知识库。"
    elif empty_items > 0:
        headline = f"{empty_items} 个文件未提取到可索引内容"
        user_message = "请检查文件内容是否为空，或确认 OCR / PDF 解析依赖已正确安装。"
    else:
        headline = "导入已完成"
        user_message = "可查看导入明细，确认各文件的最终状态。"

    next_actions: list[dict[str, Any]] = []
    for item in top_missing_dependencies:
        dependency = item["dependency"]
        next_actions.append(
            _build_display_action(
                "install_dependency",
                f"安装缺失依赖：{dependency}",
                dependency=dependency,
                count=item["count"],
            )
        )
    if failed_items > 0:
        next_actions.append(
            _build_display_action(
                "review_failed_items",
                f"查看 {failed_items} 个失败项",
                count=failed_items,
            )
        )
    if asset_registered_but_not_indexed_count > 0:
        next_actions.append(
            _build_display_action(
                "review_empty_assets",
                f"查看 {asset_registered_but_not_indexed_count} 个未索引图片资产",
                count=asset_registered_but_not_indexed_count,
                top_empty_reasons=top_empty_reasons,
            )
        )
    elif empty_items > 0:
        next_actions.append(
            _build_display_action(
                "review_empty_items",
                f"查看 {empty_items} 个空结果文件",
                count=empty_items,
                top_empty_reasons=top_empty_reasons,
            )
        )

    return {
        "source_kind": "file_import",
        "item_label": "文件",
        "total_items": total_items,
        "indexed_items": indexed_items,
        "empty_items": empty_items,
        "failed_items": failed_items,
        "asset_registered_count": asset_registered_count,
        "asset_registered_but_not_indexed_count": asset_registered_but_not_indexed_count,
        "asset_warning_count": asset_warning_count,
        "dependency_missing_count": dependency_missing_count,
        "top_missing_dependencies": top_missing_dependencies,
        "top_empty_reasons": top_empty_reasons,
        "has_blockers": has_blockers,
        "has_dependency_issues": has_dependency_issues,
        "has_warnings": has_warnings,
        "headline": headline,
        "user_message": user_message,
        "next_actions": next_actions,
    }



def _build_url_import_display_summary(result: dict[str, Any]) -> dict[str, Any]:
    """构造 URL 导入结果的展示摘要。"""
    url_results = result.get("url_results") or []
    total_items = len(url_results) or len(result.get("urls") or [])
    indexed_items = sum(1 for item in url_results if item.get("status") == "indexed")
    empty_items = sum(1 for item in url_results if item.get("status") == "empty")
    failed_items = sum(1 for item in url_results if item.get("status") == "failed")
    has_blockers = failed_items > 0
    has_warnings = empty_items > 0

    if failed_items > 0:
        headline = f"{failed_items} 个 URL 导入失败"
        user_message = "请检查抓取结果和错误信息后重试。"
    elif indexed_items == total_items and total_items > 0:
        headline = f"成功导入 {indexed_items} 个 URL"
        user_message = "URL 内容已完成抓取并写入知识库。"
    elif empty_items > 0:
        headline = f"{empty_items} 个 URL 未提取到可索引内容"
        user_message = "请检查页面正文是否可访问，或页面内容是否为空。"
    else:
        headline = "URL 导入已完成"
        user_message = "可查看导入明细确认最终状态。"

    next_actions: list[dict[str, Any]] = []
    if failed_items > 0:
        next_actions.append(
            _build_display_action(
                "review_failed_items",
                f"查看 {failed_items} 个失败 URL",
                count=failed_items,
            )
        )
    elif empty_items > 0:
        next_actions.append(
            _build_display_action(
                "review_empty_items",
                f"查看 {empty_items} 个空结果 URL",
                count=empty_items,
            )
        )

    return {
        "source_kind": "url_import",
        "item_label": "URL",
        "total_items": total_items,
        "indexed_items": indexed_items,
        "empty_items": empty_items,
        "failed_items": failed_items,
        "asset_registered_count": 0,
        "asset_registered_but_not_indexed_count": 0,
        "asset_warning_count": 0,
        "dependency_missing_count": 0,
        "top_missing_dependencies": [],
        "top_empty_reasons": [],
        "has_blockers": has_blockers,
        "has_dependency_issues": False,
        "has_warnings": has_warnings,
        "headline": headline,
        "user_message": user_message,
        "next_actions": next_actions,
    }



def _ensure_import_display_summary(result: dict[str, Any]) -> dict[str, Any]:
    """确保导入结果始终包含 display_summary，便于前端稳定渲染。"""
    if not isinstance(result, dict):
        return result
    display_summary = result.get("display_summary")
    if isinstance(display_summary, dict):
        return result

    payload = dict(result)
    if isinstance(payload.get("file_results"), list):
        payload["display_summary"] = _build_file_import_display_summary(payload)
    elif isinstance(payload.get("url_results"), list):
        payload["display_summary"] = _build_url_import_display_summary(payload)
    else:
        payload["display_summary"] = {
            "source_kind": "unknown",
            "item_label": "项目",
            "total_items": 0,
            "indexed_items": 0,
            "empty_items": 0,
            "failed_items": 0,
            "asset_registered_count": 0,
            "asset_registered_but_not_indexed_count": 0,
            "asset_warning_count": 0,
            "dependency_missing_count": 0,
            "top_missing_dependencies": [],
            "top_empty_reasons": [],
            "has_blockers": False,
            "has_dependency_issues": False,
            "has_warnings": False,
            "headline": "导入结果已生成",
            "user_message": "可查看导入明细确认状态。",
            "next_actions": [],
        }
    return payload



def _resolve_persisted_file_path(path: Path | None) -> str | None:
    """返回已落盘文件的绝对路径；如果文件不存在或无法访问则返回 None。"""
    if path is None:
        return None
    try:
        if path.exists() and path.is_file():
            return str(path.resolve())
    except OSError:
        return None
    return None



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
    embedded_assets: list[dict[str, Any]] | None = None,
    asset_warning_count: int = 0,
    ocr_diagnostics: dict[str, Any] | None = None,
    failure_diagnostics: dict[str, Any] | None = None,
    ingestion_diagnostics: dict[str, Any] | None = None,
    stage_timings: dict[str, float] | None = None,
    skip_standalone_asset: bool = False,
    file_kind_override: str | None = None,
) -> dict[str, Any]:
    """构造单文件导入结果，统一补齐 OCR、资产与诊断字段。"""
    embedded_asset_items = embedded_assets or []
    result = {
        "name": filename,
        "type": content_type,
        "size": size,
        "path": _resolve_persisted_file_path(path),
        "kb_id": kb_id,
        "status": status,
        "indexed_chunks": indexed_chunks,
        "relative_path": relative_path,
        "folder_path": folder_path,
        "embedded_assets": embedded_asset_items,
        "asset_warning_count": asset_warning_count,
        "diagnostics": _build_file_diagnostics(
            path=path,
            content_type=content_type,
            status=status,
            embedded_assets=embedded_asset_items,
            ocr_diagnostics=ocr_diagnostics,
            failure_diagnostics=failure_diagnostics,
            ingestion_diagnostics=ingestion_diagnostics,
            stage_timings=stage_timings,
            skip_standalone_asset=skip_standalone_asset,
            file_kind_override=file_kind_override,
        ),
    }
    if message is not None:
        result["message"] = message
    return result



def _is_markdown_file(path: Path | None, content_type: str) -> bool:
    """判断当前文件是否需要做 Markdown 内嵌资产解析。"""
    if path is not None and path.suffix.lower() in MARKDOWN_SUFFIXES:
        return True
    return content_type.lower().startswith("text/markdown")


def _is_image_file(path: Path | None, content_type: str) -> bool:
    """判断文件是否应视为图片资产候选。"""
    if path is not None and path.suffix.lower() in IMAGE_SUFFIXES:
        return True
    return content_type.lower().startswith("image/")


def _decoded_text_looks_reasonable(text: str) -> bool:
    """判断解码后的文本是否仍像可索引文本，而不是控制字符噪声。"""
    if not text:
        return True
    disallowed_controls = sum(1 for char in text if ord(char) < 32 and char not in _TEXT_CONTROL_CHARS)
    return disallowed_controls / len(text) <= 0.05


def _looks_like_utf16_text(sample: bytes) -> bool:
    """仅在 BOM 或零字节分布明显时，才把无后缀内容视为 UTF-16 文本。"""
    if len(sample) < 2:
        return False

    encoding = None
    if sample.startswith((b"\xff\xfe", b"\xfe\xff")):
        encoding = "utf-16"
    else:
        even_bytes = sample[0::2]
        odd_bytes = sample[1::2]
        even_zero_ratio = even_bytes.count(0) / len(even_bytes) if even_bytes else 0.0
        odd_zero_ratio = odd_bytes.count(0) / len(odd_bytes) if odd_bytes else 0.0
        if max(even_zero_ratio, odd_zero_ratio) < 0.3:
            return False
        encoding = "utf-16-le" if odd_zero_ratio >= even_zero_ratio else "utf-16-be"

    try:
        decoded = sample.decode(encoding)
    except UnicodeDecodeError:
        return False
    return _decoded_text_looks_reasonable(decoded)


def _looks_like_text_payload(content: bytes | None) -> bool:
    """判断无后缀无 MIME 内容是否像可索引文本。"""
    if content is None:
        return False
    sample = content[:8192]
    if not sample:
        return True

    for encoding in ("utf-8", "utf-8-sig"):
        try:
            decoded = sample.decode(encoding)
        except UnicodeDecodeError:
            continue
        if _decoded_text_looks_reasonable(decoded):
            return True

    return _looks_like_utf16_text(sample)


def _looks_like_binary_payload(content: bytes | None) -> bool:
    """判断无后缀无 MIME 内容是否明显属于二进制字节流。"""
    if content is None:
        return False
    sample = content[:8192]
    if not sample:
        return False
    if _looks_like_text_payload(sample):
        return False
    if b"\x00" in sample:
        return True

    disallowed_controls = sum(1 for byte in sample if byte < 32 and byte not in _TEXT_CONTROL_CHAR_BYTES)
    return disallowed_controls / len(sample) >= 0.1


def _detect_file_kind_from_content_signature(content: bytes | None) -> str | None:
    """基于常见文件头特征识别无后缀无 MIME 的已支持文件类型。"""
    if not content:
        return None

    sample = content[:32]
    if sample.startswith(b"%PDF-"):
        return "pdf"
    if sample.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image"
    if sample.startswith(b"\xff\xd8\xff"):
        return "image"
    if sample.startswith((b"GIF87a", b"GIF89a")):
        return "image"
    if sample.startswith(b"BM"):
        return "image"
    if len(sample) >= 12 and sample[:4] == b"RIFF" and sample[8:12] == b"WEBP":
        return "image"
    return None


def _detect_file_kind(path: Path | None, content_type: str, content: bytes | None = None) -> str:
    """基于文件名后缀、MIME 类型与必要时的内容嗅探推断导入文件类别。"""
    if _is_markdown_file(path, content_type):
        return "markdown"
    if _is_image_file(path, content_type):
        return "image"

    lower_content_type = str(content_type or "").strip().lower()
    suffix = path.suffix.lower() if path is not None else ""
    if suffix == ".pdf" or lower_content_type == "application/pdf":
        return "pdf"
    if lower_content_type.startswith("text/") or suffix in {".txt", ".csv", ".json", ".xml", ".yaml", ".yml", ".html", ".htm", ".rst", ".log"}:
        return "text"
    if not suffix and lower_content_type in _CONTENT_SNIFF_FALLBACK_MIME_TYPES:
        signature_kind = _detect_file_kind_from_content_signature(content)
        if signature_kind is not None:
            return signature_kind
        if _looks_like_text_payload(content):
            return "text"
        if _looks_like_binary_payload(content):
            return "binary"
    if lower_content_type:
        return "binary"
    if suffix:
        return "binary"
    return "unknown"

def _is_rejected_file_kind(file_kind: str) -> bool:
    """判断当前文件类型是否应在导入入口直接拒绝。"""
    return file_kind == "binary"


def _build_unsupported_file_type_message(*, path: Path | None, content_type: str) -> str:
    """构造不支持文件类型时的用户提示。"""
    suffix = path.suffix.lower() if path is not None else ""
    content_type_label = content_type.strip()
    detail_parts = []
    if suffix:
        detail_parts.append(suffix)
    if content_type_label:
        detail_parts.append(content_type_label)
    detail = f"（{' / '.join(detail_parts)}）" if detail_parts else ""
    return f"暂不支持该文件类型导入{detail}，请上传 Markdown、PDF、文本或图片文件"


def _extract_image_ocr_result(path: Path, content_type: str) -> dict[str, Any]:
    """对支持的图片文件执行 OCR，返回统一结果。"""
    from server.readers.image_ocr import extract_image_ocr_result

    return extract_image_ocr_result(path, content_type=content_type)


def _new_ocr_runtime_diagnostics() -> dict[str, Any]:
    """创建 OCR 运行时诊断的稳定默认结构。"""
    diagnostics = {key: 0.0 for key in OCR_RUNTIME_FLOAT_KEYS}
    diagnostics["ocr_instance_reused"] = False
    return diagnostics


def _extract_ocr_runtime_diagnostics(source: dict[str, Any] | None) -> dict[str, Any]:
    """提取 OCR 运行时耗时与实例复用诊断字段。"""
    payload = _new_ocr_runtime_diagnostics()
    if not isinstance(source, dict):
        return payload

    for key in OCR_RUNTIME_FLOAT_KEYS:
        try:
            payload[key] = float(source.get(key) or 0.0)
        except (TypeError, ValueError):
            payload[key] = 0.0
    payload["ocr_instance_reused"] = bool(source.get("ocr_instance_reused", False))
    return payload



def _extract_pdf_ocr_diagnostics_from_source(
    ingestion_diagnostics: dict[str, Any] | None,
    *,
    target_path: Path | None,
) -> dict[str, Any] | None:
    """从文件级 ingestion diagnostics 中提取 PDF OCR 诊断。"""
    if not isinstance(ingestion_diagnostics, dict):
        return None

    source_items = ingestion_diagnostics.get("source_file_diagnostics")
    if not isinstance(source_items, list) or not source_items:
        return None

    resolved_target = str(target_path.resolve()) if target_path is not None else None
    selected = None
    for item in source_items:
        if not isinstance(item, dict):
            continue
        source_type = item.get("source_type")
        if source_type not in {"pdf_text_layer", "pdf_ocr_fallback"}:
            continue
        if resolved_target is None or item.get("file_path") == resolved_target:
            selected = item
            break
    if selected is None:
        return None

    payload = {
        "ocr_attempted": bool(selected.get("ocr_attempted", False)),
        "ocr_status": selected.get("ocr_status"),
        "ocr_text_length": int(selected.get("ocr_text_length") or 0),
        "ocr_error": selected.get("ocr_error"),
        "indexed_from_ocr": bool(selected.get("indexed_from_ocr", False)),
        "ocr_engine": selected.get("ocr_engine"),
        **_extract_failure_diagnostics(selected),
        **_extract_ocr_runtime_diagnostics(selected),
    }
    if selected.get("source_type") == "pdf_ocr_fallback":
        payload["ocr_attempted"] = True
        if payload["ocr_status"] is None:
            payload["ocr_status"] = "success" if payload["indexed_from_ocr"] else "no_text"
        if payload["ocr_engine"] is None:
            payload["ocr_engine"] = "paddleocr"
    return payload


def _new_failure_diagnostics() -> dict[str, Any]:
    """创建失败诊断的稳定默认结构。"""
    return {
        "failure_category": None,
        "missing_dependency": None,
        "dependency_status": "unknown",
    }



def _canonicalize_dependency_name(raw_name: Any) -> str | None:
    """规范化依赖名，兼容 PyMuPDF / fitz 等别名。"""
    if raw_name is None:
        return None
    name = str(raw_name).strip().lower()
    if not name:
        return None
    alias_map = {
        "pymupdf": "fitz",
        "fitz": "fitz",
        "paddleocr": "paddleocr",
        "paddle": "paddle",
        "paddlepaddle": "paddle",
        "pil": "pillow",
        "pillow": "pillow",
    }
    return alias_map.get(name, name)



def _infer_missing_dependency(exc: Exception | None = None, message: str | None = None) -> str | None:
    """从异常对象或错误文案中推断缺失依赖。"""
    exc_name = _canonicalize_dependency_name(getattr(exc, "name", None)) if exc is not None else None
    if exc_name:
        return exc_name

    text = str(message or exc or "")
    lowered = text.lower()
    if "pymupdf" in lowered or "fitz" in lowered:
        return "fitz"
    if "paddleocr" in lowered:
        return "paddleocr"
    if "paddlepaddle" in lowered or "no module named 'paddle'" in lowered or 'no module named "paddle"' in lowered:
        return "paddle"
    if "pillow" in lowered or "pil" in lowered:
        return "pillow"

    match = re.search(r'no module named [\'"]([^\'"]+)[\'"]', text, re.IGNORECASE)
    if match:
        return _canonicalize_dependency_name(match.group(1))
    return None



def _dependency_display_name(dependency: str | None) -> str | None:
    """返回适合展示给用户的依赖名称。"""
    normalized = _canonicalize_dependency_name(dependency)
    label_map = {
        "fitz": "PyMuPDF（fitz）",
        "paddleocr": "paddleocr",
        "paddle": "paddlepaddle",
        "pillow": "Pillow（PIL）",
    }
    return label_map.get(normalized, normalized)



def _build_dependency_missing_message(dependency: str | None, *, file_kind: str | None = None) -> str | None:
    """为缺失依赖场景生成更可读的失败文案。"""
    normalized = _canonicalize_dependency_name(dependency)
    if normalized == "fitz":
        return "缺少 PyMuPDF（fitz）依赖，暂时无法解析 PDF 文件"
    if normalized == "paddleocr":
        return "缺少 paddleocr 依赖，暂时无法执行图片 OCR"
    if normalized == "paddle":
        return "缺少 paddlepaddle 依赖，暂时无法执行图片 OCR"
    if normalized == "pillow":
        return "缺少 Pillow（PIL）依赖，暂时无法加载图片文件"

    display_name = _dependency_display_name(normalized)
    if display_name is None:
        return None
    if file_kind == "image":
        return f"缺少 {display_name} 依赖，暂时无法处理图片文件"
    return f"缺少 {display_name} 依赖，请安装后重试"



def _build_failure_message(
    exc: Exception | None,
    *,
    failure_diagnostics: dict[str, Any] | None = None,
    file_kind: str | None = None,
) -> str:
    """构造用户可读的导入失败消息。"""
    diagnostics = _extract_failure_diagnostics(failure_diagnostics)
    message = _build_dependency_missing_message(diagnostics.get("missing_dependency"), file_kind=file_kind)
    if message:
        return message

    raw_message = str(exc or "").strip()
    if raw_message:
        return raw_message
    return "文件导入失败，请检查日志后重试"



def _build_exception_failure_diagnostics(
    exc: Exception | None,
    *,
    default_category: str | None = None,
    dependency_status: str = "unknown",
) -> dict[str, Any]:
    """根据异常生成失败诊断。"""
    payload = _new_failure_diagnostics()
    missing_dependency = _infer_missing_dependency(exc=exc)
    if missing_dependency is not None:
        payload["failure_category"] = "dependency_missing"
        payload["missing_dependency"] = missing_dependency
        payload["dependency_status"] = "missing"
        return payload

    payload["failure_category"] = default_category
    payload["dependency_status"] = dependency_status
    return payload



def _extract_failure_diagnostics(
source: dict[str, Any] | None) -> dict[str, Any]:
    """从任意诊断对象中提取统一失败诊断结构。"""
    payload = _new_failure_diagnostics()
    if not isinstance(source, dict):
        return payload

    failure_category = source.get("failure_category")
    if isinstance(failure_category, str) and failure_category:
        payload["failure_category"] = failure_category

    missing_dependency = _canonicalize_dependency_name(source.get("missing_dependency"))
    if missing_dependency is not None:
        payload["missing_dependency"] = missing_dependency

    dependency_status = source.get("dependency_status")
    if isinstance(dependency_status, str) and dependency_status:
        payload["dependency_status"] = dependency_status

    if payload["missing_dependency"] is not None:
        payload["failure_category"] = "dependency_missing"
        payload["dependency_status"] = "missing"
    return payload



def _resolve_file_failure_diagnostics(
    *,
    file_kind: str,
    status: str,
    ocr_info: dict[str, Any],
    failure_diagnostics: dict[str, Any] | None,
) -> dict[str, Any]:
    """合并文件级失败信息与 OCR 失败信息，得到最终诊断。"""
    resolved = _extract_failure_diagnostics(failure_diagnostics)
    ocr_failure = _extract_failure_diagnostics(ocr_info)

    for key in ("failure_category", "missing_dependency"):
        if resolved.get(key) is None and ocr_failure.get(key) is not None:
            resolved[key] = ocr_failure[key]
    if resolved.get("dependency_status") == "unknown" and ocr_failure.get("dependency_status") != "unknown":
        resolved["dependency_status"] = ocr_failure["dependency_status"]

    if resolved["missing_dependency"] is not None:
        resolved["failure_category"] = "dependency_missing"
        resolved["dependency_status"] = "missing"
        return resolved

    if resolved["failure_category"] is None:
        if file_kind == "image" and ocr_info.get("ocr_status") == "failed":
            resolved["failure_category"] = "ocr_runtime_error"
        elif status == "failed":
            resolved["failure_category"] = "indexing_error"

    if resolved["dependency_status"] == "unknown":
        if resolved["failure_category"] == "dependency_missing":
            resolved["dependency_status"] = "missing"
        elif ocr_info.get("ocr_attempted") or ocr_info.get("ocr_engine"):
            resolved["dependency_status"] = "ready"

    return resolved


def _build_ocr_index_document(*, text: str, metadata: dict[str, Any]) -> Document:
    """为 OCR 派生文本补齐 metadata 排除策略，避免小 chunk_size 被元数据挤爆。"""
    normalized_metadata = {key: value for key, value in metadata.items() if value is not None}
    excluded_keys = [key for key in OCR_INDEX_EXCLUDED_METADATA_KEYS if key in normalized_metadata]
    return Document(
        text=text,
        metadata=normalized_metadata,
        excluded_embed_metadata_keys=excluded_keys,
        excluded_llm_metadata_keys=excluded_keys,
    )


def _build_image_ocr_document(
    *,
    kb_id: str,
    path: Path,
    filename: str,
    content_type: str,
    relative_path: str | None,
    ocr_result: dict[str, Any],
) -> Document | None:
    """根据 OCR 结果构造派生文本 Document，用于后续切块入索引。"""
    text = str(ocr_result.get("text") or "").strip()
    if not text:
        return None

    resolved_path = path.resolve()
    asset_id = asset_service._build_standalone_asset_id(kb_id, relative_path, str(resolved_path), filename)
    metadata = {
        "kb_id": kb_id,
        "asset_id": asset_id,
        "source_type": "image_ocr",
        "file_path": str(resolved_path),
        "relative_path": relative_path,
        "file_name": filename,
        "mime_type": content_type or "application/octet-stream",
        "ocr_engine": ocr_result.get("engine"),
    }
    return _build_ocr_index_document(text=text, metadata=metadata)


def _is_embedded_image_ocr_candidate(asset: dict[str, Any]) -> bool:
    """判断 Markdown 内嵌资产是否满足 OCR 尝试条件。"""
    if asset.get("status") != "ready":
        return False
    if asset.get("asset_type") != "image":
        return False

    asset_path = asset.get("path")
    suffix = Path(str(asset_path)).suffix.lower() if asset_path else ""
    mime_type = str(asset.get("mime_type") or "").lower()
    return suffix in OCR_IMAGE_SUFFIXES or mime_type.startswith("image/")


def _build_embedded_image_ocr_document(*, kb_id: str, asset: dict[str, Any], ocr_result: dict[str, Any]) -> Document | None:
    """基于内嵌图片 OCR 结果生成可索引的派生文本 Document。"""
    text = str(ocr_result.get("text") or "").strip()
    asset_path = asset.get("path")
    if not text or not isinstance(asset_path, str) or not asset_path:
        return None

    resolved_path = Path(asset_path).resolve()
    metadata = {
        "kb_id": kb_id,
        "asset_id": asset.get("asset_id"),
        "source_type": "image_ocr",
        "file_path": str(resolved_path),
        "relative_path": asset.get("resolved_relative_path"),
        "file_name": resolved_path.name,
        "mime_type": asset.get("mime_type") or "application/octet-stream",
        "ocr_engine": ocr_result.get("engine"),
        "source_doc_path": asset.get("source_doc_path"),
        "source_doc_relative_path": asset.get("source_doc_relative_path"),
        "referenced_path": asset.get("referenced_path"),
        "occurrence_index": asset.get("occurrence_index"),
    }
    return _build_ocr_index_document(text=text, metadata=metadata)


def _index_embedded_image_assets(
    *,
    manager_getter: Callable[[], Any],
    kb_id: str,
    embedded_assets: list[dict[str, Any]],
    chunk_size: int,
    chunk_overlap: int,
    stage_targets: tuple[dict[str, float], ...] = (),
    ingestion_targets: tuple[dict[str, Any], ...] = (),
    persist: bool = True,
) -> int:
    """为 Markdown 内嵌图片执行 OCR 入索引，并累计对应阶段耗时。"""
    total_indexed_chunks = 0
    manager = None
    for asset in embedded_assets:
        asset["indexed_chunks"] = int(asset.get("indexed_chunks") or 0)
        asset["indexed_from_ocr"] = bool(asset.get("indexed_from_ocr", False))

        if not _is_embedded_image_ocr_candidate(asset):
            continue

        asset_path = asset.get("path")
        if not isinstance(asset_path, str) or not asset_path:
            continue

        ocr_started_at = time.perf_counter()
        try:
            ocr_result = _extract_image_ocr_result(Path(asset_path), str(asset.get("mime_type") or ""))
        except Exception as exc:
            _add_stage_elapsed(stage_targets, "embedded_asset_ocr_ms", ocr_started_at)
            asset["ocr_diagnostics"] = {
                "ocr_attempted": True,
                "ocr_status": "failed",
                "ocr_text_length": 0,
                "ocr_error": str(exc),
                "indexed_from_ocr": False,
                "ocr_engine": None,
                **_build_exception_failure_diagnostics(exc, default_category="ocr_runtime_error"),
                **_new_ocr_runtime_diagnostics(),
            }
            continue
        _add_stage_elapsed(stage_targets, "embedded_asset_ocr_ms", ocr_started_at)

        ocr_diagnostics = {
            "ocr_attempted": bool(ocr_result.get("attempted", False)),
            "ocr_status": ocr_result.get("status", "skipped"),
            "ocr_text_length": len(str(ocr_result.get("text") or "")),
            "ocr_error": ocr_result.get("error"),
            "indexed_from_ocr": False,
            "ocr_engine": ocr_result.get("engine"),
            **_extract_failure_diagnostics(ocr_result),
            **_extract_ocr_runtime_diagnostics(ocr_result),
        }
        asset["ocr_diagnostics"] = ocr_diagnostics

        document = _build_embedded_image_ocr_document(kb_id=kb_id, asset=asset, ocr_result=ocr_result)
        if document is None:
            continue

        index_started_at = time.perf_counter()
        try:
            if manager is None:
                manager = manager_getter()
            nodes = manager.load_documents([document], chunk_size, chunk_overlap, kb_id=kb_id, persist=persist) or []
            _consume_manager_ingestion_diagnostics(manager, *ingestion_targets)
        except Exception as exc:
            _add_stage_elapsed(stage_targets, "embedded_asset_index_ms", index_started_at)
            asset["ocr_diagnostics"] = {
                **ocr_diagnostics,
                "ocr_status": "failed",
                "ocr_error": str(exc),
                "indexed_from_ocr": False,
                **_build_exception_failure_diagnostics(exc, default_category="indexing_error", dependency_status="ready"),
            }
            continue
        _add_stage_elapsed(stage_targets, "embedded_asset_index_ms", index_started_at)

        chunk_count = len(nodes)
        asset["indexed_chunks"] = chunk_count
        asset["indexed_from_ocr"] = chunk_count > 0
        asset["ocr_diagnostics"]["indexed_from_ocr"] = chunk_count > 0
        total_indexed_chunks += chunk_count

    return total_indexed_chunks


def _summarize_embedded_assets(embedded_assets: list[dict[str, Any]] | None) -> dict[str, int]:
    """汇总 Markdown 内嵌资产的 ready/missing/invalid 状态。"""
    assets = embedded_assets or []
    summary = {
        "embedded_asset_count": len(assets),
        "embedded_asset_ready_count": 0,
        "embedded_asset_missing_count": 0,
        "embedded_asset_invalid_count": 0,
    }
    for item in assets:
        status = item.get("status")
        if status == "ready":
            summary["embedded_asset_ready_count"] += 1
        elif status == "missing":
            summary["embedded_asset_missing_count"] += 1
        elif status == "invalid":
            summary["embedded_asset_invalid_count"] += 1
    return summary


def _summarize_embedded_asset_ocr(embedded_assets: list[dict[str, Any]] | None) -> dict[str, int]:
    """汇总 Markdown 内嵌资产 OCR 的尝试结果与入索引情况。"""
    summary = {
        "embedded_ocr_attempted_count": 0,
        "embedded_ocr_success_count": 0,
        "embedded_ocr_no_text_count": 0,
        "embedded_ocr_failed_count": 0,
        "embedded_ocr_skipped_count": 0,
        "embedded_indexed_from_ocr_count": 0,
    }
    for item in embedded_assets or []:
        ocr_info = item.get("ocr_diagnostics") or {}
        if ocr_info.get("ocr_attempted"):
            summary["embedded_ocr_attempted_count"] += 1

        ocr_status = ocr_info.get("ocr_status")
        if ocr_status == "success":
            summary["embedded_ocr_success_count"] += 1
        elif ocr_status == "no_text":
            summary["embedded_ocr_no_text_count"] += 1
        elif ocr_status == "failed":
            summary["embedded_ocr_failed_count"] += 1
        elif ocr_status == "skipped":
            summary["embedded_ocr_skipped_count"] += 1

        if ocr_info.get("indexed_from_ocr") or item.get("indexed_from_ocr"):
            summary["embedded_indexed_from_ocr_count"] += 1
    return summary


def _build_file_diagnostics(
    *,
    path: Path | None,
    content_type: str,
    status: str,
    embedded_assets: list[dict[str, Any]] | None = None,
    ocr_diagnostics: dict[str, Any] | None = None,
    failure_diagnostics: dict[str, Any] | None = None,
    ingestion_diagnostics: dict[str, Any] | None = None,
    stage_timings: dict[str, float] | None = None,
    skip_standalone_asset: bool = False,
    file_kind_override: str | None = None,
) -> dict[str, Any]:
    """构建单文件 diagnostics，并补齐 empty 场景的原因字段。"""
    file_kind = file_kind_override or _detect_file_kind(path, content_type)
    embedded_summary = _summarize_embedded_assets(embedded_assets)
    embedded_ocr_summary = _summarize_embedded_asset_ocr(embedded_assets)
    ocr_info = dict(ocr_diagnostics or {})
    failure_info = _resolve_file_failure_diagnostics(
        file_kind=file_kind,
        status=status,
        ocr_info=ocr_info,
        failure_diagnostics=failure_diagnostics,
    )
    ingestion_summary = _new_ingestion_diagnostics_summary()
    _merge_ingestion_diagnostics(ingestion_summary, ingestion_diagnostics)

    empty_reason = None
    if status == "empty":
        if file_kind == "image":
            if skip_standalone_asset:
                empty_reason = "shadowed_by_embedded_asset"
            else:
                ocr_status = ocr_info.get("ocr_status")
                if ocr_status == "failed":
                    empty_reason = "ocr_failed"
                elif ocr_status == "skipped":
                    empty_reason = "ocr_skipped"
                else:
                    empty_reason = "no_extractable_text"
        elif embedded_ocr_summary["embedded_ocr_attempted_count"] > 0:
            if embedded_ocr_summary["embedded_ocr_failed_count"] > 0:
                empty_reason = "embedded_ocr_failed"
            elif embedded_ocr_summary["embedded_ocr_no_text_count"] > 0:
                empty_reason = "embedded_no_extractable_text"
            else:
                empty_reason = "embedded_ocr_no_nodes"
        else:
            empty_reason = "no_nodes_generated"

    asset_registered = False
    if status in {"indexed", "empty"}:
        asset_registered = (
            (file_kind == "image" and not skip_standalone_asset)
            or embedded_summary["embedded_asset_count"] > 0
        )

    diagnostics = {
        "file_kind": file_kind,
        "empty_reason": empty_reason,
        "standalone_asset_candidate": file_kind == "image",
        "skip_standalone_asset": bool(skip_standalone_asset),
        "file_retained_on_disk": _resolve_persisted_file_path(path) is not None,
        "ocr_attempted": bool(ocr_info.get("ocr_attempted", False)),
        "ocr_status": ocr_info.get("ocr_status"),
        "ocr_text_length": int(ocr_info.get("ocr_text_length") or 0),
        "ocr_error": ocr_info.get("ocr_error"),
        "indexed_from_ocr": bool(ocr_info.get("indexed_from_ocr", False)),
        "asset_registered": asset_registered,
        "stage_timings": dict(stage_timings or {}),
        "document_count": int(ingestion_summary.get("document_count") or 0),
        "empty_document_count": int(ingestion_summary.get("empty_document_count") or 0),
        "input_text_chars": int(ingestion_summary.get("input_text_chars") or 0),
        "node_count": int(ingestion_summary.get("node_count") or 0),
        "nodes_with_embedding_count": int(ingestion_summary.get("nodes_with_embedding_count") or 0),
        "nodes_without_embedding_count": int(ingestion_summary.get("nodes_without_embedding_count") or 0),
        "index_stage_timings": dict(ingestion_summary.get("index_stage_timings") or _new_index_stage_timings()),
        **failure_info,
        **_extract_ocr_runtime_diagnostics(ocr_info),
    }
    if ocr_info.get("ocr_engine"):
        diagnostics["ocr_engine"] = ocr_info["ocr_engine"]
    diagnostics.update(embedded_summary)
    diagnostics.update(embedded_ocr_summary)
    return diagnostics


def _aggregate_import_diagnostics(
    file_results: list[dict[str, Any]],
    *,
    stage_timings: dict[str, float] | None = None,
) -> dict[str, Any]:
    """聚合批次级 diagnostics，生成导入结果摘要。"""
    summary: dict[str, Any] = {
        "total_files": len(file_results),
        "indexed_files": 0,
        "empty_files": 0,
        "failed_files": 0,
        "standalone_asset_candidate_count": 0,
        "embedded_asset_count": 0,
        "embedded_asset_ready_count": 0,
        "embedded_asset_missing_count": 0,
        "embedded_asset_invalid_count": 0,
        "asset_warning_count": 0,
        "ocr_success_count": 0,
        "ocr_no_text_count": 0,
        "ocr_failed_count": 0,
        "ocr_skipped_count": 0,
        "indexed_from_ocr_count": 0,
        "embedded_ocr_attempted_count": 0,
        "embedded_ocr_success_count": 0,
        "embedded_ocr_no_text_count": 0,
        "embedded_ocr_failed_count": 0,
        "embedded_ocr_skipped_count": 0,
        "embedded_indexed_from_ocr_count": 0,
        "asset_registered_count": 0,
        "skip_standalone_asset_count": 0,
        "empty_reason_counts": {},
        "failure_category_counts": {},
        "dependency_status_counts": {},
        "dependency_missing_count": 0,
        "missing_dependency_counts": {},
        "stage_timings": dict(stage_timings or {}),
        **_new_ingestion_diagnostics_summary(),
    }

    for item in file_results:
        status = item.get("status")
        if status == "indexed":
            summary["indexed_files"] += 1
        elif status == "empty":
            summary["empty_files"] += 1
        elif status == "failed":
            summary["failed_files"] += 1

        diagnostics = item.get("diagnostics") or {}
        _merge_ingestion_diagnostics(summary, diagnostics)
        if diagnostics.get("standalone_asset_candidate"):
            summary["standalone_asset_candidate_count"] += 1
        if diagnostics.get("skip_standalone_asset"):
            summary["skip_standalone_asset_count"] += 1
        empty_reason = diagnostics.get("empty_reason")
        if isinstance(empty_reason, str) and empty_reason:
            summary["empty_reason_counts"][empty_reason] = int(summary["empty_reason_counts"].get(empty_reason) or 0) + 1

        failure_category = diagnostics.get("failure_category")
        if isinstance(failure_category, str) and failure_category:
            summary["failure_category_counts"][failure_category] = (
                int(summary["failure_category_counts"].get(failure_category) or 0) + 1
            )
            if failure_category == "dependency_missing":
                summary["dependency_missing_count"] += 1

        dependency_status = diagnostics.get("dependency_status")
        if isinstance(dependency_status, str) and dependency_status:
            summary["dependency_status_counts"][dependency_status] = (
                int(summary["dependency_status_counts"].get(dependency_status) or 0) + 1
            )

        missing_dependency = diagnostics.get("missing_dependency")
        if isinstance(missing_dependency, str) and missing_dependency:
            summary["missing_dependency_counts"][missing_dependency] = (
                int(summary["missing_dependency_counts"].get(missing_dependency) or 0) + 1
            )

        summary["embedded_asset_count"] += int(diagnostics.get("embedded_asset_count") or 0)
        summary["embedded_asset_ready_count"] += int(diagnostics.get("embedded_asset_ready_count") or 0)
        summary["embedded_asset_missing_count"] += int(diagnostics.get("embedded_asset_missing_count") or 0)
        summary["embedded_asset_invalid_count"] += int(diagnostics.get("embedded_asset_invalid_count") or 0)
        summary["asset_warning_count"] += int(item.get("asset_warning_count") or 0)

        ocr_status = diagnostics.get("ocr_status")
        if ocr_status == "success":
            summary["ocr_success_count"] += 1
        elif ocr_status == "no_text":
            summary["ocr_no_text_count"] += 1
        elif ocr_status == "failed":
            summary["ocr_failed_count"] += 1
        elif ocr_status == "skipped":
            summary["ocr_skipped_count"] += 1

        if diagnostics.get("indexed_from_ocr"):
            summary["indexed_from_ocr_count"] += 1

        summary["embedded_ocr_attempted_count"] += int(diagnostics.get("embedded_ocr_attempted_count") or 0)
        summary["embedded_ocr_success_count"] += int(diagnostics.get("embedded_ocr_success_count") or 0)
        summary["embedded_ocr_no_text_count"] += int(diagnostics.get("embedded_ocr_no_text_count") or 0)
        summary["embedded_ocr_failed_count"] += int(diagnostics.get("embedded_ocr_failed_count") or 0)
        summary["embedded_ocr_skipped_count"] += int(diagnostics.get("embedded_ocr_skipped_count") or 0)
        summary["embedded_indexed_from_ocr_count"] += int(diagnostics.get("embedded_indexed_from_ocr_count") or 0)

        if diagnostics.get("asset_registered"):
            summary["asset_registered_count"] += 1

    return summary



def _extract_embedded_assets_for_file(
    *,
    path: Path | None,
    kb_dir: Path,
    relative_path: str | None,
    content_type: str,
    path_aliases: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """提取 Markdown 文件中的内嵌本地图片资产；失败时不阻断主导入。"""
    if path is None or not path.exists() or not _is_markdown_file(path, content_type):
        return [], 0
    try:
        assets = extract_markdown_embedded_assets_from_file(
            source_doc_path=path,
            kb_root=kb_dir,
            source_doc_relative_path=relative_path,
            path_aliases=path_aliases,
        )
    except Exception:
        return [], 0
    warning_count = sum(1 for item in assets if item.get("status") != "ready")
    return assets, warning_count


def _validate_import_mode(import_mode: str) -> str:
    """校验导入模式，仅允许 preserve_tree 与 flatten。"""
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


def _normalize_import_path_alias(path_value: str | None) -> str | None:
    """把导入期路径别名标准化为 KB 内部使用的相对路径键。"""
    if not isinstance(path_value, str):
        return None

    raw = path_value.strip().replace("\\", "/")
    if not raw:
        return None
    if raw.startswith("/") or (len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha()):
        return None

    parts: list[str] = []
    for part in raw.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
            continue
        parts.append(part)

    if not parts:
        return None
    return "/".join(parts)


def _register_import_path_alias(alias_targets: dict[str, set[str]], alias_key: str | None, actual_relative_path: str) -> None:
    """记录导入期路径别名，后续仅对唯一映射启用修复。"""
    normalized_key = _normalize_import_path_alias(alias_key)
    if normalized_key is None:
        return
    alias_targets.setdefault(normalized_key, set()).add(actual_relative_path)


def _build_import_path_aliases(pending_items: list[dict[str, Any]], kb_dir: Path) -> dict[str, str]:
    """根据本批导入文件构建“原始路径 -> 实际落盘路径”的唯一映射。"""
    alias_targets: dict[str, set[str]] = {}
    kb_dir = kb_dir.resolve()

    for item in pending_items:
        target_path = item.get("path")
        if not isinstance(target_path, Path):
            continue

        actual_relative_path = target_path.resolve().relative_to(kb_dir).as_posix()
        item["stored_relative_path"] = actual_relative_path

        original_name = item.get("original_name")
        relative_path = item.get("relative_path")
        basename_candidates = [
            Path(str(relative_path).replace("\\", "/")).name if relative_path else None,
            Path(str(original_name).replace("\\", "/")).name if original_name else None,
            Path(actual_relative_path).name,
        ]

        for alias_key in {
            actual_relative_path,
            relative_path,
            original_name,
            *basename_candidates,
        }:
            _register_import_path_alias(alias_targets, alias_key, actual_relative_path)

    return {
        alias_key: next(iter(targets))
        for alias_key, targets in alias_targets.items()
        if len(targets) == 1
    }


def _collect_ready_embedded_image_relative_paths(embedded_assets: list[dict[str, Any]] | None) -> set[str]:
    """收集当前批次 ready 的 embedded 图片路径，用于压制同路径 standalone 处理。"""
    ready_paths: set[str] = set()
    for item in embedded_assets or []:
        if item.get("status") != "ready":
            continue
        asset_type = item.get("asset_type") or "image"
        if asset_type != "image":
            continue
        relative_path = item.get("resolved_relative_path")
        if isinstance(relative_path, str) and relative_path:
            ready_paths.add(relative_path)
    return ready_paths



def _collect_existing_embedded_image_relative_paths(
    kb_id: str,
    *,
    excluded_source_docs: set[str],
) -> set[str]:
    """收集历史已生效的 embedded 图片路径，避免跨批次重导入回弹为 standalone。"""
    ready_paths: set[str] = set()
    for asset in asset_service.list_assets(kb_id):
        if asset.get("asset_role") != "embedded":
            continue
        asset_type = asset.get("asset_type") or "image"
        if asset_type != "image":
            continue
        if asset.get("status") == "orphaned":
            continue
        source_relative_path = asset.get("source_doc_relative_path")
        if isinstance(source_relative_path, str) and source_relative_path in excluded_source_docs:
            continue
        relative_path = asset.get("relative_path")
        if isinstance(relative_path, str) and relative_path:
            ready_paths.add(relative_path)
    return ready_paths



def _build_skipped_standalone_ocr_diagnostics() -> dict[str, Any]:
    """构造被 embedded 接管后的 standalone OCR 诊断结果。"""
    return {
        "ocr_attempted": False,
        "ocr_status": "skipped",
        "ocr_text_length": 0,
        "ocr_error": None,
        "indexed_from_ocr": False,
        "ocr_engine": None,
        **_new_failure_diagnostics(),
        **_new_ocr_runtime_diagnostics(),
    }



def _should_skip_standalone_image(
    item: dict[str, Any],
    *,
    embedded_image_relative_paths: set[str],
) -> bool:
    """判断 standalone 图片是否应被 embedded 版本接管。"""
    relative_path = item.get("relative_path")
    return isinstance(relative_path, str) and relative_path in embedded_image_relative_paths



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
    asset_service.delete_kb_assets(safe_kb_id)
    kb_import_receipt_store.delete_latest_import_receipt(safe_kb_id)
    return True


def import_files(
    files: list[Any],
    chunk_size: int,
    chunk_overlap: int,
    kb_id: str = "default",
    relative_paths: list[str] | None = None,
    import_mode: str = "preserve_tree",
) -> dict[str, Any]:
    """导入本地文件并写入知识库，同时返回逐文件结果与诊断。"""
    import_started_at = time.perf_counter()
    _ensure_kb_active(kb_id)

    import_stage_timings = _new_import_stage_timings()
    manager = None
    index_storage_dirty = False
    storage_persist_diagnostics: dict[str, Any] | None = None

    def _ensure_import_runtime():
        """仅在本批次确实需要入索引时，才懒加载模型与索引管理器。"""
        nonlocal manager
        if manager is not None:
            return manager

        ensure_started_at = time.perf_counter()
        try:
            runtime_state.ensure_models_ready(require_llm=False)
        finally:
            _add_stage_elapsed((import_stage_timings,), "ensure_models_ready_ms", ensure_started_at)

        manager_started_at = time.perf_counter()
        try:
            manager = runtime_state.get_index_manager(kb_id)
        finally:
            _add_stage_elapsed((import_stage_timings,), "get_index_manager_ms", manager_started_at)
        return manager

    kb_dir = get_kb_data_dir(kb_id, create=True)
    safe_import_mode = _validate_import_mode(import_mode)
    normalized_relative_paths = _normalize_import_relative_paths(files, relative_paths)

    receipt_id = _build_import_receipt_id("kb-file-import")
    retained_files: list[dict[str, Any]] = []
    file_results: list[dict[str, Any] | None] = [None] * len(files)
    pending_items: list[dict[str, Any]] = []
    indexed_chunks = 0
    success_count = 0
    failed_count = 0
    empty_count = 0

    for index, (file, relative_path) in enumerate(zip(files, normalized_relative_paths)):
        file_stage_timings = _new_file_stage_timings()
        original_name = getattr(file, "filename", "") or "unnamed"
        content_type = getattr(file, "content_type", "") or ""
        file_size = 0
        target_path: Path | None = None
        detected_file_kind = "unknown"
        stored_filename = FilenameSanitizer.sanitize(original_name)
        folder_path = folder_path_from_relative_path(relative_path) if relative_path is not None else None
        replacement_refs: list[dict[str, Any]] = []
        replacement_backup_bytes: bytes | None = None

        persist_started_at = time.perf_counter()
        try:
            file_content = file.file.read()
            file_size = len(file_content)
            if file_size > MAX_FILE_SIZE:
                raise KBValidationError(f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE})")
            if hasattr(file.file, "seek"):
                file.file.seek(0)

            detected_path = Path(relative_path or original_name) if (relative_path or original_name) else None
            detected_file_kind = _detect_file_kind(detected_path, content_type, file_content)
            if _is_rejected_file_kind(detected_file_kind):
                failure_diagnostics = _new_failure_diagnostics()
                failure_diagnostics["failure_category"] = "unsupported_file_type"
                failed_count += 1
                _finalize_stage_total(file_stage_timings)
                file_results[index] = _build_file_result(
                    kb_id=kb_id,
                    filename=stored_filename,
                    content_type=content_type,
                    size=file_size,
                    path=detected_path,
                    status="failed",
                    indexed_chunks=0,
                    relative_path=relative_path,
                    folder_path=folder_path,
                    message=_build_unsupported_file_type_message(path=detected_path, content_type=content_type),
                    failure_diagnostics=failure_diagnostics,
                    ingestion_diagnostics=_new_ingestion_diagnostics_summary(),
                    stage_timings=file_stage_timings,
                    file_kind_override=detected_file_kind,
                )
                continue

            if safe_import_mode == "preserve_tree" and relative_path is not None:
                target_path = ensure_path_within(kb_dir, kb_dir / relative_path)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                stored_filename = target_path.name
            else:
                stored_filename = FilenameSanitizer.generate_unique_filename(stored_filename)
                target_path = ensure_path_within(kb_dir, kb_dir / stored_filename)

            if target_path.exists() and target_path.is_file():
                current_manager = _ensure_import_runtime()
                replacement_refs = _collect_existing_ref_docs_for_import(
                    current_manager,
                    kb_id=kb_id,
                    target_path=target_path,
                    relative_path=relative_path,
                )
                if replacement_refs:
                    replacement_backup_bytes = target_path.read_bytes()

            with target_path.open("wb") as buffer:
                buffer.write(file_content)
            _record_file_save_elapsed((file_stage_timings, import_stage_timings), persist_started_at)

            pending_items.append(
                {
                    "index": index,
                    "kb_id": kb_id,
                    "original_name": original_name,
                    "filename": stored_filename,
                    "content_type": content_type,
                    "size": file_size,
                    "path": target_path,
                    "relative_path": relative_path,
                    "folder_path": folder_path,
                    "file_kind": detected_file_kind,
                    "stage_timings": file_stage_timings,
                    "ingestion_diagnostics": _new_ingestion_diagnostics_summary(),
                    "replacement_refs": replacement_refs,
                    "replacement_backup_bytes": replacement_backup_bytes,
                    "created_ref_doc_ids": [],
                    "embedded_created_ref_doc_ids": [],
                    "replacement_snapshots": [],
                    "replacement_deleted_doc_count": 0,
                }
            )
        except Exception as exc:
            _record_file_save_elapsed((file_stage_timings, import_stage_timings), persist_started_at)
            if replacement_refs:
                try:
                    _restore_reimport_backup_file(target_path, replacement_backup_bytes)
                except OSError:
                    if target_path is not None:
                        try:
                            if target_path.exists() and target_path.is_file():
                                target_path.unlink()
                        except OSError:
                            pass
            elif target_path is not None:
                try:
                    if target_path.exists() and target_path.is_file():
                        target_path.unlink()
                except OSError:
                    pass
            failed_count += 1
            _finalize_stage_total(file_stage_timings)
            file_results[index] = _build_file_result(
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
                ingestion_diagnostics=_new_ingestion_diagnostics_summary(),
                stage_timings=file_stage_timings,
                file_kind_override=detected_file_kind,
            )

    import_path_aliases = _build_import_path_aliases(pending_items, kb_dir)
    for item in pending_items:
        if item.get("relative_path") is None:
            stored_relative_path = item.get("stored_relative_path")
            item["relative_path"] = stored_relative_path
            item["folder_path"] = (
                folder_path_from_relative_path(stored_relative_path)
                if stored_relative_path is not None
                else None
            )

    embedded_image_relative_paths: set[str] = set()
    current_batch_markdown_relative_paths: set[str] = set()
    for item in pending_items:
        target_path = item["path"]
        if not _is_markdown_file(target_path, item["content_type"]):
            item["embedded_assets"] = []
            item["asset_warning_count"] = 0
            continue

        relative_path = item.get("relative_path")
        if isinstance(relative_path, str) and relative_path:
            current_batch_markdown_relative_paths.add(relative_path)

        extract_started_at = time.perf_counter()
        embedded_assets, asset_warning_count = _extract_embedded_assets_for_file(
            path=target_path,
            kb_dir=kb_dir,
            relative_path=item["relative_path"],
            content_type=item["content_type"],
            path_aliases=import_path_aliases,
        )
        _add_stage_elapsed((item["stage_timings"], import_stage_timings), "embedded_asset_extract_ms", extract_started_at)
        item["embedded_assets"] = embedded_assets
        item["asset_warning_count"] = asset_warning_count
        embedded_image_relative_paths.update(_collect_ready_embedded_image_relative_paths(embedded_assets))

    embedded_image_relative_paths.update(
        _collect_existing_embedded_image_relative_paths(
            kb_id,
            excluded_source_docs=current_batch_markdown_relative_paths,
        )
    )

    for item in pending_items:
        target_path = item["path"]
        file_kind = item.get("file_kind")
        stage_targets = (item["stage_timings"], import_stage_timings)

        if file_kind == "image":
            if _should_skip_standalone_image(item, embedded_image_relative_paths=embedded_image_relative_paths):
                item["skip_standalone_asset"] = True
                item["status"] = "empty"
                item["indexed_chunks"] = 0
                item["ocr_diagnostics"] = _build_skipped_standalone_ocr_diagnostics()
                continue

            ocr_started_at = time.perf_counter()
            try:
                ocr_result = _extract_image_ocr_result(target_path, item["content_type"])
            except Exception as exc:
                _add_stage_elapsed(stage_targets, "standalone_ocr_ms", ocr_started_at)
                item["status"] = "empty"
                item["indexed_chunks"] = 0
                item["ocr_diagnostics"] = {
                    "ocr_attempted": True,
                    "ocr_status": "failed",
                    "ocr_text_length": 0,
                    "ocr_error": str(exc),
                    "indexed_from_ocr": False,
                    "ocr_engine": None,
                    **_build_exception_failure_diagnostics(exc, default_category="ocr_runtime_error"),
                    **_new_ocr_runtime_diagnostics(),
                }
                continue
            _add_stage_elapsed(stage_targets, "standalone_ocr_ms", ocr_started_at)

            ocr_diagnostics = {
                "ocr_attempted": bool(ocr_result.get("attempted", False)),
                "ocr_status": ocr_result.get("status", "skipped"),
                "ocr_text_length": len(str(ocr_result.get("text") or "")),
                "ocr_error": ocr_result.get("error"),
                "indexed_from_ocr": False,
                "ocr_engine": ocr_result.get("engine"),
                **_extract_failure_diagnostics(ocr_result),
                **_extract_ocr_runtime_diagnostics(ocr_result),
            }
            item["ocr_diagnostics"] = ocr_diagnostics

            document = _build_image_ocr_document(
                kb_id=kb_id,
                path=target_path,
                filename=item["filename"],
                content_type=item["content_type"],
                relative_path=item["relative_path"],
                ocr_result=ocr_result,
            )
            if document is None:
                item["indexed_chunks"] = 0
                item["status"] = "empty"
                continue

            index_started_at = time.perf_counter()
            try:
                current_manager = _ensure_import_runtime()
                ref_doc_ids_before_index = _capture_ref_doc_ids(current_manager)
                nodes = current_manager.load_documents([document], chunk_size, chunk_overlap, kb_id=kb_id, persist=False) or []
                item["created_ref_doc_ids"] = _collect_new_ref_doc_ids(current_manager, ref_doc_ids_before_index)
                _consume_manager_ingestion_diagnostics(current_manager, item["ingestion_diagnostics"])
            except Exception as exc:
                _add_stage_elapsed(stage_targets, "primary_index_ms", index_started_at)
                existing_ocr = dict(item.get("ocr_diagnostics") or {})
                item["status"] = "empty"
                item["indexed_chunks"] = 0
                item["ocr_diagnostics"] = {
                    "ocr_attempted": True,
                    "ocr_status": "failed",
                    "ocr_text_length": int(existing_ocr.get("ocr_text_length") or 0),
                    "ocr_error": str(exc),
                    "indexed_from_ocr": False,
                    "ocr_engine": existing_ocr.get("ocr_engine"),
                    **_build_exception_failure_diagnostics(exc, default_category="indexing_error", dependency_status="ready"),
                    **_extract_ocr_runtime_diagnostics(existing_ocr),
                }
                continue
            _add_stage_elapsed(stage_targets, "primary_index_ms", index_started_at)
            item["indexed_chunks"] = len(nodes)
            item["status"] = "indexed" if item["indexed_chunks"] > 0 else "empty"
            if item["indexed_chunks"] > 0:
                index_storage_dirty = True
            item["ocr_diagnostics"]["indexed_from_ocr"] = item["indexed_chunks"] > 0
            continue

        index_started_at = time.perf_counter()
        current_manager = None
        try:
            current_manager = _ensure_import_runtime()
            ref_doc_ids_before_index = _capture_ref_doc_ids(current_manager)
            nodes = current_manager.load_files([target_path.resolve()], chunk_size, chunk_overlap, kb_id=kb_id, persist=False) or []
            item["created_ref_doc_ids"] = _collect_new_ref_doc_ids(current_manager, ref_doc_ids_before_index)
            consumed_ingestion = _consume_manager_ingestion_diagnostics(current_manager, item["ingestion_diagnostics"])
            if file_kind == "pdf":
                pdf_ocr_diagnostics = _extract_pdf_ocr_diagnostics_from_source(consumed_ingestion, target_path=target_path)
                if pdf_ocr_diagnostics is not None:
                    item["ocr_diagnostics"] = pdf_ocr_diagnostics
        except Exception as exc:
            _add_stage_elapsed(stage_targets, "primary_index_ms", index_started_at)
            consumed_ingestion = None
            if current_manager is not None:
                consumed_ingestion = _consume_manager_ingestion_diagnostics(current_manager, item["ingestion_diagnostics"])
            if file_kind == "pdf":
                pdf_ocr_diagnostics = _extract_pdf_ocr_diagnostics_from_source(consumed_ingestion, target_path=target_path)
                if pdf_ocr_diagnostics is not None:
                    item["ocr_diagnostics"] = pdf_ocr_diagnostics
            try:
                if target_path.exists() and target_path.is_file():
                    target_path.unlink()
            except OSError:
                pass
            item["status"] = "failed"
            item["indexed_chunks"] = 0
            item["failure_diagnostics"] = _build_exception_failure_diagnostics(exc, default_category="indexing_error")
            item["message"] = _build_failure_message(
                exc,
                failure_diagnostics=item["failure_diagnostics"],
                file_kind=item.get("file_kind"),
            )
            continue
        _add_stage_elapsed(stage_targets, "primary_index_ms", index_started_at)
        item["indexed_chunks"] = len(nodes)
        item["status"] = "indexed" if item["indexed_chunks"] > 0 else "empty"
        if item["indexed_chunks"] > 0:
            index_storage_dirty = True

    for item in pending_items:
        status = item["status"]
        target_path = item["path"]
        replacement_refs = item.get("replacement_refs") or []
        replacement_backup_bytes = item.get("replacement_backup_bytes")
        if status == "failed":
            if replacement_refs:
                _restore_reimport_backup_file(target_path, replacement_backup_bytes)
            failed_count += 1
            _finalize_stage_total(item["stage_timings"])
            file_results[item["index"]] = _build_file_result(
                kb_id=kb_id,
                filename=item["filename"],
                content_type=item["content_type"],
                size=item["size"],
                path=target_path,
                status="failed",
                indexed_chunks=0,
                relative_path=item["relative_path"],
                folder_path=item["folder_path"],
                message=item.get("message"),
                embedded_assets=item.get("embedded_assets"),
                asset_warning_count=int(item.get("asset_warning_count") or 0),
                ocr_diagnostics=item.get("ocr_diagnostics"),
                failure_diagnostics=item.get("failure_diagnostics"),
                ingestion_diagnostics=item.get("ingestion_diagnostics"),
                stage_timings=item["stage_timings"],
                skip_standalone_asset=bool(item.get("skip_standalone_asset", False)),
                file_kind_override=item.get("file_kind"),
            )
            continue

        embedded_assets = item.get("embedded_assets") or []
        asset_warning_count = int(item.get("asset_warning_count") or 0)

        embedded_chunk_count = 0
        if embedded_assets:
            current_manager = _ensure_import_runtime()
            ref_doc_ids_before_embedded_index = _capture_ref_doc_ids(current_manager)
            embedded_chunk_count = _index_embedded_image_assets(
                manager_getter=_ensure_import_runtime,
                kb_id=kb_id,
                embedded_assets=embedded_assets,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                stage_targets=(item["stage_timings"], import_stage_timings),
                ingestion_targets=(item["ingestion_diagnostics"],),
                persist=False,
            )
            item["embedded_created_ref_doc_ids"] = _collect_new_ref_doc_ids(current_manager, ref_doc_ids_before_embedded_index)
            if embedded_chunk_count > 0:
                index_storage_dirty = True
        chunk_count = item["indexed_chunks"] + embedded_chunk_count
        status = item["status"]
        if status == "empty" and embedded_chunk_count > 0:
            status = "indexed"

        if status == "indexed" and replacement_refs:
            current_manager = _ensure_import_runtime()
            item["replacement_snapshots"] = _snapshot_ref_doc_payloads(
                current_manager,
                [entry.get("ref_doc_id") for entry in replacement_refs if isinstance(entry, dict)],
            )
            replacement_result = _commit_reimport_replacements(
                current_manager,
                kb_id=kb_id,
                replacement_refs=replacement_refs,
                persist=False,
            )
            item["replacement_deleted_doc_count"] = replacement_result["deleted_counted_doc_count"]
            if replacement_result["deleted_ref_doc_count"] > 0:
                item["ingestion_diagnostics"]["replaced_ref_doc_count"] = replacement_result["deleted_ref_doc_count"]
                item["ingestion_diagnostics"]["replaced_doc_count"] = replacement_result["deleted_counted_doc_count"]
        elif replacement_refs:
            _restore_reimport_backup_file(target_path, replacement_backup_bytes)

        indexed_chunks += chunk_count
        if status == "indexed":
            success_count += 1
        else:
            empty_count += 1

        _finalize_stage_total(item["stage_timings"])
        file_record = _build_file_result(
            kb_id=kb_id,
            filename=item["filename"],
            content_type=item["content_type"],
            size=item["size"],
            path=target_path,
            status=status,
            indexed_chunks=chunk_count,
            relative_path=item["relative_path"],
            folder_path=item["folder_path"],
            embedded_assets=embedded_assets,
            asset_warning_count=asset_warning_count,
            ocr_diagnostics=item.get("ocr_diagnostics"),
            ingestion_diagnostics=item.get("ingestion_diagnostics"),
            stage_timings=item["stage_timings"],
            skip_standalone_asset=bool(item.get("skip_standalone_asset", False)),
            file_kind_override=item.get("file_kind"),
        )
        retained_files.append(
            {
                k: file_record[k]
                for k in ("name", "type", "size", "path", "kb_id", "relative_path", "folder_path")
            }
        )
        file_results[item["index"]] = file_record

    completed_results: list[dict[str, Any]] | None = None
    if manager is not None and index_storage_dirty:
        persist_index_started_at = time.perf_counter()
        try:
            manager.persist_storage()
        except Exception as exc:
            _add_stage_elapsed((import_stage_timings,), "index_storage_persist_ms", persist_index_started_at)
            _rollback_import_batch_after_persist_failure(manager, kb_id=kb_id, pending_items=pending_items)
            persist_failure_diagnostics = _build_exception_failure_diagnostics(
                exc,
                default_category="storage_persist_error",
            )
            persist_failure_message = _build_failure_message(exc, failure_diagnostics=persist_failure_diagnostics)
            retained_files = []
            for item in pending_items:
                if item.get("status") == "failed":
                    continue
                _finalize_stage_total(item["stage_timings"])
                file_results[item["index"]] = _build_file_result(
                    kb_id=kb_id,
                    filename=item["filename"],
                    content_type=item["content_type"],
                    size=item["size"],
                    path=item.get("path"),
                    status="failed",
                    indexed_chunks=0,
                    relative_path=item["relative_path"],
                    folder_path=item["folder_path"],
                    message=persist_failure_message,
                    embedded_assets=item.get("embedded_assets"),
                    asset_warning_count=int(item.get("asset_warning_count") or 0),
                    ocr_diagnostics=item.get("ocr_diagnostics"),
                    failure_diagnostics=persist_failure_diagnostics,
                    ingestion_diagnostics=item.get("ingestion_diagnostics"),
                    stage_timings=item["stage_timings"],
                    skip_standalone_asset=bool(item.get("skip_standalone_asset", False)),
                    file_kind_override=item.get("file_kind"),
                )
            completed_results = [entry for entry in file_results if entry is not None]
            indexed_chunks = sum(int(entry.get("indexed_chunks") or 0) for entry in completed_results)
            success_count = sum(1 for entry in completed_results if entry.get("status") == "indexed")
            failed_count = sum(1 for entry in completed_results if entry.get("status") == "failed")
            empty_count = sum(1 for entry in completed_results if entry.get("status") == "empty")
        else:
            _add_stage_elapsed((import_stage_timings,), "index_storage_persist_ms", persist_index_started_at)
            consume_persist_diagnostics = getattr(manager, "consume_last_persist_diagnostics", None)
            if callable(consume_persist_diagnostics):
                candidate_persist_diagnostics = consume_persist_diagnostics()
                if isinstance(candidate_persist_diagnostics, dict):
                    storage_persist_diagnostics = dict(candidate_persist_diagnostics)

    if completed_results is None:
        completed_results = [item for item in file_results if item is not None]
    if success_count > 0:
        doc_count_started_at = time.perf_counter()
        _safe_add_doc_count(kb_id, success_count)
        _add_stage_elapsed((import_stage_timings,), "doc_count_update_ms", doc_count_started_at)

    register_started_at = time.perf_counter()
    asset_service.register_imported_assets(kb_id, completed_results)
    _add_stage_elapsed((import_stage_timings,), "register_assets_ms", register_started_at)
    _sync_stage_timing_aliases(import_stage_timings)

    result_build_started_at = time.perf_counter()
    result = {
        "receipt_id": receipt_id,
        "files": retained_files,
        "file_results": completed_results,
        "indexed_chunks": indexed_chunks,
        "success_count": success_count,
        "failed_count": failed_count,
        "empty_count": empty_count,
        "kb_id": kb_id,
        "import_mode": safe_import_mode,
        "diagnostics": _aggregate_import_diagnostics(completed_results, stage_timings=import_stage_timings),
    }
    result = _ensure_import_display_summary(result)
    if isinstance(storage_persist_diagnostics, dict):
        result["diagnostics"]["storage_persist_stage_timings"] = storage_persist_diagnostics
    _add_stage_elapsed((import_stage_timings,), "result_build_ms", result_build_started_at)
    _refresh_import_result_stage_timings(result, import_stage_timings)

    receipt_store_started_at = time.perf_counter()
    saved_receipt = kb_import_receipt_store.save_latest_import_receipt(
        kb_id,
        source_label="\u6587\u4ef6\u4e0a\u4f20",
        result=result,
    )
    _add_stage_elapsed((import_stage_timings,), "receipt_store_ms", receipt_store_started_at)
    import_stage_timings["total_ms"] = _elapsed_ms(import_started_at)
    _refresh_import_result_stage_timings(result, import_stage_timings)
    kb_import_receipt_store.save_latest_import_receipt(
        kb_id,
        source_label=saved_receipt["source_label"],
        result=result,
        created_at=saved_receipt["created_at"],
    )
    return result



def import_urls(urls: list[str], chunk_size: int, chunk_overlap: int, kb_id: str = "default") -> dict[str, Any]:
    """逐项导入 URL，区分 indexed / empty / failed 三种结果。"""
    _ensure_kb_active(kb_id)
    runtime_state.ensure_models_ready(require_llm=False)
    manager = runtime_state.get_index_manager(kb_id)

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

    result = {
        "receipt_id": receipt_id,
        "urls": urls,
        "url_results": url_results,
        "indexed_chunks": indexed_chunks,
        "success_count": success_count,
        "failed_count": failed_count,
        "empty_count": empty_count,
        "kb_id": kb_id,
    }
    result = _ensure_import_display_summary(result)
    kb_import_receipt_store.save_latest_import_receipt(
        kb_id,
        source_label="网页导入",
        result=result,
    )
    return result


def list_docs(kb_id: str | None = None) -> list[dict[str, Any]]:
    """列出知识库文档。

    Args:
        kb_id: 可选知识库 ID；为空时聚合全部 active 知识库文档。
    """
    safe_kb_id = validate_kb_id(kb_id) if kb_id is not None else None

    if safe_kb_id is not None:
        kb_ids = [safe_kb_id]
    else:
        kb_ids = ["default"]
        for kb in _get_registry().list_kbs():
            candidate = kb.get("kb_id")
            status = kb.get("status", "active")
            if not isinstance(candidate, str) or status != "active":
                continue
            if candidate not in kb_ids:
                kb_ids.append(candidate)

    manager_entries = [(requested_kb_id, runtime_state.get_index_manager(requested_kb_id)) for requested_kb_id in kb_ids]
    unique_manager_count = len({id(manager) for _, manager in manager_entries})
    enforce_manager_membership = safe_kb_id is None and unique_manager_count > 1

    processed_entries: list[tuple[str, Any]] = []
    seen_manager_ids: set[int] = set()
    for requested_kb_id, manager in manager_entries:
        manager_identity = id(manager)
        if manager_identity in seen_manager_ids:
            continue
        seen_manager_ids.add(manager_identity)
        processed_entries.append((requested_kb_id, manager))

    docs: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for requested_kb_id, manager in processed_entries:
        doc_store = manager.storage_context.docstore
        raw_docs = getattr(doc_store, "docs", {}) or {}
        ref_doc_info = doc_store.get_all_ref_doc_info() if len(raw_docs) > 0 else {}
        for ref_doc_id, ref_doc in ref_doc_info.items():
            metadata = getattr(ref_doc, "metadata", {}) or {}
            doc_kb_id = _normalize_doc_kb_id(metadata)
            if not _doc_belongs_to_request(metadata, safe_kb_id):
                continue
            if enforce_manager_membership and doc_kb_id != requested_kb_id:
                continue
            if _is_embedded_asset_doc(metadata):
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
    manager = runtime_state.get_index_manager(safe_kb_id)
    runtime_state.ensure_index_loaded(safe_kb_id)
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


def _get_preview_docstore(kb_id: str):
    """获取指定知识库 preview 所需的 docstore。"""
    manager = runtime_state.get_index_manager(kb_id)
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

    runtime_state.ensure_index_loaded(safe_kb_id)
    doc_store = _get_preview_docstore(safe_kb_id)
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
