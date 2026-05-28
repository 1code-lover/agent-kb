"""Model configuration and provider management services."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

import config
from api.schemas import (
    CustomProviderConnectionTestRequest,
    CustomProviderCreateRequest,
    ModelSelectRequest,
)
from api.services.fallback_store import FALLBACK_CONFIG_STORE

CUSTOM_PROVIDER_STORE_KEY = "custom_llm_providers"


def _get_config_store():
    try:
        from server.stores.config_store import CONFIG_STORE

        return CONFIG_STORE
    except Exception:
        return FALLBACK_CONFIG_STORE


def _mask_api_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}***{value[-4:]}"


def get_model_options() -> dict[str, Any]:
    config_store = _get_config_store()
    providers: dict[str, Any] = {}

    for name, provider in config.LLM_API_LIST.items():
        cloned = dict(provider)
        cloned["name"] = name
        if "api_key" in cloned and cloned["api_key"]:
            cloned["api_key"] = _mask_api_key(cloned["api_key"])
        providers[name] = cloned

    custom_provider_names: list[str] = []
    for provider in _get_custom_providers():
        cloned = dict(provider)
        cloned["name"] = provider["name"]
        if "api_key" in cloned and cloned["api_key"]:
            cloned["api_key"] = _mask_api_key(cloned["api_key"])
        providers[provider["name"]] = cloned
        custom_provider_names.append(provider["name"])

    return {
        "providers": providers,
        "custom_provider_names": custom_provider_names,
        "embedding_models": list(config.EMBEDDING_MODEL_PATH.keys()),
        "reranker_models": list(config.RERANKER_MODEL_PATH.keys()),
        "current_llm_info": config_store.get("current_llm_info"),
        "current_llm_settings": config_store.get("current_llm_settings"),
    }


def select_model(request: ModelSelectRequest) -> dict[str, Any]:
    config_store = _get_config_store()
    payload = request.model_dump(exclude_none=True)
    provider = _find_provider(request.service_provider)
    if provider is None:
        raise ValueError("provider not found")

    payload.setdefault("api_base", provider.get("api_base", ""))
    payload.setdefault("api_key", provider.get("api_key", ""))
    payload["api_base"] = (payload.get("api_base") or "").strip().rstrip("/")
    payload["api_key"] = payload.get("api_key") or ""
    payload["api_key_valid"] = True if payload["api_key"] or request.service_provider == "Ollama" else False
    config_store.put("current_llm_info", payload)
    return payload


def _find_provider(name: str) -> dict[str, Any] | None:
    if name in config.LLM_API_LIST:
        provider = dict(config.LLM_API_LIST[name])
        provider["name"] = name
        return provider

    for provider in _get_custom_providers():
        if provider.get("name") == name:
            return dict(provider)
    return None


def _get_custom_providers() -> list[dict[str, Any]]:
    config_store = _get_config_store()
    providers = config_store.get(CUSTOM_PROVIDER_STORE_KEY)
    if isinstance(providers, list):
        return providers
    return []


def _save_custom_providers(providers: list[dict[str, Any]]) -> None:
    config_store = _get_config_store()
    config_store.put(CUSTOM_PROVIDER_STORE_KEY, providers)


def add_custom_provider(request: CustomProviderCreateRequest) -> dict[str, Any]:
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
    target_name = name.strip()
    config_store = _get_config_store()
    providers = _get_custom_providers()
    new_providers = [item for item in providers if item.get("name") != target_name]
    if len(new_providers) == len(providers):
        raise ValueError("custom provider not found")
    _save_custom_providers(new_providers)

    current_llm_info = config_store.get("current_llm_info") or {}
    if current_llm_info.get("service_provider") == target_name:
        config_store.put("current_llm_info", {})

    return {"name": target_name, "deleted": True}


def _chat_completions_url(api_base: str) -> str:
    return f"{api_base.strip().rstrip('/')}/chat/completions"


def _check_openai_compatible(model_name: str, api_base: str, api_key: str) -> tuple[bool, str]:
    url = _chat_completions_url(api_base)
    payload = json.dumps(
        {
            "model": model_name,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "temperature": 0,
        }
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            if 200 <= response.status < 300:
                return True, "reachable"
            return False, f"http_{response.status}"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return False, f"http_{exc.code}: {detail[:200]}"
    except Exception as exc:
        return False, str(exc)


def test_custom_provider_connection(request: CustomProviderConnectionTestRequest) -> dict[str, Any]:
    reachable, detail = _check_openai_compatible(
        request.model.strip(),
        request.api_base.strip().rstrip("/"),
        request.api_key,
    )
    return {
        "reachable": reachable,
        "detail": detail,
        "api_base": request.api_base.strip().rstrip("/"),
        "model": request.model.strip(),
    }
