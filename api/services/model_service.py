"""模型服务，封装模型配置与候选项读取。"""

from __future__ import annotations

from typing import Any

import config
from api.schemas import (
    CustomProviderConnectionTestRequest,
    CustomProviderCreateRequest,
    ModelSelectRequest,
)

CUSTOM_PROVIDER_STORE_KEY = "custom_llm_providers"


def _get_config_store():
    """惰性加载配置存储。"""
    try:
        from server.stores.config_store import CONFIG_STORE

        return CONFIG_STORE
    except Exception:
        if not hasattr(_get_config_store, "_memory_store"):
            _get_config_store._memory_store = {}

        class _FallbackStore:
            def get(self, key):
                """
                从内存回退存储读取配置值。

                Args:
                    key: 配置键名。

                Returns:
                    Any: 键对应的值，不存在时返回 None。
                """
                return _get_config_store._memory_store.get(key)

            def put(self, key, value):
                """
                写入配置到内存回退存储。

                Args:
                    key: 配置键名。
                    value: 配置值。

                Returns:
                    None
                """
                _get_config_store._memory_store[key] = value

        return _FallbackStore()


def get_model_options() -> dict[str, Any]:
    """获取可选模型列表和当前配置。"""
    config_store = _get_config_store()
    providers: dict[str, Any] = {}
    for name, provider in config.LLM_API_LIST.items():
        cloned = dict(provider)
        if "api_key" in cloned and cloned["api_key"]:
            cloned["api_key"] = "***"
        providers[name] = cloned
    custom_provider_names: list[str] = []
    for provider in _get_custom_providers():
        cloned = dict(provider)
        if "api_key" in cloned and cloned["api_key"]:
            cloned["api_key"] = "***"
        providers[provider["name"]] = cloned
        custom_provider_names.append(provider["name"])

    return {
        "providers": providers,
        "custom_provider_names": custom_provider_names,
        "embedding_models": list(config.EMBEDDING_MODEL_PATH.keys()),
        "reranker_models": list(config.RERANKER_MODEL_PATH.keys()),
        "current_llm_info": config_store.get("current_llm_info"),
    }


def select_model(request: ModelSelectRequest) -> dict[str, Any]:
    """保存当前模型选择。"""
    config_store = _get_config_store()
    payload = request.model_dump(exclude_none=True)
    provider = _find_provider(request.service_provider)
    if provider is not None:
        payload.setdefault("api_base", provider.get("api_base", ""))
        payload.setdefault("api_key", provider.get("api_key", ""))
        payload.setdefault("api_key_valid", True if provider.get("api_key") or request.service_provider == "Ollama" else False)
    config_store.put("current_llm_info", payload)
    return payload


def _find_provider(name: str) -> dict[str, Any] | None:
    """按名称查找内置或自定义 provider。"""
    if name in config.LLM_API_LIST:
        provider = dict(config.LLM_API_LIST[name])
        provider["name"] = name
        return provider
    for provider in _get_custom_providers():
        if provider.get("name") == name:
            return dict(provider)
    return None


def _get_custom_providers() -> list[dict[str, Any]]:
    """读取已保存的自定义 provider 列表。"""
    config_store = _get_config_store()
    providers = config_store.get(CUSTOM_PROVIDER_STORE_KEY)
    if isinstance(providers, list):
        return providers
    return []


def _save_custom_providers(providers: list[dict[str, Any]]) -> None:
    """持久化自定义 provider 列表。"""
    config_store = _get_config_store()
    config_store.put(CUSTOM_PROVIDER_STORE_KEY, providers)


def add_custom_provider(request: CustomProviderCreateRequest) -> dict[str, Any]:
    """新增或更新自定义 provider。"""
    providers = _get_custom_providers()
    payload = request.model_dump()
    normalized = {
        "name": payload["name"].strip(),
        "provider": payload["name"].strip(),
        "api_base": payload["api_base"].strip().rstrip("/"),
        "models": [item.strip() for item in payload["models"] if item.strip()],
        "api_key": payload["api_key"],
    }
    if len(normalized["models"]) == 0:
        raise ValueError("models cannot be empty")

    updated = False
    for idx, provider in enumerate(providers):
        if provider.get("name") == normalized["name"]:
            providers[idx] = normalized
            updated = True
            break
    if not updated:
        providers.append(normalized)
    _save_custom_providers(providers)
    return {"name": normalized["name"], "api_base": normalized["api_base"], "models": normalized["models"]}


def delete_custom_provider(name: str) -> dict[str, Any]:
    """删除自定义 provider。"""
    target_name = name.strip()
    providers = _get_custom_providers()
    new_providers = [item for item in providers if item.get("name") != target_name]
    if len(new_providers) == len(providers):
        raise ValueError("custom provider not found")
    _save_custom_providers(new_providers)
    return {"name": target_name, "deleted": True}


def _check_openai_compatible(model_name: str, api_base: str, api_key: str) -> bool:
    """检查 OpenAI 兼容接口连通性。"""
    from server.models.llm_api import check_openai_llm

    return check_openai_llm(model_name=model_name, api_base=api_base, api_key=api_key)


def test_custom_provider_connection(request: CustomProviderConnectionTestRequest) -> dict[str, Any]:
    """测试自定义 provider 连通性。"""
    reachable = _check_openai_compatible(
        request.model.strip(),
        request.api_base.strip().rstrip("/"),
        request.api_key,
    )
    return {
        "reachable": reachable,
        "api_base": request.api_base.strip().rstrip("/"),
        "model": request.model.strip(),
    }
