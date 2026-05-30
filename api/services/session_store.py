"""Persistent session snapshot store."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

import config
from api.services.fallback_store import FALLBACK_CONFIG_STORE
from api.services.skill_registry import DEFAULT_ENABLED_SKILLS
from utils.logging_utils import SESSION_LOG_FILE, append_json_log, now_iso, safe_preview


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SESSION_DIR = _PROJECT_ROOT / config.STORAGE_DIR / "sessions"
_CURRENT_VERSION = 1


def _ensure_session_dir() -> None:
    _SESSION_DIR.mkdir(parents=True, exist_ok=True)


def _session_file(session_id: str) -> Path:
    _ensure_session_dir()
    safe_session_id = (session_id or "desktop-default").strip() or "desktop-default"
    return _SESSION_DIR / f"{safe_session_id}.json"


def _default_provider_snapshot() -> dict[str, str]:
    current_llm_info = FALLBACK_CONFIG_STORE.get("current_llm_info") or {}
    return {
        "name": current_llm_info.get("service_provider", ""),
        "base_url": current_llm_info.get("api_base", ""),
        "model": current_llm_info.get("model", ""),
    }


def _default_snapshot(session_id: str) -> dict[str, Any]:
    timestamp = now_iso()
    return {
        "version": _CURRENT_VERSION,
        "session_id": session_id,
        "updated_at": timestamp,
        "workspace": {
            "current_mode": "agent",
            "provider": _default_provider_snapshot(),
            "knowledge_scope": {"kb_id": "default", "kb_name": "NorthAgent Workspace"},
            "task_goal": "",
            "draft_question": "",
            "run_state": "idle",
            "last_answer": "",
            "attached_files": [],
            "enabled_skills": list(DEFAULT_ENABLED_SKILLS),
        },
        "chat_history": [],
        "timeline": [],
        "plan": [],
        "evidence": [],
        "receipts": [],
        "pending_actions": [],
        "task_state": None,
        "approval_message": "",
        "ui_state": {
            "active_detail": "receipts",
            "show_details": False,
        },
    }


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _migrate_snapshot(snapshot: dict[str, Any] | None, session_id: str) -> dict[str, Any]:
    default = _default_snapshot(session_id)
    if not isinstance(snapshot, dict):
        return default

    merged = _deep_merge(default, snapshot)
    merged["version"] = _CURRENT_VERSION
    merged["session_id"] = session_id
    merged["updated_at"] = merged.get("updated_at") or now_iso()

    workspace = merged.setdefault("workspace", {})
    workspace.setdefault("enabled_skills", list(DEFAULT_ENABLED_SKILLS))
    workspace.setdefault("attached_files", [])
    workspace.setdefault("provider", _default_provider_snapshot())
    merged.setdefault("ui_state", default["ui_state"])
    return merged


def _safe_read_snapshot(path: Path, session_id: str) -> dict[str, Any]:
    if not path.exists():
        return _default_snapshot(session_id)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return _migrate_snapshot(raw, session_id)
    except Exception as exc:
        broken_path = path.with_suffix(f".broken.{path.stat().st_mtime_ns}.json")
        path.replace(broken_path)
        snapshot = _default_snapshot(session_id)
        append_json_log(
            "session_logger",
            SESSION_LOG_FILE,
            {
                "logged_at": now_iso(),
                "event": "session_recovered_from_broken_file",
                "session_id": session_id,
                "broken_file": str(broken_path),
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        return snapshot


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    json.loads(tmp_path.read_text(encoding="utf-8"))
    tmp_path.replace(path)


def load_session(session_id: str = "desktop-default") -> dict[str, Any]:
    path = _session_file(session_id)
    snapshot = _safe_read_snapshot(path, session_id)
    if not path.exists():
        _atomic_write(path, snapshot)
    append_json_log(
        "session_logger",
        SESSION_LOG_FILE,
        {
            "logged_at": now_iso(),
            "event": "session_loaded",
            "session_id": session_id,
            "path": str(path),
            "timeline_count": len(snapshot.get("timeline", [])),
            "receipt_count": len(snapshot.get("receipts", [])),
            "pending_count": len(snapshot.get("pending_actions", [])),
        },
    )
    return snapshot


def save_session(session_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    path = _session_file(session_id)
    merged = _migrate_snapshot(snapshot, session_id)
    merged["updated_at"] = now_iso()
    _atomic_write(path, merged)
    append_json_log(
        "session_logger",
        SESSION_LOG_FILE,
        {
            "logged_at": merged["updated_at"],
            "event": "session_saved",
            "session_id": session_id,
            "path": str(path),
            "timeline_count": len(merged.get("timeline", [])),
            "receipt_count": len(merged.get("receipts", [])),
            "pending_count": len(merged.get("pending_actions", [])),
        },
    )
    return merged


def update_session(session_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    current = load_session(session_id)
    merged = _deep_merge(current, patch)
    merged["updated_at"] = now_iso()
    return save_session(session_id, merged)


def reset_session(session_id: str = "desktop-default") -> dict[str, Any]:
    snapshot = _default_snapshot(session_id)
    append_json_log(
        "session_logger",
        SESSION_LOG_FILE,
        {
            "logged_at": now_iso(),
            "event": "session_reset",
            "session_id": session_id,
        },
    )
    return save_session(session_id, snapshot)


def append_chat_message(session_id: str, role: str, content: str) -> dict[str, Any]:
    if not content:
        return load_session(session_id)

    snapshot = load_session(session_id)
    snapshot["chat_history"].append(
        {
            "id": f"msg-{uuid4().hex[:12]}",
            "role": role,
            "content": content,
            "created_at": now_iso(),
        }
    )
    return save_session(session_id, snapshot)


def list_chat_messages(session_id: str) -> list[dict[str, Any]]:
    snapshot = load_session(session_id)
    return snapshot.get("chat_history", [])


def clear_chat_messages(session_id: str) -> dict[str, Any]:
    snapshot = load_session(session_id)
    snapshot["chat_history"] = []
    return save_session(session_id, snapshot)


def append_receipt(session_id: str, receipt: dict[str, Any]) -> dict[str, Any]:
    snapshot = load_session(session_id)
    receipts = snapshot.get("receipts", [])
    receipts.append(receipt)
    snapshot["receipts"] = receipts[-200:]
    return save_session(session_id, snapshot)


def list_receipts(session_id: str, limit: int = 50) -> list[dict[str, Any]]:
    snapshot = load_session(session_id)
    return snapshot.get("receipts", [])[-limit:]


def append_pending_action(session_id: str, action: dict[str, Any]) -> dict[str, Any]:
    snapshot = load_session(session_id)
    actions = snapshot.get("pending_actions", [])
    actions.append(action)
    snapshot["pending_actions"] = actions
    return save_session(session_id, snapshot)


def list_pending_actions(session_id: str, status: str | None = None) -> list[dict[str, Any]]:
    snapshot = load_session(session_id)
    actions = snapshot.get("pending_actions", [])
    if status is None:
        return actions
    return [item for item in actions if item.get("status") == status]


def update_pending_action(action_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    _ensure_session_dir()
    for session_file in _SESSION_DIR.glob("*.json"):
        session_id = session_file.stem
        snapshot = load_session(session_id)
        changed = False
        for index, action in enumerate(snapshot.get("pending_actions", [])):
            if action.get("action_id") == action_id:
                snapshot["pending_actions"][index] = _deep_merge(action, patch)
                changed = True
                updated_action = snapshot["pending_actions"][index]
                save_session(session_id, snapshot)
                return updated_action
        if changed:
            break
    return None


def find_pending_action(action_id: str) -> dict[str, Any] | None:
    _ensure_session_dir()
    for session_file in _SESSION_DIR.glob("*.json"):
        session_id = session_file.stem
        snapshot = load_session(session_id)
        for action in snapshot.get("pending_actions", []):
            if action.get("action_id") == action_id:
                return action
    return None


def replace_run_artifacts(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    snapshot = load_session(session_id)
    for key in ("timeline", "plan", "evidence", "receipts", "pending_actions", "task_state"):
        if key in payload:
            snapshot[key] = deepcopy(payload[key])

    if "approval_message" in payload:
        snapshot["approval_message"] = payload["approval_message"]

    workspace_patch = payload.get("workspace", {})
    snapshot["workspace"] = _deep_merge(snapshot.get("workspace", {}), workspace_patch)
    append_json_log(
        "session_logger",
        SESSION_LOG_FILE,
        {
            "logged_at": now_iso(),
            "event": "session_artifacts_replaced",
            "session_id": session_id,
            "timeline_count": len(snapshot.get("timeline", [])),
            "receipt_count": len(snapshot.get("receipts", [])),
            "pending_count": len(snapshot.get("pending_actions", [])),
            "answer_preview": safe_preview(snapshot.get("workspace", {}).get("last_answer", "")),
        },
    )
    return save_session(session_id, snapshot)
