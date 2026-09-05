"""本地 API 启动入口。

说明：
- 当前仓库默认/推荐启动的是 FastAPI API 服务；
- 与 `start_dev.ps1` / `scripts/dev-all.ps1` 一样，继续兼容历史环境变量别名；
- 在本地开发机场景下补齐预热与线程数默认值，避免冷启动过慢。
"""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

import uvicorn

_REPO_ROOT = Path(__file__).resolve().parent
_DEFAULT_LOG_DIR = _REPO_ROOT / "logs"
_LOG_DIR_ENV_KEYS = ("KB_LOG_DIR", "NORTHAGENT_LOG_DIR", "THINKRAG_LOG_DIR", "FOXGLOVE_LOG_DIR")

_LOG_CONFIG_TEMPLATE = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "format": "%(asctime)s  %(levelprefix)s  %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "use_colors": True,
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "format": "%(asctime)s  %(levelprefix)s  %(client_addr)s - %(request_line)s %(status_code)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "use_colors": True,
        },
    },
    "handlers": {
        "backend_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "backend.log",
            "maxBytes": 1_048_576,
            "backupCount": 5,
            "formatter": "default",
            "encoding": "utf-8",
        },
        "access_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "access.log",
            "maxBytes": 1_048_576,
            "backupCount": 5,
            "formatter": "access",
            "encoding": "utf-8",
        },
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["backend_file", "console"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["backend_file", "console"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["access_file", "console"], "level": "INFO", "propagate": False},
    },
}

_DEFAULT_LOCAL_THREAD_COUNT = "4"
_API_PORT_ENV_KEYS = ("KB_API_PORT", "NORTHAGENT_API_PORT", "THINKRAG_API_PORT", "FOXGLOVE_API_PORT", "PORT")
_API_HOST_ENV_KEYS = ("KB_API_HOST", "NORTHAGENT_API_HOST", "THINKRAG_API_HOST", "FOXGLOVE_API_HOST")
_RUNTIME_DEFAULTS = {
    "THINKRAG_EMBED_PREWARM": "1",
    "THINKRAG_OCR_PREWARM": "1",
    "OPENBLAS_NUM_THREADS": _DEFAULT_LOCAL_THREAD_COUNT,
    "OMP_NUM_THREADS": _DEFAULT_LOCAL_THREAD_COUNT,
    "MKL_NUM_THREADS": _DEFAULT_LOCAL_THREAD_COUNT,
    "NUMEXPR_NUM_THREADS": _DEFAULT_LOCAL_THREAD_COUNT,
}


def _is_reload_enabled() -> bool:
    """是否启用 uvicorn reload。"""
    return os.getenv("KB_API_RELOAD", "0").strip() == "1"


def _read_first_non_empty_env(env_names: tuple[str, ...], *, default: str) -> tuple[str | None, str]:
    """按优先级读取第一个非空环境变量值。"""
    for env_name in env_names:
        value = os.getenv(env_name, "").strip()
        if value:
            return env_name, value
    return None, default


def _get_log_dir() -> Path:
    """解析 API 日志目录，并避免依赖当前工作目录。"""
    _, raw_log_dir = _read_first_non_empty_env(_LOG_DIR_ENV_KEYS, default=str(_DEFAULT_LOG_DIR))
    path = Path(raw_log_dir).expanduser()
    if not path.is_absolute():
        path = (_REPO_ROOT / path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_log_config(*, log_dir: Path | None = None) -> dict:
    """基于目标日志目录构造 uvicorn log config。"""
    resolved_log_dir = Path(log_dir) if log_dir is not None else _get_log_dir()
    resolved_log_dir.mkdir(parents=True, exist_ok=True)

    config = deepcopy(_LOG_CONFIG_TEMPLATE)
    handlers = config.get("handlers", {})
    backend_handler = handlers.get("backend_file")
    access_handler = handlers.get("access_file")
    if isinstance(backend_handler, dict):
        backend_handler["filename"] = str(resolved_log_dir / "backend.log")
    if isinstance(access_handler, dict):
        access_handler["filename"] = str(resolved_log_dir / "access.log")
    return config


def _get_port() -> int:
    """读取 API 监听端口，默认 18080。"""
    env_name, raw_port = _read_first_non_empty_env(_API_PORT_ENV_KEYS, default="18080")
    try:
        return int(raw_port)
    except ValueError as exc:
        source = env_name or _API_PORT_ENV_KEYS[0]
        raise ValueError(f"{source} 配置无效: {raw_port!r}") from exc


def _get_host() -> str:
    """读取 API 监听地址，默认绑定到本机回环地址。"""
    _, host = _read_first_non_empty_env(_API_HOST_ENV_KEYS, default="127.0.0.1")
    return host


def _configure_local_runtime_env() -> None:
    """补齐本地运行时默认值。

    目标：
    - 默认开启 embedding / OCR 预热，减少首次请求冷启动等待；
    - 将 OpenBLAS / OMP / MKL / NumExpr 的线程数收敛到 4，避免 PDF / OCR 本地任务过度抢占；
    - 如果用户已经显式设置环境变量，则保持用户配置优先。
    """
    for key, value in _RUNTIME_DEFAULTS.items():
        os.environ.setdefault(key, value)


if __name__ == "__main__":
    _configure_local_runtime_env()
    uvicorn.run(
        "api.app:app",
        host=_get_host(),
        port=_get_port(),
        reload=_is_reload_enabled(),
        log_config=_build_log_config(),
    )
