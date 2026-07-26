"""
知识库 API 路由。

职责：
1. 将 KB CRUD 请求转交给 kb_service 和 registry。
2. 将文件/URL 导入请求转交给服务层处理。
3. 返回统一 API 响应结构。
4. 将稳定 KB 服务异常映射为 HTTPException。
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.schemas import DeleteDocsRequest, PreviewRequest, UrlImportRequest
from api.schemas.kb import KBCreateRequest, KBUpdateRequest
from api.services import asset_service, folder_service, kb_service
from server.kb_errors import (
    KBConflictError,
    KBConsistencyError,
    KBNotFoundError,
    KBServiceError,
    KBUnavailableError,
    KBValidationError,
)
from utils.api_response import success_response

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])


def _raise_http_from_kb_error(exc: KBServiceError) -> None:
    """把稳定服务异常映射为明确的 HTTP 状态码。"""
    if isinstance(exc, (KBValidationError, KBUnavailableError)):
        status_code = 400
    elif isinstance(exc, KBNotFoundError):
        status_code = 404
    elif isinstance(exc, KBConflictError):
        status_code = 409
    elif isinstance(exc, KBConsistencyError):
        status_code = 500
    else:
        status_code = 400
    raise HTTPException(status_code=status_code, detail=exc.message) from exc


# KB CRUD 基础接口。

@router.post("")
def create_kb(request: KBCreateRequest) -> dict:
    """创建知识库。"""
    try:
        result = kb_service.create_kb(request.kb_id, request.kb_name)
        return success_response(result)
    except KBServiceError as exc:
        _raise_http_from_kb_error(exc)


@router.get("")
def list_kbs() -> dict:
    """列出所有知识库。"""
    return success_response({"items": kb_service.list_kbs()})


# 兼容旧前端路径，必须放在 /{kb_id} 动态路由之前。

@router.get("/list")
def list_docs(kb_id: str | None = None) -> dict:
    """列出文档，按可选 kb_id 严格隔离。"""
    try:
        return success_response({"docs": kb_service.list_docs(kb_id=kb_id)})
    except KBServiceError as exc:
        _raise_http_from_kb_error(exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/folders")
def list_folders(kb_id: str) -> dict:
    """列出指定知识库的 folder 节点。"""
    try:
        return success_response({"folders": folder_service.list_folders(kb_id)})
    except KBServiceError as exc:
        _raise_http_from_kb_error(exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.delete("/docs")
def delete_docs(request: DeleteDocsRequest) -> dict:
    """删除知识库内文档。"""
    try:
        result = kb_service.delete_docs(request)
        return success_response(result)
    except KBServiceError as exc:
        _raise_http_from_kb_error(exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# 文件与网页导入接口。

@router.post("/file/import")
def import_files(
    files: list[UploadFile] = File(...),
    chunk_size: int = Form(2048),
    chunk_overlap: int = Form(512),
    kb_id: str = Form("default"),
    relative_paths: list[str] | None = Form(None),
    import_mode: str = Form("preserve_tree"),
) -> dict:
    """导入本地文件，并支持保留目录树或拍平写入。"""
    try:
        result = kb_service.import_files(
            files,
            chunk_size,
            chunk_overlap,
            kb_id=kb_id,
            relative_paths=relative_paths,
            import_mode=import_mode,
        )
        return success_response(result)
    except KBServiceError as exc:
        _raise_http_from_kb_error(exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/web/import")
def import_web(request: UrlImportRequest) -> dict:
    """导入网页 URL。"""
    try:
        result = kb_service.import_urls(
            request.urls,
            request.chunk_size,
            request.chunk_overlap,
            kb_id=request.kb_id,
        )
        return success_response(result)
    except KBServiceError as exc:
        _raise_http_from_kb_error(exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/import-receipt/latest")
def get_latest_import_receipt(kb_id: str) -> dict:
    """返回指定知识库最近一次导入回执。"""
    try:
        return success_response({"receipt": kb_service.get_latest_import_receipt(kb_id)})
    except KBServiceError as exc:
        _raise_http_from_kb_error(exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/preview")
def preview(request: PreviewRequest) -> dict:
    """返回最小文档/证据预览对象。"""
    try:
        result = kb_service.preview_document(request)
        return success_response(result)
    except KBServiceError as exc:
        _raise_http_from_kb_error(exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# 动态 KB CRUD 路由，必须放在静态子路径之后。


@router.get("/assets")
def list_assets(kb_id: str) -> dict:
    """List assets for the given knowledge base."""
    try:
        return success_response({"items": asset_service.list_assets(kb_id)})
    except KBServiceError as exc:
        _raise_http_from_kb_error(exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/assets/{asset_id}")
def get_asset_preview(asset_id: str, kb_id: str) -> dict:
    """Return the minimal preview payload for one asset."""
    try:
        return success_response(asset_service.get_asset_preview(kb_id, asset_id))
    except KBServiceError as exc:
        _raise_http_from_kb_error(exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

@router.get("/{kb_id}")
def get_kb(kb_id: str) -> dict:
    """获取知识库详情。"""
    try:
        result = kb_service.get_kb(kb_id)
    except KBServiceError as exc:
        _raise_http_from_kb_error(exc)
    if result is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return success_response(result)


@router.put("/{kb_id}")
def update_kb(kb_id: str, request: KBUpdateRequest) -> dict:
    """更新知识库名称。"""
    try:
        result = kb_service.update_kb(kb_id, request.kb_name)
        return success_response(result)
    except KBServiceError as exc:
        _raise_http_from_kb_error(exc)


@router.delete("/{kb_id}")
def delete_kb(kb_id: str) -> dict:
    """删除空知识库；非空知识库不会级联删除。"""
    try:
        kb_service.delete_kb(kb_id)
        return success_response({"deleted": True})
    except KBServiceError as exc:
        _raise_http_from_kb_error(exc)
