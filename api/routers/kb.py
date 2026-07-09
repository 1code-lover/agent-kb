"""
模块功能：
- 提供知识库 CRUD、文件/网页导入、文档列表和删除接口。

执行逻辑：
1. 接收 KB CRUD 请求并调用 kb_service 操作 registry。
2. 接收文件/URL 请求并调用 kb_service 进行索引构建。
3. 返回知识库文档列表和删除结果。
4. 将异常统一映射为 HTTPException。
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.schemas import DeleteDocsRequest, UrlImportRequest
from api.schemas.kb import KBCreateRequest, KBUpdateRequest
from api.services import kb_service
from utils.api_response import success_response

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])


# ── KB CRUD ──

@router.post("")
def create_kb(request: KBCreateRequest) -> dict:
    """创建知识库"""
    try:
        result = kb_service.create_kb(request.kb_id, request.kb_name)
        return success_response(result)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("")
def list_kbs() -> dict:
    """获取全部知识库列表"""
    return success_response({"items": kb_service.list_kbs()})


@router.get("/{kb_id}")
def get_kb(kb_id: str) -> dict:
    """获取指定知识库"""
    result = kb_service.get_kb(kb_id)
    if result is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return success_response(result)


@router.put("/{kb_id}")
def update_kb(kb_id: str, request: KBUpdateRequest) -> dict:
    """更新知识库名称"""
    try:
        result = kb_service.update_kb(kb_id, request.kb_name)
        return success_response(result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{kb_id}")
def delete_kb(kb_id: str) -> dict:
    """删除知识库（含级联删除关联文档）"""
    try:
        kb_service.delete_kb(kb_id)
        return success_response({"deleted": True})
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── 文件/网页导入 ──

@router.post("/file/import")
def import_files(
    files: list[UploadFile] = File(...),
    chunk_size: int = Form(2048),
    chunk_overlap: int = Form(512),
    kb_id: str = Form("default"),
) -> dict:
    """导入上传文件并构建索引（支持按知识库导入）"""
    try:
        result = kb_service.import_files(files, chunk_size, chunk_overlap, kb_id=kb_id)
        return success_response(result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/web/import")
def import_web(request: UrlImportRequest) -> dict:
    """导入网页并构建索引"""
    try:
        result = kb_service.import_urls(request.urls, request.chunk_size, request.chunk_overlap)
        return success_response(result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── 文档管理 ──

@router.get("/list")
def list_docs(kb_id: str | None = None) -> dict:
    """查询知识库文档列表（可选按 kb_id 过滤）"""
    try:
        return success_response({"docs": kb_service.list_docs(kb_id=kb_id)})
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/docs")
def delete_docs(request: DeleteDocsRequest) -> dict:
    """删除指定知识库文档"""
    try:
        result = kb_service.delete_docs(request)
        return success_response(result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
