"""
模块功能：
- 暴露 Agent 执行、回执查询、待审批查询和审批处理接口。

执行逻辑：
1. 接收请求参数并调用 agent_service。
2. 将服务层结果封装为统一成功响应。
3. 将常见异常映射为对应 HTTP 状态码。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import AgentApprovalRequest, AgentRunRequest
from api.services import agent_service
from utils.api_response import success_response

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/run")
def run_agent(request: AgentRunRequest) -> dict:
    """
    执行一次 Agent 任务。

    输入：
    - request(AgentRunRequest): 任务请求参数。

    输出：
    - dict: 标准化 API 响应，data 中包含执行结果。
    """
    try:
        return success_response(agent_service.run_agent(request))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/receipts")
def get_receipts(session_id: str = "default", limit: int = 50) -> dict:
    """
    查询指定会话的 Agent 工具回执。

    输入：
    - session_id(str): 会话 ID。
    - limit(int): 回执数量上限。

    输出：
    - dict: 标准化 API 响应，data 中包含回执列表。
    """
    return success_response({"session_id": session_id, "receipts": agent_service.get_agent_receipts(session_id, limit)})


@router.get("/pending")
def get_pending_actions(session_id: str = "default") -> dict:
    """
    查询会话中的待审批命令动作。

    输入：
    - session_id(str): 会话 ID。

    输出：
    - dict: 标准化 API 响应，data 中包含待审批动作列表。
    """
    return success_response({"session_id": session_id, "pending_actions": agent_service.get_pending_actions(session_id)})


@router.post("/approvals")
def approve_action(request: AgentApprovalRequest) -> dict:
    """
    提交命令审批结果。

    输入：
    - request(AgentApprovalRequest): 审批请求参数。

    输出：
    - dict: 标准化 API 响应，data 中包含审批处理结果。
    """
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
