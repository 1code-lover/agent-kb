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

_OCR_TIMING_FIELDS = (
    "ocr_init_ms",
    "ocr_load_image_ms",
    "ocr_predict_ms",
    "ocr_postprocess_ms",
    "ocr_total_ms",
)

_registry: KBAssetRegistry | None = None


def _get_registry() -> KBAssetRegistry:
    """返回资产注册表单例。"""
    global _registry
    if _registry is None:
        _registry = KBAssetRegistry()
    return _registry



def _get_kb_registry() -> KBRegistry:
    """返回知识库注册表实例。"""
    return KBRegistry(storage_path=Path("storage") / "kb_registry.json")



def _ensure_kb_active(kb_id: str) -> str:
    """确保知识库存在且处于 active 状态。"""
    safe_kb_id = validate_kb_id(kb_id)
    kb = _get_kb_registry().get_kb(safe_kb_id)
    if kb is None:
        raise KBNotFoundError(f"知识库不存在: {safe_kb_id}")
    if kb.get("status", "active") != "active":
        raise KBUnavailableError(f"知识库不可用: {safe_kb_id}")
    return safe_kb_id



def _is_markdown_result(file_result: dict[str, Any]) -> bool:
    """判断导入结果是否表示 Markdown 文件。"""
    relative_path = file_result.get("relative_path")
    if isinstance(relative_path, str) and Path(relative_path).suffix.lower() in _MARKDOWN_SUFFIXES:
        return True
    content_type = str(file_result.get("type") or "").lower()
    return content_type.startswith("text/markdown")



def _is_image_result(file_result: dict[str, Any]) -> bool:
    """判断导入结果是否表示图片文件。"""
    relative_path = file_result.get("relative_path")
    if isinstance(relative_path, str) and Path(relative_path).suffix.lower() in _IMAGE_SUFFIXES:
        return True
    content_type = str(file_result.get("type") or "").lower()
    return content_type.startswith("image/")



def _to_int(value: Any) -> int:
    """把任意输入尽量稳定转换为 int。"""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0



def _to_float(value: Any) -> float:
    """把任意输入尽量稳定转换为 float。"""
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0



def _normalize_ocr_diagnostics(diagnostics: dict[str, Any] | None) -> dict[str, Any]:
    """规范化 OCR 诊断字段，便于资产对象稳定复用。"""
    source = diagnostics if isinstance(diagnostics, dict) else {}
    missing_dependency = source.get("missing_dependency")
    dependency_status = source.get("dependency_status")
    if not dependency_status:
        if missing_dependency:
            dependency_status = "missing"
        elif source.get("ocr_attempted") or source.get("ocr_engine"):
            dependency_status = "ready"
        else:
            dependency_status = "unknown"
    normalized = {
        "ocr_attempted": bool(source.get("ocr_attempted", False)),
        "ocr_status": source.get("ocr_status"),
        "ocr_text_length": _to_int(source.get("ocr_text_length")),
        "ocr_error": source.get("ocr_error"),
        "indexed_from_ocr": bool(source.get("indexed_from_ocr", False)),
        "ocr_instance_reused": bool(source.get("ocr_instance_reused", False)),
        "failure_category": source.get("failure_category"),
        "missing_dependency": missing_dependency,
        "dependency_status": dependency_status,
    }
    for key in _OCR_TIMING_FIELDS:
        normalized[key] = _to_float(source.get(key))
    ocr_engine = source.get("ocr_engine")
    if ocr_engine:
        normalized["ocr_engine"] = ocr_engine
    return normalized



def _build_asset_runtime_fields(
    *,
    diagnostics: dict[str, Any] | None,
    indexed_chunks: Any = 0,
    asset_registered: bool = True,
) -> dict[str, Any]:
    """构造资产对象上的 OCR 与索引运行态字段。"""
    normalized_ocr = _normalize_ocr_diagnostics(diagnostics)
    payload = {
        "indexed_chunks": _to_int(indexed_chunks),
        "ocr_attempted": normalized_ocr["ocr_attempted"],
        "ocr_status": normalized_ocr["ocr_status"],
        "ocr_text_length": normalized_ocr["ocr_text_length"],
        "ocr_error": normalized_ocr["ocr_error"],
        "indexed_from_ocr": normalized_ocr["indexed_from_ocr"],
        "failure_category": normalized_ocr["failure_category"],
        "missing_dependency": normalized_ocr["missing_dependency"],
        "dependency_status": normalized_ocr["dependency_status"],
        "asset_registered": bool(asset_registered),
        "ocr_instance_reused": normalized_ocr["ocr_instance_reused"],
        "ocr_diagnostics": normalized_ocr,
    }
    for key in _OCR_TIMING_FIELDS:
        payload[key] = normalized_ocr[key]
    if "ocr_engine" in normalized_ocr:
        payload["ocr_engine"] = normalized_ocr["ocr_engine"]
    return payload



def _build_standalone_asset_id(kb_id: str, relative_path: str | None, path: str | None, filename: str | None) -> str:
    """为独立图片资产生成稳定 asset_id。"""
    raw = relative_path or path or filename or "standalone"
    digest = hashlib.sha1(f"{kb_id}:standalone:{raw}".encode("utf-8")).hexdigest()[:16]
    return f"asset-standalone-{digest}"



def _build_standalone_asset(kb_id: str, file_result: dict[str, Any]) -> dict[str, Any] | None:
    """把图片导入结果转换为独立资产对象。"""
    if not _is_image_result(file_result):
        return None

    relative_path = file_result.get("relative_path")
    path = file_result.get("path")
    filename = file_result.get("name")
    if not isinstance(path, str) or not path:
        return None

    diagnostics = file_result.get("diagnostics") if isinstance(file_result.get("diagnostics"), dict) else {}
    asset = {
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
    asset.update(
        _build_asset_runtime_fields(
            diagnostics=diagnostics,
            indexed_chunks=file_result.get("indexed_chunks"),
            asset_registered=bool(diagnostics.get("asset_registered", True)),
        )
    )
    return asset



def _build_embedded_asset(kb_id: str, source_file: dict[str, Any], embedded_item: dict[str, Any]) -> dict[str, Any] | None:
    """把 Markdown 内嵌资产结果转换为资产对象。"""
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
    asset = {
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
    asset.update(
        _build_asset_runtime_fields(
            diagnostics=embedded_item.get("ocr_diagnostics"),
            indexed_chunks=embedded_item.get("indexed_chunks"),
            asset_registered=True,
        )
    )
    return asset



def _resolve_asset_status(asset: dict[str, Any]) -> str:
    """根据文件存在性刷新资产运行时状态。"""
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
    """刷新资产状态字段，并在状态变化时写回注册表。"""
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



def _collect_ready_embedded_image_paths(file_results: list[dict[str, Any]]) -> set[str]:
    """收集本批导入中 ready 的 embedded 图片路径，用于跳过 standalone 注册。"""
    ready_paths: set[str] = set()
    for file_result in file_results:
        if not _is_markdown_result(file_result):
            continue
        for embedded_item in file_result.get("embedded_assets") or []:
            if embedded_item.get("status") != "ready":
                continue
            asset_type = embedded_item.get("asset_type") or "image"
            if asset_type != "image":
                continue
            resolved_relative_path = embedded_item.get("resolved_relative_path")
            if isinstance(resolved_relative_path, str) and resolved_relative_path:
                ready_paths.add(resolved_relative_path)
    return ready_paths



def _collect_existing_embedded_image_paths(
    assets: list[dict[str, Any]],
    *,
    excluded_source_docs: set[str],
) -> set[str]:
    """收集已登记的 embedded 图片路径，用于过滤重复的 standalone 资产。"""
    ready_paths: set[str] = set()
    for asset in assets:
        if asset.get("asset_role") != "embedded":
            continue
        if asset.get("asset_type") not in {None, "image"}:
            continue
        source_relative_path = asset.get("source_doc_relative_path")
        if isinstance(source_relative_path, str) and source_relative_path in excluded_source_docs:
            continue
        if asset.get("status") == "orphaned":
            continue
        relative_path = asset.get("relative_path")
        if isinstance(relative_path, str) and relative_path:
            ready_paths.add(relative_path)
    return ready_paths



def _should_skip_standalone_asset(
    file_result: dict[str, Any],
    *,
    embedded_ready_paths: set[str],
) -> bool:
    """判断 standalone 资产是否应被 embedded 资产去重掉。"""
    diagnostics = file_result.get("diagnostics") if isinstance(file_result.get("diagnostics"), dict) else {}
    if diagnostics.get("skip_standalone_asset"):
        return True
    relative_path = file_result.get("relative_path")
    return isinstance(relative_path, str) and relative_path in embedded_ready_paths



def register_imported_assets(kb_id: str, file_results: list[dict[str, Any]]) -> dict[str, int]:
    """登记导入过程中发现的 embedded 与 standalone 资产。"""
    safe_kb_id = validate_kb_id(kb_id)
    registry = _get_registry()

    standalone_assets: list[dict[str, Any]] = []
    embedded_assets: list[dict[str, Any]] = []
    embedded_source_docs: set[str] = set()
    skipped_standalone_paths: set[str] = set()

    for file_result in file_results:
        status = file_result.get("status")
        if status not in {"indexed", "empty"}:
            continue
        if not _is_markdown_result(file_result):
            continue
        source_relative_path = file_result.get("relative_path")
        if isinstance(source_relative_path, str) and source_relative_path:
            embedded_source_docs.add(source_relative_path)
        for embedded_item in file_result.get("embedded_assets") or []:
            embedded_asset = _build_embedded_asset(safe_kb_id, file_result, embedded_item)
            if embedded_asset is not None:
                embedded_assets.append(embedded_asset)

    current_batch_embedded_ready_paths = _collect_ready_embedded_image_paths(file_results)
    existing_embedded_ready_paths = _collect_existing_embedded_image_paths(
        registry.list_assets(safe_kb_id),
        excluded_source_docs=embedded_source_docs,
    )
    embedded_ready_paths = current_batch_embedded_ready_paths | existing_embedded_ready_paths
    standalone_prune_paths = set(current_batch_embedded_ready_paths)

    for file_result in file_results:
        status = file_result.get("status")
        if status not in {"indexed", "empty"}:
            continue
        if not _is_image_result(file_result):
            continue

        relative_path = file_result.get("relative_path")
        if _should_skip_standalone_asset(file_result, embedded_ready_paths=embedded_ready_paths):
            if isinstance(relative_path, str) and relative_path:
                skipped_standalone_paths.add(relative_path)
                standalone_prune_paths.add(relative_path)
            continue

        standalone_asset = _build_standalone_asset(safe_kb_id, file_result)
        if standalone_asset is not None:
            standalone_assets.append(standalone_asset)

    if embedded_source_docs:
        registry.replace_embedded_assets(safe_kb_id, embedded_source_docs, embedded_assets)
    if standalone_prune_paths:
        registry.prune_standalone_assets(safe_kb_id, standalone_prune_paths)
    if standalone_assets:
        registry.upsert_assets(safe_kb_id, standalone_assets)

    return {
        "standalone_count": len(standalone_assets),
        "embedded_count": len(embedded_assets),
        "skipped_standalone_count": len(skipped_standalone_paths),
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
