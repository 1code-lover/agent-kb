from __future__ import annotations

import importlib.util
import io
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "app.py"


def _load_legacy_app_module():
    spec = importlib.util.spec_from_file_location("legacy_root_app", APP_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legacy_streamlit_entry_requires_explicit_opt_in() -> None:
    module = _load_legacy_app_module()

    assert module.legacy_streamlit_enabled({}) is False
    assert module.legacy_streamlit_enabled({"KB_ALLOW_LEGACY_STREAMLIT": "1"}) is True
    assert module.legacy_streamlit_enabled({"THINKRAG_ALLOW_LEGACY_STREAMLIT": "true"}) is True
    assert module.legacy_streamlit_enabled({"NORTHAGENT_ALLOW_LEGACY_STREAMLIT": "yes"}) is True


def test_legacy_streamlit_entry_prints_current_primary_entry_guidance() -> None:
    module = _load_legacy_app_module()
    buffer = io.StringIO()

    exit_code = module.main(environ={}, stderr=buffer)
    message = buffer.getvalue()

    assert exit_code == 1
    assert "FastAPI + React (Vite) + Electron" in message
    assert "start_all.ps1" in message
    assert "scripts\\dev-all.ps1" in message
    assert "KB_ALLOW_LEGACY_STREAMLIT=1" in message
    assert "requirements.txt" in message


def test_legacy_streamlit_entry_reports_full_profile_requirement(monkeypatch) -> None:
    module = _load_legacy_app_module()
    buffer = io.StringIO()

    def _raise_runtime_error() -> None:
        raise RuntimeError("Legacy Streamlit entry requires the full local profile.")

    monkeypatch.setattr(module, "run_legacy_streamlit_app", _raise_runtime_error)
    exit_code = module.main(environ={"KB_ALLOW_LEGACY_STREAMLIT": "1"}, stderr=buffer)

    assert exit_code == 2
    assert "full local profile" in buffer.getvalue()


def test_legacy_streamlit_entry_runs_when_explicitly_enabled(monkeypatch) -> None:
    module = _load_legacy_app_module()
    called = {"value": False}

    def _fake_run() -> None:
        called["value"] = True

    monkeypatch.setattr(module, "run_legacy_streamlit_app", _fake_run)
    exit_code = module.main(environ={"KB_ALLOW_LEGACY_STREAMLIT": "1"}, stderr=io.StringIO())

    assert exit_code == 0
    assert called["value"] is True
