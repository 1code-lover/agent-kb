"""
模块功能：
- 提供聊天问答与会话历史管理接口。

执行逻辑：
1. 接收 query 请求并调用 chat_service 生成回答。
2. 提供会话历史查询与清理能力。
3. 将异常转换为标准 HTTP 错误响应。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import QueryRequest
from api.services import chat_service
from utils.api_response import success_response

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/query")
def query(request: QueryRequest) -> dict:
    """
    执行一次聊天问答。

    输入：
    - request(QueryRequest): 用户问题和会话参数。

    输出：
    - dict: 标准化 API 响应，data 中包含答案与引用信息。
    """
    try:
        result = chat_service.query(request)
        return success_response(result)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/history")
def history(session_id: str = "default") -> dict:
    """
    查询指定会话历史消息。

    输入：
    - session_id(str): 会话 ID。

    输出：
    - dict: 标准化 API 响应，data 中包含消息数组。
    """
    return success_response({"session_id": session_id, "messages": chat_service.get_history(session_id)})


@router.delete("/history")
def clear_history(session_id: str = "default") -> dict:
    """
    清空指定会话历史。

    输入：
    - session_id(str): 会话 ID。

    输出：
    - dict: 标准化 API 响应，data 中返回清理结果。
    """
    chat_service.clear_history(session_id)
    return success_response({"session_id": session_id, "cleared": True})
