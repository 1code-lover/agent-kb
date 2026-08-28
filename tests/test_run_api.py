"""run_api 启动入口契约测试。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import run_api


def test_configure_local_runtime_env_sets_prewarm_and_thread_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """未配置时，应写入本地默认预热与线程数。"""
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
    """显式配置的环境变量不应被默认值覆盖。"""
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


def test_get_port_prefers_kb_contract_before_legacy_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    """KB_API_PORT 应优先于历史别名。"""
    for key in run_api._API_PORT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("NORTHAGENT_API_PORT", "19080")
    monkeypatch.setenv("KB_API_PORT", "18081")

    assert run_api._get_port() == 18081


def test_get_port_falls_back_to_legacy_alias_when_kb_contract_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """缺少 KB_API_PORT 时，应继续兼容历史端口别名。"""
    for key in run_api._API_PORT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("THINKRAG_API_PORT", "18082")

    assert run_api._get_port() == 18082


def test_get_port_falls_back_to_platform_port_when_repo_contracts_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """容器场景缺少仓库端口变量时，应继续兼容通用 PORT 约定。"""
    for key in run_api._API_PORT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("PORT", "28080")

    assert run_api._get_port() == 28080


def test_get_port_rejects_invalid_integer_from_actual_env_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """错误提示应指向真实触发问题的环境变量。"""
    for key in run_api._API_PORT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("FOXGLOVE_API_PORT", "abc")

    with pytest.raises(ValueError, match="FOXGLOVE_API_PORT"):
        run_api._get_port()


def test_get_port_defaults_to_18080_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """未配置端口时，API-only 入口应继续使用默认端口。"""
    for key in run_api._API_PORT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    assert run_api._get_port() == 18080


def test_get_host_prefers_kb_contract_before_legacy_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    """KB_API_HOST should win over legacy aliases."""
    for key in run_api._API_HOST_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("NORTHAGENT_API_HOST", "0.0.0.0")
    monkeypatch.setenv("KB_API_HOST", "127.0.0.2")

    assert run_api._get_host() == "127.0.0.2"


def test_get_host_falls_back_to_loopback_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without configuration, run_api should keep loopback binding."""
    for key in run_api._API_HOST_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    assert run_api._get_host() == "127.0.0.1"


def test_get_log_dir_defaults_to_repo_logs_without_using_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """未配置日志目录时，应锚定到仓库默认 logs/，而不是当前工作目录。"""
    for key in run_api._LOG_DIR_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    fake_repo_root = tmp_path / "repo-root"
    fake_repo_root.mkdir()
    expected = fake_repo_root / "logs"
    other_cwd = tmp_path / "other-cwd"
    other_cwd.mkdir()
    monkeypatch.setattr(run_api, "_REPO_ROOT", fake_repo_root)
    monkeypatch.setattr(run_api, "_DEFAULT_LOG_DIR", expected)
    monkeypatch.chdir(other_cwd)

    resolved = run_api._get_log_dir()

    assert resolved == expected
    assert resolved.is_dir()


def test_get_log_dir_prefers_kb_contract_and_resolves_relative_path_from_repo_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """KB_LOG_DIR 应优先于历史别名，且相对路径应相对仓库根目录解析。"""
    for key in run_api._LOG_DIR_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    fake_repo_root = tmp_path / "repo-root"
    fake_repo_root.mkdir()
    monkeypatch.setattr(run_api, "_REPO_ROOT", fake_repo_root)
    monkeypatch.setenv("NORTHAGENT_LOG_DIR", str(tmp_path / "legacy-logs"))
    monkeypatch.setenv("KB_LOG_DIR", "temp/test-run-api-logs")
    monkeypatch.chdir(tmp_path)

    resolved = run_api._get_log_dir()

    assert resolved == (fake_repo_root / "temp" / "test-run-api-logs").resolve()
    assert resolved.is_dir()


def test_build_log_config_writes_rotating_log_files_under_target_directory(tmp_path: Path) -> None:
    """构造的 uvicorn log config 应指向目标目录下的 backend/access 文件。"""
    log_dir = tmp_path / "custom-logs"

    config = run_api._build_log_config(log_dir=log_dir)

    assert config["handlers"]["backend_file"]["filename"] == str(log_dir / "backend.log")
    assert config["handlers"]["access_file"]["filename"] == str(log_dir / "access.log")
    assert log_dir.is_dir()
