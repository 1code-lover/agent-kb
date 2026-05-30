"""API request and response models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: str = Field(default="default")
    top_k: int | None = None
    response_mode: str | None = None
    use_reranker: bool | None = None
    top_n: int | None = None
    reranker_model: str | None = None


class UrlImportRequest(BaseModel):
    urls: list[str]
    chunk_size: int = 2048
    chunk_overlap: int = 512


class DeleteDocsRequest(BaseModel):
    doc_ids: list[str] = Field(default_factory=list)
    paths: list[str] = Field(default_factory=list)


class SettingsUpdateRequest(BaseModel):
    temperature: float | None = None
    system_prompt: str | None = None
    top_k: int | None = None
    response_mode: str | None = None
    use_reranker: bool | None = None
    top_n: int | None = None
    embedding_model: str | None = None
    reranker_model: str | None = None


class ModelSelectRequest(BaseModel):
    service_provider: str
    model: str
    api_base: str | None = None
    api_key: str | None = None
    api_key_valid: bool | None = None
    session_id: str = Field(default="desktop-default")


class CustomProviderCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    api_base: str = Field(..., min_length=1)
    models: list[str] = Field(default_factory=list)
    api_key: str = ""


class CustomProviderConnectionTestRequest(BaseModel):
    api_base: str = Field(..., min_length=1)
    api_key: str = ""
    provider_name: str | None = None
    model: str = Field(..., min_length=1)


class ProviderConfigExport(BaseModel):
    custom_llm_providers: list[CustomProviderCreateRequest] = Field(default_factory=list)
    current_llm_info: ModelSelectRequest | None = None


class ProviderConfigImportRequest(BaseModel):
    mode: Literal["replace", "merge"] = "replace"
    custom_llm_providers: list[CustomProviderCreateRequest] = Field(default_factory=list)
    current_llm_info: ModelSelectRequest | None = None


class ApiEnvelope(BaseModel):
    code: int
    message: str
    data: Any = {}
    request_id: str


class KnowledgeScope(BaseModel):
    kb_id: str = Field(default="default")
    kb_name: str = Field(default="NorthAgent Workspace")


class AgentProviderSnapshot(BaseModel):
    name: str = ""
    base_url: str = ""
    model: str = ""


class FileAttachmentItem(BaseModel):
    id: str
    name: str
    path: str = ""
    source: Literal["desktop_pick", "upload_import"] = "desktop_pick"
    status: Literal["selected", "imported"] = "selected"
    size: int | None = None
    content_type: str | None = None


class AgentWorkspaceSnapshot(BaseModel):
    current_mode: Literal["agent", "kb_search", "read_file", "run_cmd"] = "agent"
    provider: AgentProviderSnapshot = Field(default_factory=AgentProviderSnapshot)
    knowledge_scope: KnowledgeScope = Field(default_factory=KnowledgeScope)
    task_goal: str = ""
    draft_question: str = ""
    run_state: Literal["idle", "running", "completed", "waiting_approval", "failed"] = "idle"
    last_answer: str = ""
    attached_files: list[FileAttachmentItem] = Field(default_factory=list)
    enabled_skills: list[str] = Field(default_factory=list)


class AgentSessionUiState(BaseModel):
    active_detail: str = "receipts"
    show_details: bool = False


class ChatMessageItem(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: str


class AgentRunRequest(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: str = Field(default="default")
    mode: Literal["agent", "kb_search", "read_file", "run_cmd"] = "agent"
    tool_hint: str | None = None
    knowledge_scope: KnowledgeScope = Field(default_factory=KnowledgeScope)


class AgentReceiptQuery(BaseModel):
    session_id: str = Field(default="default")
    limit: int = Field(default=50, ge=1, le=500)


class AgentApprovalRequest(BaseModel):
    action_id: str = Field(..., min_length=1)
    approve: bool
    reason: str = ""
    approver: str = "local-user"


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
    review_reason: str = ""
    reviewed_by: str = ""


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


class AgentSessionSnapshot(BaseModel):
    version: int = 1
    session_id: str
    updated_at: str
    workspace: AgentWorkspaceSnapshot = Field(default_factory=AgentWorkspaceSnapshot)
    chat_history: list[ChatMessageItem] = Field(default_factory=list)
    timeline: list[TimelineItem] = Field(default_factory=list)
    plan: list[PlanItem] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    receipts: list[dict[str, Any]] = Field(default_factory=list)
    pending_actions: list[PendingActionItem] = Field(default_factory=list)
    task_state: TaskState | None = None
    approval_message: str = ""
    ui_state: AgentSessionUiState = Field(default_factory=AgentSessionUiState)


class AgentSessionUpdateRequest(BaseModel):
    session_id: str = Field(default="desktop-default")
    workspace: dict[str, Any] = Field(default_factory=dict)
    ui_state: dict[str, Any] = Field(default_factory=dict)
    timeline: list[dict[str, Any]] | None = None
    plan: list[dict[str, Any]] | None = None
    evidence: list[dict[str, Any]] | None = None
    receipts: list[dict[str, Any]] | None = None
    pending_actions: list[dict[str, Any]] | None = None
    task_state: dict[str, Any] | None = None
    approval_message: str | None = None


class AgentSessionResetRequest(BaseModel):
    session_id: str = Field(default="desktop-default")

