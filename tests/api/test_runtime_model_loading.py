"""RuntimeState 运行时管理测试。

覆盖模型预热、embedding 后台预热、按知识库缓存 IndexManager 与索引加载行为。
"""

from __future__ import annotations

from typing import Any
import builtins
import sys
import threading
import types

import config
import pytest

from api import runtime as runtime_module
from api.runtime import RuntimeState
from llama_index.core import Settings
from server import index as index_module
from server.models import embedding as embedding_module
from server.models import llm_api as llm_module
from server.stores import config_store as config_store_module


class _ImmediateThread:
    """同步执行 target 的轻量线程替身，便于测试后台预热。"""

    def __init__(self, target, name: str | None = None, daemon: bool | None = None) -> None:
        self._target = target
        self.name = name
        self.daemon = daemon
        self._alive = False

    def start(self) -> None:
        self._alive = True
        try:
            self._target()
        finally:
            self._alive = False

    def is_alive(self) -> bool:
        return self._alive


class _AliveThread:
    """始终处于运行中的线程替身，用于验证防重入逻辑。"""

    def is_alive(self) -> bool:
        return True


def test_ensure_models_ready_uses_private_llm_cache_without_triggering_default_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """避免访问 LLM 为空时触发 Settings.llm getter。"""

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


def test_get_embedding_warmup_status_marks_ready_when_runtime_is_already_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """即使内部状态仍为 idle，只要运行时已就绪，对外快照也应显示 ready。"""

    state = RuntimeState(embedding_model_name="bge-small-zh-v1.5")
    monkeypatch.setattr(state, "_get_configured_embedding_model_name", lambda: "bge-small-zh-v1.5")
    monkeypatch.setattr(state, "_embedding_runtime_is_ready", lambda: True)

    status = state.get_embedding_warmup_status()

    assert status["state"] == "ready"
    assert status["is_ready"] is True
    assert status["current_model"] == "bge-small-zh-v1.5"
    assert status["loaded_model"] == "bge-small-zh-v1.5"
    assert status["attempt_count"] == 0


def test_start_embedding_warmup_in_background_skips_when_runtime_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """若 embedding 已就绪，则不重复启动后台线程，但要刷新 ready 状态。"""

    state = RuntimeState(embedding_model_name="bge-small-zh-v1.5")
    monkeypatch.setattr(state, "_embedding_runtime_is_ready", lambda: True)
    monkeypatch.setattr(state, "_get_configured_embedding_model_name", lambda: "bge-small-zh-v1.5")

    assert state.start_embedding_warmup_in_background() is False

    status = state.get_embedding_warmup_status()
    assert status["state"] == "ready"
    assert status["is_ready"] is True
    assert status["current_model"] == "bge-small-zh-v1.5"
    assert status["loaded_model"] == "bge-small-zh-v1.5"
    assert status["finished_at"] is not None


def test_start_embedding_warmup_in_background_rejects_duplicate_running_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """已有存活线程时不应重复启动 embedding 预热。"""

    state = RuntimeState()
    state._embedding_warmup_thread = _AliveThread()
    monkeypatch.setattr(state, "_embedding_runtime_is_ready", lambda: False)

    assert state.start_embedding_warmup_in_background() is False
    assert state.get_embedding_warmup_status()["state"] == "idle"


def test_start_embedding_warmup_in_background_marks_runtime_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """后台预热成功后应更新为 ready，并记录耗时与尝试次数。"""

    state = RuntimeState()
    calls: list[bool] = []

    def fake_ensure_models_ready(require_llm: bool = False) -> bool:
        calls.append(require_llm)
        state.embedding_model_name = "bge-small-zh-v1.5"
        return True

    monkeypatch.setattr(runtime_module, "Thread", _ImmediateThread)
    monkeypatch.setattr(state, "ensure_models_ready", fake_ensure_models_ready)
    monkeypatch.setattr(state, "_get_configured_embedding_model_name", lambda: "bge-small-zh-v1.5")
    monkeypatch.setattr(state, "_embedding_runtime_is_ready", lambda: state.embedding_model_name == "bge-small-zh-v1.5")

    assert state.start_embedding_warmup_in_background() is True

    status = state.get_embedding_warmup_status()
    assert calls == [False]
    assert status["state"] == "ready"
    assert status["attempt_count"] == 1
    assert status["last_error"] is None
    assert status["last_duration_ms"] is not None
    assert status["is_ready"] is True
    assert status["loaded_model"] == "bge-small-zh-v1.5"
    assert state._embedding_warmup_thread is None


def test_start_embedding_warmup_in_background_marks_runtime_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """后台预热失败后应暴露 failed 状态与错误信息。"""

    state = RuntimeState()

    monkeypatch.setattr(runtime_module, "Thread", _ImmediateThread)
    monkeypatch.setattr(state, "ensure_models_ready", lambda require_llm=False: (_ for _ in ()).throw(RuntimeError("mock warmup failed")))
    monkeypatch.setattr(state, "_get_configured_embedding_model_name", lambda: "bge-small-zh-v1.5")
    monkeypatch.setattr(state, "_embedding_runtime_is_ready", lambda: False)

    assert state.start_embedding_warmup_in_background() is True

    status = state.get_embedding_warmup_status()
    assert status["state"] == "failed"
    assert status["attempt_count"] == 1
    assert status["last_error"] == "mock warmup failed"
    assert status["last_duration_ms"] is not None
    assert status["is_ready"] is False
    assert status["current_model"] == "bge-small-zh-v1.5"
    assert state._embedding_warmup_thread is None


def test_get_embedding_warmup_status_does_not_block_during_model_init(monkeypatch: pytest.MonkeyPatch) -> None:
    """embedding ????????????????????????"""

    entered = threading.Event()
    release = threading.Event()
    status_ready = threading.Event()
    worker_done = threading.Event()
    state = RuntimeState()

    monkeypatch.setattr(Settings, "_embed_model", None, raising=False)
    monkeypatch.setattr(Settings, "_llm", None, raising=False)

    def fake_create_embedding_model(model_name: str) -> Any:
        assert model_name == "bge-small-zh-v1.5"
        entered.set()
        assert release.wait(timeout=5), "test did not release embedding init"
        Settings._embed_model = object()
        return Settings._embed_model

    def fake_config_get(key: str) -> Any:
        if key == "current_llm_settings":
            return {"embedding_model": "bge-small-zh-v1.5"}
        if key == "current_llm_info":
            return {}
        return None

    def _run_worker() -> None:
        try:
            state.ensure_models_ready(require_llm=False)
        finally:
            worker_done.set()

    captured: dict[str, Any] = {}

    def _read_status() -> None:
        try:
            captured["status"] = state.get_embedding_warmup_status()
        finally:
            status_ready.set()

    monkeypatch.setattr(embedding_module, "create_embedding_model", fake_create_embedding_model)
    monkeypatch.setattr(config_store_module.CONFIG_STORE, "get", fake_config_get)

    worker = threading.Thread(target=_run_worker, daemon=True)
    worker.start()
    assert entered.wait(timeout=2), "embedding init never started"

    reader = threading.Thread(target=_read_status, daemon=True)
    reader.start()
    try:
        assert status_ready.wait(timeout=0.5), "get_embedding_warmup_status blocked during embedding init"
    finally:
        release.set()

    assert worker_done.wait(timeout=2), "embedding init did not finish after release"
    worker.join(timeout=2)
    reader.join(timeout=2)

    status = captured["status"]
    assert status["current_model"] == "bge-small-zh-v1.5"
    assert status["is_ready"] is False


def test_get_index_manager_caches_instances_per_kb(monkeypatch: pytest.MonkeyPatch) -> None:
    """按 kb_id 缓存不同的 IndexManager，同一 kb_id 应复用实例。"""

    created: list[tuple[str, str | None]] = []

    class FakeManager:
        def __init__(self, index_name: str, *, kb_id: str | None = None) -> None:
            created.append((index_name, kb_id))
            self.index_name = index_name
            self.kb_id = kb_id

    monkeypatch.setattr(index_module, "IndexManager", FakeManager)
    state = RuntimeState()

    manager_a_first = state.get_index_manager("kb-a")
    manager_a_second = state.get_index_manager("kb-a")
    manager_b = state.get_index_manager("kb-b")
    manager_default_first = state.get_index_manager()
    manager_default_second = state.get_index_manager("default")

    assert manager_a_first is manager_a_second
    assert manager_a_first is not manager_b
    assert manager_default_first is manager_default_second
    assert created == [
        (config.DEFAULT_INDEX_NAME, "kb-a"),
        (config.DEFAULT_INDEX_NAME, "kb-b"),
        (config.DEFAULT_INDEX_NAME, "default"),
    ]




def test_get_index_manager_does_not_block_status_reads_during_manager_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """缓慢创建 IndexManager 时，不应持有 runtime 主锁阻塞状态读取。"""

    entered = threading.Event()
    release = threading.Event()
    status_ready = threading.Event()
    worker_done = threading.Event()
    captured: dict[str, object] = {}

    class SlowManager:
        def __init__(self, index_name: str, *, kb_id: str | None = None) -> None:
            captured["index_name"] = index_name
            captured["kb_id"] = kb_id
            entered.set()
            release.wait(timeout=2)

    monkeypatch.setattr(index_module, "IndexManager", SlowManager)
    state = RuntimeState()

    def _build_manager() -> None:
        try:
            state.get_index_manager("kb-a")
        finally:
            worker_done.set()

    def _read_status() -> None:
        captured["status"] = state.get_embedding_warmup_status()
        status_ready.set()

    worker = threading.Thread(target=_build_manager, daemon=True)
    worker.start()
    assert entered.wait(timeout=2), "IndexManager creation never started"

    reader = threading.Thread(target=_read_status, daemon=True)
    reader.start()
    try:
        assert status_ready.wait(timeout=0.5), "get_embedding_warmup_status blocked during IndexManager creation"
    finally:
        release.set()

    assert worker_done.wait(timeout=2), "IndexManager creation did not finish after release"
    worker.join(timeout=2)
    reader.join(timeout=2)

    assert captured["index_name"] == config.DEFAULT_INDEX_NAME
    assert captured["kb_id"] == "kb-a"
    assert isinstance(captured["status"], dict)

def test_get_index_manager_reuses_legacy_default_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    """兼容历史的 state.index_manager 单例字段。"""

    class FakeManager:
        pass

    monkeypatch.setattr(index_module, "IndexManager", FakeManager)
    state = RuntimeState()
    legacy_manager = FakeManager()
    state.index_manager = legacy_manager

    assert state.get_index_manager() is legacy_manager
    assert state.get_index_manager("default") is legacy_manager


def test_ensure_index_loaded_warms_embedding_before_touching_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """确保先预热 embedding，避免隐式访问 OpenAI。"""

    calls: list[str] = []
    state = RuntimeState()

    class FakeManager:
        def check_index_exists(self) -> bool:
            calls.append("check")
            assert calls == ["models", "check"]
            return False

        def load_index(self) -> None:  # pragma: no cover - 不应该被调用
            raise AssertionError("load_index should not run when index does not exist")

    def fake_ensure_models_ready(require_llm: bool = False) -> bool:
        assert require_llm is False
        calls.append("models")
        return True

    state.index_manager = FakeManager()
    monkeypatch.setattr(state, "ensure_models_ready", fake_ensure_models_ready)

    assert state.ensure_index_loaded() is False
    assert calls == ["models", "check"]


def test_ensure_index_loaded_uses_requested_kb_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    """确保按请求的 kb_id 选择对应 manager 加载索引。"""

    requested: list[str] = []
    state = RuntimeState()

    class FakeManager:
        def check_index_exists(self) -> bool:
            return True

        def load_index(self) -> None:
            requested.append("load")

    def fake_get_index_manager(kb_id: str = "default") -> FakeManager:
        requested.append(kb_id)
        return FakeManager()

    monkeypatch.setattr(state, "ensure_models_ready", lambda require_llm=False: True)
    monkeypatch.setattr(state, "get_index_manager", fake_get_index_manager)

    assert state.ensure_index_loaded("kb-a") is True
    assert requested == ["kb-a", "load"]



def test_get_configured_embedding_model_name_falls_back_when_config_store_import_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配置存储不可用时，embedding 模型名应回退到默认值。"""

    original_import = builtins.__import__

    def fake_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):
        if name == "server.stores.config_store":
            raise ImportError("config store unavailable")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    state = RuntimeState()

    assert state._get_configured_embedding_model_name() == config.DEFAULT_EMBEDDING_MODEL


def test_embedding_runtime_is_ready_returns_false_when_settings_import_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """llama_index Settings 无法导入时，运行时就绪检查应安全返回 False。"""

    original_import = builtins.__import__

    def fake_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):
        if name == "llama_index.core":
            raise ImportError("settings unavailable")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    state = RuntimeState(embedding_model_name="bge-small-zh-v1.5")

    assert state._embedding_runtime_is_ready() is False


def test_run_embedding_warmup_marks_failed_when_models_are_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """预热过程若发现 embedding 不可用，应写入 failed 状态。"""

    state = RuntimeState()
    monkeypatch.setattr(state, "ensure_models_ready", lambda require_llm=False: False)
    monkeypatch.setattr(state, "_get_configured_embedding_model_name", lambda: "bge-small-zh-v1.5")
    monkeypatch.setattr(state, "_embedding_runtime_is_ready", lambda: False)

    state._run_embedding_warmup()

    status = state.embedding_warmup_status
    assert status["state"] == "failed"
    assert status["last_error"] == "Embedding model is unavailable."
    assert status["current_model"] == "bge-small-zh-v1.5"
    assert status["is_ready"] is False


def test_get_index_manager_falls_back_for_legacy_index_manager_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """旧版 IndexManager 不支持 kb_id 参数时，runtime 仍应能兼容创建。"""

    created: list[str] = []

    class LegacyManager:
        def __init__(self, index_name: str) -> None:
            created.append(index_name)
            self.index_name = index_name

    monkeypatch.setattr(index_module, "IndexManager", LegacyManager)
    state = RuntimeState()

    manager = state.get_index_manager("kb-legacy")

    assert isinstance(manager, LegacyManager)
    assert manager.index_name == config.DEFAULT_INDEX_NAME
    assert created == [config.DEFAULT_INDEX_NAME]
    assert state.index_managers["kb-legacy"] is manager


def test_ensure_models_ready_marks_failed_when_embedding_factory_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """embedding 工厂返回 None 时，应及时写入 warmup 失败状态。"""

    monkeypatch.setattr(Settings, "_embed_model", None, raising=False)
    monkeypatch.setattr(Settings, "_llm", None, raising=False)
    monkeypatch.setattr(embedding_module, "create_embedding_model", lambda model_name: None)

    def fake_config_get(key: str) -> Any:
        if key == "current_llm_settings":
            return {"embedding_model": "bge-small-zh-v1.5"}
        if key == "current_llm_info":
            return {}
        return None

    monkeypatch.setattr(config_store_module.CONFIG_STORE, "get", fake_config_get)
    state = RuntimeState()

    assert state.ensure_models_ready(require_llm=False) is False

    status = state.embedding_warmup_status
    assert status["state"] == "failed"
    assert status["last_error"] == "Embedding model is unavailable."
    assert status["current_model"] == "bge-small-zh-v1.5"
    assert status["loaded_model"] is None
    assert status["is_ready"] is False


def test_ensure_models_ready_reuses_loaded_embedding_and_cached_llm_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """embedding 已加载且 LLM 指纹未变时，不应重复初始化模型。"""

    embed_sentinel = object()
    llm_sentinel = object()
    monkeypatch.setattr(Settings, "_embed_model", embed_sentinel, raising=False)
    monkeypatch.setattr(Settings, "_llm", llm_sentinel, raising=False)

    def fake_config_get(key: str) -> Any:
        if key == "current_llm_settings":
            return {"embedding_model": "bge-small-zh-v1.5"}
        if key == "current_llm_info":
            return {
                "service_provider": "OpenAI",
                "model": "gpt-4o-mini",
                "api_base": "https://api.example.com/v1",
                "api_key": "sk-test",
            }
        return None

    monkeypatch.setattr(config_store_module.CONFIG_STORE, "get", fake_config_get)
    monkeypatch.setattr(embedding_module, "create_embedding_model", lambda model_name: (_ for _ in ()).throw(AssertionError("embedding should not reload")))
    monkeypatch.setattr(llm_module, "create_openai_llm", lambda **kwargs: (_ for _ in ()).throw(AssertionError("llm should not reload")))

    state = RuntimeState(embedding_model_name="bge-small-zh-v1.5")
    state.llm_fingerprint = ("OpenAI", "gpt-4o-mini", "https://api.example.com/v1")

    assert state.ensure_models_ready(require_llm=True) is True


def test_ensure_models_ready_uses_openai_defaults_when_credentials_are_missing_in_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAI 供应商缺省 api_base/api_key 时，应回退到全局默认配置。"""

    embed_sentinel = object()
    llm_sentinel = object()
    monkeypatch.setattr(Settings, "_embed_model", None, raising=False)
    monkeypatch.setattr(Settings, "_llm", None, raising=False)
    captured: dict[str, Any] = {}

    def fake_create_embedding_model(model_name: str) -> Any:
        Settings._embed_model = embed_sentinel
        return embed_sentinel

    def fake_create_openai_llm(**kwargs: Any) -> Any:
        captured.update(kwargs)
        Settings._llm = llm_sentinel
        return llm_sentinel

    def fake_config_get(key: str) -> Any:
        if key == "current_llm_settings":
            return {"embedding_model": "bge-small-zh-v1.5"}
        if key == "current_llm_info":
            return {
                "service_provider": "OpenAI",
                "model": "gpt-4o-mini",
                "api_base": "",
                "api_key": "",
            }
        return None

    monkeypatch.setattr(embedding_module, "create_embedding_model", fake_create_embedding_model)
    monkeypatch.setattr(llm_module, "create_openai_llm", fake_create_openai_llm)
    monkeypatch.setattr(config_store_module.CONFIG_STORE, "get", fake_config_get)
    monkeypatch.setattr(config, "OPENAI_API_BASE", "https://openai.example/v1", raising=False)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-openai-default", raising=False)

    state = RuntimeState()

    assert state.ensure_models_ready(require_llm=True) is True
    assert captured["api_base"] == "https://openai.example/v1"
    assert captured["api_key"] == "sk-openai-default"


@pytest.mark.parametrize(
    ("provider", "config_key", "expected_base"),
    [
        ("Aliyun Bailian", "DASHSCOPE_BASE_URL", "https://dashscope.example/v1"),
        ("Volcengine Ark", "ARK_BASE_URL", "https://ark.example/v3"),
    ],
)
def test_ensure_models_ready_allows_embedding_only_mode_for_missing_provider_credentials(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    config_key: str,
    expected_base: str,
) -> None:
    """非 OpenAI 供应商缺少凭据且不强制 LLM 时，应允许仅 embedding 模式继续。"""

    embed_sentinel = object()
    monkeypatch.setattr(Settings, "_embed_model", None, raising=False)
    monkeypatch.setattr(Settings, "_llm", None, raising=False)

    def fake_create_embedding_model(model_name: str) -> Any:
        Settings._embed_model = embed_sentinel
        return embed_sentinel

    def fake_config_get(key: str) -> Any:
        if key == "current_llm_settings":
            return {"embedding_model": "bge-small-zh-v1.5"}
        if key == "current_llm_info":
            return {
                "service_provider": provider,
                "model": "provider-model",
                "api_base": "",
                "api_key": "",
            }
        return None

    monkeypatch.setattr(embedding_module, "create_embedding_model", fake_create_embedding_model)
    monkeypatch.setattr(llm_module, "create_openai_llm", lambda **kwargs: (_ for _ in ()).throw(AssertionError("llm factory should not run")))
    monkeypatch.setattr(config_store_module.CONFIG_STORE, "get", fake_config_get)
    monkeypatch.setattr(config, config_key, expected_base, raising=False)

    state = RuntimeState()

    assert state.ensure_models_ready(require_llm=False) is True


def test_ensure_models_ready_returns_true_for_openai_like_without_api_key_when_llm_not_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAI-like 缺少 api_key 但只做 embedding 时，应视为可用。"""

    embed_sentinel = object()
    monkeypatch.setattr(Settings, "_embed_model", None, raising=False)
    monkeypatch.setattr(Settings, "_llm", None, raising=False)

    def fake_create_embedding_model(model_name: str) -> Any:
        Settings._embed_model = embed_sentinel
        return embed_sentinel

    def fake_config_get(key: str) -> Any:
        if key == "current_llm_settings":
            return {"embedding_model": "bge-small-zh-v1.5"}
        if key == "current_llm_info":
            return {
                "service_provider": "OpenAI-like",
                "model": "custom-model",
                "api_base": "",
                "api_key": "",
            }
        return None

    monkeypatch.setattr(embedding_module, "create_embedding_model", fake_create_embedding_model)
    monkeypatch.setattr(llm_module, "create_openai_llm", lambda **kwargs: (_ for _ in ()).throw(AssertionError("llm factory should not run")))
    monkeypatch.setattr(config_store_module.CONFIG_STORE, "get", fake_config_get)
    monkeypatch.setattr(config, "OPENAI_API_BASE", "https://openai-like.example/v1", raising=False)

    state = RuntimeState()

    assert state.ensure_models_ready(require_llm=False) is True


def test_ensure_models_ready_returns_false_when_openai_factory_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM 工厂返回 None 且强制要求 LLM 时，运行时应拒绝继续。"""

    embed_sentinel = object()
    monkeypatch.setattr(Settings, "_embed_model", None, raising=False)
    monkeypatch.setattr(Settings, "_llm", None, raising=False)

    def fake_create_embedding_model(model_name: str) -> Any:
        Settings._embed_model = embed_sentinel
        return embed_sentinel

    def fake_config_get(key: str) -> Any:
        if key == "current_llm_settings":
            return {"embedding_model": "bge-small-zh-v1.5"}
        if key == "current_llm_info":
            return {
                "service_provider": "DeepSeek",
                "model": "deepseek-chat",
                "api_base": "",
                "api_key": "",
            }
        return None

    monkeypatch.setattr(embedding_module, "create_embedding_model", fake_create_embedding_model)
    monkeypatch.setattr(llm_module, "create_openai_llm", lambda **kwargs: None)
    monkeypatch.setattr(config_store_module.CONFIG_STORE, "get", fake_config_get)
    monkeypatch.setattr(config, "DEEPSEEK_API_BASE", "https://deepseek.example/v1", raising=False)
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "sk-deepseek-default", raising=False)

    state = RuntimeState()

    assert state.ensure_models_ready(require_llm=True) is False


def test_ensure_models_ready_initializes_ollama_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ollama 供应商应使用独立初始化路径并更新 LLM 指纹。"""

    monkeypatch.setattr(Settings, "_embed_model", object(), raising=False)
    monkeypatch.setattr(Settings, "_llm", None, raising=False)

    def llm_getter(_settings: Any) -> Any:
        return getattr(_settings, "_llm", None)

    def llm_setter(_settings: Any, value: Any) -> None:
        _settings._llm = value

    monkeypatch.setattr(type(Settings), "llm", property(llm_getter, llm_setter))

    captured: dict[str, Any] = {}
    ollama_module = types.ModuleType("llama_index.llms.ollama")

    class FakeOllama:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    ollama_module.Ollama = FakeOllama
    monkeypatch.setitem(sys.modules, "llama_index.llms", types.ModuleType("llama_index.llms"))
    monkeypatch.setitem(sys.modules, "llama_index.llms.ollama", ollama_module)

    def fake_config_get(key: str) -> Any:
        if key == "current_llm_settings":
            return {
                "embedding_model": "bge-small-zh-v1.5",
                "temperature": 0.4,
                "system_prompt": "ollama system",
            }
        if key == "current_llm_info":
            return {
                "service_provider": "Ollama",
                "model": "qwen2.5:7b",
                "api_base": "",
                "api_key": "",
            }
        return None

    monkeypatch.setattr(config_store_module.CONFIG_STORE, "get", fake_config_get)
    monkeypatch.setattr(config, "OLLAMA_API_URL", "http://127.0.0.1:11434", raising=False)

    state = RuntimeState(embedding_model_name="bge-small-zh-v1.5")

    assert state.ensure_models_ready(require_llm=True) is True
    assert state.llm_fingerprint == ("Ollama", "qwen2.5:7b", "http://127.0.0.1:11434")
    assert captured["base_url"] == "http://127.0.0.1:11434"
    assert captured["model"] == "qwen2.5:7b"


def test_ensure_models_ready_returns_false_when_ollama_init_fails_and_llm_is_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ollama 初始化失败且强制要求 LLM 时，应返回 False。"""

    monkeypatch.setattr(Settings, "_embed_model", object(), raising=False)
    monkeypatch.setattr(Settings, "_llm", None, raising=False)

    def llm_getter(_settings: Any) -> Any:
        return getattr(_settings, "_llm", None)

    def llm_setter(_settings: Any, value: Any) -> None:
        _settings._llm = value

    monkeypatch.setattr(type(Settings), "llm", property(llm_getter, llm_setter))

    ollama_module = types.ModuleType("llama_index.llms.ollama")

    class BrokenOllama:
        def __init__(self, **kwargs: Any) -> None:
            raise RuntimeError("ollama unavailable")

    ollama_module.Ollama = BrokenOllama
    monkeypatch.setitem(sys.modules, "llama_index.llms", types.ModuleType("llama_index.llms"))
    monkeypatch.setitem(sys.modules, "llama_index.llms.ollama", ollama_module)

    def fake_config_get(key: str) -> Any:
        if key == "current_llm_settings":
            return {"embedding_model": "bge-small-zh-v1.5"}
        if key == "current_llm_info":
            return {
                "service_provider": "Ollama",
                "model": "qwen2.5:7b",
                "api_base": "",
                "api_key": "",
            }
        return None

    monkeypatch.setattr(config_store_module.CONFIG_STORE, "get", fake_config_get)
    monkeypatch.setattr(config, "OLLAMA_API_URL", "http://127.0.0.1:11434", raising=False)

    state = RuntimeState(embedding_model_name="bge-small-zh-v1.5")

    assert state.ensure_models_ready(require_llm=True) is False


def test_build_query_engine_rejects_when_llm_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """查询引擎构建前若 LLM 不可用，应给出明确拒绝。"""

    state = RuntimeState()
    monkeypatch.setattr(state, "ensure_models_ready", lambda require_llm=False: False)

    with pytest.raises(RuntimeError, match="LLM is not configured or unavailable"):
        state.build_query_engine(["kb-a"])


def test_build_query_engine_rejects_multi_kb_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """P0 阶段仍应拒绝多知识库 query engine 构建请求。"""

    state = RuntimeState()
    monkeypatch.setattr(state, "ensure_models_ready", lambda require_llm=False: True)

    with pytest.raises(RuntimeError, match="Multi-KB query is not supported"):
        state.build_query_engine(["kb-a", "kb-b"])


def test_build_query_engine_loads_missing_index_and_forwards_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """查询引擎应在需要时先 load_index，再透传当前 RAG 配置。"""

    import server.engine as engine_module

    captured: dict[str, Any] = {}

    class FakeManager:
        def __init__(self) -> None:
            self.index = None

        def check_index_exists(self) -> bool:
            return True

        def load_index(self) -> None:
            self.index = "loaded-index"

    def fake_create_query_engine(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return "query-engine"

    def fake_config_get(key: str) -> Any:
        if key == "current_llm_settings":
            return {
                "use_reranker": True,
                "response_mode": "tree_summarize",
                "top_k": 6,
                "top_n": 3,
                "reranker_model": "bge-reranker-v2-m3",
            }
        return None

    manager = FakeManager()
    state = RuntimeState()
    monkeypatch.setattr(state, "ensure_models_ready", lambda require_llm=False: True)
    monkeypatch.setattr(state, "get_index_manager", lambda kb_id=None: manager)
    monkeypatch.setattr(engine_module, "create_query_engine", fake_create_query_engine)
    monkeypatch.setattr(config_store_module.CONFIG_STORE, "get", fake_config_get)

    result = state.build_query_engine(["kb-a"])

    assert result == "query-engine"
    assert captured == {
        "index": "loaded-index",
        "use_reranker": True,
        "response_mode": "tree_summarize",
        "top_k": 6,
        "top_n": 3,
        "reranker": "bge-reranker-v2-m3",
        "kb_ids": ["kb-a"],
    }


def test_bootstrap_runtime_returns_quietly_when_config_store_import_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """config store 导入失败时，bootstrap_runtime 应安静返回。"""

    original_import = builtins.__import__

    def fake_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):
        if name == "server.stores.config_store":
            raise ImportError("config store unavailable")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    runtime_module.bootstrap_runtime()


def test_bootstrap_runtime_initializes_default_settings_and_default_kb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bootstrap_runtime 应在首次启动时写入默认 LLM 配置并创建 default KB。"""

    import server.kb_registry as kb_registry_module

    puts: list[tuple[str, Any]] = []
    created: list[tuple[str, str]] = []

    class FakeRegistry:
        def exists(self, kb_id: str) -> bool:
            assert kb_id == "default"
            return False

        def create_kb(self, kb_id: str, kb_name: str) -> None:
            created.append((kb_id, kb_name))

    monkeypatch.setattr(
        config_store_module.CONFIG_STORE,
        "get",
        lambda key: None if key == "current_llm_settings" else {},
    )
    monkeypatch.setattr(
        config_store_module.CONFIG_STORE,
        "put",
        lambda key, val: puts.append((key, val)),
    )
    monkeypatch.setattr(kb_registry_module, "KBRegistry", FakeRegistry)

    runtime_module.bootstrap_runtime()

    assert puts
    assert puts[0][0] == "current_llm_settings"
    assert puts[0][1]["embedding_model"] == config.DEFAULT_EMBEDDING_MODEL
    assert created == [("default", "Default Knowledge Base")]
