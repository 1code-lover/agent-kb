"""
模块功能：
- 提供服务健康检查接口。

执行逻辑：
1. 返回服务基础健康状态用于前端与监控探测。
"""

from __future__ import annotations

from fastapi import APIRouter

from utils.api_response import success_response

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict:
    """
    返回服务健康状态。

    输出：
    - dict: 标准化 API 响应，data.status 固定为 ok。
    """
    return success_response({"status": "ok"})
