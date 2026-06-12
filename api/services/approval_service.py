"""Approval and command-risk helpers."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import config
from api.services.risk_assessor import RiskAssessor
from api.services.session_store import append_pending_action, find_pending_action
from api.services.session_store import list_pending_actions as load_pending_actions
from api.services.session_store import update_pending_action
from api.services.tool_receipt_store import append_receipt
from server.security.command_validator import CommandValidator
from server.security.path_validator import PathValidator
from utils.logging_utils import APPROVAL_LOG_FILE, append_json_log, now_iso as log_now_iso

CMD_ALLOWLIST = {"ls", "pwd", "whoami", "date"}
HIGH_RISK_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bdel\s+/f\b",
    r"\bformat\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bcurl\b.*\|\s*(bash|sh|powershell)\b",
]

_path_validator = PathValidator(config.PATH_SECURITY)
_command_validator = CommandValidator(config.COMMAND_SECURITY, path_validator=_path_validator)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_command_policy(command: str) -> tuple[bool, str]:
    return _command_validator.validate((command or "").strip())


def classify_command_risk(command: str) -> str:
    """分类命令风险等级，返回 L0/L1/L2/L3，硬拒绝命令直接返回 L3"""
    from api.services.command_filter import CommandFilter
    deny_reason = CommandFilter.check_hard_deny(command)
    if deny_reason:
        return "L3"
    return RiskAssessor.assess(command).value


def create_pending_action(session_id: str, command: str, risk_level: str) -> dict[str, Any]:
    action = {
        "action_id": str(uuid4()),
        "session_id": session_id,
        "command": command.strip(),
        "risk_level": risk_level,
        "status": "pending",
        "created_at": now_iso(),
        "review_reason": "",
        "reviewed_by": "",
    }
    append_pending_action(session_id, action)
    append_receipt(
        session_id=session_id,
        tool_name="run_cmd",
        input_data={"command": command.strip()},
        output_data={"risk_level": risk_level, "message": "waiting for approval"},
        status="pending_approval",
    )
    append_json_log(
        "approval_logger",
        APPROVAL_LOG_FILE,
        {
            "logged_at": log_now_iso(),
            "event": "approval_requested",
            "session_id": session_id,
            "action_id": action["action_id"],
            "command": command.strip(),
            "risk_level": risk_level,
            "status": "pending",
        },
    )
    return action


def get_pending_actions(session_id: str) -> list[dict[str, Any]]:
    return load_pending_actions(session_id, status="pending")


def get_action(action_id: str) -> dict[str, Any] | None:
    return find_pending_action(action_id)


def resolve_action(action_id: str, status: str, reason: str = "", approver: str = "local-user") -> dict[str, Any] | None:
    return update_pending_action(
        action_id,
        {
            "status": status,
            "review_reason": reason,
            "reviewed_by": approver,
            "reviewed_at": now_iso(),
        },
    )
