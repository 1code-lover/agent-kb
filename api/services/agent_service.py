"""Agent 执行服务，提供最小可用的计划与工具调用链路。"""

from __future__ import annotations

import os
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from api.schemas import AgentRunRequest, QueryRequest
from api.services import chat_service
from api.services.tool_receipt_store import append_receipt, list_receipts

_CMD_ALLOWLIST = {"dir", "ls", "pwd", "whoami", "python --version"}
_PENDING_ACTIONS: dict[str, dict[str, Any]] = {}
_SESSION_ACTIONS: dict[str, list[str]] = defaultdict(list)

_HIGH_RISK_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bdel\s+/f\b",
    r"\bformat\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bcurl\b.*\|\s*(bash|sh|powershell)\b",
]


def _now_iso() -> str:
    """返回统一的 UTC 时间戳。"""
    return datetime.now(timezone.utc).isoformat()


def _build_plan(question: str) -> list[dict[str, Any]]:
    """根据任务输入生成最小可执行计划。"""
    if question.lower().startswith("cmd:"):
        return [
            {"id": "plan-risk", "title": "评估命令风险", "status": "completed"},
            {"id": "plan-execute", "title": "执行或提交审批", "status": "pending"},
            {"id": "plan-summarize", "title": "汇总命令结果", "status": "pending"},
        ]
    if _extract_path_from_question(question):
        return [
            {"id": "plan-read", "title": "读取目标文件", "status": "pending"},
            {"id": "plan-summarize", "title": "提炼文件内容", "status": "pending"},
        ]
    return [
        {"id": "plan-search", "title": "检索知识库证据", "status": "pending"},
        {"id": "plan-answer", "title": "基于证据生成回答", "status": "pending"},
        {"id": "plan-trace", "title": "返回来源和执行回执", "status": "pending"},
    ]


def _complete_plan(plan: list[dict[str, Any]], *ids: str) -> None:
    """将指定计划项标记完成。"""
    target_ids = set(ids)
    for item in plan:
        if item["id"] in target_ids:
            item["status"] = "completed"


def _normalize_evidence(sources: list[dict[str, Any]], receipt_id: str | None = None) -> list[dict[str, Any]]:
    """把知识库来源转换成 Agent 证据结构。"""
    evidence: list[dict[str, Any]] = []
    for idx, source in enumerate(sources or [], start=1):
        text = source.get("text") or ""
        evidence.append(
            {
                "id": f"ev-{idx}",
                "title": source.get("file") or "Knowledge Source",
                "source": source.get("file") or "N/A",
                "page": source.get("page") or "N/A",
                "score": source.get("score"),
                "excerpt": text[:600],
                "receipt_id": receipt_id,
            }
        )
    return evidence


def _task_state(status: str, pending_actions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """生成前端可消费的任务状态摘要。"""
    pending_count = len(pending_actions or [])
    return {
        "status": status,
        "pending_approval_count": pending_count,
        "updated_at": _now_iso(),
    }


def _tool_kb_search(session_id: str, question: str) -> dict[str, Any]:
    """调用知识库问答工具。"""
    result = chat_service.query(request=QueryRequest(question=question, session_id=session_id))
    sources = result.get("sources", [])
    receipt = append_receipt(
        session_id=session_id,
        tool_name="kb_search",
        input_data={"question": question},
        output_data={"answer": result.get("answer", ""), "sources_count": len(sources)},
        status="ok",
    )
    return {"result": result, "receipt": receipt, "evidence": _normalize_evidence(sources, receipt["id"])}


def _extract_path_from_question(question: str) -> str | None:
    """从问题中提取本地路径。"""
    match = re.search(r"[A-Za-z]:\\[^\s]+", question)
    if match:
        return match.group(0)
    for token in re.split(r"\s+", question):
        cleaned = token.strip("`'\"，。；;、()[]{}<>")
        if "://" in cleaned:
            continue
        if cleaned.startswith("/"):
            return cleaned
    return None


def _tool_read_file(session_id: str, path_text: str) -> dict[str, Any]:
    """调用本地文件读取工具。"""
    target = Path(path_text)
    if not target.exists() or not target.is_file():
        raise ValueError("file not found")
    content = target.read_text(encoding="utf-8", errors="ignore")
    excerpt = content[:2000]
    receipt = append_receipt(
        session_id=session_id,
        tool_name="read_file",
        input_data={"path": str(target)},
        output_data={"chars": len(content), "excerpt": excerpt},
        status="ok",
    )
    return {"result": {"path": str(target), "excerpt": excerpt}, "receipt": receipt}


def _classify_command_risk(command: str) -> str:
    """命令风险分级。"""
    normalized = command.strip().lower()
    for pattern in _HIGH_RISK_PATTERNS:
        if re.search(pattern, normalized):
            return "high"
    if normalized in _CMD_ALLOWLIST:
        return "low"
    return "medium"


def _tool_run_cmd(session_id: str, command: str, enforce_allowlist: bool = True) -> dict[str, Any]:
    """调用命令工具（白名单）。"""
    cmd = command.strip()
    if enforce_allowlist and cmd not in _CMD_ALLOWLIST:
        raise ValueError("command not allowed")
    completed = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=8,
        cwd=os.getcwd(),
    )
    output = (completed.stdout or completed.stderr or "").strip()
    receipt = append_receipt(
        session_id=session_id,
        tool_name="run_cmd",
        input_data={"command": cmd},
        output_data={"exit_code": completed.returncode, "output": output[:2000]},
        status="ok" if completed.returncode == 0 else "error",
    )
    return {"result": {"exit_code": completed.returncode, "output": output}, "receipt": receipt}


def _create_pending_action(session_id: str, command: str, risk_level: str) -> dict[str, Any]:
    """创建待审批动作。"""
    action_id = str(uuid4())
    action = {
        "action_id": action_id,
        "session_id": session_id,
        "command": command.strip(),
        "risk_level": risk_level,
        "status": "pending",
        "created_at": _now_iso(),
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


def run_agent(request: AgentRunRequest) -> dict[str, Any]:
    """执行最小 Agent 循环。

    Args:
        request: Agent 请求参数。

    Returns:
        Dict[str, Any]: 结果与步骤回执。
    """
    session_id = request.session_id
    question = request.question.strip()
    plan = _build_plan(question)
    steps: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    pending_actions: list[dict[str, Any]] = []
    status = "completed"

    # 规则优先：明确文件路径问题优先读文件，否则走知识库。
    try:
        path = _extract_path_from_question(question)
        if path:
            read_file_output = _tool_read_file(session_id=session_id, path_text=path)
            _complete_plan(plan, "plan-read", "plan-summarize")
            steps.append(
                {
                    "step": "read_file",
                    "title": "读取本地文件",
                    "status": "completed",
                    "risk_level": "low",
                    "receipt_id": read_file_output["receipt"]["id"],
                    "summary": f"读取 {read_file_output['result']['path']}",
                }
            )
            final_answer = f"已读取文件：{read_file_output['result']['path']}\n\n{read_file_output['result']['excerpt']}"
        elif question.lower().startswith("cmd:"):
            command = question.split("cmd:", 1)[1].strip()
            risk_level = _classify_command_risk(command)
            if risk_level == "low":
                cmd_output = _tool_run_cmd(session_id=session_id, command=command)
                _complete_plan(plan, "plan-execute", "plan-summarize")
                steps.append(
                    {
                        "step": "run_cmd",
                        "title": "执行低风险命令",
                        "status": "completed",
                        "risk_level": risk_level,
                        "receipt_id": cmd_output["receipt"]["id"],
                        "summary": command,
                    }
                )
                final_answer = cmd_output["result"]["output"] or "命令执行完成。"
            else:
                pending_action = _create_pending_action(session_id=session_id, command=command, risk_level=risk_level)
                _complete_plan(plan, "plan-risk")
                steps.append(
                    {
                        "step": "run_cmd_pending_approval",
                        "title": "命令等待审批",
                        "status": "waiting_approval",
                        "risk_level": risk_level,
                        "action_id": pending_action["action_id"],
                        "summary": command,
                    }
                )
                final_answer = f"命令风险等级 `{risk_level}`，已进入审批队列，请在前端确认后执行。"
                status = "waiting_approval"
        else:
            kb_output = _tool_kb_search(session_id=session_id, question=question)
            _complete_plan(plan, "plan-search", "plan-answer", "plan-trace")
            evidence = kb_output["evidence"]
            steps.append(
                {
                    "step": "kb_search",
                    "title": "检索知识库",
                    "status": "completed",
                    "risk_level": "low",
                    "receipt_id": kb_output["receipt"]["id"],
                    "evidence_ids": [item["id"] for item in evidence],
                    "summary": f"命中 {len(evidence)} 条证据",
                }
            )
            final_answer = kb_output["result"]["answer"]
            if not final_answer:
                final_answer = "知识库已检索，但未返回有效答案。"
    except Exception as exc:
        append_receipt(
            session_id=session_id,
            tool_name="agent_error",
            input_data={"question": question},
            output_data={"message": str(exc)},
            status="error",
        )
        raise

    pending_actions = get_pending_actions(session_id)
    return {
        "session_id": session_id,
        "question": question,
        "answer": final_answer,
        "task_state": _task_state(status, pending_actions),
        "plan": plan,
        "steps": steps,
        "evidence": evidence,
        "receipts": list_receipts(session_id=session_id, limit=20),
        "pending_actions": pending_actions,
    }


def get_agent_receipts(session_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """查询会话 Agent 回执。"""
    return list_receipts(session_id=session_id, limit=limit)


def get_pending_actions(session_id: str) -> list[dict[str, Any]]:
    """查询会话待审批动作。"""
    action_ids = _SESSION_ACTIONS.get(session_id, [])
    return [action for action_id in action_ids if (action := _PENDING_ACTIONS.get(action_id)) and action["status"] == "pending"]


def resolve_pending_action(action_id: str, approve: bool, reason: str = "", approver: str = "local-user") -> dict[str, Any]:
    """审批待执行命令。"""
    action = _PENDING_ACTIONS.get(action_id)
    if action is None:
        raise ValueError("action not found")
    if action["status"] != "pending":
        raise ValueError("action already resolved")

    session_id = action["session_id"]
    if not approve:
        action["status"] = "rejected"
        action["review_reason"] = reason
        action["reviewed_by"] = approver
        action["reviewed_at"] = _now_iso()
        append_receipt(
            session_id=session_id,
            tool_name="run_cmd_approval",
            input_data={"action_id": action_id, "command": action["command"], "approver": approver},
            output_data={"message": "command rejected by user", "review_reason": reason},
            status="rejected",
        )
        return {
            "action_id": action_id,
            "status": "rejected",
            "review_reason": reason,
            "reviewed_by": approver,
            "reviewed_at": action["reviewed_at"],
        }

    cmd_output = _tool_run_cmd(
        session_id=session_id,
        command=action["command"],
        enforce_allowlist=False,
    )
    action["status"] = "approved"
    action["review_reason"] = reason
    action["reviewed_by"] = approver
    action["reviewed_at"] = _now_iso()
    append_receipt(
        session_id=session_id,
        tool_name="run_cmd_approval",
        input_data={"action_id": action_id, "command": action["command"], "approver": approver},
        output_data={"message": "command approved by user", "review_reason": reason},
        status="approved",
    )
    return {
        "action_id": action_id,
        "status": "approved",
        "review_reason": reason,
        "reviewed_by": approver,
        "reviewed_at": action["reviewed_at"],
        "result": cmd_output["result"],
    }
