"""Target-state agent runtime."""

from __future__ import annotations

from time import perf_counter

from api.services.agent_router import extract_path_from_text, route_agent_task
from api.services.agent_tools import run_cmd, run_kb_search, run_llm_chat, run_read_file
from api.services.approval_service import classify_command_risk, create_pending_action, get_pending_actions
from api.services.session_store import append_chat_message, replace_run_artifacts
from api.services.timeline_service import build_task_state, build_timeline
from api.services.tool_receipt_store import list_receipts
from utils.logging_utils import AGENT_RUN_LOG_FILE, append_json_log, new_trace_id, now_iso, safe_preview


def build_plan(tool_name: str) -> list[dict]:
    if tool_name == "run_cmd":
        return [
            {"id": "plan-risk", "title": "Assess command risk", "status": "pending"},
            {"id": "plan-execute", "title": "Execute or request approval", "status": "pending"},
            {"id": "plan-summarize", "title": "Summarize command result", "status": "pending"},
        ]

    if tool_name == "read_file":
        return [
            {"id": "plan-read", "title": "Read target file", "status": "pending"},
            {"id": "plan-summarize", "title": "Summarize file content", "status": "pending"},
        ]

    if tool_name == "llm_chat":
        return [
            {"id": "plan-model", "title": "Load current model config", "status": "pending"},
            {"id": "plan-answer", "title": "Call configured model", "status": "pending"},
            {"id": "plan-trace", "title": "Write receipt", "status": "pending"},
        ]

    return [
        {"id": "plan-search", "title": "Search knowledge evidence", "status": "pending"},
        {"id": "plan-answer", "title": "Compose grounded answer", "status": "pending"},
        {"id": "plan-trace", "title": "Return evidence and receipts", "status": "pending"},
    ]


def mark_completed(plan: list[dict], *ids: str) -> None:
    wanted = set(ids)
    for item in plan:
        if item["id"] in wanted:
            item["status"] = "completed"


def run_agent(request) -> dict:
    trace_id = new_trace_id("agentrun")
    started_at = perf_counter()
    session_id = request.session_id
    question = request.question.strip()

    replace_run_artifacts(
        session_id,
        {
            "workspace": {
                "current_mode": request.mode,
                "knowledge_scope": request.knowledge_scope.model_dump(),
                "task_goal": question,
                "draft_question": question,
                "run_state": "running",
            },
            "approval_message": "",
        },
    )

    append_json_log(
        "agent_run_logger",
        AGENT_RUN_LOG_FILE,
        {
            "logged_at": now_iso(),
            "trace_id": trace_id,
            "event": "run_started",
            "session_id": session_id,
            "mode": request.mode,
            "knowledge_scope": request.knowledge_scope.model_dump(),
            "question_preview": safe_preview(question, 300),
        },
    )

    route = route_agent_task(question=question, mode=request.mode)
    tool_name = route["tool_name"]
    append_json_log(
        "agent_run_logger",
        AGENT_RUN_LOG_FILE,
        {
            "logged_at": now_iso(),
            "trace_id": trace_id,
            "event": "route_selected",
            "session_id": session_id,
            "mode": request.mode,
            "tool_name": tool_name,
            "route": route,
        },
    )

    plan = build_plan(tool_name)
    steps: list[dict] = []
    evidence: list[dict] = []
    answer = ""
    status = "completed"

    try:
        if tool_name == "read_file":
            path = extract_path_from_text(question) or question
            output = run_read_file(session_id, path)
            mark_completed(plan, "plan-read", "plan-summarize")
            steps.append(
                {
                    "step": "read_file",
                    "title": "Read local file",
                    "status": "completed",
                    "risk_level": "low",
                    "receipt_id": output["receipt"]["id"],
                    "summary": f"Read {output['result']['path']}",
                }
            )
            answer = f"Read file: {output['result']['path']}\n\n{output['result']['excerpt']}"

        elif tool_name == "run_cmd":
            command = question.removeprefix("cmd:").strip() if question.lower().startswith("cmd:") else question
            risk_level = classify_command_risk(command)
            append_json_log(
                "agent_run_logger",
                AGENT_RUN_LOG_FILE,
                {
                    "logged_at": now_iso(),
                    "trace_id": trace_id,
                    "event": "command_risk_assessed",
                    "session_id": session_id,
                    "tool_name": tool_name,
                    "command": command,
                    "risk_level": risk_level,
                },
            )

            if risk_level == "low":
                output = run_cmd(session_id, command)
                mark_completed(plan, "plan-risk", "plan-execute", "plan-summarize")
                steps.append(
                    {
                        "step": "run_cmd",
                        "title": "Run low-risk command",
                        "status": "completed",
                        "risk_level": risk_level,
                        "receipt_id": output["receipt"]["id"],
                        "summary": command,
                    }
                )
                answer = output["result"]["output"] or "Command finished."
            else:
                pending_action = create_pending_action(session_id, command, risk_level)
                mark_completed(plan, "plan-risk")
                steps.append(
                    {
                        "step": "run_cmd_pending_approval",
                        "title": "Command waiting for approval",
                        "status": "waiting_approval",
                        "risk_level": risk_level,
                        "action_id": pending_action["action_id"],
                        "summary": command,
                    }
                )
                answer = f"Command risk level is `{risk_level}`. Approval is required before execution."
                status = "waiting_approval"

        elif tool_name == "kb_search":
            output = run_kb_search(session_id, question)
            evidence = output["evidence"]
            mark_completed(plan, "plan-search", "plan-answer", "plan-trace")
            steps.append(
                {
                    "step": "kb_search",
                    "title": "Search knowledge base",
                    "status": "completed",
                    "risk_level": "low",
                    "receipt_id": output["receipt"]["id"],
                    "evidence_ids": [item["id"] for item in evidence],
                    "summary": f"Found {len(evidence)} evidence items",
                }
            )
            answer = output["result"].get("answer") or "Knowledge search completed, but no final answer was returned."

        else:
            output = run_llm_chat(session_id, question)
            mark_completed(plan, "plan-model", "plan-answer", "plan-trace")
            steps.append(
                {
                    "step": "llm_chat",
                    "title": "Call current model",
                    "status": "completed",
                    "risk_level": "low",
                    "receipt_id": output["receipt"]["id"],
                    "summary": f"{output['result']['provider']} / {output['result']['model']}",
                }
            )
            answer = output["result"]["answer"] or "Model returned no answer."
            append_json_log(
                "agent_run_logger",
                AGENT_RUN_LOG_FILE,
                {
                    "logged_at": now_iso(),
                    "trace_id": trace_id,
                    "event": "tool_completed",
                    "session_id": session_id,
                    "tool_name": tool_name,
                    "receipt_id": output["receipt"]["id"],
                    "provider": output["result"]["provider"],
                    "model": output["result"]["model"],
                    "api_base": output["result"]["api_base"],
                    "answer_preview": safe_preview(output["result"]["answer"]),
                },
            )
    except Exception as exc:
        replace_run_artifacts(
            session_id,
            {
                "workspace": {
                    "run_state": "failed",
                }
            },
        )
        append_json_log(
            "agent_run_logger",
            AGENT_RUN_LOG_FILE,
            {
                "logged_at": now_iso(),
                "trace_id": trace_id,
                "event": "run_failed",
                "session_id": session_id,
                "tool_name": tool_name,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        raise

    pending_actions = get_pending_actions(session_id)
    task_state = build_task_state(status, pending_actions)
    timeline = build_timeline(question, answer, steps)

    append_chat_message(session_id, "user", question)
    append_chat_message(session_id, "assistant", answer)

    result = {
        "trace_id": trace_id,
        "session_id": session_id,
        "question": question,
        "knowledge_scope": request.knowledge_scope.model_dump(),
        "answer": answer,
        "task_state": task_state,
        "plan": plan,
        "steps": steps,
        "timeline": timeline,
        "evidence": evidence,
        "receipts": list_receipts(session_id=session_id, limit=20),
        "pending_actions": pending_actions,
    }

    replace_run_artifacts(
        session_id,
        {
            "timeline": timeline,
            "plan": plan,
            "evidence": evidence,
            "receipts": result["receipts"],
            "pending_actions": pending_actions,
            "task_state": task_state,
            "workspace": {
                "current_mode": request.mode,
                "knowledge_scope": request.knowledge_scope.model_dump(),
                "task_goal": question,
                "draft_question": "",
                "run_state": task_state["status"],
                "last_answer": answer,
            },
        },
    )

    append_json_log(
        "agent_run_logger",
        AGENT_RUN_LOG_FILE,
        {
            "logged_at": now_iso(),
            "trace_id": trace_id,
            "event": "run_finished",
            "session_id": session_id,
            "tool_name": tool_name,
            "status": result["task_state"]["status"],
            "pending_approval_count": result["task_state"]["pending_approval_count"],
            "receipts_count": len(result["receipts"]),
            "evidence_count": len(result["evidence"]),
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            "answer_preview": safe_preview(answer),
        },
    )
    return result

