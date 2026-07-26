"""?????? OCR ?????"""

from __future__ import annotations

import pytest

import api.app as app_module


def test_should_enable_ocr_prewarm_parses_truthy_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """????????????? OCR ???"""
    for raw in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("THINKRAG_OCR_PREWARM", raw)
        assert app_module._should_enable_ocr_prewarm() is True


def test_should_enable_ocr_prewarm_defaults_to_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """???????????????/?????????"""
    monkeypatch.delenv("THINKRAG_OCR_PREWARM", raising=False)
    assert app_module._should_enable_ocr_prewarm() is False


def test_run_startup_tasks_schedules_ocr_prewarm_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """???????????????? OCR ???"""
    calls: list[str] = []

    monkeypatch.setenv("THINKRAG_OCR_PREWARM", "1")
    monkeypatch.setattr(app_module, "bootstrap_runtime", lambda: calls.append("bootstrap"))
    monkeypatch.setattr(app_module, "start_ocr_warmup_in_background", lambda: calls.append("warmup") or True)

    app_module._run_startup_tasks()

    assert calls == ["bootstrap", "warmup"]


def test_run_startup_tasks_skips_ocr_prewarm_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """????????????? runtime bootstrap?"""
    calls: list[str] = []

    monkeypatch.delenv("THINKRAG_OCR_PREWARM", raising=False)
    monkeypatch.setattr(app_module, "bootstrap_runtime", lambda: calls.append("bootstrap"))
    monkeypatch.setattr(app_module, "start_ocr_warmup_in_background", lambda: calls.append("warmup") or True)

    app_module._run_startup_tasks()

    assert calls == ["bootstrap"]
