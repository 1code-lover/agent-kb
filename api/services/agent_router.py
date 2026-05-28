"""Agent routing helpers."""

from __future__ import annotations

import re


WINDOWS_PATH_PATTERN = re.compile(r"[A-Za-z]:\\[^\s]+")


def extract_path_from_text(question: str) -> str | None:
    """Extract a Windows local path from free text."""
    match = WINDOWS_PATH_PATTERN.search(question or "")
    if match:
        return match.group(0)
    return None


def route_agent_task(question: str, mode: str) -> dict[str, str]:
    """Resolve the target tool for the current run."""
    normalized_mode = (mode or "agent").strip().lower()

    if normalized_mode == "agent":
        return {"tool_name": "llm_chat", "reason": "explicit_agent_mode"}
    if normalized_mode == "kb_search":
        return {"tool_name": "kb_search", "reason": "explicit_mode"}
    if normalized_mode == "read_file":
        return {"tool_name": "read_file", "reason": "explicit_mode"}
    if normalized_mode == "run_cmd":
        return {"tool_name": "run_cmd", "reason": "explicit_mode"}

    if extract_path_from_text(question):
        return {"tool_name": "read_file", "reason": "path_detected"}

    if (question or "").strip().lower().startswith("cmd:"):
        return {"tool_name": "run_cmd", "reason": "command_prefix"}

    return {"tool_name": "llm_chat", "reason": "default_rule"}
