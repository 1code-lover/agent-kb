"""Timeline and task-state assembly helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_task_state(status: str, pending_actions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "pending_approval_count": len(pending_actions or []),
        "updated_at": now_iso(),
    }


def build_timeline(question: str, answer: str, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    timeline = [{"type": "user", "content": question}]

    for step in steps:
        timeline.append(
            {
                "type": "step",
                "content": step.get("summary") or step.get("title") or step.get("step") or "unknown-step",
                "meta": {
                    "name": step.get("step"),
                    "title": step.get("title"),
                    "status": step.get("status"),
                    "riskLevel": step.get("risk_level"),
                    "receiptId": step.get("receipt_id"),
                    "actionId": step.get("action_id"),
                    "evidenceIds": step.get("evidence_ids", []),
                },
            }
        )

    timeline.append({"type": "assistant", "content": answer})
    return timeline
