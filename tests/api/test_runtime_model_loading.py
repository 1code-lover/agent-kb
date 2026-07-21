"""RuntimeState ?????????

???? / OpenAI-compatible ????????????? Settings.llm getter?
?? LlamaIndex ???????????? OpenAI ??? OPENAI_API_KEY ???
"""

from __future__ import annotations

from typing import Any

import pytest

from api.runtime import RuntimeState
from llama_index.core import Settings
from server.models import embedding as embedding_module
from server.models import llm_api as llm_module
from server.stores import config_store as config_store_module


def test_ensure_models_ready_uses_private_llm_cache_without_triggering_default_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """??????????? LLM????? Settings.llm getter?"""

    def forbidden_llm_getter(_settings: Any) -> Any:
        raise AssertionError("Settings.llm getter must not be accessed during runtime warm-up")

    def llm_setter(_settings: Any, value: Any) -> None:
        _settings._llm = value

    monkeypatch.setattr(type(Settings), "llm", property(forbidden_llm_getter, llm_setter))
    monkeypatch.setattr(Settings, "_embed_model", None, raising=False)
    monkeypatch.setattr(Settings, "_llm", None, raising=False)

    embed_sentinel = object()
    llm_sentinel = object()
    captured_llm_kwargs: dict[str, Any] = {}

    def fake_create_embedding_model(model_name: str) -> Any:
        assert model_name == "bge-small-zh-v1.5"
        Settings._embed_model = embed_sentinel
        return embed_sentinel

    def fake_create_openai_llm(**kwargs: Any) -> Any:
        captured_llm_kwargs.update(kwargs)
        Settings._llm = llm_sentinel
        return llm_sentinel

    def fake_config_get(key: str) -> Any:
        if key == "current_llm_settings":
            return {
                "embedding_model": "bge-small-zh-v1.5",
                "temperature": 0.2,
                "system_prompt": "grain assistant",
            }
        if key == "current_llm_info":
            return {
                "service_provider": "Aliyun Bailian",
                "model": "qwen-plus",
                "api_base": " https://dashscope.aliyuncs.com/compatible-mode/v1`",
                "api_key": "sk-test",
            }
        return None

    monkeypatch.setattr(embedding_module, "create_embedding_model", fake_create_embedding_model)
    monkeypatch.setattr(llm_module, "create_openai_llm", fake_create_openai_llm)
    monkeypatch.setattr(config_store_module.CONFIG_STORE, "get", fake_config_get)

    state = RuntimeState()

    assert state.ensure_models_ready(require_llm=True) is True
    assert Settings._embed_model is embed_sentinel
    assert Settings._llm is llm_sentinel
    assert captured_llm_kwargs == {
        "model_name": "qwen-plus",
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "sk-test",
        "temperature": 0.2,
        "system_prompt": "grain assistant",
    }



def test_ensure_index_loaded_warms_embedding_before_touching_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """????????????? embedding??????? OpenAI?"""

    calls: list[str] = []
    state = RuntimeState()

    class FakeManager:
        def check_index_exists(self) -> bool:
            calls.append("check")
            assert calls == ["models", "check"]
            return False

        def load_index(self) -> None:  # pragma: no cover - ???????
            raise AssertionError("load_index should not run when index does not exist")

    def fake_ensure_models_ready(require_llm: bool = False) -> bool:
        assert require_llm is False
        calls.append("models")
        return True

    state.index_manager = FakeManager()
    monkeypatch.setattr(state, "ensure_models_ready", fake_ensure_models_ready)

    assert state.ensure_index_loaded() is False
    assert calls == ["models", "check"]
