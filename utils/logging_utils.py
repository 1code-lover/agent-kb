from __future__ import annotations

import json
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


def append_json_log(name: str, file_path: Path, payload: dict[str, Any]) -> None:
    """以 JSON Lines 追加写日志，并立即释放文件句柄。"""
    del name
    ensure_log_dir()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")
