"""?? API ????????? uvicorn ??????????"""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# uvicorn ????????????????
LOG_CONFIG = {
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
            "filename": str(LOG_DIR / "backend.log"),
            "maxBytes": 1_048_576,
            "backupCount": 5,
            "formatter": "default",
            "encoding": "utf-8",
        },
        "access_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "access.log"),
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


def _is_reload_enabled() -> bool:
    """?????????? KB_API_RELOAD=1 ???"""
    return os.getenv("KB_API_RELOAD", "0").strip() == "1"


def _get_port() -> int:
    """?? API ????? 18080??? KB_API_PORT ???"""
    raw_port = os.getenv("KB_API_PORT", "18080").strip() or "18080"
    try:
        return int(raw_port)
    except ValueError as exc:
        raise ValueError(f"KB_API_PORT ??????: {raw_port!r}") from exc


if __name__ == "__main__":
    # ??????? API ????? OCR ??????? api.app ?????????
    os.environ.setdefault("THINKRAG_OCR_PREWARM", "1")
    uvicorn.run(
        "api.app:app",
        host="127.0.0.1",
        port=_get_port(),
        reload=_is_reload_enabled(),
        log_config=LOG_CONFIG,
    )
