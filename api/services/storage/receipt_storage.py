"""
文件功能：回执存储抽象接口
文件描述：定义回执存储的抽象基类，规范 save、find_by_id、list_by_session 方法
核心逻辑：使用 ABC 定义接口契约，确保所有存储实现遵循统一规范
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ReceiptStorage(ABC):
    """回执存储接口"""

    @abstractmethod
    def save(self, receipt: dict[str, Any]) -> dict[str, Any]:
        """
        函数名：save
        入参：
            - receipt (dict[str, Any]): 回执数据，包含 session_id、tool_name、input、output、status 等字段
        功能：保存一条回执记录
        运行逻辑：由具体子类实现持久化逻辑
        出参：dict[str, Any] - 保存后的回执（含生成的 id 和 created_at）
        """
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, receipt_id: str) -> dict[str, Any] | None:
        """
        函数名：find_by_id
        入参：
            - receipt_id (str): 回执唯一标识
        功能：根据 ID 查询单条回执
        运行逻辑：由具体子类实现查询逻辑
        出参：dict[str, Any] | None - 找到时返回回执字典，未找到返回 None
        """
        raise NotImplementedError

    @abstractmethod
    def list_by_session(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        函数名：list_by_session
        入参：
            - session_id (str): 会话 ID
            - limit (int): 返回记录数量上限，默认 50
        功能：按会话 ID 查询回执列表
        运行逻辑：由具体子类实现查询逻辑，按创建时间倒序返回
        出参：list[dict[str, Any]] - 回执列表
        """
        raise NotImplementedError
