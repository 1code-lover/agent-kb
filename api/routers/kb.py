"""
模块功能：
- 提供知识库文件导入、网页导入、列表查询和删除接口。

执行逻辑：
1. 接收文件/URL 请求并调用 kb_service 进行索引构建。
2. 返回知识库文档列表和删除结果。
3. 将异常统一映射为 HTTPException。
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.schemas import DeleteDocsRequest, UrlImportRequest
from api.services import kb_service
from utils.api_response import success_response

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])


@router.post("/file/import")
def import_files(
    files: list[UploadFile] = File(...),
    chunk_size: int = Form(2048),
    chunk_overlap: int = Form(512),
) -> dict:
    """
    导入上传文件并构建索引。

    输入：
    - files(list[UploadFile]): 上传文件集合。
    - chunk_size(int): 分块大小。
    - chunk_overlap(int): 分块重叠大小。

    输出：
    - dict: 标准化 API 响应，data 中包含导入与索引结果。
    """
    try:
        result = kb_service.import_files(files, chunk_size, chunk_overlap)
        return success_response(result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/web/import")
def import_web(request: UrlImportRequest) -> dict:
    """
    导入网页并构建索引。

    输入：
    - request(UrlImportRequest): URL 列表及分块参数。

    输出：
    - dict: 标准化 API 响应，data 中包含导入统计。
    """
    try:
        result = kb_service.import_urls(request.urls, request.chunk_size, request.chunk_overlap)
        return success_response(result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/list")
def list_docs() -> dict:
    """
    查询当前知识库文档列表。

    输出：
    - dict: 标准化 API 响应，data.docs 为文档数组。
    """
    try:
        return success_response({"docs": kb_service.list_docs()})
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/docs")
def delete_docs(request: DeleteDocsRequest) -> dict:
    """
    删除指定知识库文档。

    输入：
    - request(DeleteDocsRequest): 待删除文档 ID 或路径集合。

    输出：
    - dict: 标准化 API 响应，data 中包含删除结果。
    """
    try:
        result = kb_service.delete_docs(request)
        return success_response(result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
