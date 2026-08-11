"""\u6a21\u578b\u670d\u52a1\u4e0e\u4f9b\u5e94\u5546\u914d\u7f6e\u56de\u5f52\u6d4b\u8bd5\u3002"""

from __future__ import annotations

from io import BytesIO
from typing import Any
import urllib.error

import pytest

from api.schemas import (
    CustomProviderConnectionTestRequest,
    CustomProviderCreateRequest,
    ModelSelectRequest,
    ProviderConfigImportRequest,
)
from api.services import model_service


class _DummyStore:
    """\u6700\u5c0f\u5316\u914d\u7f6e\u5b58\u50a8\u66ff\u8eab\u3002"""

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self.values = dict(initial or {})
        self.put_calls: list[tuple[str, Any]] = []

    def get(self, key: str) -> Any:
        return self.values.get(key)

    def put(self, key: str, val: Any) -> None:
        self.put_calls.append((key, val))
        self.values[key] = val


class _FakeResponse:
    """\u6a21\u62df urllib \u6210\u529f\u54cd\u5e94\u4e0a\u4e0b\u6587\u3002"""

    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_mask_api_key_covers_empty_short_and_long_values() -> None:
    """API Key \u8131\u654f\u5e94\u8986\u76d6\u7a7a\u4e32\u3001\u77ed\u4e32\u548c\u957f\u4e32\u3002"""

    assert model_service._mask_api_key("") == ""
    assert model_service._mask_api_key("12345678") == "********"
    assert model_service._mask_api_key("sk-1234567890") == "sk-1***7890"


def test_get_model_options_masks_builtin_and_custom_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """\u6a21\u578b\u9009\u9879\u5e94\u8fd4\u56de\u8131\u654f\u540e\u7684\u5185\u7f6e/\u81ea\u5b9a\u4e49\u4f9b\u5e94\u5546\u5feb\u7167\u3002"""

    store = _DummyStore(
        {
            "current_llm_info": {"service_provider": "Builtin"},
            "current_llm_settings": {"embedding_model": "embed-x"},
        }
    )
    monkeypatch.setattr(model_service, "_get_config_store", lambda: store)
    monkeypatch.setattr(
        model_service.config,
        "LLM_API_LIST",
        {
            "Builtin": {
                "provider": "Builtin",
                "api_base": "https://builtin.example/v1",
                "api_key": "builtin-secret-1234",
                "models": ["gpt-test"],
            }
        },
        raising=False,
    )
    monkeypatch.setattr(model_service.config, "EMBEDDING_MODEL_PATH", {"embed-x": "x"}, raising=False)
    monkeypatch.setattr(model_service.config, "RERANKER_MODEL_PATH", {"rerank-y": "y"}, raising=False)
    monkeypatch.setattr(
        model_service,
        "_get_custom_providers",
        lambda: [
            {
                "name": "Acme",
                "provider": "Acme",
                "api_base": "https://acme.example/v1",
                "api_key": "custom-secret-5678",
                "models": ["acme-chat"],
            }
        ],
    )

    result = model_service.get_model_options()

    assert result["providers"]["Builtin"]["api_key"] == "buil***1234"
    assert result["providers"]["Acme"]["api_key"] == "cust***5678"
    assert result["custom_provider_names"] == ["Acme"]
    assert result["embedding_models"] == ["embed-x"]
    assert result["reranker_models"] == ["rerank-y"]
    assert result["current_llm_info"] == {"service_provider": "Builtin"}


def test_select_model_uses_provider_defaults_and_updates_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """\u9009\u62e9\u6a21\u578b\u65f6\u5e94\u8865\u9f50\u4f9b\u5e94\u5546\u9ed8\u8ba4\u503c\u5e76\u5237\u65b0\u4f1a\u8bdd\u5feb\u7167\u3002"""

    store = _DummyStore()
    session_updates: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(model_service, "_get_config_store", lambda: store)
    monkeypatch.setattr(model_service, "now_iso", lambda: "2026-08-10T00:00:00Z")
    monkeypatch.setattr(
        model_service,
        "_find_provider",
        lambda name: {"name": name, "api_base": " https://provider.example/v1/ ", "api_key": "sk-provider"},
    )
    monkeypatch.setattr(model_service, "update_session", lambda session_id, payload: session_updates.append((session_id, payload)))

    payload = model_service.select_model(
        ModelSelectRequest(service_provider="Builtin", model="gpt-test", session_id="sess-1")
    )

    assert payload["api_base"] == "https://provider.example/v1"
    assert payload["api_key"] == "sk-provider"
    assert payload["api_key_valid"] is True
    assert store.values["current_llm_info"]["model"] == "gpt-test"
    assert store.values["model_health_status"]["state"] == "healthy"
    assert store.values["model_health_status"]["current_model"] == "gpt-test"
    assert session_updates == [
        (
            "sess-1",
            {
                "workspace": {
                    "provider": {
                        "name": "Builtin",
                        "base_url": "https://provider.example/v1",
                        "model": "gpt-test",
                    }
                }
            },
        )
    ]


def test_select_model_allows_ollama_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ollama \u4f5c\u4e3a\u672c\u5730\u63d0\u4f9b\u65b9\u65f6\u53ef\u65e0 API Key\u3002"""

    store = _DummyStore()
    monkeypatch.setattr(model_service, "_get_config_store", lambda: store)
    monkeypatch.setattr(
        model_service,
        "_find_provider",
        lambda name: {"name": name, "api_base": "http://localhost:11434", "api_key": ""},
    )
    monkeypatch.setattr(model_service, "update_session", lambda *_args, **_kwargs: None)

    payload = model_service.select_model(ModelSelectRequest(service_provider="Ollama", model="qwen2.5"))

    assert payload["api_key"] == ""
    assert payload["api_key_valid"] is True


def test_select_model_rejects_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """\u672a\u77e5\u4f9b\u5e94\u5546\u5e94\u7acb\u5373\u62d2\u7edd\u3002"""

    monkeypatch.setattr(model_service, "_find_provider", lambda _name: None)

    with pytest.raises(ValueError, match="provider not found"):
        model_service.select_model(ModelSelectRequest(service_provider="missing", model="x"))


def test_normalize_provider_payload_reuses_existing_key_and_validates_models() -> None:
    """\u4f9b\u5e94\u5546\u5f52\u4e00\u5316\u5e94\u4fdd\u7559\u65e7 key\uff0c\u5e76\u62d2\u7edd\u7a7a\u6a21\u578b\u5217\u8868\u3002"""

    normalized = model_service._normalize_provider_payload(
        {
            "name": "  Acme  ",
            "api_base": " https://acme.example/v1/ ",
            "models": [" chat-a ", "  ", "chat-b"],
            "api_key": "",
        },
        {"api_key": "persisted-key"},
    )

    assert normalized == {
        "name": "Acme",
        "provider": "Acme",
        "api_base": "https://acme.example/v1",
        "models": ["chat-a", "chat-b"],
        "api_key": "persisted-key",
    }

    with pytest.raises(ValueError, match="models cannot be empty"):
        model_service._normalize_provider_payload(
            {"name": "Acme", "api_base": "https://acme.example/v1", "models": ["  ", ""], "api_key": "x"}
        )


def test_add_custom_provider_appends_new_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """\u65b0\u589e\u81ea\u5b9a\u4e49\u4f9b\u5e94\u5546\u65f6\u5e94\u8ffd\u52a0\u5230\u6301\u4e45\u5316\u5217\u8868\u3002"""

    providers: list[dict[str, Any]] = []
    saved: dict[str, Any] = {}
    monkeypatch.setattr(model_service, "_get_custom_providers", lambda: providers)
    monkeypatch.setattr(model_service, "_save_custom_providers", lambda items: saved.setdefault("providers", list(items)))

    result = model_service.add_custom_provider(
        CustomProviderCreateRequest(
            name="Acme",
            api_base=" https://acme.example/v1/ ",
            models=["chat-a", " "],
            api_key="sk-acme",
        )
    )

    assert result == {
        "name": "Acme",
        "api_base": "https://acme.example/v1",
        "models": ["chat-a"],
        "api_key_saved": True,
    }
    assert saved["providers"] == [
        {
            "name": "Acme",
            "provider": "Acme",
            "api_base": "https://acme.example/v1",
            "models": ["chat-a"],
            "api_key": "sk-acme",
        }
    ]


def test_add_custom_provider_updates_existing_provider_without_losing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """\u66f4\u65b0\u540c\u540d\u4f9b\u5e94\u5546\u65f6\uff0c\u7a7a key \u4e0d\u5e94\u8986\u76d6\u5df2\u4fdd\u5b58\u5bc6\u94a5\u3002"""

    providers = [
        {
            "name": "Acme",
            "provider": "Acme",
            "api_base": "https://old.example/v1",
            "models": ["old-model"],
            "api_key": "persisted-key",
        }
    ]
    saved: list[list[dict[str, Any]]] = []
    monkeypatch.setattr(model_service, "_get_custom_providers", lambda: providers)
    monkeypatch.setattr(model_service, "_save_custom_providers", lambda items: saved.append(list(items)))

    result = model_service.add_custom_provider(
        CustomProviderCreateRequest(
            name="Acme",
            api_base="https://new.example/v1/",
            models=["new-model"],
            api_key="",
        )
    )

    assert result["api_key_saved"] is True
    assert saved[-1] == [
        {
            "name": "Acme",
            "provider": "Acme",
            "api_base": "https://new.example/v1",
            "models": ["new-model"],
            "api_key": "persisted-key",
        }
    ]


def test_export_and_import_provider_config_cover_merge_and_replace(monkeypatch: pytest.MonkeyPatch) -> None:
    """\u5bfc\u51fa/\u5bfc\u5165\u914d\u7f6e\u5e94\u8986\u76d6 merge \u4e0e replace \u4e24\u79cd\u6a21\u5f0f\u3002"""

    store = _DummyStore({"current_llm_info": {"service_provider": "Acme", "model": "chat-old"}})
    existing = [
        {
            "name": "Existing",
            "provider": "Existing",
            "api_base": "https://existing.example/v1",
            "models": ["existing-chat"],
            "api_key": "existing-key",
        }
    ]
    saved_batches: list[list[dict[str, Any]]] = []
    monkeypatch.setattr(model_service, "_get_config_store", lambda: store)
    monkeypatch.setattr(model_service, "_get_custom_providers", lambda: list(existing))
    monkeypatch.setattr(model_service, "_save_custom_providers", lambda items: saved_batches.append(list(items)))

    exported = model_service.export_provider_config()
    assert exported == {
        "custom_llm_providers": existing,
        "current_llm_info": {"service_provider": "Acme", "model": "chat-old"},
    }

    merge_result = model_service.import_provider_config(
        ProviderConfigImportRequest(
            mode="merge",
            custom_llm_providers=[
                CustomProviderCreateRequest(name="Existing", api_base="https://existing.example/v2", models=["existing-chat-v2"], api_key=""),
                CustomProviderCreateRequest(name="NewOne", api_base="https://new.example/v1", models=["new-chat"], api_key="new-key"),
            ],
            current_llm_info=ModelSelectRequest(service_provider="NewOne", model="new-chat", api_base="https://new.example/v1", api_key="new-key"),
        )
    )

    assert merge_result["mode"] == "merge"
    assert merge_result["provider_count"] == 2
    assert merge_result["current_llm_info"]["service_provider"] == "NewOne"
    assert {item["name"] for item in saved_batches[-1]} == {"Existing", "NewOne"}
    existing_saved = next(item for item in saved_batches[-1] if item["name"] == "Existing")
    assert existing_saved["api_key"] == "existing-key"
    assert existing_saved["api_base"] == "https://existing.example/v2"

    replace_store = _DummyStore({"current_llm_info": {"service_provider": "Old", "model": "old"}})
    monkeypatch.setattr(model_service, "_get_config_store", lambda: replace_store)
    monkeypatch.setattr(model_service, "_get_custom_providers", lambda: list(existing))
    replace_batches: list[list[dict[str, Any]]] = []
    monkeypatch.setattr(model_service, "_save_custom_providers", lambda items: replace_batches.append(list(items)))

    replace_result = model_service.import_provider_config(ProviderConfigImportRequest(mode="replace", custom_llm_providers=[]))

    assert replace_result == {"mode": "replace", "provider_count": 0, "current_llm_info": {}}
    assert replace_batches[-1] == []
    assert replace_store.values["current_llm_info"] == {}


def test_delete_custom_provider_updates_current_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    """\u5220\u9664\u5f53\u524d\u6b63\u5728\u4f7f\u7528\u7684\u81ea\u5b9a\u4e49\u4f9b\u5e94\u5546\u65f6\u5e94\u6e05\u7a7a\u5f53\u524d\u9009\u62e9\u3002"""

    store = _DummyStore({"current_llm_info": {"service_provider": "Acme"}})
    providers = [
        {"name": "Acme", "provider": "Acme", "api_base": "https://acme.example/v1", "models": ["chat"], "api_key": "k"},
        {"name": "Other", "provider": "Other", "api_base": "https://other.example/v1", "models": ["chat"], "api_key": "o"},
    ]
    saved: list[list[dict[str, Any]]] = []
    monkeypatch.setattr(model_service, "_get_config_store", lambda: store)
    monkeypatch.setattr(model_service, "_get_custom_providers", lambda: list(providers))
    monkeypatch.setattr(model_service, "_save_custom_providers", lambda items: saved.append(list(items)))

    result = model_service.delete_custom_provider("  Acme  ")

    assert result == {"name": "Acme", "deleted": True}
    assert saved[-1] == [providers[1]]
    assert store.values["current_llm_info"] == {}

    with pytest.raises(ValueError, match="custom provider not found"):
        model_service.delete_custom_provider("missing")


def test_check_openai_compatible_covers_success_http_error_and_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenAI \u517c\u5bb9\u6027\u63a2\u6d3b\u5e94\u8986\u76d6\u6210\u529f\u3001HTTP \u9519\u8bef\u4e0e\u5f02\u5e38\u3002"""

    def fake_success(request: Any, timeout: int = 0) -> _FakeResponse:
        assert timeout == 8
        assert request.full_url == "https://api.example/v1/chat/completions"
        assert request.get_header("Authorization") == "Bearer sk-test"
        return _FakeResponse(204)

    monkeypatch.setattr(model_service.urllib.request, "urlopen", fake_success)
    monkeypatch.setattr(model_service, "now_iso", lambda: "2026-07-30T00:00:00Z")

    ok, detail, meta = model_service._check_openai_compatible("chat-a", "https://api.example/v1/", "sk-test", "trace-1")
    assert (ok, detail) == (True, "reachable")
    assert meta["status_code"] == 204
    assert meta["request_url"] == "https://api.example/v1/chat/completions"

    def fake_http_error(_request: Any, timeout: int = 0) -> _FakeResponse:
        raise urllib.error.HTTPError(
            "https://api.example/v1/chat/completions",
            401,
            "Unauthorized",
            hdrs=None,
            fp=BytesIO(b'{"error":"bad key"}'),
        )

    monkeypatch.setattr(model_service.urllib.request, "urlopen", fake_http_error)
    ok, detail, meta = model_service._check_openai_compatible("chat-a", "https://api.example/v1", "sk-test", "trace-2")
    assert ok is False
    assert detail.startswith("http_401")
    assert meta["status_code"] == 401
    assert "bad key" in meta["detail"]

    monkeypatch.setattr(model_service.urllib.request, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("timeout")))
    ok, detail, meta = model_service._check_openai_compatible("chat-a", "https://api.example/v1", "sk-test", "trace-3")
    assert (ok, detail) == (False, "timeout")
    assert meta["result"] == "exception"
    assert meta["exception_type"] == "TimeoutError"


def test_classify_model_error_covers_quota_auth_forbidden_and_unavailable() -> None:
    """模型错误分类应覆盖额度、权限、不可用和网络问题。"""

    assert model_service.classify_model_error("Free quota exhausted AllocationQuota.FreeTierOnly") == "quota_exhausted"
    assert model_service.classify_model_error("bad key", status_code=401) == "unauthorized"
    assert model_service.classify_model_error("Error code: 403 forbidden") == "forbidden"
    assert model_service.classify_model_error("model not found") == "model_unavailable"
    assert model_service.classify_model_error("request timeout") == "network_error"
    assert model_service.classify_model_error("other") == "unknown"


def test_attempt_model_fallback_selects_first_reachable_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    """fallback 应跳过当前模型并选择首个探活成功候选。"""

    store = _DummyStore(
        {
            "current_llm_info": {
                "service_provider": "Acme",
                "model": "bad-chat",
                "api_base": "https://acme.example/v1",
                "api_key": "bad-key",
            },
            "custom_llm_providers": [
                {
                    "name": "Acme",
                    "provider": "Acme",
                    "api_base": "https://acme.example/v1",
                    "models": ["bad-chat", "good-chat"],
                    "api_key": "acme-key",
                },
                {
                    "name": "Other",
                    "provider": "Other",
                    "api_base": "https://other.example/v1",
                    "models": ["other-chat"],
                    "api_key": "other-key",
                },
            ],
        }
    )
    checks: list[tuple[str, str]] = []
    session_updates: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(model_service, "_get_config_store", lambda: store)
    monkeypatch.setattr(model_service.config, "LLM_API_LIST", {}, raising=False)
    monkeypatch.setattr(model_service, "now_iso", lambda: "2026-08-10T01:00:00Z")
    monkeypatch.setattr(model_service, "new_trace_id", lambda _prefix: "fallback-trace")
    monkeypatch.setattr(model_service, "update_session", lambda session_id, payload: session_updates.append((session_id, payload)))

    def fake_check(model_name: str, api_base: str, api_key: str, trace_id: str):
        checks.append((model_name, api_base))
        return model_name == "good-chat", "reachable" if model_name == "good-chat" else "http_403", {}

    monkeypatch.setattr(model_service, "_check_openai_compatible", fake_check)

    result = model_service.attempt_model_fallback("Free quota exhausted", session_id="sess-fallback")

    assert result["applied"] is True
    assert result["selected"]["model"] == "good-chat"
    assert checks[0] == ("good-chat", "https://acme.example/v1")
    assert store.values["current_llm_info"]["model"] == "good-chat"
    assert store.values["model_health_status"]["state"] == "fallback_applied"
    assert store.values["model_health_status"]["last_error_kind"] == "quota_exhausted"
    assert store.values["model_health_status"]["fallback_to"]["model"] == "good-chat"
    assert store.values["model_health_status"]["fallback_attempt_summary"] == {
        "total": 1,
        "reachable_count": 1,
        "failed_count": 0,
        "ollama_candidate_count": 0,
        "ollama_reachable_count": 0,
        "last_provider": "Acme",
        "last_model": "good-chat",
        "last_detail": "reachable",
    }
    assert store.values["model_health_status"]["fallback_attempts"] == [
        {
            "service_provider": "Acme",
            "model": "good-chat",
            "api_base": "https://acme.example/v1",
            "reachable": True,
            "detail": "reachable",
        }
    ]
    assert session_updates[0][0] == "sess-fallback"


def test_attempt_model_fallback_records_unavailable_when_no_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    """没有候选模型可用时，应记录 unavailable 状态并返回未切换。"""

    store = _DummyStore(
        {
            "current_llm_info": {"service_provider": "Acme", "model": "bad-chat", "api_base": "https://acme.example/v1", "api_key": "k"},
            "custom_llm_providers": [
                {"name": "Acme", "provider": "Acme", "api_base": "https://acme.example/v1", "models": ["bad-chat"], "api_key": "k"}
            ],
        }
    )
    monkeypatch.setattr(model_service, "_get_config_store", lambda: store)
    monkeypatch.setattr(model_service.config, "LLM_API_LIST", {}, raising=False)
    monkeypatch.setattr(model_service, "now_iso", lambda: "2026-08-10T01:30:00Z")

    result = model_service.attempt_model_fallback("Error code: 403", session_id="sess")

    assert result == {
        "applied": False,
        "reason": "no_reachable_candidate",
        "error_kind": "forbidden",
        "candidate_count": 0,
        "fallback_attempts": [],
        "fallback_attempt_summary": {
            "total": 0,
            "reachable_count": 0,
            "failed_count": 0,
            "ollama_candidate_count": 0,
            "ollama_reachable_count": 0,
            "last_provider": "",
            "last_model": "",
            "last_detail": "",
        },
        "health": store.values["model_health_status"],
    }
    assert store.values["model_health_status"]["state"] == "unavailable"


def test_attempt_model_fallback_can_select_ollama_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    """fallback 应支持无 API Key 的 Ollama 本地模型候选。"""

    store = _DummyStore(
        {
            "current_llm_info": {
                "service_provider": "OpenAI",
                "model": "bad-chat",
                "api_base": "https://api.example/v1",
                "api_key": "bad-key",
            },
        }
    )
    checks: list[tuple[str, str]] = []
    session_updates: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(model_service, "_get_config_store", lambda: store)
    monkeypatch.setattr(
        model_service.config,
        "LLM_API_LIST",
        {
            "Ollama": {
                "provider": "Ollama",
                "api_base": "http://localhost:11434",
                "models": [],
            }
        },
        raising=False,
    )
    monkeypatch.setattr(model_service, "now_iso", lambda: "2026-08-10T02:00:00Z")
    monkeypatch.setattr(model_service, "new_trace_id", lambda prefix: prefix + "-trace")
    monkeypatch.setattr(model_service, "update_session", lambda session_id, payload: session_updates.append((session_id, payload)))
    monkeypatch.setattr(model_service, "_list_ollama_models", lambda api_base, trace_id: (["qwen2.5:7b"], {"trace_id": trace_id}))

    def fake_check(model_name: str, api_base: str, trace_id: str):
        checks.append((model_name, api_base))
        return True, "reachable", {"trace_id": trace_id}

    monkeypatch.setattr(model_service, "_check_ollama_model", fake_check)

    result = model_service.attempt_model_fallback("model not found", session_id="ollama-fallback")

    assert result["applied"] is True
    assert result["selected"]["service_provider"] == "Ollama"
    assert result["selected"]["model"] == "qwen2.5:7b"
    assert result["selected"]["api_key"] == ""
    assert result["selected"]["api_key_valid"] is True
    assert checks == [("qwen2.5:7b", "http://localhost:11434")]
    assert store.values["model_health_status"]["fallback_to"]["service_provider"] == "Ollama"
    assert store.values["model_health_status"]["fallback_attempt_summary"] == {
        "total": 1,
        "reachable_count": 1,
        "failed_count": 0,
        "ollama_candidate_count": 1,
        "ollama_reachable_count": 1,
        "last_provider": "Ollama",
        "last_model": "qwen2.5:7b",
        "last_detail": "reachable",
    }
    assert store.values["model_health_status"]["fallback_attempts"] == [
        {
            "service_provider": "Ollama",
            "model": "qwen2.5:7b",
            "api_base": "http://localhost:11434",
            "reachable": True,
            "detail": "reachable",
        }
    ]
    assert session_updates[0][0] == "ollama-fallback"


def test_attempt_model_fallback_records_ollama_discovery_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ollama 动态发现失败时也应留下诊断候选，避免 UI 只看到 0 候选。"""

    store = _DummyStore(
        {
            "current_llm_info": {
                "service_provider": "OpenAI",
                "model": "bad-chat",
                "api_base": "https://api.example/v1",
                "api_key": "bad-key",
            },
        }
    )
    list_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(model_service, "_get_config_store", lambda: store)
    monkeypatch.setattr(
        model_service.config,
        "LLM_API_LIST",
        {
            "Ollama": {
                "provider": "Ollama",
                "api_base": "http://localhost:11434",
                "models": [],
            }
        },
        raising=False,
    )
    monkeypatch.setattr(model_service, "now_iso", lambda: "2026-08-11T22:00:00Z")
    monkeypatch.setattr(model_service, "new_trace_id", lambda prefix: prefix + "-trace")

    def fake_list_ollama_models(api_base: str, trace_id: str):
        list_calls.append((api_base, trace_id))
        return [], {"result": "exception", "detail": "connection refused", "trace_id": trace_id}

    monkeypatch.setattr(model_service, "_list_ollama_models", fake_list_ollama_models)

    result = model_service.attempt_model_fallback("model not found", session_id="ollama-discovery")

    assert result["applied"] is False
    assert result["candidate_count"] == 1
    assert result["fallback_attempts"] == [
        {
            "service_provider": "Ollama",
            "model": "",
            "api_base": "http://localhost:11434",
            "reachable": False,
            "detail": "ollama_unreachable",
        }
    ]
    assert result["fallback_attempt_summary"] == {
        "total": 1,
        "reachable_count": 0,
        "failed_count": 1,
        "ollama_candidate_count": 1,
        "ollama_reachable_count": 0,
        "last_provider": "Ollama",
        "last_model": "",
        "last_detail": "ollama_unreachable",
    }
    assert store.values["model_health_status"]["state"] == "unavailable"
    assert store.values["model_health_status"]["fallback_attempt_summary"] == result["fallback_attempt_summary"]
    assert list_calls == [("http://localhost:11434", "ollama-trace"), ("http://localhost:11434", "fallback-trace")]


def test_attempt_model_fallback_summarizes_failed_ollama_and_cloud_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    """fallback 全部失败时应记录可展示的云端/Ollama 候选摘要。"""

    store = _DummyStore(
        {
            "current_llm_info": {
                "service_provider": "OpenAI",
                "model": "bad-chat",
                "api_base": "https://api.example/v1",
                "api_key": "bad-key",
            },
        }
    )
    monkeypatch.setattr(model_service, "_get_config_store", lambda: store)
    monkeypatch.setattr(
        model_service.config,
        "LLM_API_LIST",
        {
            "Cloud": {
                "provider": "Cloud",
                "api_base": "https://cloud.example/v1",
                "api_key": "cloud-key",
                "models": ["cloud-chat"],
            },
            "Ollama": {
                "provider": "Ollama",
                "api_base": "http://localhost:11434",
                "models": ["qwen2.5:7b"],
            },
        },
        raising=False,
    )
    monkeypatch.setattr(model_service, "now_iso", lambda: "2026-08-10T02:30:00Z")
    monkeypatch.setattr(model_service, "new_trace_id", lambda prefix: prefix + "-trace")
    monkeypatch.setattr(
        model_service,
        "_check_openai_compatible",
        lambda model_name, api_base, api_key, trace_id: (False, "http_403", {"trace_id": trace_id}),
    )
    monkeypatch.setattr(
        model_service,
        "_check_ollama_model",
        lambda model_name, api_base, trace_id: (False, "model_not_found", {"trace_id": trace_id}),
    )

    result = model_service.attempt_model_fallback("model not found", session_id="fallback-summary")

    assert result["applied"] is False
    assert result["fallback_attempt_summary"] == {
        "total": 2,
        "reachable_count": 0,
        "failed_count": 2,
        "ollama_candidate_count": 1,
        "ollama_reachable_count": 0,
        "last_provider": "Ollama",
        "last_model": "qwen2.5:7b",
        "last_detail": "model_not_found",
    }
    assert store.values["model_health_status"]["fallback_attempt_summary"] == result["fallback_attempt_summary"]


def test_test_custom_provider_connection_rejects_missing_api_key_and_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    """\u8fde\u63a5\u6d4b\u8bd5\u5728\u6ca1\u6709 API Key \u65f6\u5e94\u76f4\u63a5\u62d2\u7edd\u5e76\u5199\u65e5\u5fd7\u3002"""

    log_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(model_service, "new_trace_id", lambda _prefix: "trace-no-key")
    monkeypatch.setattr(model_service, "now_iso", lambda: "2026-07-30T08:00:00Z")
    monkeypatch.setattr(model_service, "append_json_log", lambda _logger, _path, payload: log_calls.append(payload))

    result = model_service.test_custom_provider_connection(
        CustomProviderConnectionTestRequest(api_base=" https://api.example/v1/ ", api_key="", model="chat-a")
    )

    assert result["reachable"] is False
    assert result["detail"] == "api_key is required"
    assert result["trace_id"] == "trace-no-key"
    assert result["api_base"] == "https://api.example/v1"
    assert log_calls == [
        {
            "trace_id": "trace-no-key",
            "tested_at": "2026-07-30T08:00:00Z",
            "api_base": "https://api.example/v1",
            "model": "chat-a",
            "provider_name": None,
            "reachable": False,
            "detail": "api_key is required",
            "api_key_present": False,
        }
    ]


def test_test_custom_provider_connection_uses_saved_provider_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """\u8fde\u63a5\u6d4b\u8bd5\u5e94\u652f\u6301\u56de\u9000\u5230\u5df2\u4fdd\u5b58\u4f9b\u5e94\u5546\u5bc6\u94a5\uff0c\u5e76\u8bb0\u5f55\u63a2\u6d3b\u7ed3\u679c\u3002"""

    log_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(model_service, "new_trace_id", lambda _prefix: "trace-with-key")
    monkeypatch.setattr(model_service, "now_iso", lambda: "2026-07-30T09:00:00Z")
    monkeypatch.setattr(model_service, "append_json_log", lambda _logger, _path, payload: log_calls.append(payload))
    monkeypatch.setattr(model_service, "_find_provider", lambda _name: {"api_key": "persisted-key"})
    monkeypatch.setattr(
        model_service,
        "_check_openai_compatible",
        lambda model_name, api_base, api_key, trace_id: (
            True,
            "reachable",
            {
                "tested_at": "2026-07-30T09:00:01Z",
                "request_url": "https://api.example/v1/chat/completions",
                "status_code": 200,
                "api_key_present": bool(api_key),
                "detail": "",
                "trace_id": trace_id,
                "model": model_name,
                "api_base": api_base,
            },
        ),
    )

    result = model_service.test_custom_provider_connection(
        CustomProviderConnectionTestRequest(
            api_base=" https://api.example/v1/ ",
            api_key="",
            provider_name="Acme",
            model=" chat-a ",
        )
    )

    assert result == {
        "reachable": True,
        "detail": "reachable",
        "trace_id": "trace-with-key",
        "log_file": str(model_service.MODEL_TEST_LOG_FILE),
        "api_base": "https://api.example/v1",
        "model": "chat-a",
    }
    assert log_calls == [
        {
            "trace_id": "trace-with-key",
            "tested_at": "2026-07-30T09:00:01Z",
            "api_base": "https://api.example/v1",
            "model": "chat-a",
            "reachable": True,
            "detail": "reachable",
            "request_url": "https://api.example/v1/chat/completions",
            "status_code": 200,
            "exception_type": None,
            "api_key_present": True,
            "raw_detail": "",
        }
    ]
