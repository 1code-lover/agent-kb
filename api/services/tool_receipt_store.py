"""
文件功能：工具回执持久化服务
文件描述：提供工具回执的添加和查询功能，使用 SQLite 持久化存储
核心逻辑：通过工厂函数获取存储实例，委托存储层执行实际的数据库操作
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from api.services.storage.receipt_storage_factory import get_receipt_storage


def append_receipt(session_id: str, tool_name: str, input_data: Any, output_data: Any, status: str) -> dict[str, Any]:
    """
    函数名：append_receipt
    入参：
        - session_id (str): 会话 ID
        - tool_name (str): 工具名称
        - input_data (Any): 工具输入数据
        - output_data (Any): 工具输出数据
        - status (str): 执行状态
    功能：添加一条工具回执记录
    运行逻辑：
        1. 构造回执字典，生成唯一 ID 和时间戳
        2. 调用存储层 save 方法持久化
        3. 返回保存后的回执
    出参：dict[str, Any] - 保存后的完整回执
    """
    receipt = {
        "id": str(uuid4()),
        "session_id": session_id,
        "tool_name": tool_name,
        "input": input_data,
        "output": output_data,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return get_receipt_storage().save(receipt)


def list_receipts(session_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """
    函数名：list_receipts
    入参：
        - session_id (str): 会话 ID
        - limit (int): 返回记录数量上限，默认 50
    功能：列出指定会话的回执记录
    运行逻辑：调用存储层 list_by_session 方法查询
    出参：list[dict[str, Any]] - 回执列表，按创建时间倒序
    """
    return get_receipt_storage().list_by_session(session_id, limit)

