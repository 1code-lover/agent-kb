"""
配置存储辅助工具

提供统一的配置存储访问逻辑，避免 model_service 和 settings_service 重复。
"""

import warnings
from typing import Any


class FallbackStore:
    """内存回退存储，当持久化存储不可用时使用"""
    
    def __init__(self):
        self._data = {}
    
    def get(self, key: str, default=None):
        return self._data.get(key, default)
    
    def put(self, key: str, value):
        self._data[key] = value
        warnings.warn(
            "Config store is using in-memory fallback. "
            "Settings will be lost on restart.",
            RuntimeWarning,
            stacklevel=2
        )
    
    def delete(self, key: str):
        self._data.pop(key, None)


def get_config_store() -> Any:
    """
    获取配置存储实例
    
    优先使用持久化存储，失败时回退到内存存储
    """
    try:
        from server.stores.config_store import CONFIG_STORE
        return CONFIG_STORE
    except Exception as e:
        warnings.warn(
            f"Config store unavailable ({e}), using in-memory fallback. "
            "All settings will be lost on restart.",
            RuntimeWarning,
            stacklevel=2
        )
        return FallbackStore()
