"""Agent 模型工具的 Ollama 与 fallback 测试。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from api.services import agent_tools


class _DummyStore:
    """提供当前模型配置的最小存储替身。"""

    def __init__(self, values: dict):
        self.values = values

    def get(self, key: str):
        return self.values.get(key)


class _FakeResponse:
    """模拟 urllib 上下文响应。"""

    status = 200

    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_call_configured_model_supports_native_ollama_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agent 直连 Ollama 应调用原生 /api/chat，且不要求 API Key。"""
    store = _DummyStore(
        {
            "current_llm_info": {
                "service_provider": "Ollama",
                "model": "qwen2.5:7b",
                "api_base": "http://localhost:11434/",
                "api_key": "",
            },
            "current_llm_settings": {"temperature": 0.2, "system_prompt": "本地系统提示"},
        }
    )
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return _FakeResponse({"message": {"role": "assistant", "content": "本地回答"}, "done": True})

    monkeypatch.setattr(agent_tools, "_get_config_store", lambda: store)
    monkeypatch.setattr(agent_tools.urllib.request, "urlopen", fake_urlopen)

    result = agent_tools._call_configured_model("你好")

    assert result["provider"] == "Ollama"
    assert result["model"] == "qwen2.5:7b"
    assert result["answer"] == "本地回答"
    request, timeout = requests[0]
    assert request.full_url == "http://localhost:11434/api/chat"
    assert timeout == 30
    assert "Authorization" not in request.headers
    assert json.loads(request.data.decode("utf-8")) == {
        "model": "qwen2.5:7b",
        "messages": [
            {"role": "system", "content": "本地系统提示"},
            {"role": "user", "content": "你好"},
        ],
        "options": {"temperature": 0.2},
        "stream": False,
    }


def test_call_configured_model_keeps_openai_compatible_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    """新增 Ollama 分支不能破坏原有云端 OpenAI 兼容请求。"""
    store = _DummyStore(
        {
            "current_llm_info": {
                "service_provider": "Cloud",
                "model": "cloud-chat",
                "api_base": "https://cloud.example/v1/",
                "api_key": "sk-test",
            },
            "current_llm_settings": {"temperature": 0.3, "system_prompt": "cloud system"},
        }
    )
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return _FakeResponse({"choices": [{"message": {"content": "cloud answer"}}]})

    monkeypatch.setattr(agent_tools, "_get_config_store", lambda: store)
    monkeypatch.setattr(agent_tools.urllib.request, "urlopen", fake_urlopen)

    result = agent_tools._call_configured_model("hello")

    assert result["provider"] == "Cloud"
    assert result["answer"] == "cloud answer"
    request, timeout = requests[0]
    assert request.full_url == "https://cloud.example/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer sk-test"
    assert timeout == 30
    assert json.loads(request.data.decode("utf-8")) == {
        "model": "cloud-chat",
        "messages": [
            {"role": "system", "content": "cloud system"},
            {"role": "user", "content": "hello"},
        ],
        "temperature": 0.3,
    }


def test_run_llm_chat_success_keeps_fallback_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """当前模型直接成功时不应伪造切换记录。"""
    result = {
        "provider": "Cloud",
        "model": "cloud-chat",
        "api_base": "https://cloud.example/v1",
        "answer": "cloud answer",
        "raw": {"choices": []},
    }
    model_health = {"state": "healthy", "current_provider": "Cloud", "current_model": "cloud-chat"}
    model_service = SimpleNamespace(get_model_health=MagicMock(return_value=model_health))
    append_receipt = MagicMock(return_value={"id": "receipt-cloud"})
    monkeypatch.setattr(agent_tools, "_call_configured_model", MagicMock(return_value=result))
    monkeypatch.setattr(agent_tools, "model_service", model_service)
    monkeypatch.setattr(agent_tools, "append_receipt", append_receipt)

    output = agent_tools.run_llm_chat("agent-session", "hello")

    assert output["fallback"] is None
    assert output["model_health"] == model_health
    assert append_receipt.call_args.kwargs["output_data"]["fallback"] is None


def test_run_llm_chat_fallbacks_once_and_returns_public_switch_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agent 首次模型失败后应切换到 Ollama，并返回不含凭证的切换摘要。"""
    call_model = MagicMock(
        side_effect=[
            RuntimeError("Free quota exhausted"),
            {
                "provider": "Ollama",
                "model": "qwen2.5:7b",
                "api_base": "http://localhost:11434",
                "answer": "fallback answer",
                "raw": {"done": True},
            },
        ]
    )
    fallback_result = {
        "applied": True,
        "error_kind": "quota_exhausted",
        "candidate_count": 2,
        "selected": {
            "service_provider": "Ollama",
            "model": "qwen2.5:7b",
            "api_base": "http://localhost:11434",
            "api_key": "must-not-leak",
        },
        "fallback_attempt_summary": {"total": 1, "reachable_count": 1},
    }
    model_health = {
        "state": "fallback_applied",
        "fallback_from": {"service_provider": "Cloud", "model": "expired"},
        "fallback_to": {"service_provider": "Ollama", "model": "qwen2.5:7b"},
        "current_provider": "Ollama",
        "current_model": "qwen2.5:7b",
    }
    model_service = SimpleNamespace(
        attempt_model_fallback=MagicMock(return_value=fallback_result),
        get_model_health=MagicMock(return_value=model_health),
        classify_model_error=MagicMock(return_value="network_error"),
        update_model_health=MagicMock(),
    )
    append_receipt = MagicMock(return_value={"id": "receipt-fallback"})
    monkeypatch.setattr(agent_tools, "_call_configured_model", call_model, raising=False)
    monkeypatch.setattr(agent_tools, "model_service", model_service, raising=False)
    monkeypatch.setattr(agent_tools, "append_receipt", append_receipt)

    output = agent_tools.run_llm_chat("agent-session", "hello")

    assert call_model.call_count == 2
    model_service.attempt_model_fallback.assert_called_once()
    assert output["result"]["provider"] == "Ollama"
    assert output["model_health"] == model_health
    assert output["fallback"] == {
        "applied": True,
        "error_kind": "quota_exhausted",
        "candidate_count": 2,
        "fallback_from": model_health["fallback_from"],
        "fallback_to": model_health["fallback_to"],
        "fallback_attempt_summary": {"total": 1, "reachable_count": 1},
    }
    receipt_kwargs = append_receipt.call_args.kwargs
    assert receipt_kwargs["output_data"]["fallback"] == output["fallback"]
    assert "must-not-leak" not in json.dumps(receipt_kwargs, ensure_ascii=False)


def test_run_llm_chat_does_not_retry_when_fallback_is_not_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    """不可恢复错误或没有候选时，应保留首次异常且不重复调用。"""
    first_error = RuntimeError("malformed model response")
    call_model = MagicMock(side_effect=first_error)
    model_service = SimpleNamespace(
        attempt_model_fallback=MagicMock(return_value={"applied": False, "reason": "non_recoverable"}),
    )
    monkeypatch.setattr(agent_tools, "_call_configured_model", call_model, raising=False)
    monkeypatch.setattr(agent_tools, "model_service", model_service, raising=False)

    with pytest.raises(RuntimeError, match="malformed model response"):
        agent_tools.run_llm_chat("agent-session", "hello")

    assert call_model.call_count == 1
    model_service.attempt_model_fallback.assert_called_once_with(first_error, session_id="agent-session")


def test_run_llm_chat_marks_unavailable_when_retry_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """fallback 探活成功但真实重试仍失败时，应停止并覆盖健康状态。"""
    retry_error = RuntimeError("connection reset by peer")
    call_model = MagicMock(side_effect=[RuntimeError("HTTP 403 forbidden"), retry_error])
    unavailable_health = {
        "state": "unavailable",
        "last_error_kind": "network_error",
        "last_error": "connection reset by peer",
    }
    model_service = SimpleNamespace(
        attempt_model_fallback=MagicMock(return_value={"applied": True, "error_kind": "forbidden"}),
        classify_model_error=MagicMock(return_value="network_error"),
        update_model_health=MagicMock(return_value=unavailable_health),
        get_model_health=MagicMock(return_value=unavailable_health),
    )
    monkeypatch.setattr(agent_tools, "_call_configured_model", call_model, raising=False)
    monkeypatch.setattr(agent_tools, "model_service", model_service, raising=False)

    with pytest.raises(RuntimeError, match="connection reset by peer"):
        agent_tools.run_llm_chat("agent-session", "hello")

    assert call_model.call_count == 2
    model_service.update_model_health.assert_called_once()
    assert model_service.update_model_health.call_args.kwargs["state"] == "unavailable"
    assert model_service.update_model_health.call_args.kwargs["last_error_kind"] == "network_error"
