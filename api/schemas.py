"""API 请求/响应模型定义。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """问答请求。"""

    question: str = Field(..., min_length=1)
    session_id: str = Field(default="default")
    top_k: int | None = None
    response_mode: str | None = None
    use_reranker: bool | None = None
    top_n: int | None = None
    reranker_model: str | None = None


class UrlImportRequest(BaseModel):
    """网页导入请求。"""

    urls: list[str]
    chunk_size: int = 2048
    chunk_overlap: int = 512


class DeleteDocsRequest(BaseModel):
    """删除知识库文档请求。"""

    doc_ids: list[str] = Field(default_factory=list)
    paths: list[str] = Field(default_factory=list)


class SettingsUpdateRequest(BaseModel):
    """设置更新请求。"""

    temperature: float | None = None
    system_prompt: str | None = None
    top_k: int | None = None
    response_mode: str | None = None
    use_reranker: bool | None = None
    top_n: int | None = None
    embedding_model: str | None = None
    reranker_model: str | None = None


class ModelSelectRequest(BaseModel):
    """模型选择请求。"""

    service_provider: str
    model: str
    api_base: str | None = None
    api_key: str | None = None
    api_key_valid: bool | None = None


class CustomProviderCreateRequest(BaseModel):
    """自定义 Provider 创建请求。"""

    name: str = Field(..., min_length=1)
    api_base: str = Field(..., min_length=1)
    models: list[str] = Field(default_factory=list)
    api_key: str = ""


class CustomProviderConnectionTestRequest(BaseModel):
    """自定义 Provider 连通性测试请求。"""

    api_base: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)


class ApiEnvelope(BaseModel):
    """统一响应结构。"""

    code: int
    message: str
    data: Any = {}
    request_id: str


class KnowledgeScope(BaseModel):
    """知识范围。"""

    kb_id: str = Field(default="default")
    kb_name: str = Field(default="Default KB")


class AgentRunRequest(BaseModel):
    """Agent 执行请求。"""

    question: str = Field(..., min_length=1)
    session_id: str = Field(default="default")
    mode: Literal["agent", "kb_search", "read_file", "run_cmd"] = "agent"
    tool_hint: str | None = None
    knowledge_scope: KnowledgeScope = Field(default_factory=KnowledgeScope)


class AgentReceiptQuery(BaseModel):
    """Agent 回执查询参数。"""

    session_id: str = Field(default="default")
    limit: int = Field(default=50, ge=1, le=500)


class AgentApprovalRequest(BaseModel):
    """Agent 命令审批请求。"""

    action_id: str = Field(..., min_length=1)
    approve: bool
    reason: str = ""
    approver: str = "local-user"


class TaskState(BaseModel):
    """任务状态摘要。"""

    status: Literal["idle", "running", "completed", "waiting_approval", "failed"]
    pending_approval_count: int = 0
    updated_at: str


class PlanItem(BaseModel):
    """计划项。"""

    id: str
    title: str
    status: Literal["pending", "completed", "waiting_approval", "failed"]


class StepItem(BaseModel):
    """步骤项。"""

    step: str
    title: str
    status: Literal["pending", "completed", "waiting_approval", "failed"]
    risk_level: Literal["low", "medium", "high"] | None = None
    receipt_id: str | None = None
    action_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    summary: str = ""


class TimelineItem(BaseModel):
    """时间线项。"""

    type: str
    content: str
    meta: dict[str, Any] | None = None


class EvidenceItem(BaseModel):
    """证据项。"""

    id: str
    title: str
    source: str
    page: str | None = None
    score: float | None = None
    excerpt: str = ""
    receipt_id: str | None = None
    kb_id: str = "default"


class PendingActionItem(BaseModel):
    """待审批动作。"""

    action_id: str
    session_id: str
    command: str
    risk_level: Literal["low", "medium", "high"]
    status: str
    created_at: str


class AgentRunData(BaseModel):
    """Agent 运行结果。"""

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
