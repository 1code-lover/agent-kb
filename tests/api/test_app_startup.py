"""应用启动预热逻辑测试。"""

from __future__ import annotations

import pytest

import api.app as app_module


class _FakeRuntimeState:
    """真值环境变量应开启 embedding 预热。"""

    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def start_embedding_warmup_in_background(self) -> bool:
        self._calls.append("embed")
        return True


PREWARM_EMBED_KEYS = (
    "KB_EMBED_PREWARM",
    "NORTHAGENT_EMBED_PREWARM",
    "THINKRAG_EMBED_PREWARM",
    "FOXGLOVE_EMBED_PREWARM",
)
PREWARM_OCR_KEYS = (
    "KB_OCR_PREWARM",
    "NORTHAGENT_OCR_PREWARM",
    "THINKRAG_OCR_PREWARM",
    "FOXGLOVE_OCR_PREWARM",
)
EXTRA_ORIGIN_KEYS = (
    "KB_EXTRA_DEV_ORIGINS",
    "NORTHAGENT_EXTRA_DEV_ORIGINS",
    "THINKRAG_EXTRA_DEV_ORIGINS",
    "FOXGLOVE_EXTRA_DEV_ORIGINS",
)
FRONTEND_DEV_PORT_KEYS = (
    "KB_WEBAPP_PORT",
    "KB_WEB_PORT",
    "NORTHAGENT_WEB_PORT",
    "THINKRAG_WEB_PORT",
    "FOXGLOVE_WEB_PORT",
)


def _clear_env(monkeypatch: pytest.MonkeyPatch, keys: tuple[str, ...]) -> None:
    for key in keys:
        monkeypatch.delenv(key, raising=False)


def test_parse_extra_dev_origins_prefers_kb_contract_before_legacy_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    """附加调试来源应优先读取 KB_* 契约。"""

    _clear_env(monkeypatch, EXTRA_ORIGIN_KEYS)
    monkeypatch.setenv("THINKRAG_EXTRA_DEV_ORIGINS", "http://127.0.0.1:5176")
    monkeypatch.setenv("KB_EXTRA_DEV_ORIGINS", " http://127.0.0.1:5188 , http://localhost:5188 ")

    assert app_module._parse_extra_dev_origins() == ["http://127.0.0.1:5188", "http://localhost:5188"]


def test_default_frontend_dev_origins_prefers_webapp_port_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认显式前端来源应优先读取 KB_WEBAPP_PORT，而不是退回 desktop/legacy 口径。"""

    _clear_env(monkeypatch, FRONTEND_DEV_PORT_KEYS)
    monkeypatch.setenv("THINKRAG_WEB_PORT", "5199")
    monkeypatch.setenv("KB_WEBAPP_PORT", "5188")

    assert app_module._default_frontend_dev_origins() == ["http://127.0.0.1:5188", "http://localhost:5188"]


def test_default_frontend_dev_origins_falls_back_when_port_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """错误端口值不应污染默认来源，应稳定回退到 5173。"""

    _clear_env(monkeypatch, FRONTEND_DEV_PORT_KEYS)
    monkeypatch.setenv("KB_WEBAPP_PORT", "not-a-port")

    assert app_module._default_frontend_dev_origins() == ["http://127.0.0.1:5173", "http://localhost:5173"]


@pytest.mark.parametrize("env_key", PREWARM_EMBED_KEYS)
def test_should_enable_embedding_prewarm_parses_truthy_values(monkeypatch: pytest.MonkeyPatch, env_key: str) -> None:
    """任一品牌别名的真值环境变量都应开启 embedding 预热。"""

    _clear_env(monkeypatch, PREWARM_EMBED_KEYS)
    for raw in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv(env_key, raw)
        assert app_module._should_enable_embedding_prewarm() is True
        monkeypatch.delenv(env_key, raising=False)


def test_should_enable_embedding_prewarm_defaults_to_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """未设置环境变量时 embedding 预热默认关闭。"""

    _clear_env(monkeypatch, PREWARM_EMBED_KEYS)
    assert app_module._should_enable_embedding_prewarm() is False


def test_should_enable_embedding_prewarm_prefers_kb_contract_before_legacy_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    """KB_EMBED_PREWARM 应覆盖 legacy alias。"""

    _clear_env(monkeypatch, PREWARM_EMBED_KEYS)
    monkeypatch.setenv("THINKRAG_EMBED_PREWARM", "0")
    monkeypatch.setenv("KB_EMBED_PREWARM", "1")

    assert app_module._should_enable_embedding_prewarm() is True


@pytest.mark.parametrize("env_key", PREWARM_OCR_KEYS)
def test_should_enable_ocr_prewarm_parses_truthy_values(monkeypatch: pytest.MonkeyPatch, env_key: str) -> None:
    """任一品牌别名的真值环境变量都应开启 OCR 预热。"""

    _clear_env(monkeypatch, PREWARM_OCR_KEYS)
    for raw in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv(env_key, raw)
        assert app_module._should_enable_ocr_prewarm() is True
        monkeypatch.delenv(env_key, raising=False)


def test_should_enable_ocr_prewarm_defaults_to_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """未设置环境变量时 OCR 预热默认关闭。"""

    _clear_env(monkeypatch, PREWARM_OCR_KEYS)
    assert app_module._should_enable_ocr_prewarm() is False


def test_should_enable_ocr_prewarm_prefers_kb_contract_before_legacy_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    """KB_OCR_PREWARM 应覆盖 legacy alias。"""

    _clear_env(monkeypatch, PREWARM_OCR_KEYS)
    monkeypatch.setenv("THINKRAG_OCR_PREWARM", "0")
    monkeypatch.setenv("KB_OCR_PREWARM", "1")

    assert app_module._should_enable_ocr_prewarm() is True


def test_run_startup_tasks_schedules_embedding_and_ocr_prewarm_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """启动阶段应先 bootstrap，再按需调度 embedding 与 OCR 预热。"""

    calls: list[str] = []

    _clear_env(monkeypatch, PREWARM_EMBED_KEYS)
    _clear_env(monkeypatch, PREWARM_OCR_KEYS)
    monkeypatch.setenv("KB_EMBED_PREWARM", "1")
    monkeypatch.setenv("KB_OCR_PREWARM", "1")
    monkeypatch.setattr(app_module, "bootstrap_runtime", lambda: calls.append("bootstrap"))
    monkeypatch.setattr(app_module, "runtime_state", _FakeRuntimeState(calls))
    monkeypatch.setattr(app_module, "start_ocr_warmup_in_background", lambda: calls.append("ocr") or True)

    app_module._run_startup_tasks()

    assert calls == ["bootstrap", "embed", "ocr"]


def test_run_startup_tasks_skips_optional_prewarm_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """未开启预热时，启动阶段只执行 runtime bootstrap。"""

    calls: list[str] = []

    _clear_env(monkeypatch, PREWARM_EMBED_KEYS)
    _clear_env(monkeypatch, PREWARM_OCR_KEYS)
    monkeypatch.setattr(app_module, "bootstrap_runtime", lambda: calls.append("bootstrap"))
    monkeypatch.setattr(app_module, "runtime_state", _FakeRuntimeState(calls))
    monkeypatch.setattr(app_module, "start_ocr_warmup_in_background", lambda: calls.append("ocr") or True)

    app_module._run_startup_tasks()

    assert calls == ["bootstrap"]


def test_app_uses_lifespan_startup_instead_of_on_event() -> None:
    """应用应使用 lifespan 而不是 on_event 注册启动逻辑。"""

    assert app_module.app.router.on_startup == []
    assert callable(app_module.app.router.lifespan_context)
