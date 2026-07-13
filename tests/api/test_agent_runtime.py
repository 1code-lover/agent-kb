from __future__ import annotations

from api.schemas import AgentRunRequest, KnowledgeScope
from api.services import agent_runtime
from api.services.session_store import load_session, reset_session


def _request(question: str, session_id: str, mode: str = "run_cmd") -> AgentRunRequest:
    return AgentRunRequest(
        question=question,
        session_id=session_id,
        mode=mode,
        knowledge_scope=KnowledgeScope(),
    )


def test_run_cmd_requires_approval_and_persists_pending_action() -> None:
    session_id = "test-agent-runtime-pending"
    reset_session(session_id)

    result = agent_runtime.run_agent(_request("cmd: git status", session_id))

    assert result["task_state"]["status"] == "waiting_approval"
    assert len(result["pending_actions"]) == 1
    assert result["pending_actions"][0]["command"] == "git status"

    snapshot = load_session(session_id)
    assert snapshot["workspace"]["run_state"] == "waiting_approval"
    assert len(snapshot["pending_actions"]) == 1
    assert snapshot["pending_actions"][0]["status"] == "pending"


def test_rejecting_pending_action_updates_session_artifacts() -> None:
    session_id = "test-agent-runtime-reject"
    reset_session(session_id)
    created = agent_runtime.run_agent(_request("cmd: git status", session_id))
    action_id = created["pending_actions"][0]["action_id"]

    result = agent_runtime.resolve_pending_action(action_id, approve=False, reason="not now", approver="tester")

    assert result["status"] == "rejected"
    assert result["task_state"]["status"] == "completed"
    assert result["pending_actions"] == []
    assert result["answer"] == "Command was rejected."

    snapshot = load_session(session_id)
    assert snapshot["workspace"]["run_state"] == "completed"
    assert snapshot["approval_message"] == "Approval result: rejected"
    assert all(action["status"] != "pending" for action in snapshot["pending_actions"])


def test_approving_pending_action_executes_command_and_persists_result() -> None:
    session_id = "test-agent-runtime-approve"
    reset_session(session_id)
    created = agent_runtime.run_agent(_request("cmd: git status", session_id))
    action_id = created["pending_actions"][0]["action_id"]

    result = agent_runtime.resolve_pending_action(action_id, approve=True, reason="safe", approver="tester")

    assert result["status"] == "approved"
    assert result["task_state"]["status"] == "completed"
    assert result["pending_actions"] == []
    assert isinstance(result["result"], dict)
    assert "exit_code" in result["result"]
    assert "output" in result["result"]

    snapshot = load_session(session_id)
    assert snapshot["workspace"]["run_state"] == "completed"
    assert snapshot["approval_message"] == "Approval result: approved"
    assert snapshot["workspace"]["last_answer"] == result["answer"]
    assert all(action["status"] != "pending" for action in snapshot["pending_actions"])

