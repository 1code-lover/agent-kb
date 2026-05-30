from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import config


LOG_DIR = Path(config.STORAGE_DIR) / "logs"
MODEL_TEST_LOG_FILE = LOG_DIR / "model_test.log"
AGENT_RUN_LOG_FILE = LOG_DIR / "agent_run.log"
APPROVAL_LOG_FILE = LOG_DIR / "approval.log"
COMMAND_LOG_FILE = LOG_DIR / "command.log"
SESSION_LOG_FILE = LOG_DIR / "session.log"


def ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_trace_id(prefix: str = "trace") -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def safe_preview(value: Any, limit: int = 800) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except Exception:
            text = repr(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...(truncated)"


def get_file_logger(name: str, file_path: Path) -> logging.Logger:
    ensure_log_dir()
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = logging.FileHandler(file_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger


def append_json_log(name: str, file_path: Path, payload: dict[str, Any]) -> None:
    logger = get_file_logger(name, file_path)
    logger.info(json.dumps(payload, ensure_ascii=False))
