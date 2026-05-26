"""工具调用回执存储。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

_RECEIPTS: dict[str, list[dict[str, Any]]] = defaultdict(list)


def append_receipt(session_id: str, tool_name: str, input_data: Any, output_data: Any, status: str) -> dict[str, Any]:
    """写入一条工具回执。

    Args:
        session_id: 会话 ID。
        tool_name: 工具名称。
        input_data: 工具输入。
        output_data: 工具输出。
        status: 执行状态。

    Returns:
        Dict[str, Any]: 回执对象。
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
    _RECEIPTS[session_id].append(receipt)
    return receipt


def list_receipts(session_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """读取会话回执列表。"""
    return _RECEIPTS.get(session_id, [])[-limit:]
