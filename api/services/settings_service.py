"""Settings service."""

from __future__ import annotations

from typing import Any

import config
from api.schemas import SettingsUpdateRequest
from api.services.fallback_store import FALLBACK_CONFIG_STORE


def _get_config_store():
    try:
        from server.stores.config_store import CONFIG_STORE

        return CONFIG_STORE
    except Exception:
        return FALLBACK_CONFIG_STORE


def get_settings() -> dict[str, Any]:
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
    config_store = _get_config_store()
    saved = get_settings()["settings"]
    updates = request.model_dump(exclude_none=True)
    saved.update(updates)
    config_store.put("current_llm_settings", saved)
    return saved
