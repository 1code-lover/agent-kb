"""Approval and command-risk helpers."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from api.services.tool_receipt_store import append_receipt

CMD_ALLOWLIST = {"dir", "ls", "pwd", "whoami", "python --version"}
HIGH_RISK_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bdel\s+/f\b",
    r"\bformat\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bcurl\b.*\|\s*(bash|sh|powershell)\b",
]

_PENDING_ACTIONS: dict[str, dict[str, Any]] = {}
_SESSION_ACTIONS: dict[str, list[str]] = defaultdict(list)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_command_risk(command: str) -> str:
    normalized = (command or "").strip().lower()
    for pattern in HIGH_RISK_PATTERNS:
        if re.search(pattern, normalized):
            return "high"
    if normalized in CMD_ALLOWLIST:
        return "low"
    return "medium"


def create_pending_action(session_id: str, command: str, risk_level: str) -> dict[str, Any]:
    action_id = str(uuid4())
    action = {
        "action_id": action_id,
        "session_id": session_id,
        "command": command.strip(),
        "risk_level": risk_level,
        "status": "pending",
        "created_at": now_iso(),
    }
    _PENDING_ACTIONS[action_id] = action
    _SESSION_ACTIONS[session_id].append(action_id)

    append_receipt(
        session_id=session_id,
        tool_name="run_cmd",
        input_data={"command": command.strip()},
        output_data={"risk_level": risk_level, "message": "waiting for approval"},
        status="pending_approval",
    )
    return action


def get_pending_actions(session_id: str) -> list[dict[str, Any]]:
    action_ids = _SESSION_ACTIONS.get(session_id, [])
    return [action for action_id in action_ids if (action := _PENDING_ACTIONS.get(action_id)) and action["status"] == "pending"]


def get_action(action_id: str) -> dict[str, Any] | None:
    return _PENDING_ACTIONS.get(action_id)
