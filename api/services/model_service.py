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
MODEL_HEALTH_STORE_KEY = "model_health_status"
RECOVERABLE_MODEL_ERROR_KINDS = {
    "quota_exhausted",
    "forbidden",
    "unauthorized",
    "model_unavailable",
    "network_error",
    "request_incompatible",
}


def _default_model_health() -> dict[str, Any]:
    """创建模型健康状态默认快照。"""
    return {
        "state": "unknown",
        "current_provider": "",
        "current_model": "",
        "last_error_kind": None,
        "last_error": None,
        "last_checked_at": None,
        "last_fallback_at": None,
        "fallback_from": None,
        "fallback_to": None,
        "candidate_count": 0,
        "fallback_attempts": [],
        "fallback_attempt_summary": {},
    }


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
        "model_health": get_model_health(),
    }


def select_model(
    request: ModelSelectRequest,
    probe_result: tuple[bool, str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
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
    reachable, detail, meta = probe_result or _probe_selected_model(payload)
    probe_results = [
        {
            "service_provider": payload["service_provider"],
            "model": payload["model"],
            "api_base": payload["api_base"],
            "reachable": reachable,
            "detail": detail,
        }
    ]
    error_kind = None if reachable else classify_model_error(detail, meta.get("status_code"))
    update_model_health(
        state="healthy" if reachable else "unavailable",
        current_provider=payload["service_provider"],
        current_model=payload["model"],
        last_error_kind=error_kind,
        last_error=None if reachable else detail,
        last_checked_at=now_iso(),
        last_fallback_at=None,
        fallback_from=None,
        fallback_to=None,
        candidate_count=1,
        fallback_attempts=probe_results,
        fallback_attempt_summary=_summarize_fallback_attempts(probe_results),
    )
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


def _probe_selected_model(payload: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    """选择模型后做一次轻量探活，避免坏配置被标记为 healthy。"""
    trace_id = new_trace_id("select")
    provider = str(payload.get("service_provider") or "")
    model = str(payload.get("model") or "")
    api_base = str(payload.get("api_base") or "")
    api_key = str(payload.get("api_key") or "")
    if not payload.get("api_key_valid"):
        return False, "api_key is required", {"trace_id": trace_id, "status_code": 401}
    candidate = {"service_provider": provider, "model": model, "api_base": api_base, "api_key": api_key}
    if _candidate_is_ollama(candidate):
        return _check_ollama_model(model, api_base, trace_id)
    return _check_openai_compatible(model, api_base, api_key, trace_id)


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


def get_model_health() -> dict[str, Any]:
    """读取模型健康状态，并补齐当前模型快照。"""
    config_store = _get_config_store()
    current = config_store.get("current_llm_info") or {}
    saved = config_store.get(MODEL_HEALTH_STORE_KEY)
    status = _default_model_health()
    if isinstance(saved, dict):
        status.update(saved)
    status["current_provider"] = current.get("service_provider", status.get("current_provider") or "")
    status["current_model"] = current.get("model", status.get("current_model") or "")
    return status


def update_model_health(**changes: Any) -> dict[str, Any]:
    """合并写入模型健康状态。"""
    config_store = _get_config_store()
    status = get_model_health()
    status.update(changes)
    config_store.put(MODEL_HEALTH_STORE_KEY, status)
    return status


def classify_model_error(error: Any, status_code: int | None = None) -> str:
    """把模型调用异常或 HTTP 错误文本归类为稳定错误类型。"""
    text = str(error or "")
    lowered = text.lower()
    if status_code == 401 or "http_401" in lowered or "401 unauthorized" in lowered or "invalid_api_key" in lowered:
        return "unauthorized"
    if (
        "free quota exhausted" in lowered
        or "quota exhausted" in lowered
        or "allocationquota" in lowered
        or "insufficient_quota" in lowered
        or "rate limit" in lowered
    ):
        return "quota_exhausted"
    if status_code == 403 or "http_403" in lowered or "error code: 403" in lowered or "403 forbidden" in lowered:
        return "forbidden"
    if (
        "model not found" in lowered
        or "model_not_found" in lowered
        or "does not exist" in lowered
        or "unsupported model" in lowered
        or "model unavailable" in lowered
    ):
        return "model_unavailable"
    if any(
        marker in lowered
        for marker in (
            "range of input length should be",
            "maximum context length",
            "context_length_exceeded",
            "prompt is too long",
            "input is too long",
        )
    ):
        return "request_incompatible"
    if any(marker in lowered for marker in ("timed out", "timeout", "connection refused", "connection reset", "network")):
        return "network_error"
    return "unknown"


def is_recoverable_model_error(error: Any) -> bool:
    """判断异常是否适合触发自动 fallback。"""
    return classify_model_error(error) in RECOVERABLE_MODEL_ERROR_KINDS


def _ollama_tags_url(api_base: str) -> str:
    """返回 Ollama 本地模型列表接口地址。"""
    return f"{(api_base or config.OLLAMA_API_URL).strip().rstrip('/')}/api/tags"


def _extract_ollama_model_names(payload: dict[str, Any]) -> list[str]:
    """从 Ollama /api/tags 响应中提取模型名。"""
    models = payload.get("models")
    if not isinstance(models, list):
        return []
    names: list[str] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("model") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _list_ollama_models(api_base: str, trace_id: str) -> tuple[list[str], dict[str, Any]]:
    """读取本地 Ollama 已安装模型列表。"""
    url = _ollama_tags_url(api_base)
    request = urllib.request.Request(url, method="GET")
    meta: dict[str, Any] = {
        "trace_id": trace_id,
        "tested_at": now_iso(),
        "api_base": api_base,
        "request_url": url,
        "api_key_present": False,
    }
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8", errors="ignore")
            payload = json.loads(body or "{}")
            names = _extract_ollama_model_names(payload if isinstance(payload, dict) else {})
            meta["status_code"] = response.status
            meta["result"] = "reachable"
            meta["models"] = names[:50]
            return names, meta
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        meta["status_code"] = exc.code
        meta["result"] = "http_error"
        meta["detail"] = detail[:800]
        return [], meta
    except Exception as exc:
        meta["result"] = "exception"
        meta["exception_type"] = type(exc).__name__
        meta["detail"] = str(exc)
        return [], meta


def _check_ollama_model(model_name: str, api_base: str, trace_id: str) -> tuple[bool, str, dict[str, Any]]:
    """判断本地 Ollama 服务是否存在目标模型。"""
    names, meta = _list_ollama_models(api_base, trace_id)
    if model_name in names:
        meta["model"] = model_name
        meta["result"] = "reachable"
        return True, "reachable", meta
    meta["model"] = model_name
    meta["result"] = "model_missing" if names else meta.get("result", "no_models")
    return False, "model_not_found" if names else "ollama_unreachable", meta


def _ollama_discovery_detail(names: list[str], meta: dict[str, Any]) -> str:
    """把 Ollama 动态候选发现结果转换为可展示的诊断详情。"""
    if names:
        return "ollama_models_discovered"
    result = str(meta.get("result") or "").strip()
    if result == "reachable":
        return "ollama_no_models"
    if result == "http_error":
        status_code = meta.get("status_code")
        return f"ollama_http_{status_code}" if status_code else "ollama_http_error"
    return "ollama_unreachable"


def _candidate_is_ollama(candidate: dict[str, Any]) -> bool:
    """判断候选是否为 Ollama 本地模型。"""
    return str(candidate.get("service_provider") or "").strip() == "Ollama"


def _summarize_fallback_attempts(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总 fallback 候选探测结果，供 API/UI 展示明确切换提示。"""
    total = len(attempts)
    reachable = [item for item in attempts if item.get("reachable")]
    failed = [item for item in attempts if not item.get("reachable")]
    ollama = [item for item in attempts if _candidate_is_ollama(item)]
    last_attempt = attempts[-1] if attempts else {}
    return {
        "total": total,
        "reachable_count": len(reachable),
        "failed_count": len(failed),
        "ollama_candidate_count": len(ollama),
        "ollama_reachable_count": sum(1 for item in ollama if item.get("reachable")),
        "last_provider": str(last_attempt.get("service_provider") or ""),
        "last_model": str(last_attempt.get("model") or ""),
        "last_detail": str(last_attempt.get("detail") or ""),
    }


def _iter_provider_candidates(current_info: dict[str, Any]) -> list[dict[str, Any]]:
    """按优先级枚举 OpenAI 兼容与 Ollama 本地模型候选。"""
    providers: list[dict[str, Any]] = []
    for name, provider in config.LLM_API_LIST.items():
        item = dict(provider)
        item["name"] = name
        providers.append(item)
    providers.extend(dict(item) for item in _get_custom_providers())

    current_provider = current_info.get("service_provider")
    current_model = current_info.get("model")

    def provider_priority(provider: dict[str, Any]) -> tuple[int, str]:
        return (0 if provider.get("name") == current_provider else 1, str(provider.get("name") or ""))

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for provider in sorted(providers, key=provider_priority):
        provider_name = str(provider.get("name") or provider.get("provider") or "").strip()
        api_base = str(provider.get("api_base") or (config.OLLAMA_API_URL if provider_name == "Ollama" else "")).strip().rstrip("/")
        api_key = provider.get("api_key") or ""
        if not api_base:
            continue
        provider_models = [str(item or "").strip() for item in (provider.get("models", []) or []) if str(item or "").strip()]
        if provider_name == "Ollama" and not provider_models:
            provider_models, _meta = _list_ollama_models(api_base, new_trace_id("ollama"))
            if not provider_models:
                key = (provider_name, api_base, "__ollama_discovery__")
                if key not in seen:
                    seen.add(key)
                    candidates.append(
                        {
                            "service_provider": provider_name,
                            "model": "",
                            "api_base": api_base,
                            "api_key": "",
                            "discovery_only": True,
                        }
                    )
                continue
        if provider_name != "Ollama" and not api_key:
            continue
        for model_name in provider_models:
            model = str(model_name or "").strip()
            if not model:
                continue
            if provider_name == current_provider and model == current_model:
                continue
            key = (provider_name, api_base, model)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "service_provider": provider_name,
                    "model": model,
                    "api_base": api_base,
                    "api_key": api_key,
                }
            )
    return candidates


def attempt_model_fallback(error: Any, session_id: str = "desktop-default") -> dict[str, Any]:
    """遇到可恢复模型错误时，探测并切换到首个可用候选模型。"""
    config_store = _get_config_store()
    current_info = config_store.get("current_llm_info") or {}
    error_kind = classify_model_error(error)
    candidates = _iter_provider_candidates(current_info)
    base_status = {
        "state": "degraded" if error_kind in RECOVERABLE_MODEL_ERROR_KINDS else "unavailable",
        "current_provider": current_info.get("service_provider", ""),
        "current_model": current_info.get("model", ""),
        "last_error_kind": error_kind,
        "last_error": str(error)[:500],
        "last_checked_at": now_iso(),
        "candidate_count": len(candidates),
        "fallback_from": {
            "service_provider": current_info.get("service_provider", ""),
            "model": current_info.get("model", ""),
            "api_base": current_info.get("api_base", ""),
        },
    }
    update_model_health(**base_status)

    if error_kind not in RECOVERABLE_MODEL_ERROR_KINDS:
        return {"applied": False, "reason": "non_recoverable", "error_kind": error_kind, "candidate_count": len(candidates)}

    trace_id = new_trace_id("fallback")
    probe_results: list[dict[str, Any]] = []
    for candidate in candidates:
        if _candidate_is_ollama(candidate):
            if candidate.get("discovery_only"):
                names, meta = _list_ollama_models(candidate["api_base"], trace_id)
                reachable = False
                detail = _ollama_discovery_detail(names, meta)
            else:
                reachable, detail, _meta = _check_ollama_model(candidate["model"], candidate["api_base"], trace_id)
        else:
            reachable, detail, _meta = _check_openai_compatible(
                candidate["model"],
                candidate["api_base"],
                candidate["api_key"],
                trace_id,
            )
        probe_results.append(
            {
                "service_provider": candidate["service_provider"],
                "model": candidate["model"],
                "api_base": candidate["api_base"],
                "reachable": reachable,
                "detail": detail,
            }
        )
        if not reachable:
            continue
        attempt_summary = _summarize_fallback_attempts(probe_results)
        selected = select_model(
            ModelSelectRequest(
                service_provider=candidate["service_provider"],
                model=candidate["model"],
                api_base=candidate["api_base"],
                api_key=candidate["api_key"],
                session_id=session_id,
            ),
            probe_result=(reachable, detail, _meta),
        )
        status = update_model_health(
            state="fallback_applied",
            current_provider=selected["service_provider"],
            current_model=selected["model"],
            last_error_kind=error_kind,
            last_error=str(error)[:500],
            last_checked_at=now_iso(),
            last_fallback_at=now_iso(),
            fallback_to={
                "service_provider": selected["service_provider"],
                "model": selected["model"],
                "api_base": selected.get("api_base", ""),
            },
            candidate_count=len(candidates),
            fallback_attempts=probe_results,
            fallback_attempt_summary=attempt_summary,
        )
        return {
            "applied": True,
            "error_kind": error_kind,
            "selected": selected,
            "candidate_count": len(candidates),
            "fallback_attempts": probe_results,
            "fallback_attempt_summary": attempt_summary,
            "health": status,
        }

    attempt_summary = _summarize_fallback_attempts(probe_results)
    status = update_model_health(
        state="unavailable",
        last_checked_at=now_iso(),
        candidate_count=len(candidates),
        fallback_attempts=probe_results,
        fallback_attempt_summary=attempt_summary,
    )
    return {
        "applied": False,
        "reason": "no_reachable_candidate",
        "error_kind": error_kind,
        "candidate_count": len(candidates),
        "fallback_attempts": probe_results,
        "fallback_attempt_summary": attempt_summary,
        "health": status,
    }


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
