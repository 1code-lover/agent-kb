"""
文件功能：回执存储模块
文件描述：提供回执持久化存储的接口和实现
核心逻辑：定义抽象存储接口，SQLite 具体实现，以及工厂函数获取单例
"""

from api.services.storage.receipt_storage import ReceiptStorage
from api.services.storage.receipt_storage_factory import get_receipt_storage
from api.services.storage.sqlite_receipt_storage import SQLiteReceiptStorage

__all__ = ["ReceiptStorage", "SQLiteReceiptStorage", "get_receipt_storage"]
