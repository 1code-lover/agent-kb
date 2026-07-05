"""
文件功能：回执存储工厂
文件描述：提供获取回执存储单例的工厂函数
核心逻辑：使用模块级变量缓存 SQLiteReceiptStorage 实例，确保全局唯一
"""

from __future__ import annotations

from pathlib import Path

from api.services.storage.receipt_storage import ReceiptStorage
from api.services.storage.sqlite_receipt_storage import SQLiteReceiptStorage

_STORAGE: ReceiptStorage | None = None


def get_receipt_storage() -> ReceiptStorage:
    """
    函数名：get_receipt_storage
    入参：无
    功能：获取回执存储实例（单例模式）
    运行逻辑：
        1. 检查模块级缓存 _STORAGE 是否已初始化
        2. 如未初始化，创建 SQLiteReceiptStorage 实例（默认路径 storage/receipts.db）
        3. 返回存储实例
    出参：ReceiptStorage - 回执存储实例
    """
    global _STORAGE
    if _STORAGE is None:
        db_path = Path("storage") / "receipts.db"
        _STORAGE = SQLiteReceiptStorage(str(db_path))
    return _STORAGE
