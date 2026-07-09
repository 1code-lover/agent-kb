"""本地 API 启动脚本（带轮转日志）。"""

from __future__ import annotations

from pathlib import Path

import uvicorn

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# uvicorn 日志配置：1MB 轮转 + 时间戳
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

if __name__ == "__main__":
    uvicorn.run("api.app:app", host="127.0.0.1", port=18080, reload=True, log_config=LOG_CONFIG)
