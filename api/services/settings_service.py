"""设置服务，封装读取与更新配置。"""

from __future__ import annotations

from typing import Any

import config
from api.schemas import SettingsUpdateRequest


def _get_config_store():
    """惰性加载配置存储，减少导入阶段硬依赖。"""
    try:
        from server.stores.config_store import CONFIG_STORE

        return CONFIG_STORE
    except Exception:
        # 降级为内存存储，保证 API 在依赖异常时仍可启动。
        if not hasattr(_get_config_store, "_memory_store"):
            _get_config_store._memory_store = {}

        class _FallbackStore:
            def get(self, key):
                """
                从内存回退存储读取配置值。

                Args:
                    key: 配置键名。

                Returns:
                    Any: 键对应值，不存在时返回 None。
                """
                return _get_config_store._memory_store.get(key)

            def put(self, key, value):
                """
                将配置写入内存回退存储。

                Args:
                    key: 配置键名。
                    value: 配置值。

                Returns:
                    None
                """
                _get_config_store._memory_store[key] = value

        return _FallbackStore()


def get_settings() -> dict[str, Any]:
    """读取当前 LLM 设置并返回存储环境信息。"""
    config_store = _get_config_store()
    current_llm_settings = config_store.get("current_llm_settings") or {
        "temperature": config.TEMPERATURE,
        "system_prompt": config.SYSTEM_PROMPT,
        "top_k": config.TOP_K,
        "response_mode": config.DEFAULT_RESPONSE_MODE,
        "use_reranker": config.USE_RERANKER,
        "top_n": config.RERANKER_MODEL_TOP_N,
        "embedding_model": config.DEFAULT_EMBEDDING_MODEL,
        "reranker_model": config.DEFAULT_RERANKER_MODEL,
    }
    return {
        "settings": current_llm_settings,
        "storage_mode": config.THINKRAG_ENV,
    }


def update_settings(request: SettingsUpdateRequest) -> dict[str, Any]:
    """更新当前 LLM 设置。"""
    config_store = _get_config_store()
    saved = get_settings()["settings"]
    updates = request.model_dump(exclude_none=True)
    saved.update(updates)
    config_store.put("current_llm_settings", saved)
    return saved
