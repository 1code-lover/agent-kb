# Desktop Knowledge Agent MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 允许对现有 Agent 雏形进行大改，直接重建符合目标态的桌面端 Knowledge Agent MVP，并在功能分支内完成一次性切换。

**Architecture:** 以现有 Electron + React + FastAPI 为底座，但不要求兼容当前前端页面和单文件 agent 实现。先建立新 contract、新 runtime、新首页，再补审批闭环和桌面联调，最后切主入口并清理旧实现。

**Tech Stack:** Electron、React、Vite、Zustand、FastAPI、Pydantic、LlamaIndex

---

## 文件结构与职责

### 需要新增的文件

- `api/services/agent_runtime.py`
  - 新版 agent 运行时总调度
- `api/services/agent_router.py`
  - 规则优先、LLM 兜底的路由层
- `api/services/agent_tools.py`
  - 新版工具注册与执行封装
- `api/services/approval_service.py`
  - 审批流和风险分级
- `api/services/timeline_service.py`
  - 时间线、步骤、证据、状态组装
- `webapp/src/pages/AgentPage.jsx`
  - 新版首页
- `webapp/src/components/agent/AgentInputPanel.jsx`
  - 输入区与模式切换
- `webapp/src/components/agent/AgentTaskStateBar.jsx`
  - 顶部状态摘要
- `webapp/src/components/agent/AgentTimeline.jsx`
  - 时间线展示
- `webapp/src/components/agent/AgentEvidencePanel.jsx`
  - 证据展示
- `webapp/src/components/agent/AgentApprovalPanel.jsx`
  - 审批区
- `webapp/src/components/agent/AgentReceiptsPanel.jsx`
  - 回执区

### 需要重点修改的文件

- `api/schemas.py`
  - 改成目标态 schema
- `api/routers/agent.py`
  - 切到新 runtime
- `api/services/agent_service.py`
  - 最终降为兼容层或删除旧逻辑
- `api/services/tool_receipt_store.py`
  - 校验是否满足新前端对 receipt 的读取需求
- `webapp/src/App.jsx`
  - 切首页路由
- `webapp/src/components/ShellLayout.jsx`
  - 调整导航和首页入口
- `webapp/src/api/agent.js`
  - 按目标态 contract 收口
- `webapp/src/store/appStore.js`
  - 补足新工作台状态与 action
- `webapp/src/store/agentState.js`
  - 纯映射新 contract
- `webapp/src/pages/QueryPage.jsx`
  - 最后降级或下线

### 继续复用的文件

- `api/runtime.py`
- `api/services/chat_service.py`
- `api/services/kb_service.py`
- `server/engine.py`
- `server/retriever.py`
- `desktop/src/main.js`
- `desktop/src/python-process.js`

## Task 1: 先建立目标态 Agent Contract 与新 runtime 入口

**Files:**
- Modify: `api/schemas.py`
- Modify: `api/routers/agent.py`
- Create: `api/services/agent_runtime.py`
- Test: `tests/api/test_agent_contract.py`

- [ ] **Step 1: 在 `api/schemas.py` 中定义目标态 schema，不再保留 `mode="auto"` 作为核心 contract**

```python
from typing import Any, Literal
from pydantic import BaseModel, Field


class KnowledgeScope(BaseModel):
    kb_id: str = Field(default="default")
    kb_name: str = Field(default="Default KB")


class AgentRunRequest(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: str = Field(default="default")
    mode: Literal["agent", "kb_search", "read_file", "run_cmd"] = "agent"
    tool_hint: str | None = None
    knowledge_scope: KnowledgeScope = Field(default_factory=KnowledgeScope)


class TaskState(BaseModel):
    status: Literal["idle", "running", "completed", "waiting_approval", "failed"]
    pending_approval_count: int = 0
    updated_at: str


class PlanItem(BaseModel):
    id: str
    title: str
    status: Literal["pending", "completed", "waiting_approval", "failed"]


class StepItem(BaseModel):
    step: str
    title: str
    status: Literal["pending", "completed", "waiting_approval", "failed"]
    risk_level: Literal["low", "medium", "high"] | None = None
    receipt_id: str | None = None
    action_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    summary: str = ""


class TimelineItem(BaseModel):
    type: str
    content: str
    meta: dict[str, Any] | None = None


class EvidenceItem(BaseModel):
    id: str
    title: str
    source: str
    page: str | None = None
    score: float | None = None
    excerpt: str = ""
    receipt_id: str | None = None
    kb_id: str = "default"


class PendingActionItem(BaseModel):
    action_id: str
    session_id: str
    command: str
    risk_level: Literal["low", "medium", "high"]
    status: str
    created_at: str


class AgentRunData(BaseModel):
    session_id: str
    question: str
    knowledge_scope: KnowledgeScope
    answer: str
    task_state: TaskState
    plan: list[PlanItem] = Field(default_factory=list)
    steps: list[StepItem] = Field(default_factory=list)
    timeline: list[TimelineItem] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    receipts: list[dict[str, Any]] = Field(default_factory=list)
    pending_actions: list[PendingActionItem] = Field(default_factory=list)
```

- [ ] **Step 2: 新建 `api/services/agent_runtime.py` 作为新版运行时入口，先返回静态目标结构**

```python
from __future__ import annotations

from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_agent(request) -> dict:
    return {
        "session_id": request.session_id,
        "question": request.question,
        "knowledge_scope": request.knowledge_scope.model_dump(),
        "answer": "",
        "task_state": {
            "status": "running",
            "pending_approval_count": 0,
            "updated_at": _now_iso(),
        },
        "plan": [],
        "steps": [],
        "timeline": [],
        "evidence": [],
        "receipts": [],
        "pending_actions": [],
    }
```

- [ ] **Step 3: 修改 `api/routers/agent.py`，直接切到新 runtime**

```python
from fastapi import APIRouter, HTTPException

from api.schemas import AgentRunRequest
from api.services.agent_runtime import run_agent
from utils.api_response import success_response

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/run")
def run_agent_route(request: AgentRunRequest) -> dict:
    try:
        return success_response(run_agent(request))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
```

- [ ] **Step 4: 为新 contract 增加最小测试，确保目标结构已可用**

```python
from fastapi.testclient import TestClient
from api.app import app


def test_agent_run_target_contract(monkeypatch):
    client = TestClient(app)

    def fake_run_agent(request):
        return {
            "session_id": request.session_id,
            "question": request.question,
            "knowledge_scope": {"kb_id": "default", "kb_name": "Default KB"},
            "answer": "",
            "task_state": {
                "status": "running",
                "pending_approval_count": 0,
                "updated_at": "2026-05-28T10:00:00Z",
            },
            "plan": [],
            "steps": [],
            "timeline": [],
            "evidence": [],
            "receipts": [],
            "pending_actions": [],
        }

    monkeypatch.setattr("api.routers.agent.run_agent", fake_run_agent)
    response = client.post("/api/agent/run", json={"question": "hello", "mode": "agent"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["knowledge_scope"]["kb_id"] == "default"
    assert "timeline" in data
```

- [ ] **Step 5: 运行 contract 测试**

Run:

```powershell
pytest tests/api/test_agent_contract.py -q
```

Expected:
- 测试通过

- [ ] **Step 6: Commit**

```bash
git add api/schemas.py api/routers/agent.py api/services/agent_runtime.py tests/api/test_agent_contract.py
git commit -m "feat: establish target-state agent contract"
```

## Task 2: 重建 runtime 分层，不复用旧单文件实现

**Files:**
- Create: `api/services/agent_router.py`
- Create: `api/services/agent_tools.py`
- Create: `api/services/approval_service.py`
- Create: `api/services/timeline_service.py`
- Modify: `api/services/agent_runtime.py`
- Modify: `api/services/agent_service.py`
- Test: `tests/api/test_agent_runtime.py`

- [ ] **Step 1: 为新 router 写测试，要求显式模式优先、规则次之**

```python
from api.services.agent_router import route_agent_task


def test_route_agent_task_uses_explicit_mode_first():
    route = route_agent_task(question="python --version", mode="run_cmd")
    assert route["tool_name"] == "run_cmd"


def test_route_agent_task_detects_windows_path():
    route = route_agent_task(question=r"读取 C:\repo\README.md", mode="agent")
    assert route["tool_name"] == "read_file"


def test_route_agent_task_defaults_to_kb_search():
    route = route_agent_task(question="总结部署流程", mode="agent")
    assert route["tool_name"] == "kb_search"
```

- [ ] **Step 2: 新建 `api/services/agent_router.py`**

```python
from __future__ import annotations

import re


def extract_path_from_text(question: str) -> str | None:
    match = re.search(r"[A-Za-z]:\\[^\s]+", question)
    if match:
        return match.group(0)
    return None


def route_agent_task(question: str, mode: str) -> dict[str, str]:
    normalized_mode = (mode or "agent").strip().lower()
    if normalized_mode == "kb_search":
        return {"tool_name": "kb_search", "reason": "explicit_mode"}
    if normalized_mode == "read_file":
        return {"tool_name": "read_file", "reason": "explicit_mode"}
    if normalized_mode == "run_cmd":
        return {"tool_name": "run_cmd", "reason": "explicit_mode"}
    if extract_path_from_text(question):
        return {"tool_name": "read_file", "reason": "path_detected"}
    if question.strip().lower().startswith("cmd:"):
        return {"tool_name": "run_cmd", "reason": "command_prefix"}
    return {"tool_name": "kb_search", "reason": "default_rule"}
```

- [ ] **Step 3: 新建 `api/services/approval_service.py`，完整定义风险分级、pending 队列、审批状态读取**

```python
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from api.services.tool_receipt_store import append_receipt

CMD_ALLOWLIST = {"dir", "ls", "pwd", "whoami", "python --version"}
HIGH_RISK_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bdel\s+/f\b",
    r"\bformat\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bcurl\b.*\|\s*(bash|sh|powershell)\b",
]

PENDING_ACTIONS: dict[str, dict[str, Any]] = {}
SESSION_ACTIONS: dict[str, list[str]] = defaultdict(list)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_command_risk(command: str) -> str:
    normalized = command.strip().lower()
    for pattern in HIGH_RISK_PATTERNS:
        if re.search(pattern, normalized):
            return "high"
    if normalized in CMD_ALLOWLIST:
        return "low"
    return "medium"


def create_pending_action(session_id: str, command: str, risk_level: str) -> dict[str, Any]:
    action_id = str(uuid4())
    action = {
        "action_id": action_id,
        "session_id": session_id,
        "command": command.strip(),
        "risk_level": risk_level,
        "status": "pending",
        "created_at": now_iso(),
    }
    PENDING_ACTIONS[action_id] = action
    SESSION_ACTIONS[session_id].append(action_id)
    append_receipt(
        session_id=session_id,
        tool_name="run_cmd",
        input_data={"command": command.strip()},
        output_data={"risk_level": risk_level, "message": "waiting for approval"},
        status="pending_approval",
    )
    return action


def get_pending_actions(session_id: str) -> list[dict[str, Any]]:
    action_ids = SESSION_ACTIONS.get(session_id, [])
    return [action for action_id in action_ids if (action := PENDING_ACTIONS.get(action_id)) and action["status"] == "pending"]
```

- [ ] **Step 4: 新建 `api/services/agent_tools.py`，只保留目标态工具接口**

```python
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from api.schemas import QueryRequest
from api.services import chat_service
from api.services.approval_service import CMD_ALLOWLIST
from api.services.tool_receipt_store import append_receipt


def normalize_evidence(sources: list[dict[str, Any]], receipt_id: str | None = None) -> list[dict[str, Any]]:
    evidence = []
    for idx, source in enumerate(sources or [], start=1):
        evidence.append(
            {
                "id": f"ev-{idx}",
                "title": source.get("file") or "Knowledge Source",
                "source": source.get("file") or "N/A",
                "page": source.get("page") or "N/A",
                "score": source.get("score"),
                "excerpt": (source.get("text") or "")[:600],
                "receipt_id": receipt_id,
                "kb_id": "default",
            }
        )
    return evidence


def run_kb_search(session_id: str, question: str) -> dict[str, Any]:
    result = chat_service.query(QueryRequest(question=question, session_id=session_id))
    sources = result.get("sources", [])
    receipt = append_receipt(
        session_id=session_id,
        tool_name="kb_search",
        input_data={"question": question},
        output_data={"answer": result.get("answer", ""), "sources_count": len(sources)},
        status="ok",
    )
    return {"result": result, "receipt": receipt, "evidence": normalize_evidence(sources, receipt["id"])}


def run_read_file(session_id: str, path_text: str) -> dict[str, Any]:
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


def run_cmd(session_id: str, command: str, enforce_allowlist: bool = True) -> dict[str, Any]:
    cmd = command.strip()
    if enforce_allowlist and cmd not in CMD_ALLOWLIST:
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
```

- [ ] **Step 5: 新建 `api/services/timeline_service.py`，让 timeline 完全由后端生成**

```python
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
                    "evidenceIds": step.get("evidence_ids", []),
                },
            }
        )
    timeline.append({"type": "assistant", "content": answer})
    return timeline
```

- [ ] **Step 6: 把 `api/services/agent_runtime.py` 改成真正的总调度器**

```python
from __future__ import annotations

from api.services.agent_router import extract_path_from_text, route_agent_task
from api.services.agent_tools import run_kb_search, run_read_file, run_cmd
from api.services.approval_service import classify_command_risk, create_pending_action, get_pending_actions
from api.services.timeline_service import build_task_state, build_timeline
from api.services.tool_receipt_store import list_receipts


def build_plan(tool_name: str) -> list[dict]:
    if tool_name == "run_cmd":
        return [
            {"id": "plan-risk", "title": "评估命令风险", "status": "pending"},
            {"id": "plan-execute", "title": "执行或提交审批", "status": "pending"},
            {"id": "plan-summarize", "title": "汇总命令结果", "status": "pending"},
        ]
    if tool_name == "read_file":
        return [
            {"id": "plan-read", "title": "读取目标文件", "status": "pending"},
            {"id": "plan-summarize", "title": "提炼文件内容", "status": "pending"},
        ]
    return [
        {"id": "plan-search", "title": "检索知识库证据", "status": "pending"},
        {"id": "plan-answer", "title": "基于证据生成回答", "status": "pending"},
        {"id": "plan-trace", "title": "返回来源和执行回执", "status": "pending"},
    ]


def mark_completed(plan: list[dict], *ids: str) -> None:
    wanted = set(ids)
    for item in plan:
        if item["id"] in wanted:
            item["status"] = "completed"


def run_agent(request) -> dict:
    session_id = request.session_id
    question = request.question.strip()
    route = route_agent_task(question=question, mode=request.mode)
    tool_name = route["tool_name"]
    plan = build_plan(tool_name)
    steps = []
    evidence = []
    answer = ""
    status = "completed"

    if tool_name == "read_file":
        path = extract_path_from_text(question) or question
        output = run_read_file(session_id, path)
        mark_completed(plan, "plan-read", "plan-summarize")
        steps.append(
            {
                "step": "read_file",
                "title": "读取本地文件",
                "status": "completed",
                "risk_level": "low",
                "receipt_id": output["receipt"]["id"],
                "summary": f"读取 {output['result']['path']}",
            }
        )
        answer = f"已读取文件：{output['result']['path']}\\n\\n{output['result']['excerpt']}"
    elif tool_name == "run_cmd":
        command = question
        risk_level = classify_command_risk(command)
        if risk_level == "low":
            output = run_cmd(session_id, command)
            mark_completed(plan, "plan-risk", "plan-execute", "plan-summarize")
            steps.append(
                {
                    "step": "run_cmd",
                    "title": "执行低风险命令",
                    "status": "completed",
                    "risk_level": risk_level,
                    "receipt_id": output["receipt"]["id"],
                    "summary": command,
                }
            )
            answer = output["result"]["output"] or "命令执行完成。"
        else:
            pending_action = create_pending_action(session_id, command, risk_level)
            mark_completed(plan, "plan-risk")
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
            answer = f"命令风险等级 `{risk_level}`，已进入审批队列，请确认后再执行。"
            status = "waiting_approval"
    else:
        output = run_kb_search(session_id, question)
        evidence = output["evidence"]
        mark_completed(plan, "plan-search", "plan-answer", "plan-trace")
        steps.append(
            {
                "step": "kb_search",
                "title": "检索知识库",
                "status": "completed",
                "risk_level": "low",
                "receipt_id": output["receipt"]["id"],
                "evidence_ids": [item["id"] for item in evidence],
                "summary": f"命中 {len(evidence)} 条证据",
            }
        )
        answer = output["result"].get("answer") or "知识库已检索，但未返回有效答案。"

    pending_actions = get_pending_actions(session_id)
    return {
        "session_id": session_id,
        "question": question,
        "knowledge_scope": request.knowledge_scope.model_dump(),
        "answer": answer,
        "task_state": build_task_state(status, pending_actions),
        "plan": plan,
        "steps": steps,
        "timeline": build_timeline(question, answer, steps),
        "evidence": evidence,
        "receipts": list_receipts(session_id=session_id, limit=20),
        "pending_actions": pending_actions,
    }
```

- [ ] **Step 7: 将 `api/services/agent_service.py` 改成最终薄入口，不复制旧逻辑**

```python
from __future__ import annotations

from api.services.agent_runtime import run_agent
from api.services.approval_service import get_pending_actions
from api.services.tool_receipt_store import list_receipts


def run_agent_service(request):
    return run_agent(request)


def get_agent_receipts(session_id: str, limit: int = 50):
    return list_receipts(session_id=session_id, limit=limit)


def get_pending_actions_service(session_id: str):
    return get_pending_actions(session_id)
```

- [ ] **Step 8: 为新 runtime 写测试**

```python
from types import SimpleNamespace

from api.services.agent_runtime import run_agent


def test_runtime_generates_timeline_for_kb_search(monkeypatch):
    monkeypatch.setattr(
        "api.services.agent_runtime.run_kb_search",
        lambda session_id, question: {
            "result": {"answer": "ok"},
            "receipt": {"id": "r1"},
            "evidence": [],
        },
    )
    monkeypatch.setattr(
        "api.services.agent_runtime.list_receipts",
        lambda session_id, limit: [],
    )
    monkeypatch.setattr(
        "api.services.agent_runtime.get_pending_actions",
        lambda session_id: [],
    )

    request = SimpleNamespace(
        question="总结部署流程",
        session_id="default",
        mode="agent",
        knowledge_scope=SimpleNamespace(model_dump=lambda: {"kb_id": "default", "kb_name": "Default KB"}),
    )
    result = run_agent(request)
    assert result["answer"] == "ok"
    assert len(result["timeline"]) == 3
    assert result["steps"][0]["step"] == "kb_search"
```

- [ ] **Step 9: 运行 runtime 测试**

Run:

```powershell
pytest tests/api/test_agent_runtime.py -q
```

Expected:
- 测试通过

- [ ] **Step 10: Commit**

```bash
git add api/services/agent_runtime.py api/services/agent_router.py api/services/agent_tools.py api/services/approval_service.py api/services/timeline_service.py api/services/agent_service.py tests/api/test_agent_runtime.py
git commit -m "refactor: rebuild agent runtime for target-state architecture"
```

## Task 3: 重建前端首页与工作台组件

**Files:**
- Create: `webapp/src/pages/AgentPage.jsx`
- Create: `webapp/src/components/agent/AgentInputPanel.jsx`
- Create: `webapp/src/components/agent/AgentTaskStateBar.jsx`
- Create: `webapp/src/components/agent/AgentTimeline.jsx`
- Create: `webapp/src/components/agent/AgentEvidencePanel.jsx`
- Create: `webapp/src/components/agent/AgentApprovalPanel.jsx`
- Create: `webapp/src/components/agent/AgentReceiptsPanel.jsx`
- Modify: `webapp/src/store/appStore.js`
- Modify: `webapp/src/store/agentState.js`
- Modify: `webapp/src/api/agent.js`
- Test: `webapp/src/store/agentState.test.js`

- [ ] **Step 1: 为前端映射逻辑写测试，要求直接使用后端 timeline**

```javascript
import { mapAgentRunToTimeline } from "./agentState";

test("mapAgentRunToTimeline returns backend timeline when available", () => {
  const timeline = mapAgentRunToTimeline("hello", {
    timeline: [
      { type: "user", content: "hello" },
      { type: "step", content: "执行工具" },
      { type: "assistant", content: "ok" }
    ]
  });
  expect(timeline).toHaveLength(3);
  expect(timeline[1].content).toBe("执行工具");
});
```

- [ ] **Step 2: 修改 `webapp/src/store/agentState.js`，优先消费后端 timeline**

```javascript
export function mapAgentRunToTimeline(question, runData) {
  if (Array.isArray(runData?.timeline) && runData.timeline.length > 0) {
    return runData.timeline;
  }

  return [
    { type: "user", content: question },
    { type: "assistant", content: runData?.answer || "" }
  ];
}
```

- [ ] **Step 3: 修改 `webapp/src/store/appStore.js`，补齐目标态工作台状态和 action**

```javascript
const useAppStore = create((set) => ({
  sessionId: "desktop-default",
  taskGoal: "",
  runState: "idle",
  currentMode: "agent",
  timeline: [],
  plan: [],
  evidence: [],
  receipts: [],
  taskState: null,
  pendingActions: [],
  approvalMessage: "",
  setRunState: (runState) => set({ runState }),
  setCurrentMode: (currentMode) => set({ currentMode }),
  setPlan: (plan) => set({ plan }),
  setEvidence: (evidence) => set({ evidence }),
  setReceipts: (receipts) => set({ receipts }),
  setTaskState: (taskState) => set({ taskState }),
  setPendingActions: (pendingActions) => set({ pendingActions }),
  setApprovalMessage: (approvalMessage) => set({ approvalMessage }),
  hydrateFromAgentRun: (runData) =>
    set({
      timeline: runData?.timeline || [],
      plan: runData?.plan || [],
      evidence: runData?.evidence || [],
      receipts: runData?.receipts || [],
      taskState: runData?.task_state || null,
      pendingActions: runData?.pending_actions || []
    })
}));
```

- [ ] **Step 4: 创建 `AgentInputPanel.jsx`**

```jsx
export default function AgentInputPanel({
  question,
  setQuestion,
  mode,
  setMode,
  isPending,
  onSubmit
}) {
  return (
    <form onSubmit={onSubmit} className="query-form">
      <select value={mode} onChange={(e) => setMode(e.target.value)}>
        <option value="agent">Agent</option>
        <option value="kb_search">KB Search</option>
        <option value="read_file">Read File</option>
        <option value="run_cmd">Run Command</option>
      </select>
      <input
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="描述你的任务、路径或命令..."
      />
      <button type="submit" disabled={isPending}>
        {isPending ? "Running..." : "Run Task"}
      </button>
    </form>
  );
}
```

- [ ] **Step 5: 创建 `AgentTaskStateBar.jsx`、`AgentTimeline.jsx`、`AgentEvidencePanel.jsx`、`AgentReceiptsPanel.jsx`**

```jsx
export function AgentTaskStateBar({ taskState, sessionId }) {
  return (
    <div className="workspace-meta">
      Session: {sessionId} | 状态: <strong>{taskState?.status || "idle"}</strong> | 待审批:{" "}
      <strong>{taskState?.pending_approval_count || 0}</strong>
    </div>
  );
}
```

```jsx
export function AgentTimeline({ timeline }) {
  if (!timeline.length) return <p>暂无执行事件</p>;
  return timeline.map((item, idx) => (
    <div key={`${item.type}-${idx}`} className={`message ${item.type}`}>
      <div className="role">{item.type}</div>
      <div>{item.content}</div>
    </div>
  ));
}
```

```jsx
export function AgentEvidencePanel({ evidence }) {
  if (!evidence.length) return <p>暂无证据</p>;
  return evidence.map((item) => (
    <div key={item.id} className="evidence-item">
      <div><strong>{item.title}</strong> / {item.kb_id}</div>
      <div>{item.source}</div>
      <p>{item.excerpt}</p>
    </div>
  ));
}
```

```jsx
export function AgentReceiptsPanel({ receipts }) {
  if (!receipts.length) return <p>暂无回执</p>;
  return receipts.map((receipt) => (
    <div key={receipt.id} className="receipt-item">
      <div><strong>{receipt.tool_name}</strong> / {receipt.status}</div>
      <pre>{JSON.stringify(receipt.output_data || receipt.output || {}, null, 2)}</pre>
    </div>
  ));
}
```

- [ ] **Step 6: 单独实现 `AgentApprovalPanel.jsx`，确保审批闭环是独立组件**

```jsx
export default function AgentApprovalPanel({
  pendingActions,
  approvalPending,
  onApprove,
  onReject
}) {
  if (!pendingActions.length) return <p>暂无待审批命令</p>;

  return (
    <>
      {pendingActions.map((action) => (
        <div key={action.action_id} className="pending-action">
          <div><strong>{action.command}</strong></div>
          <div>风险等级：{action.risk_level}</div>
          <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
            <button disabled={approvalPending} onClick={() => onApprove(action)}>批准</button>
            <button disabled={approvalPending} onClick={() => onReject(action)}>拒绝</button>
          </div>
        </div>
      ))}
    </>
  );
}
```

- [ ] **Step 7: 创建新的 `webapp/src/pages/AgentPage.jsx`，完整组合输入、时间线、证据、审批、回执**

```jsx
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { approveAgentAction, getAgentReceipts, getPendingActions, runAgent } from "../api/agent";
import useAppStore from "../store/appStore";
import AgentInputPanel from "../components/agent/AgentInputPanel";
import { AgentTaskStateBar } from "../components/agent/AgentTaskStateBar";
import { AgentTimeline } from "../components/agent/AgentTimeline";
import { AgentEvidencePanel } from "../components/agent/AgentEvidencePanel";
import AgentApprovalPanel from "../components/agent/AgentApprovalPanel";
import { AgentReceiptsPanel } from "../components/agent/AgentReceiptsPanel";

export default function AgentPage() {
  const sessionId = useAppStore((s) => s.sessionId);
  const timeline = useAppStore((s) => s.timeline);
  const plan = useAppStore((s) => s.plan);
  const evidence = useAppStore((s) => s.evidence);
  const receipts = useAppStore((s) => s.receipts);
  const taskState = useAppStore((s) => s.taskState);
  const pendingActions = useAppStore((s) => s.pendingActions);
  const setRunState = useAppStore((s) => s.setRunState);
  const setCurrentMode = useAppStore((s) => s.setCurrentMode);
  const hydrateFromAgentRun = useAppStore((s) => s.hydrateFromAgentRun);
  const setReceipts = useAppStore((s) => s.setReceipts);
  const setPendingActions = useAppStore((s) => s.setPendingActions);
  const setApprovalMessage = useAppStore((s) => s.setApprovalMessage);

  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState("agent");

  const agentMutation = useMutation({
    mutationFn: (payload) => runAgent(payload),
    onSuccess: (res) => {
      const data = res.data;
      hydrateFromAgentRun(data);
      setRunState(data.task_state?.status || "completed");
      setQuestion("");
    },
    onError: () => setRunState("failed")
  });

  const approvalMutation = useMutation({
    mutationFn: (payload) => approveAgentAction(payload),
    onSuccess: async () => {
      const receiptsRes = await getAgentReceipts(sessionId, 20);
      const pendingRes = await getPendingActions(sessionId);
      setReceipts(receiptsRes.data.receipts || []);
      setPendingActions(pendingRes.data.pending_actions || []);
      setApprovalMessage("审批已提交");
      setRunState((pendingRes.data.pending_actions || []).length > 0 ? "waiting_approval" : "completed");
    }
  });

  const onSubmit = (event) => {
    event.preventDefault();
    if (!question.trim()) return;
    setCurrentMode(mode);
    setRunState("running");
    agentMutation.mutate({
      question,
      session_id: sessionId,
      mode,
      knowledge_scope: { kb_id: "default", kb_name: "Default KB" }
    });
  };

  return (
    <section className="workspace-page">
      <header className="workspace-header">
        <div>
          <h2>Agent Workspace</h2>
          <AgentTaskStateBar taskState={taskState} sessionId={sessionId} />
        </div>
      </header>
      <AgentInputPanel
        question={question}
        setQuestion={setQuestion}
        mode={mode}
        setMode={setMode}
        isPending={agentMutation.isPending}
        onSubmit={onSubmit}
      />
      <div className="workspace-layout">
        <div className="workspace-timeline">
          <h3>执行时间线</h3>
          <AgentTimeline timeline={timeline} />
        </div>
        <aside className="receipt-panel">
          <div className="context-block">
            <h4>执行计划</h4>
            {plan.map((item) => (
              <div key={item.id} className={`plan-item ${item.status}`}>
                <span>{item.title}</span>
                <strong>{item.status}</strong>
              </div>
            ))}
          </div>
          <div className="context-block">
            <h4>知识证据</h4>
            <AgentEvidencePanel evidence={evidence} />
          </div>
          <div className="context-block">
            <h4>待审批命令</h4>
            <AgentApprovalPanel
              pendingActions={pendingActions}
              approvalPending={approvalMutation.isPending}
              onApprove={(action) =>
                approvalMutation.mutate({
                  action_id: action.action_id,
                  approve: true,
                  reason: "desktop-user approved",
                  approver: "desktop-user"
                })
              }
              onReject={(action) =>
                approvalMutation.mutate({
                  action_id: action.action_id,
                  approve: false,
                  reason: "desktop-user rejected",
                  approver: "desktop-user"
                })
              }
            />
          </div>
          <div className="context-block">
            <h4>工具回执</h4>
            <AgentReceiptsPanel receipts={receipts} />
          </div>
        </aside>
      </div>
    </section>
  );
}
```

- [ ] **Step 8: 运行前端测试**

Run:

```powershell
cd webapp
npm test -- --runInBand
```

Expected:
- `agentState` 测试通过

- [ ] **Step 9: 前端 build 验证**

Run:

```powershell
cd webapp
npm run build
```

Expected:
- 构建成功

- [ ] **Step 10: Commit**

```bash
git add webapp/src/pages/AgentPage.jsx webapp/src/components/agent webapp/src/store/appStore.js webapp/src/store/agentState.js webapp/src/store/agentState.test.js webapp/src/api/agent.js
git commit -m "feat: build target-state agent workspace ui"
```

## Task 4: 最后切主入口并处理旧页面

**Files:**
- Modify: `webapp/src/App.jsx`
- Modify: `webapp/src/components/ShellLayout.jsx`
- Modify: `webapp/src/pages/QueryPage.jsx`

- [ ] **Step 1: 修改 `webapp/src/App.jsx`，将首页切到 `AgentPage`**

```jsx
import { Navigate, Route, Routes } from "react-router-dom";
import ShellLayout from "./components/ShellLayout";
import AgentPage from "./pages/AgentPage";
import QueryPage from "./pages/QueryPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<ShellLayout />}>
        <Route index element={<AgentPage />} />
        <Route path="query" element={<QueryPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
```

- [ ] **Step 2: 修改 `QueryPage.jsx`，将其降级为旧入口说明页或最小兼容页**

```jsx
export default function QueryPage() {
  return (
    <section className="workspace-page">
      <header className="workspace-header">
        <div>
          <h2>Legacy Query</h2>
          <p className="workspace-meta">首页已切换到 Agent Workspace，这个页面仅保留兼容入口。</p>
        </div>
      </header>
    </section>
  );
}
```

- [ ] **Step 3: 修改 `ShellLayout.jsx`，导航上突出 Agent 首页**

```jsx
const navItems = [
  { to: "/", label: "Agent" },
  { to: "/query", label: "Legacy Query" },
  { to: "/kb-file", label: "KB File" },
  { to: "/kb-web", label: "KB Web" },
  { to: "/kb-manage", label: "KB Manage" }
];
```

- [ ] **Step 4: 前端 build 再次验证首页切换**

Run:

```powershell
cd webapp
npm run build
```

Expected:
- 首页路由切换后构建成功

- [ ] **Step 5: Commit**

```bash
git add webapp/src/App.jsx webapp/src/components/ShellLayout.jsx webapp/src/pages/QueryPage.jsx
git commit -m "feat: switch desktop home to agent workspace"
```

## Task 5: 按真实桌面链路联调并完成验收

**Files:**
- Modify: `docs/desktop_regression_checklist.md`
- Verify: `desktop/src/python-process.js`
- Verify: `desktop/src/main.js`

- [ ] **Step 1: 确认桌面健康检查端口与实际链路一致**

Run:

```powershell
Get-Content desktop\src\python-process.js -TotalCount 200
```

Expected:
- 明确看到健康检查地址使用 `http://127.0.0.1:18080/api/health`

- [ ] **Step 2: 更新 `docs/desktop_regression_checklist.md`，加入 Agent MVP 验收项**

```markdown
- 启动桌面端后默认进入 Agent Workspace
- Agent 模式可以正常运行
- KB Search 模式可以返回 evidence
- Read File 模式可以返回 excerpt
- Run Command 低风险命令可直接执行
- Run Command 高风险命令进入审批
- 批准后 receipts 刷新
- 拒绝后 pending_actions 减少
- timeline 能展示 user / step / assistant
```

- [ ] **Step 3: 按桌面真实链路启动本地 API**

Run:

```powershell
Get-Content scripts\desktop-dev.ps1 -TotalCount 240
```

Then run the documented desktop dev command so the app uses the same port and startup chain as Electron expects.

Expected:
- API 按桌面链路启动
- 健康检查命中 `127.0.0.1:18080/api/health`

- [ ] **Step 4: 启动桌面应用进行手工联调**

Run:

```powershell
cd desktop
npm run dev
```

Expected:
- Electron 成功拉起
- 首页显示 Agent Workspace

- [ ] **Step 5: 手工验证四种模式**

Run these scenarios:

```text
mode=agent, question="总结知识库中的部署流程"
mode=kb_search, question="部署流程"
mode=read_file, question="C:\\repo\\README.md"
mode=run_cmd, question="python --version"
mode=run_cmd, question="shutdown /r /t 0"
```

Expected:
- `agent` 返回 answer / timeline / receipts
- `kb_search` 返回 evidence
- `read_file` 返回 excerpt
- 低风险命令直接执行
- 高风险命令进入审批

- [ ] **Step 6: 单独验证审批闭环**

Run this approval flow:

```text
1. 用 run_cmd 模式提交高风险命令
2. 页面出现待审批命令
3. 点击批准
4. receipts 刷新
5. pending_actions 更新
6. task_state 更新
7. timeline 追加审批后的执行结果
```

Expected:
- 审批展示、批准/拒绝、receipt 刷新、timeline 更新都在同一页面内完成

- [ ] **Step 7: Commit**

```bash
git add docs/desktop_regression_checklist.md
git commit -m "test: validate desktop knowledge agent mvp end-to-end"
```

## Self-Review

- [ ] plan 已改成目标态重建，不再以兼容旧 `mode="auto"` 为前提
- [ ] 执行顺序是“先建新 runtime 和新页面，再最后切入口”
- [ ] 审批闭环被单独列成组件和验收项
- [ ] 联调端口和桌面真实链路保持一致
- [ ] plan 中没有使用 TBD、TODO、后续再补 等占位词

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-28-desktop-knowledge-agent-mvp.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
