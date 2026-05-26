"""统一 API 响应封装工具。"""

from __future__ import annotations

from typing import Any
from uuid import uuid4


def success_response(data: Any = None, message: str = "ok", request_id: str | None = None) -> dict[str, Any]:
    """构造成功响应。

    Args:
        data: 业务数据。
        message: 响应消息。
        request_id: 请求追踪 ID；若为空则自动生成。

    Returns:
        统一响应字典。
    """
    return {
        "code": 0,
        "message": message,
        "data": data if data is not None else {},
        "request_id": request_id or str(uuid4()),
    }


def error_response(code: int, message: str, data: Any = None, request_id: str | None = None) -> dict[str, Any]:
    """构造失败响应。

    Args:
        code: 错误码（非 0）。
        message: 错误信息。
        data: 附加数据。
        request_id: 请求追踪 ID；若为空则自动生成。

    Returns:
        统一响应字典。
    """
    return {
        "code": code,
        "message": message,
        "data": data if data is not None else {},
        "request_id": request_id or str(uuid4()),
    }
