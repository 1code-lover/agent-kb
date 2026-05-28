"""Compatibility layer over the target-state agent runtime."""

from __future__ import annotations

from api.services.agent_runtime import build_plan, mark_completed
from api.services.agent_tools import run_cmd
from api.services.approval_service import get_action, get_pending_actions as list_pending_actions
from api.services.timeline_service import build_task_state, build_timeline
from api.services.tool_receipt_store import append_receipt, list_receipts


def run_agent(request):
    from api.services.agent_runtime import run_agent as runtime_run_agent

    return runtime_run_agent(request)


def get_agent_receipts(session_id: str, limit: int = 50):
    return list_receipts(session_id=session_id, limit=limit)


def get_pending_actions(session_id: str):
    return list_pending_actions(session_id)


def resolve_pending_action(action_id: str, approve: bool, reason: str = "", approver: str = "local-user") -> dict:
    action = get_action(action_id)
    if action is None:
        raise ValueError("action not found")
    if action["status"] != "pending":
        raise ValueError("action already resolved")

    session_id = action["session_id"]
    command = action["command"]
    pending_actions = []

    if not approve:
        action["status"] = "rejected"
        action["review_reason"] = reason
        action["reviewed_by"] = approver
        approval_receipt = append_receipt(
            session_id=session_id,
            tool_name="run_cmd_approval",
            input_data={"action_id": action_id, "command": command, "approver": approver},
            output_data={"message": "command rejected by user", "review_reason": reason},
            status="rejected",
        )
        plan = build_plan("run_cmd")
        mark_completed(plan, "plan-risk")
        task_state = build_task_state("failed", pending_actions)
        steps = [
            {
                "step": "run_cmd_pending_approval",
                "title": "Command waiting for approval",
                "status": "failed",
                "risk_level": action["risk_level"],
                "action_id": action_id,
                "receipt_id": approval_receipt["id"],
                "summary": command,
            }
        ]
        answer = "Command was rejected."
        return {
            "action_id": action_id,
            "status": "rejected",
            "review_reason": reason,
            "reviewed_by": approver,
            "answer": answer,
            "task_state": task_state,
            "plan": plan,
            "steps": steps,
            "timeline": build_timeline(command, answer, steps),
            "receipts": list_receipts(session_id=session_id, limit=20),
            "pending_actions": pending_actions,
        }

    output = run_cmd(session_id=session_id, command=command, enforce_allowlist=False)
    action["status"] = "approved"
    action["review_reason"] = reason
    action["reviewed_by"] = approver
    approval_receipt = append_receipt(
        session_id=session_id,
        tool_name="run_cmd_approval",
        input_data={"action_id": action_id, "command": command, "approver": approver},
        output_data={"message": "command approved by user", "review_reason": reason, "run_receipt_id": output["receipt"]["id"]},
        status="approved",
    )

    plan = build_plan("run_cmd")
    mark_completed(plan, "plan-risk", "plan-execute", "plan-summarize")
    answer = output["result"]["output"] or "Command finished."
    steps = [
        {
            "step": "run_cmd_approval",
            "title": "Command approved",
            "status": "completed",
            "risk_level": action["risk_level"],
            "action_id": action_id,
            "receipt_id": approval_receipt["id"],
            "summary": f"Approved: {command}",
        },
        {
            "step": "run_cmd",
            "title": "Run approved command",
            "status": "completed",
            "risk_level": action["risk_level"],
            "receipt_id": output["receipt"]["id"],
            "summary": command,
        },
    ]
    task_state = build_task_state("completed", pending_actions)
    return {
        "action_id": action_id,
        "status": "approved",
        "review_reason": reason,
        "reviewed_by": approver,
        "run_receipt_id": output["receipt"]["id"],
        "answer": answer,
        "task_state": task_state,
        "plan": plan,
        "steps": steps,
        "timeline": build_timeline(command, answer, steps),
        "receipts": list_receipts(session_id=session_id, limit=20),
        "pending_actions": pending_actions,
    }
