"""Built-in skill registry for NorthAgent."""

from __future__ import annotations

from typing import Any


DEFAULT_ENABLED_SKILLS = ["planner", "file_context", "safe_command"]

_BUILTIN_SKILLS: list[dict[str, Any]] = [
    {
        "id": "planner",
        "name": "任务规划",
        "kind": "builtin",
        "status": "enabled",
        "summary": "把输入任务拆成清晰步骤，方便后续逐步执行。",
    },
    {
        "id": "file_context",
        "name": "文件上下文",
        "kind": "builtin",
        "status": "enabled",
        "summary": "把本地选择的文件或上传导入的文件纳入当前工作上下文。",
    },
    {
        "id": "safe_command",
        "name": "安全命令",
        "kind": "builtin",
        "status": "enabled",
        "summary": "对命令执行做风险分级，并在必要时进入审批流程。",
    },
    {
        "id": "receipt_trace",
        "name": "回执追踪",
        "kind": "builtin",
        "status": "enabled",
        "summary": "记录工具调用结果、证据摘要和审计信息。",
    },
]


def list_skills() -> list[dict[str, Any]]:
    return [dict(item) for item in _BUILTIN_SKILLS]


def get_skill(skill_id: str) -> dict[str, Any] | None:
    for item in _BUILTIN_SKILLS:
        if item["id"] == skill_id:
            return dict(item)
    return None

