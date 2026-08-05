"""run_api ???????"""

from __future__ import annotations

import os

import pytest

import run_api


def test_configure_local_runtime_env_sets_prewarm_and_thread_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """????????????? 4 ??????"""
    for key in run_api._RUNTIME_DEFAULTS:
        monkeypatch.delenv(key, raising=False)

    run_api._configure_local_runtime_env()

    assert os.getenv("THINKRAG_EMBED_PREWARM") == "1"
    assert os.getenv("THINKRAG_OCR_PREWARM") == "1"
    assert os.getenv("OPENBLAS_NUM_THREADS") == "4"
    assert os.getenv("OMP_NUM_THREADS") == "4"
    assert os.getenv("MKL_NUM_THREADS") == "4"
    assert os.getenv("NUMEXPR_NUM_THREADS") == "4"


def test_configure_local_runtime_env_preserves_explicit_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """???????????????????"""
    monkeypatch.setenv("THINKRAG_EMBED_PREWARM", "0")
    monkeypatch.setenv("THINKRAG_OCR_PREWARM", "custom")
    monkeypatch.setenv("OPENBLAS_NUM_THREADS", "8")
    monkeypatch.setenv("OMP_NUM_THREADS", "6")
    monkeypatch.setenv("MKL_NUM_THREADS", "4")
    monkeypatch.setenv("NUMEXPR_NUM_THREADS", "2")

    run_api._configure_local_runtime_env()

    assert os.getenv("THINKRAG_EMBED_PREWARM") == "0"
    assert os.getenv("THINKRAG_OCR_PREWARM") == "custom"
    assert os.getenv("OPENBLAS_NUM_THREADS") == "8"
    assert os.getenv("OMP_NUM_THREADS") == "6"
    assert os.getenv("MKL_NUM_THREADS") == "4"
    assert os.getenv("NUMEXPR_NUM_THREADS") == "2"


def test_get_port_rejects_invalid_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    """??????????????????"""
    monkeypatch.setenv("KB_API_PORT", "abc")

    with pytest.raises(ValueError, match="KB_API_PORT"):
        run_api._get_port()
