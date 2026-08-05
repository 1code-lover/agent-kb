"""兼容历史拼写模块，统一转发到 storage_context。"""

from server.stores.storage_context import (
    STORAGE_CONTEXT,
    LazyStorageContext,
    create_storage_context,
    create_storage_context_for_kb,
    get_default_storage_context,
)

__all__ = [
    "STORAGE_CONTEXT",
    "LazyStorageContext",
    "create_storage_context",
    "create_storage_context_for_kb",
    "get_default_storage_context",
]
