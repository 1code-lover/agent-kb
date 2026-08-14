from __future__ import annotations

from unittest.mock import patch

from api.schemas import AgentRunRequest, KnowledgeScope
from api.services import agent_runtime
from api.services.session_store import load_session, reset_session


def _request(
    question: str,
    session_id: str,
    mode: str = "run_cmd",
    knowledge_scope: KnowledgeScope | None = None,
) -> AgentRunRequest:
    return AgentRunRequest(
        question=question,
        session_id=session_id,
        mode=mode,
        knowledge_scope=knowledge_scope or KnowledgeScope(),
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



def test_kb_search_passes_knowledge_scope_as_kb_ids() -> None:
    session_id = "test-agent-runtime-kb-scope"
    reset_session(session_id)

    request = _request(
        "帮我查产品文档",
        session_id,
        mode="kb_search",
        knowledge_scope=KnowledgeScope(kb_id="my-kb", kb_name="My KB"),
    )

    with patch("api.services.agent_runtime.run_kb_search") as mock_run_kb_search:
        mock_run_kb_search.return_value = {
            "result": {"answer": "ok"},
            "receipt": {"id": "receipt-1"},
            "evidence": [],
        }
        result = agent_runtime.run_agent(request)

    mock_run_kb_search.assert_called_once_with(session_id, "帮我查产品文档", kb_ids=["my-kb"])
    assert result["task_state"]["status"] == "completed"
    assert result["answer"] == "ok"


def test_agent_llm_chat_returns_fallback_health_and_switch_summary() -> None:
    """Agent 直连模型切换后应把健康状态和明确切换摘要返回给前端。"""
    session_id = "test-agent-runtime-fallback"
    reset_session(session_id)
    fallback = {
        "applied": True,
        "error_kind": "quota_exhausted",
        "fallback_from": {"service_provider": "Cloud", "model": "expired"},
        "fallback_to": {"service_provider": "Ollama", "model": "qwen2.5:7b"},
    }
    model_health = {
        "state": "fallback_applied",
        "current_provider": "Ollama",
        "current_model": "qwen2.5:7b",
        "fallback_from": fallback["fallback_from"],
        "fallback_to": fallback["fallback_to"],
    }

    with (
        patch("api.services.agent_runtime.route_agent_task", return_value={"tool_name": "llm_chat"}),
        patch("api.services.agent_runtime.run_llm_chat") as mock_run_llm_chat,
    ):
        mock_run_llm_chat.return_value = {
            "result": {
                "provider": "Ollama",
                "model": "qwen2.5:7b",
                "api_base": "http://localhost:11434",
                "answer": "fallback answer",
            },
            "receipt": {"id": "receipt-agent-fallback"},
            "evidence": [],
            "fallback": fallback,
            "model_health": model_health,
        }
        result = agent_runtime.run_agent(_request("hello", session_id, mode="agent"))

    assert result["answer"] == "fallback answer"
    assert result["fallback"] == fallback
    assert result["model_health"] == model_health
    assert result["steps"][0]["summary"] == "已自动切换到 Ollama / qwen2.5:7b"
