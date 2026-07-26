"""知识库服务：处理 KB CRUD、文件/URL 导入与文档管理。"""

from __future__ import annotations

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

# 延迟初始化 registry，便于测试替换工作目录。
_registry: KBRegistry | None = None


def _get_registry() -> KBRegistry:
    global _registry
    if _registry is None:
        _registry = KBRegistry(storage_path=Path("storage/kb_registry.json"))
    return _registry


def _new_import_stage_timings() -> dict[str, float]:
    """创建导入批次级 stage_timings 初始结构，便于统一累计耗时。"""
    return {
        "ensure_models_ready_ms": 0.0,
        "get_index_manager_ms": 0.0,
        "persist_ms": 0.0,
        "standalone_ocr_ms": 0.0,
        "primary_index_ms": 0.0,
        "embedded_asset_extract_ms": 0.0,
        "embedded_asset_ocr_ms": 0.0,
        "embedded_asset_index_ms": 0.0,
        "register_assets_ms": 0.0,
        "total_ms": 0.0,
    }


def _new_file_stage_timings() -> dict[str, float]:
    """创建单文件级 stage_timings 初始结构。"""
    return {
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
    """??????????embedding ???????????"""
    return {key: 0.0 for key in INDEX_STAGE_TIMING_KEYS}


def _new_ingestion_diagnostics_summary() -> dict[str, Any]:
    """????????? ingestion diagnostics ?????"""
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
    """? IndexManager ??? ingestion diagnostics ????????"""
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
    """?? manager ???? ingestion diagnostics????????????"""
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
    """把当前阶段耗时累计写入多个 timing 容器。"""
    elapsed_ms = _elapsed_ms(started_at)
    for target in stage_targets:
        target[key] = round(float(target.get(key, 0.0)) + elapsed_ms, 3)
    return elapsed_ms


def _finalize_stage_total(stage_timings: dict[str, float]) -> None:
    """汇总除 total_ms 外的阶段耗时，并回填 total_ms。"""
    stage_timings["total_ms"] = round(
        sum(float(value) for key, value in stage_timings.items() if key != "total_ms"),
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


def _build_import_receipt_id(prefix: str) -> str:
    """生成导入回执 ID，便于前后端串联一次导入批次。"""
    return f"{prefix}-{uuid4().hex}"


def get_latest_import_receipt(kb_id: str) -> dict[str, Any] | None:
    """读取指定知识库最近一次导入回执。"""
    safe_kb_id = validate_kb_id(kb_id)
    _ensure_kb_active(safe_kb_id)
    return kb_import_receipt_store.load_latest_import_receipt(safe_kb_id)


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
    ingestion_diagnostics: dict[str, Any] | None = None,
    stage_timings: dict[str, float] | None = None,
    skip_standalone_asset: bool = False,
) -> dict[str, Any]:
    """??????????????????????"""
    embedded_asset_items = embedded_assets or []
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
        "embedded_assets": embedded_asset_items,
        "asset_warning_count": asset_warning_count,
        "diagnostics": _build_file_diagnostics(
            path=path,
            content_type=content_type,
            status=status,
            embedded_assets=embedded_asset_items,
            ocr_diagnostics=ocr_diagnostics,
            ingestion_diagnostics=ingestion_diagnostics,
            stage_timings=stage_timings,
            skip_standalone_asset=skip_standalone_asset,
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


def _detect_file_kind(path: Path | None, content_type: str) -> str:
    """基于文件名后缀与 MIME 类型推断导入文件类别。"""
    if _is_markdown_file(path, content_type):
        return "markdown"
    if _is_image_file(path, content_type):
        return "image"

    lower_content_type = content_type.lower()
    suffix = path.suffix.lower() if path is not None else ""
    if suffix == ".pdf" or lower_content_type == "application/pdf":
        return "pdf"
    if lower_content_type.startswith("text/") or suffix in {".txt", ".csv", ".json", ".xml", ".yaml", ".yml", ".html", ".htm", ".rst", ".log"}:
        return "text"
    if lower_content_type:
        return "binary"
    return "unknown"


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
    """提取 OCR 细粒度运行时字段，避免主链路散落复制逻辑。"""
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
    metadata = {key: value for key, value in metadata.items() if value is not None}
    return Document(text=text, metadata=metadata)


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
    metadata = {key: value for key, value in metadata.items() if value is not None}
    return Document(text=text, metadata=metadata)


def _index_embedded_image_assets(
    *,
    manager_getter: Callable[[], Any],
    kb_id: str,
    embedded_assets: list[dict[str, Any]],
    chunk_size: int,
    chunk_overlap: int,
    stage_targets: tuple[dict[str, float], ...] = (),
    ingestion_targets: tuple[dict[str, Any], ...] = (),
) -> int:
    """? Markdown ?????? OCR?????????????????"""
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
            nodes = manager.load_documents([document], chunk_size, chunk_overlap, kb_id=kb_id) or []
            _consume_manager_ingestion_diagnostics(manager, *ingestion_targets)
        except Exception as exc:
            _add_stage_elapsed(stage_targets, "embedded_asset_index_ms", index_started_at)
            asset["ocr_diagnostics"] = {
                **ocr_diagnostics,
                "ocr_status": "failed",
                "ocr_error": str(exc),
                "indexed_from_ocr": False,
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
    ingestion_diagnostics: dict[str, Any] | None = None,
    stage_timings: dict[str, float] | None = None,
    skip_standalone_asset: bool = False,
) -> dict[str, Any]:
    """????? diagnostics??? empty ???????????"""
    file_kind = _detect_file_kind(path, content_type)
    embedded_summary = _summarize_embedded_assets(embedded_assets)
    embedded_ocr_summary = _summarize_embedded_asset_ocr(embedded_assets)
    ocr_info = dict(ocr_diagnostics or {})
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
    """?????? diagnostics????????????"""
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
    """收集 ready 的 embedded 图片路径，用于压制同图 standalone 处理。"""
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



def _build_skipped_standalone_ocr_diagnostics() -> dict[str, Any]:
    """构造被 embedded 接管后的 standalone OCR 诊断结果。"""
    return {
        "ocr_attempted": False,
        "ocr_status": "skipped",
        "ocr_text_length": 0,
        "ocr_error": None,
        "indexed_from_ocr": False,
        "ocr_engine": None,
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
            manager = runtime_state.get_index_manager()
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
        stored_filename = FilenameSanitizer.sanitize(original_name)
        folder_path = folder_path_from_relative_path(relative_path) if relative_path is not None else None

        persist_started_at = time.perf_counter()
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
            _add_stage_elapsed((file_stage_timings, import_stage_timings), "persist_ms", persist_started_at)

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
                    "file_kind": _detect_file_kind(target_path, content_type),
                    "stage_timings": file_stage_timings,
                    "ingestion_diagnostics": _new_ingestion_diagnostics_summary(),
                }
            )
        except Exception as exc:
            _add_stage_elapsed((file_stage_timings, import_stage_timings), "persist_ms", persist_started_at)
            if target_path is not None:
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
    for item in pending_items:
        target_path = item["path"]
        if not _is_markdown_file(target_path, item["content_type"]):
            item["embedded_assets"] = []
            item["asset_warning_count"] = 0
            continue

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
                nodes = current_manager.load_documents([document], chunk_size, chunk_overlap, kb_id=kb_id) or []
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
                    **_extract_ocr_runtime_diagnostics(existing_ocr),
                }
                continue
            _add_stage_elapsed(stage_targets, "primary_index_ms", index_started_at)
            item["indexed_chunks"] = len(nodes)
            item["status"] = "indexed" if item["indexed_chunks"] > 0 else "empty"
            item["ocr_diagnostics"]["indexed_from_ocr"] = item["indexed_chunks"] > 0
            continue

        index_started_at = time.perf_counter()
        try:
            current_manager = _ensure_import_runtime()
            nodes = current_manager.load_files([target_path.resolve()], chunk_size, chunk_overlap, kb_id=kb_id) or []
            _consume_manager_ingestion_diagnostics(current_manager, item["ingestion_diagnostics"])
        except Exception as exc:
            _add_stage_elapsed(stage_targets, "primary_index_ms", index_started_at)
            try:
                if target_path.exists() and target_path.is_file():
                    target_path.unlink()
            except OSError:
                pass
            item["status"] = "failed"
            item["indexed_chunks"] = 0
            item["message"] = str(exc)
            continue
        _add_stage_elapsed(stage_targets, "primary_index_ms", index_started_at)
        item["indexed_chunks"] = len(nodes)
        item["status"] = "indexed" if item["indexed_chunks"] > 0 else "empty"

    for item in pending_items:
        status = item["status"]
        target_path = item["path"]
        if status == "failed":
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
                ingestion_diagnostics=item.get("ingestion_diagnostics"),
                stage_timings=item["stage_timings"],
            )
            continue

        embedded_assets = item.get("embedded_assets") or []
        asset_warning_count = int(item.get("asset_warning_count") or 0)

        embedded_chunk_count = 0
        if embedded_assets:
            embedded_chunk_count = _index_embedded_image_assets(
                manager_getter=_ensure_import_runtime,
                kb_id=kb_id,
                embedded_assets=embedded_assets,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                stage_targets=(item["stage_timings"], import_stage_timings),
                ingestion_targets=(item["ingestion_diagnostics"],),
            )
        chunk_count = item["indexed_chunks"] + embedded_chunk_count
        status = item["status"]
        if status == "empty" and embedded_chunk_count > 0:
            status = "indexed"
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
        )
        retained_files.append(
            {
                k: file_record[k]
                for k in ("name", "type", "size", "path", "kb_id", "relative_path", "folder_path")
            }
        )
        file_results[item["index"]] = file_record

    completed_results = [item for item in file_results if item is not None]
    if success_count > 0:
        _safe_add_doc_count(kb_id, success_count)

    register_started_at = time.perf_counter()
    asset_service.register_imported_assets(kb_id, completed_results)
    _add_stage_elapsed((import_stage_timings,), "register_assets_ms", register_started_at)
    import_stage_timings["total_ms"] = _elapsed_ms(import_started_at)

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
    kb_import_receipt_store.save_latest_import_receipt(
        kb_id,
        source_label="文件上传",
        result=result,
    )
    return result



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
    kb_import_receipt_store.save_latest_import_receipt(
        kb_id,
        source_label="网页导入",
        result=result,
    )
    return result


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
