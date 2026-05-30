"""Agent execution, approval and session routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import AgentApprovalRequest, AgentRunRequest, AgentSessionResetRequest, AgentSessionUpdateRequest
from api.services import agent_service
from api.services.session_store import load_session, reset_session, update_session
from api.services.skill_registry import list_skills
from utils.api_response import success_response

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/run")
def run_agent(request: AgentRunRequest) -> dict:
    try:
        return success_response(agent_service.run_agent(request))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/receipts")
def get_receipts(session_id: str = "desktop-default", limit: int = 50) -> dict:
    return success_response({"session_id": session_id, "receipts": agent_service.get_agent_receipts(session_id, limit)})


@router.get("/pending")
def get_pending_actions(session_id: str = "desktop-default") -> dict:
    return success_response({"session_id": session_id, "pending_actions": agent_service.get_pending_actions(session_id)})


@router.post("/approvals")
def approve_action(request: AgentApprovalRequest) -> dict:
    try:
        return success_response(
            agent_service.resolve_pending_action(
                request.action_id,
                request.approve,
                request.reason,
                request.approver,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/session")
def get_session_snapshot(session_id: str = "desktop-default") -> dict:
    return success_response({"session_id": session_id, "snapshot": load_session(session_id)})


@router.put("/session")
def update_session_snapshot(request: AgentSessionUpdateRequest) -> dict:
    patch: dict = {}
    if request.workspace:
        patch["workspace"] = request.workspace
    if request.ui_state:
        patch["ui_state"] = request.ui_state
    if request.timeline is not None:
        patch["timeline"] = request.timeline
    if request.plan is not None:
        patch["plan"] = request.plan
    if request.evidence is not None:
        patch["evidence"] = request.evidence
    if request.receipts is not None:
        patch["receipts"] = request.receipts
    if request.pending_actions is not None:
        patch["pending_actions"] = request.pending_actions
    if request.task_state is not None:
        patch["task_state"] = request.task_state
    if request.approval_message is not None:
        patch["approval_message"] = request.approval_message
    return success_response({"session_id": request.session_id, "snapshot": update_session(request.session_id, patch)})


@router.post("/session/reset")
def reset_session_snapshot(request: AgentSessionResetRequest) -> dict:
    return success_response({"session_id": request.session_id, "snapshot": reset_session(request.session_id)})


@router.get("/skills")
def get_skill_registry() -> dict:
    return success_response({"skills": list_skills()})

