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
    ProviderConfigImportRequest,
)
from api.services.fallback_store import FALLBACK_CONFIG_STORE
from api.services.session_store import update_session
from utils.logging_utils import MODEL_TEST_LOG_FILE, append_json_log, new_trace_id, now_iso

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
    update_session(
        request.session_id,
        {
            "workspace": {
                "provider": {
                    "name": payload["service_provider"],
                    "base_url": payload["api_base"],
                    "model": payload["model"],
                }
            }
        },
    )
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


def _normalize_provider_payload(payload: dict[str, Any], existing_provider: dict[str, Any] | None = None) -> dict[str, Any]:
    incoming_api_key = payload.get("api_key", "")
    persisted_api_key = existing_provider.get("api_key", "") if existing_provider else ""
    normalized = {
        "name": payload["name"].strip(),
        "provider": payload["name"].strip(),
        "api_base": payload["api_base"].strip().rstrip("/"),
        "models": [item.strip() for item in payload["models"] if item.strip()],
        "api_key": incoming_api_key if incoming_api_key else persisted_api_key,
    }
    if len(normalized["models"]) == 0:
        raise ValueError("models cannot be empty")
    return normalized


def add_custom_provider(request: CustomProviderCreateRequest) -> dict[str, Any]:
    providers = _get_custom_providers()
    payload = request.model_dump()
    existing_provider = next((item for item in providers if item.get("name") == payload["name"].strip()), None)
    normalized = _normalize_provider_payload(payload, existing_provider)

    updated = False
    for idx, provider in enumerate(providers):
        if provider.get("name") == normalized["name"]:
            providers[idx] = normalized
            updated = True
            break
    if not updated:
        providers.append(normalized)
    _save_custom_providers(providers)
    return {
        "name": normalized["name"],
        "api_base": normalized["api_base"],
        "models": normalized["models"],
        "api_key_saved": bool(normalized["api_key"]),
    }


def export_provider_config() -> dict[str, Any]:
    config_store = _get_config_store()
    return {
        "custom_llm_providers": _get_custom_providers(),
        "current_llm_info": config_store.get("current_llm_info"),
    }


def import_provider_config(request: ProviderConfigImportRequest) -> dict[str, Any]:
    config_store = _get_config_store()
    existing_providers = _get_custom_providers()
    existing_provider_map = {item.get("name"): item for item in existing_providers}

    if request.mode == "merge":
        merged_provider_map = {item.get("name"): item for item in existing_providers}
    else:
        merged_provider_map = {}

    for item in request.custom_llm_providers:
        payload = item.model_dump()
        name = payload["name"].strip()
        merged_provider_map[name] = _normalize_provider_payload(payload, existing_provider_map.get(name))

    normalized_providers = list(merged_provider_map.values())
    _save_custom_providers(normalized_providers)

    current_llm_info = request.current_llm_info.model_dump(exclude_none=True) if request.current_llm_info else None
    if current_llm_info is not None:
        config_store.put("current_llm_info", current_llm_info)
    elif request.mode == "replace":
        config_store.put("current_llm_info", {})

    return {
        "mode": request.mode,
        "provider_count": len(normalized_providers),
        "current_llm_info": config_store.get("current_llm_info"),
    }


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


def _check_openai_compatible(model_name: str, api_base: str, api_key: str, trace_id: str) -> tuple[bool, str, dict[str, Any]]:
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
    meta: dict[str, Any] = {
        "trace_id": trace_id,
        "tested_at": now_iso(),
        "api_base": api_base,
        "request_url": url,
        "model": model_name,
        "api_key_present": bool(api_key),
    }

    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            meta["status_code"] = response.status
            if 200 <= response.status < 300:
                meta["result"] = "reachable"
                return True, "reachable", meta
            meta["result"] = "http_error"
            return False, f"http_{response.status}", meta
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        meta["status_code"] = exc.code
        meta["result"] = "http_error"
        meta["detail"] = detail[:800]
        return False, f"http_{exc.code}: {detail[:200]}", meta
    except Exception as exc:
        meta["result"] = "exception"
        meta["exception_type"] = type(exc).__name__
        meta["detail"] = str(exc)
        return False, str(exc), meta


def test_custom_provider_connection(request: CustomProviderConnectionTestRequest) -> dict[str, Any]:
    trace_id = new_trace_id("modeltest")
    normalized_api_base = request.api_base.strip().rstrip("/")
    normalized_model = request.model.strip()
    api_key = request.api_key

    if not api_key and request.provider_name:
        provider = _find_provider(request.provider_name)
        if provider:
            api_key = provider.get("api_key", "")

    if not api_key:
        detail = "api_key is required"
        append_json_log(
            "model_test_logger",
            MODEL_TEST_LOG_FILE,
            {
                "trace_id": trace_id,
                "tested_at": now_iso(),
                "api_base": normalized_api_base,
                "model": normalized_model,
                "provider_name": request.provider_name,
                "reachable": False,
                "detail": detail,
                "api_key_present": False,
            },
        )
        return {
            "reachable": False,
            "detail": detail,
            "trace_id": trace_id,
            "log_file": str(MODEL_TEST_LOG_FILE),
            "api_base": normalized_api_base,
            "model": normalized_model,
        }

    reachable, detail, meta = _check_openai_compatible(
        normalized_model,
        normalized_api_base,
        api_key,
        trace_id,
    )
    log_payload = {
        "trace_id": trace_id,
        "tested_at": meta.get("tested_at", now_iso()),
        "api_base": normalized_api_base,
        "model": normalized_model,
        "reachable": reachable,
        "detail": detail,
        "request_url": meta.get("request_url"),
        "status_code": meta.get("status_code"),
        "exception_type": meta.get("exception_type"),
        "api_key_present": meta.get("api_key_present"),
        "raw_detail": meta.get("detail", ""),
    }
    append_json_log("model_test_logger", MODEL_TEST_LOG_FILE, log_payload)

    return {
        "reachable": reachable,
        "detail": detail,
        "trace_id": trace_id,
        "log_file": str(MODEL_TEST_LOG_FILE),
        "api_base": normalized_api_base,
        "model": normalized_model,
    }
