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


def test_should_enable_embedding_prewarm_parses_truthy_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """未设置环境变量时 embedding 预热默认关闭。"""

    for raw in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("THINKRAG_EMBED_PREWARM", raw)
        assert app_module._should_enable_embedding_prewarm() is True


def test_should_enable_embedding_prewarm_defaults_to_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """真值环境变量应开启 embedding 预热。"""

    monkeypatch.delenv("THINKRAG_EMBED_PREWARM", raising=False)
    assert app_module._should_enable_embedding_prewarm() is False


def test_should_enable_ocr_prewarm_parses_truthy_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """真值环境变量应开启 OCR 预热。"""

    for raw in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("THINKRAG_OCR_PREWARM", raw)
        assert app_module._should_enable_ocr_prewarm() is True


def test_should_enable_ocr_prewarm_defaults_to_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """未设置环境变量时 OCR 预热默认关闭。"""

    monkeypatch.delenv("THINKRAG_OCR_PREWARM", raising=False)
    assert app_module._should_enable_ocr_prewarm() is False


def test_run_startup_tasks_schedules_embedding_and_ocr_prewarm_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """启动阶段应先 bootstrap，再按需调度 embedding 与 OCR 预热。"""

    calls: list[str] = []

    monkeypatch.setenv("THINKRAG_EMBED_PREWARM", "1")
    monkeypatch.setenv("THINKRAG_OCR_PREWARM", "1")
    monkeypatch.setattr(app_module, "bootstrap_runtime", lambda: calls.append("bootstrap"))
    monkeypatch.setattr(app_module, "runtime_state", _FakeRuntimeState(calls))
    monkeypatch.setattr(app_module, "start_ocr_warmup_in_background", lambda: calls.append("ocr") or True)

    app_module._run_startup_tasks()

    assert calls == ["bootstrap", "embed", "ocr"]


def test_run_startup_tasks_skips_optional_prewarm_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """未开启预热时，启动阶段只执行 runtime bootstrap。"""

    calls: list[str] = []

    monkeypatch.delenv("THINKRAG_EMBED_PREWARM", raising=False)
    monkeypatch.delenv("THINKRAG_OCR_PREWARM", raising=False)
    monkeypatch.setattr(app_module, "bootstrap_runtime", lambda: calls.append("bootstrap"))
    monkeypatch.setattr(app_module, "runtime_state", _FakeRuntimeState(calls))
    monkeypatch.setattr(app_module, "start_ocr_warmup_in_background", lambda: calls.append("ocr") or True)

    app_module._run_startup_tasks()

    assert calls == ["bootstrap"]

def test_app_uses_lifespan_startup_instead_of_on_event() -> None:
    """????? lifespan ??????? on_event ?????"""

    assert app_module.app.router.on_startup == []
    assert callable(app_module.app.router.lifespan_context)

