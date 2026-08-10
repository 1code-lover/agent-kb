import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useLocation, useNavigate } from "../router";
import AgentApprovalPanel from "../components/agent/AgentApprovalPanel";
import AgentEvidencePanel from "../components/agent/AgentEvidencePanel";
import AgentInputPanel from "../components/agent/AgentInputPanel";
import AgentReceiptsPanel from "../components/agent/AgentReceiptsPanel";
import AgentTimeline from "../components/agent/AgentTimeline";
import {
  approveAgentAction,
  getAgentReceipts,
  getAgentSession,
  getAgentSkills,
  getPendingActions,
  runAgent,
  updateAgentSession,
  uploadFilesToKnowledge,
} from "../api/agent";
import { getHistory, queryChat } from "../api/chat";
import { previewItem } from "../api/evidence";
import { getModelOptions, selectModel } from "../api/models";
import { readApiData } from "../api/response";
import { KbProvider, useKb } from "../components/kb/KbContext";
import { canUseKbTarget } from "../domain/kbSelection";
import {
  buildKnowledgeAgentLink,
  buildKnowledgeWorkspaceLink,
  parseKnowledgeAgentEntry,
} from "../domain/kbNavigation";
import KbEvidencePreview from "../components/kb/KbEvidencePreview";
import {
  AGENT_EXPERIENCES,
  buildChatPayload,
  buildChatSessionId,
  buildExperienceSummary,
} from "../domain/agentExperience";
import { buildModelHealthSummary } from "../domain/modelHealth";
import useAppStore from "../store/appStore";
import "./agent-page.css";

const DEFAULT_KNOWLEDGE_SCOPE = {
  kb_id: "default",
  kb_name: "默认知识库",
};

function safeBuildChatSessionId({ experience, sessionId, selectedKbId }) {
  try {
    return buildChatSessionId({ experience, sessionId, selectedKbId });
  } catch {
    return "";
  }
}

function createAttachmentFromPath(path, index = 0) {
  const normalizedPath = path || "";
  const name = normalizedPath.split(/[/\\]/).pop() || normalizedPath;
  return {
    id: "local-" + Date.now() + "-" + index,
    name,
    path: normalizedPath,
    source: "desktop_pick",
    status: "selected",
  };
}

function createAttachmentFromImportedFile(file, index = 0) {
  return {
    id: "import-" + Date.now() + "-" + index,
    name: file.name,
    path: file.path || "",
    source: "upload_import",
    status: "imported",
    size: file.size,
    content_type: file.type,
  };
}

function mergeAttachments(existingFiles, nextFiles) {
  const merged = [...(existingFiles || [])];
  for (const nextFile of nextFiles || []) {
    const exists = merged.some(
      (item) => item.path && nextFile.path && item.path === nextFile.path,
    );
    if (!exists) {
      merged.push(nextFile);
    }
  }
  return merged;
}

function formatMessageTime(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatScore(score) {
  return typeof score === "number" ? score.toFixed(3) : "-";
}

function ExperienceTabs({ experience, onChange }) {
  return (
    <div className="qa-experience-switcher" role="tablist" aria-label="问答体验切换">
      {AGENT_EXPERIENCES.map((item) => (
        <button
          key={item.value}
          type="button"
          role="tab"
          aria-selected={experience === item.value}
          className={
            experience === item.value
              ? "qa-experience-tab active"
              : "qa-experience-tab"
          }
          onClick={() => onChange(item.value)}
        >
          <span className="qa-experience-tab-title">{item.label}</span>
          <span className="qa-experience-tab-desc">{item.description}</span>
        </button>
      ))}
    </div>
  );
}

function QaConversation({ messages, pendingQuestion, historyLoading, chatBusy }) {
  const hasMessages = (messages || []).length > 0;

  return (
    <section className="qa-surface-card qa-conversation-card">
      <div className="qa-section-head">
        <div>
          <p className="qa-section-eyebrow">会话记录</p>
          <h2>问答线程</h2>
        </div>
        {historyLoading ? <span className="toolbar-pill subtle">正在同步历史…</span> : null}
      </div>

      <div className="qa-conversation-thread">
        {!hasMessages && !pendingQuestion ? (
          <div className="empty-block">还没有对话记录，先输入一个问题试试。</div>
        ) : null}

        {(messages || []).map((item, index) => {
          const role = item.role === "user" ? "user" : "assistant";
          return (
            <article
              key={item.id || role + "-" + index}
              className={
                role === "user"
                  ? "qa-message-row qa-message-row-user"
                  : "qa-message-row qa-message-row-assistant"
              }
            >
              <div className={role === "user" ? "qa-message qa-message-user" : "qa-message qa-message-assistant"}>
                <div className="qa-message-meta">
                  <span>{role === "user" ? "你" : "助手"}</span>
                  <span>{formatMessageTime(item.created_at)}</span>
                </div>
                <div className="qa-message-body">{item.content}</div>
              </div>
            </article>
          );
        })}

        {pendingQuestion ? (
          <>
            <article className="qa-message-row qa-message-row-user">
              <div className="qa-message qa-message-user pending">
                <div className="qa-message-meta">
                  <span>你</span>
                  <span>刚刚</span>
                </div>
                <div className="qa-message-body">{pendingQuestion}</div>
              </div>
            </article>
            <article className="qa-message-row qa-message-row-assistant">
              <div className="qa-message qa-message-assistant pending">
                <div className="qa-message-meta">
                  <span>助手</span>
                  <span>{chatBusy ? "生成中" : "排队中"}</span>
                </div>
                <div className="qa-message-body">正在检索并组织回答，请稍候…</div>
              </div>
            </article>
          </>
        ) : null}
      </div>
    </section>
  );
}

function SourceList({
  sources,
  evidence,
  onPreview,
  preview,
  previewLoading,
  previewError,
}) {
  const items =
    evidence.length > 0
      ? evidence
      : sources.map((item, index) => ({
          id: item.id || (item.file || "source") + "-" + index,
          title: item.file || "未命名来源",
          source: item.file || "未命名来源",
          page: item.page,
          score: item.score,
          excerpt: item.excerpt || item.text || "",
          kb_id: item.kb_id || "default",
          doc_id: item.doc_id || null,
          preview_locator: item.preview_locator || null,
          asset_id: item.asset_id || null,
        }));

  return (
    <section className="qa-surface-card qa-source-card">
      <div className="qa-section-head">
        <div>
          <p className="qa-section-eyebrow">证据</p>
          <h2>命中来源</h2>
        </div>
        <span className="toolbar-pill subtle">{items.length} 条</span>
      </div>

      {items.length === 0 ? (
        <div className="empty-block">
          当前还没有可展示的证据；发送问题后，命中的文档片段会出现在这里。
        </div>
      ) : (
        <div className="qa-source-list">
          {items.map((item, index) => (
            <article key={(item.id || item.title || "source") + "-" + index} className="qa-source-item">
              <div className="qa-source-title-row">
                <strong>{item.title || item.source || "未命名来源"}</strong>
                <span>{"score " + formatScore(item.score)}</span>
              </div>
              <p className="stack-subtle">
                {"kb_id=" + (item.kb_id || "default")}
                {item.page && item.page !== "N/A" ? " / 页码 " + item.page : ""}
              </p>
              {item.asset_id ? <p className="stack-subtle">{"关联资产：" + item.asset_id}</p> : null}
              <p className="qa-source-excerpt">{item.excerpt || "未返回摘录"}</p>
              {item.asset_id || item.doc_id || item.id ? (
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => onPreview(item)}
                  disabled={previewLoading}
                >
                  {previewLoading ? "加载中" : "预览"}
                </button>
              ) : null}
            </article>
          ))}
        </div>
      )}

      <KbEvidencePreview
        preview={preview}
        loading={previewLoading}
        error={previewError}
      />
    </section>
  );
}


function KnowledgeScopeSelector({ selectedKbId, selectedKb, kbList, kbLoading, onSelectKb }) {
  return (
    <section className="qa-surface-card qa-kb-target-card">
      <div className="qa-section-head">
        <div>
          <p className="qa-section-eyebrow">知识库范围</p>
          <h2>选择问答目标</h2>
        </div>
      </div>

      <div className="qa-kb-bar">
        <label className="qa-field-label" htmlFor="knowledge-kb-select">
          Active 知识库
        </label>
        <select
          id="knowledge-kb-select"
          className="qa-select"
          value={selectedKbId || ""}
          disabled={kbLoading}
          onChange={(event) => onSelectKb(event.target.value)}
        >
          <option value="">请选择知识库</option>
          {kbList.map((kb) => (
            <option key={kb.kb_id} value={kb.kb_id}>
              {(kb.kb_name || kb.kb_id) + "（" + kb.kb_id + "）"}
            </option>
          ))}
        </select>
      </div>

      <div className="qa-inline-tip">
        {selectedKb
          ? "当前问答将严格限定在“" + (selectedKb.kb_name || selectedKb.kb_id) + "”（kb_id=" + selectedKb.kb_id + "）范围内。"
          : "知识库问答必须先显式选择一个 active 知识库，避免误用默认库。"}
      </div>
    </section>
  );
}

function QaWorkbench(props) {
  const {
    experience,
    selectedKb,
    selectedKbId,
    kbList,
    kbLoading,
    onSelectKb,
    currentModelLabel,
    modelHealthSummary,
    modelReady,
    question,
    onQuestionChange,
    onSubmit,
    messages,
    sources,
    evidence,
    pendingQuestion,
    error,
    historyLoading,
    chatBusy,
    preview,
    previewLoading,
    previewError,
    onPreviewEvidence,
  } = props;

  const summary = buildExperienceSummary({ experience, selectedKb });
  const submitDisabled =
    chatBusy ||
    !question.trim() ||
    !modelReady ||
    (experience === "knowledge" && !selectedKbId);

  return (
    <div className="qa-page-shell">
      <header className="qa-hero-card">
        <div className="qa-hero-content">
          <div className="qa-hero-copy">
            <span className="qa-eyebrow">问答工作台</span>
            <h1>先问答，再决定是否进入 Agent 高级模式</h1>
            <p>{summary}</p>
          </div>
          <div className="qa-hero-meta">
            <span className="qa-badge">{"当前模型：" + currentModelLabel}</span>
            <span className="qa-badge">{modelHealthSummary?.chipLabel || "状态未知"}</span>
            <span className="qa-badge">
              {"当前范围：" + (experience === "knowledge" ? (selectedKb?.kb_name || "未选择知识库") : "全部知识范围")}
            </span>
            <span className="qa-badge">{"可用知识库：" + kbList.length + " 个"}</span>
          </div>
        </div>
        <div className="qa-hero-actions">
          <Link className="secondary-button link-button" to={buildKnowledgeWorkspaceLink(selectedKbId)}>
            管理知识库
          </Link>
          <Link className="secondary-button link-button" to="/models">
            模型配置
          </Link>
        </div>
      </header>

      <div className="qa-layout">
        <div className="qa-main-column">
          {experience === "knowledge" ? (
            <KnowledgeScopeSelector
              selectedKbId={selectedKbId}
              selectedKb={selectedKb}
              kbList={kbList}
              kbLoading={kbLoading}
              onSelectKb={onSelectKb}
            />
          ) : null}

          <section className="qa-surface-card qa-compose-card">
            <div className="qa-section-head">
              <div>
                <p className="qa-section-eyebrow">立即提问</p>
                <h2>{experience === "knowledge" ? "知识库定向问答" : "基础问答"}</h2>
              </div>
              <span className="toolbar-pill subtle">{modelReady ? currentModelLabel : "尚未配置模型"}</span>
            </div>

            <form className="qa-compose-form" onSubmit={onSubmit}>
              <textarea
                className="qa-compose-input"
                rows={5}
                value={question}
                onChange={(event) => onQuestionChange(event.target.value)}
                placeholder={
                  experience === "knowledge"
                    ? "例如：这份知识库里对实习要求是怎么描述的？"
                    : "例如：帮我总结一下当前知识库里有哪些主题。"
                }
              />
              <div className="qa-compose-actions">
                <div className="qa-inline-tip">
                  {experience === "knowledge" && !selectedKbId
                    ? "请先在上方选择知识库后再发送问题。"
                    : "问答会保留独立会话历史，方便你连续追问。"}
                </div>
                <button type="submit" className="primary-button" disabled={submitDisabled}>
                  {chatBusy ? "回答生成中…" : "发送问题"}
                </button>
              </div>
            </form>

            {error ? <div className="banner-info banner-danger">{error}</div> : null}
            {!modelReady ? (
              <div className="banner-info">
                还没有可用模型，请先前往模型配置页完成提供商与模型选择。
              </div>
            ) : null}
          </section>

          <QaConversation
            messages={messages}
            pendingQuestion={pendingQuestion}
            historyLoading={historyLoading}
            chatBusy={chatBusy}
          />
        </div>

        <aside className="qa-side-column">
          <section className="qa-surface-card qa-summary-card">
            <div className="qa-section-head">
              <div>
                <p className="qa-section-eyebrow">当前状态</p>
                <h2>工作台概览</h2>
              </div>
            </div>
            <div className="qa-summary-list">
              <div className="qa-summary-item">
                <span>体验模式</span>
                <strong>{AGENT_EXPERIENCES.find((item) => item.value === experience)?.label}</strong>
              </div>
              <div className="qa-summary-item">
                <span>模型状态</span>
                <strong>{modelHealthSummary?.title || (modelReady ? "已就绪" : "待配置")}</strong>
              </div>
              <div className="qa-summary-item">
                <span>健康详情</span>
                <strong>{modelHealthSummary?.detail || (modelReady ? "最近未发现异常" : "请先配置模型")}</strong>
              </div>
              <div className="qa-summary-item">
                <span>知识库范围</span>
                <strong>{experience === "knowledge" ? (selectedKb?.kb_name || "未选择") : "全局检索"}</strong>
              </div>
            </div>
          </section>

          <SourceList
            sources={sources}
            evidence={evidence}
            onPreview={onPreviewEvidence}
            preview={preview}
            previewLoading={previewLoading}
            previewError={previewError}
          />
        </aside>
      </div>
    </div>
  );
}

function AgentRuntimePanel({ selectedKbId, selectedKb }) {
  const sessionId = useAppStore((state) => state.sessionId);
  const currentMode = useAppStore((state) => state.currentMode);
  const knowledgeScope = useAppStore((state) => state.knowledgeScope);
  const draftQuestion = useAppStore((state) => state.draftQuestion);
  const timeline = useAppStore((state) => state.timeline);
  const evidence = useAppStore((state) => state.evidence);
  const receipts = useAppStore((state) => state.receipts);
  const pendingActions = useAppStore((state) => state.pendingActions);
  const approvalMessage = useAppStore((state) => state.approvalMessage);
  const taskGoal = useAppStore((state) => state.taskGoal);
  const runState = useAppStore((state) => state.runState);
  const lastAnswer = useAppStore((state) => state.lastAnswer);
  const attachedFiles = useAppStore((state) => state.attachedFiles);
  const enabledSkills = useAppStore((state) => state.enabledSkills);
  const activeDetail = useAppStore((state) => state.activeDetail);
  const showDetails = useAppStore((state) => state.showDetails);
  const sessionLoaded = useAppStore((state) => state.sessionLoaded);

  const setCurrentMode = useAppStore((state) => state.setCurrentMode);
  const setDraftQuestion = useAppStore((state) => state.setDraftQuestion);
  const setReceipts = useAppStore((state) => state.setReceipts);
  const setPendingActions = useAppStore((state) => state.setPendingActions);
  const setApprovalMessage = useAppStore((state) => state.setApprovalMessage);
  const setAttachedFiles = useAppStore((state) => state.setAttachedFiles);
  const setEnabledSkills = useAppStore((state) => state.setEnabledSkills);
  const setActiveDetail = useAppStore((state) => state.setActiveDetail);
  const setShowDetails = useAppStore((state) => state.setShowDetails);
  const appendTimeline = useAppStore((state) => state.appendTimeline);
  const bootstrapTask = useAppStore((state) => state.bootstrapTask);
  const hydrateFromAgentRun = useAppStore((state) => state.hydrateFromAgentRun);
  const hydrateFromApproval = useAppStore((state) => state.hydrateFromApproval);
  const hydrateSessionSnapshot = useAppStore((state) => state.hydrateSessionSnapshot);
  const markSessionLoaded = useAppStore((state) => state.markSessionLoaded);

  const saveTimerRef = useRef(null);

  const sessionQuery = useQuery({
    queryKey: ["agent-session", sessionId],
    queryFn: () => getAgentSession(sessionId),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 30000,
  });

  const receiptsQuery = useQuery({
    queryKey: ["agent-receipts", sessionId],
    queryFn: () => getAgentReceipts(sessionId, 20),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 30000,
  });

  const pendingQuery = useQuery({
    queryKey: ["agent-pending", sessionId],
    queryFn: () => getPendingActions(sessionId),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 30000,
  });

  const skillsQuery = useQuery({
    queryKey: ["agent-skills"],
    queryFn: getAgentSkills,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 300000,
  });

  const modelOptionsQuery = useQuery({
    queryKey: ["agent-model-options"],
    queryFn: getModelOptions,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 60000,
  });

  const currentModel = modelOptionsQuery.data?.current_llm_info || null;
  const modelHealthSummary = useMemo(
    () => buildModelHealthSummary(modelOptionsQuery.data?.model_health || null),
    [modelOptionsQuery.data?.model_health],
  );
  const sessionProvider = sessionQuery.data?.snapshot?.workspace?.provider || null;
  const providers = modelOptionsQuery.data?.providers || {};

  const providerItems = useMemo(() => {
    const names = Object.keys(providers);
    const currentProviderName = currentModel?.service_provider || sessionProvider?.name || "";
    const ordered =
      currentProviderName && names.includes(currentProviderName)
        ? [currentProviderName, ...names.filter((item) => item !== currentProviderName)]
        : names;

    return ordered.map((providerName) => ({
      value: providerName,
      label: providerName,
      models: providers[providerName]?.models || [],
    }));
  }, [providers, currentModel, sessionProvider]);

  const selectedProvider = useMemo(() => {
    const currentProviderName = currentModel?.service_provider || sessionProvider?.name || "";
    if (currentProviderName && providers[currentProviderName]) {
      return {
        name: currentProviderName,
        ...providers[currentProviderName],
      };
    }

    const firstProviderName = providerItems[0]?.value;
    if (!firstProviderName) {
      return null;
    }

    return {
      name: firstProviderName,
      ...providers[firstProviderName],
    };
  }, [providerItems, providers, currentModel, sessionProvider]);

  const providerOptions = useMemo(
    () => ({
      items: providerItems,
      value: selectedProvider?.name || "",
      disabled: providerItems.length === 0,
    }),
    [providerItems, selectedProvider],
  );

  const modelItems = useMemo(() => {
    if (!selectedProvider) {
      return [];
    }
    return (selectedProvider.models || []).map((modelName) => ({
      value: modelName,
      label: modelName,
    }));
  }, [selectedProvider]);

  const modelOptions = useMemo(() => {
    const currentModelName = currentModel?.model || sessionProvider?.model || "";
    const nextValue = modelItems.some((item) => item.value === currentModelName)
      ? currentModelName
      : modelItems[0]?.value || "";

    return {
      items: modelItems,
      value: nextValue,
      disabled: modelItems.length === 0,
    };
  }, [modelItems, currentModel, sessionProvider]);

  const currentModelLabel = useMemo(() => {
    const providerName = currentModel?.service_provider || sessionProvider?.name || "";
    const modelName = currentModel?.model || sessionProvider?.model || "";
    if (!providerName || !modelName) {
      return "未启用模型";
    }
    return providerName + " / " + modelName;
  }, [currentModel, sessionProvider]);

  const hasDetailContent =
    receipts.length > 0 ||
    evidence.length > 0 ||
    pendingActions.length > 0 ||
    Boolean(approvalMessage);

  useEffect(() => {
    if (sessionQuery.data?.snapshot) {
      hydrateSessionSnapshot(sessionQuery.data.snapshot);
    }
  }, [sessionQuery.data, hydrateSessionSnapshot]);

  useEffect(() => {
    if (sessionQuery.isError) {
      markSessionLoaded();
    }
  }, [sessionQuery.isError, markSessionLoaded]);

  useEffect(() => {
    if (skillsQuery.data?.skills?.length && enabledSkills.length === 0) {
      setEnabledSkills(
        skillsQuery.data.skills
          .filter((item) => item.status === "enabled")
          .map((item) => item.id),
      );
    }
  }, [skillsQuery.data, enabledSkills.length, setEnabledSkills]);

  useEffect(() => {
    if (receiptsQuery.data?.receipts) {
      setReceipts(receiptsQuery.data.receipts);
    }
  }, [receiptsQuery.data, setReceipts]);

  useEffect(() => {
    if (pendingQuery.data?.pending_actions) {
      const nextPending = pendingQuery.data.pending_actions;
      setPendingActions(nextPending);
      if (nextPending.length > 0) {
        setShowDetails(true);
        setActiveDetail("approvals");
      }
    }
  }, [pendingQuery.data, setPendingActions, setShowDetails, setActiveDetail]);

  useEffect(() => {
    if (!sessionLoaded) {
      return undefined;
    }

    if (saveTimerRef.current) {
      window.clearTimeout(saveTimerRef.current);
    }

    const providerPatch = currentModel
      ? {
          name: currentModel.service_provider || "",
          base_url: currentModel.api_base || "",
          model: currentModel.model || "",
        }
      : sessionProvider || { name: "", base_url: "", model: "" };

    saveTimerRef.current = window.setTimeout(() => {
      updateAgentSession({
        session_id: sessionId,
        workspace: {
          current_mode: currentMode,
          knowledge_scope: knowledgeScope,
          task_goal: taskGoal,
          draft_question: draftQuestion,
          run_state: runState,
          last_answer: lastAnswer,
          provider: providerPatch,
          attached_files: attachedFiles,
          enabled_skills: enabledSkills,
        },
        ui_state: {
          active_detail: activeDetail,
          show_details: showDetails,
        },
      }).catch(() => {});
    }, 400);

    return () => {
      if (saveTimerRef.current) {
        window.clearTimeout(saveTimerRef.current);
      }
    };
  }, [
    sessionLoaded,
    sessionId,
    currentMode,
    knowledgeScope,
    taskGoal,
    draftQuestion,
    runState,
    lastAnswer,
    attachedFiles,
    enabledSkills,
    activeDetail,
    showDetails,
    currentModel,
    sessionProvider,
  ]);

  const runMutation = useMutation({
    mutationFn: (payload) => runAgent(payload),
    onSuccess: (data) => {
      hydrateFromAgentRun(data);
      receiptsQuery.refetch();
      pendingQuery.refetch();
      modelOptionsQuery.refetch();
    },
    onError: (error) => {
      appendTimeline({
        type: "error",
        content: error.message || "任务执行失败。",
      });
    },
  });

  const approvalMutation = useMutation({
    mutationFn: (payload) => approveAgentAction(payload),
    onSuccess: (result) => {
      hydrateFromApproval(result);
      receiptsQuery.refetch();
      pendingQuery.refetch();
    },
    onError: (error) => {
      setApprovalMessage(error.message || "审批失败。");
    },
  });

  const quickSwitchMutation = useMutation({
    mutationFn: (payload) => selectModel(payload),
    onSuccess: async () => {
      await modelOptionsQuery.refetch();
    },
  });

  const uploadMutation = useMutation({
    mutationFn: async (files) => {
      const formData = new FormData();
      for (const file of files) {
        formData.append("files", file);
      }
      formData.append("chunk_size", "2048");
      formData.append("chunk_overlap", "512");
      formData.append("kb_id", selectedKbId || knowledgeScope?.kb_id || DEFAULT_KNOWLEDGE_SCOPE.kb_id);
      return uploadFilesToKnowledge(formData);
    },
    onSuccess: (result) => {
      const importedAttachments = (result.files || []).map((file, index) =>
        createAttachmentFromImportedFile(file, index),
      );
      setAttachedFiles(mergeAttachments(attachedFiles, importedAttachments));
      appendTimeline({
        type: "status",
        content:
          "已导入 " +
          (result.files?.length || 0) +
          " 个文件到知识库 " +
          (result.kb_id || selectedKbId || knowledgeScope?.kb_id || DEFAULT_KNOWLEDGE_SCOPE.kb_id) +
          "。",
      });
    },
    onError: (error) => {
      appendTimeline({
        type: "error",
        content: error.message || "文件导入失败。",
      });
    },
  });

  const isBusy = runMutation.isPending || approvalMutation.isPending || quickSwitchMutation.isPending;
  const canRunAgent = currentMode !== "agent" || Boolean(currentModel?.service_provider && currentModel?.model);
  const uploadTargetText = selectedKb
    ? (selectedKb.kb_name || selectedKb.kb_id) + "（kb_id=" + selectedKb.kb_id + "）"
    : (knowledgeScope?.kb_name || DEFAULT_KNOWLEDGE_SCOPE.kb_name) + "（kb_id=" + (knowledgeScope?.kb_id || DEFAULT_KNOWLEDGE_SCOPE.kb_id) + "）";

  function handleSubmit(event) {
    event.preventDefault();
    const question = draftQuestion.trim();
    if (!question) {
      return;
    }
    if (!canRunAgent) {
      appendTimeline({
        type: "error",
        content: "请先在模型配置页启用一个可用模型。",
      });
      return;
    }

    bootstrapTask({ question, mode: currentMode });
    runMutation.mutate({
      question,
      session_id: sessionId,
      mode: currentMode,
      knowledge_scope: knowledgeScope,
    });
  }

  function handleProviderChange(nextProviderName) {
    const nextProvider = providers[nextProviderName];
    const nextModelName = nextProvider?.models?.[0] || "";
    if (!nextModelName) {
      return;
    }

    quickSwitchMutation.mutate({
      service_provider: nextProviderName,
      model: nextModelName,
      api_base: nextProvider.api_base,
      session_id: sessionId,
    });
  }

  function handleModelChange(nextModelName) {
    if (!selectedProvider || nextModelName === modelOptions.value) {
      return;
    }

    quickSwitchMutation.mutate({
      service_provider: selectedProvider.name,
      model: nextModelName,
      api_base: selectedProvider.api_base,
      session_id: sessionId,
    });
  }

  async function handlePickLocalFiles() {
    const desktopBridge = window.northAgentDesktop || window.foxgloveDesktop || window.thinkragDesktop;
    if (!desktopBridge?.pickFiles) {
      appendTimeline({
        type: "error",
        content: "当前环境不支持桌面文件选择，请使用上传并导入。",
      });
      return;
    }

    const result = await desktopBridge.pickFiles({
      title: "选择本地文件",
      multiSelections: true,
    });

    if (result?.canceled || !result?.filePaths?.length) {
      return;
    }

    const nextAttachments = result.filePaths.map((path, index) => createAttachmentFromPath(path, index));
    const merged = mergeAttachments(attachedFiles, nextAttachments);
    setAttachedFiles(merged);
    setCurrentMode("read_file");
    setDraftQuestion(result.filePaths[0]);
    appendTimeline({
      type: "status",
      content: "已选择 " + result.filePaths.length + " 个本地文件，读文件模式将优先读取第一项。",
    });
  }

  function handleUploadFiles(files) {
    uploadMutation.mutate(files);
  }

  function handleRemoveAttachedFile(fileId) {
    const nextFiles = attachedFiles.filter((item) => item.id !== fileId);
    setAttachedFiles(nextFiles);
  }

  return (
    <section className="qa-agent-mode">
      <header className="qa-hero-card agent-hero-card">
        <div className="qa-hero-content">
          <div className="qa-hero-copy">
            <span className="qa-eyebrow">Agent 高级模式</span>
            <h1>复杂任务、工具调用、审批与回执都保留在这里</h1>
            <p>当基础问答不够用时，可以切到 Agent 高级模式继续执行读文件、知识检索、命令执行和审批流。</p>
          </div>
          <div className="qa-hero-meta">
            <span className="qa-badge">{"当前模型：" + currentModelLabel}</span>
            <span className="qa-badge">{modelHealthSummary.chipLabel}</span>
            <span className="qa-badge">{"运行状态：" + runState}</span>
            <span className="qa-badge">{"上传目标：" + uploadTargetText}</span>
          </div>
        </div>
        <div className="qa-hero-actions">
          <Link className="secondary-button link-button" to={buildKnowledgeWorkspaceLink(selectedKbId)}>
            管理知识库
          </Link>
          <Link className="secondary-button link-button" to="/models">
            模型配置
          </Link>
        </div>
      </header>

      <div className="agent-runtime-note banner-info">
        {selectedKb
          ? "当前已选知识库：" + (selectedKb.kb_name || selectedKb.kb_id) + "（kb_id=" + selectedKb.kb_id + "）。Agent 在 kb_search 模式下会优先使用该范围。"
          : "当前使用知识范围：" + (knowledgeScope?.kb_name || DEFAULT_KNOWLEDGE_SCOPE.kb_name) + "。如果要定向到某个知识库，可先切换到“知识库问答”选择目标。"}
      </div>

      <section className="agent-chat-page">
        <header className="agent-chat-toolbar">
          <div className="agent-chat-toolbar-left">
            <span className="toolbar-pill">{currentModelLabel}</span>
            <span className="toolbar-pill subtle">{modelHealthSummary.chipLabel}</span>
            <span className="toolbar-pill subtle">{"状态：" + runState}</span>
          </div>
          <div className="agent-chat-toolbar-right">
            <button
              type="button"
              className="secondary-button subtle-button"
              onClick={() => setShowDetails(!showDetails)}
            >
              {showDetails ? "隐藏详情" : "查看详情"}
            </button>
          </div>
        </header>

        <div className={showDetails && hasDetailContent ? "agent-chat-layout with-drawer" : "agent-chat-layout"}>
          <div className="agent-chat-main">
            <AgentTimeline timeline={timeline} />
            <AgentInputPanel
              question={draftQuestion}
              mode={currentMode}
              disabled={isBusy || (currentMode === "agent" && !canRunAgent)}
              providerOptions={providerOptions}
              modelOptions={modelOptions}
              attachedFiles={attachedFiles}
              enabledSkills={enabledSkills}
              uploadBusy={uploadMutation.isPending}
              onQuestionChange={setDraftQuestion}
              onModeChange={setCurrentMode}
              onProviderChange={handleProviderChange}
              onModelChange={handleModelChange}
              onSubmit={handleSubmit}
              onPickLocalFiles={handlePickLocalFiles}
              onUploadFiles={handleUploadFiles}
              onRemoveAttachedFile={handleRemoveAttachedFile}
            />
          </div>

          {showDetails && hasDetailContent ? (
            <aside className="agent-detail-drawer">
              <div className="mode-switcher drawer-tabs">
                {pendingActions.length > 0 ? (
                  <button
                    type="button"
                    className={activeDetail === "approvals" ? "mode-chip active" : "mode-chip"}
                    onClick={() => setActiveDetail("approvals")}
                  >
                    审批
                  </button>
                ) : null}
                {receipts.length > 0 ? (
                  <button
                    type="button"
                    className={activeDetail === "receipts" ? "mode-chip active" : "mode-chip"}
                    onClick={() => setActiveDetail("receipts")}
                  >
                    回执
                  </button>
                ) : null}
                {evidence.length > 0 ? (
                  <button
                    type="button"
                    className={activeDetail === "evidence" ? "mode-chip active" : "mode-chip"}
                    onClick={() => setActiveDetail("evidence")}
                  >
                    证据
                  </button>
                ) : null}
              </div>

              <div className="agent-detail-scroll">
                {activeDetail === "approvals" ? (
                  <AgentApprovalPanel
                    pendingActions={pendingActions}
                    approvalMessage={approvalMessage}
                    disabled={approvalMutation.isPending}
                    onReview={(payload) => approvalMutation.mutate(payload)}
                  />
                ) : null}
                {activeDetail === "evidence" ? <AgentEvidencePanel evidence={evidence} /> : null}
                {activeDetail === "receipts" ? <AgentReceiptsPanel receipts={receipts} /> : null}
              </div>
            </aside>
          ) : null}
        </div>
      </section>
    </section>
  );
}

function AgentPageContent() {
  const sessionId = useAppStore((state) => state.sessionId);
  const knowledgeScope = useAppStore((state) => state.knowledgeScope);
  const setKnowledgeScope = useAppStore((state) => state.setKnowledgeScope);

  const location = useLocation();
  const navigate = useNavigate();
  const { kbList, selectedKbId, selectedKb, loading: kbLoading, selectKb } = useKb();
  const routeIntentAppliedRef = useRef("");
  const routeIntent = useMemo(() => parseKnowledgeAgentEntry(location.search), [location.search]);
  const isRouteIntentPending = Boolean(location.search) && routeIntentAppliedRef.current !== location.search;

  const [experience, setExperience] = useState(routeIntent.requestedExperience || "basic");
  const [chatQuestion, setChatQuestion] = useState("");
  const [chatMessages, setChatMessages] = useState([]);
  const [chatSources, setChatSources] = useState([]);
  const [chatEvidence, setChatEvidence] = useState([]);
  const [chatPreview, setChatPreview] = useState(null);
  const [chatPreviewError, setChatPreviewError] = useState("");
  const [chatError, setChatError] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState("");

  const modelOptionsQuery = useQuery({
    queryKey: ["agent-model-options"],
    queryFn: getModelOptions,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 60000,
  });

  const activeKbList = useMemo(
    () => (kbList || []).filter((kb) => kb.status === "active"),
    [kbList],
  );

  useEffect(() => {
    if (!isRouteIntentPending) {
      return;
    }

    if (routeIntent.requestedExperience) {
      setExperience(routeIntent.requestedExperience);
    }

    if (kbLoading) {
      return;
    }

    if (routeIntent.requestedKbId && canUseKbTarget(kbList, routeIntent.requestedKbId)) {
      selectKb(routeIntent.requestedKbId);
    }

    routeIntentAppliedRef.current = location.search;
  }, [isRouteIntentPending, kbList, kbLoading, location.search, routeIntent, selectKb]);

  useEffect(() => {
    if (isRouteIntentPending) {
      return;
    }

    const target = experience === "knowledge"
      ? buildKnowledgeAgentLink(selectedKbId)
      : "/agent";
    const current = location.pathname + location.search;
    if (target !== current) {
      navigate(target, { replace: true });
    }
  }, [experience, isRouteIntentPending, location.pathname, location.search, navigate, selectedKbId]);

  const currentModel = modelOptionsQuery.data?.current_llm_info || null;
  const modelHealthSummary = useMemo(
    () => buildModelHealthSummary(modelOptionsQuery.data?.model_health || null),
    [modelOptionsQuery.data?.model_health],
  );
  const currentModelLabel =
    currentModel?.service_provider && currentModel?.model
      ? currentModel.service_provider + " / " + currentModel.model
      : "未启用模型";
  const modelReady = Boolean(currentModel?.service_provider && currentModel?.model);

  useEffect(() => {
    const nextKnowledgeScope = selectedKb?.kb_id
      ? { kb_id: selectedKb.kb_id, kb_name: selectedKb.kb_name || selectedKb.kb_id }
      : DEFAULT_KNOWLEDGE_SCOPE;

    if (
      knowledgeScope?.kb_id !== nextKnowledgeScope.kb_id ||
      knowledgeScope?.kb_name !== nextKnowledgeScope.kb_name
    ) {
      setKnowledgeScope(nextKnowledgeScope);
    }
  }, [knowledgeScope, selectedKb, setKnowledgeScope]);

  const chatSessionId = useMemo(
    () => safeBuildChatSessionId({ experience, sessionId, selectedKbId }),
    [experience, selectedKbId, sessionId],
  );

  const historyQuery = useQuery({
    queryKey: ["agent-chat-history", chatSessionId],
    enabled: experience !== "agent" && Boolean(chatSessionId),
    queryFn: async () => {
      const response = await getHistory(chatSessionId);
      return readApiData(response) || { session_id: chatSessionId, messages: [] };
    },
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 0,
  });

  useEffect(() => {
    setChatMessages(historyQuery.data?.messages || []);
  }, [historyQuery.data]);

  useEffect(() => {
    setChatError("");
    setPendingQuestion("");
    setChatSources([]);
    setChatEvidence([]);
    setChatPreview(null);
    setChatPreviewError("");
  }, [chatSessionId, experience]);

  const chatMutation = useMutation({
    mutationFn: async (payload) => {
      const queryResponse = await queryChat(payload);
      const queryData = readApiData(queryResponse) || {};
      const historyResponse = await getHistory(queryData.session_id || payload.session_id);
      const historyData = readApiData(historyResponse) || { messages: [] };
      return {
        ...queryData,
        messages: historyData.messages || [],
      };
    },
    onMutate: (payload) => {
      setChatError("");
      setPendingQuestion(payload.question);
      setChatPreview(null);
      setChatPreviewError("");
    },
    onSuccess: (result) => {
      setPendingQuestion("");
      setChatQuestion("");
      setChatSources(result.sources || []);
      setChatEvidence(result.evidence || []);
      setChatMessages(result.messages || []);
      historyQuery.refetch();
    },
    onError: (error) => {
      setPendingQuestion("");
      setChatError(error.message || "问答请求失败，请稍后重试。");
    },
  });

  const previewMutation = useMutation({
    mutationFn: async (item) => {
      const targetKbId = item?.kb_id || selectedKbId;
      if (!targetKbId) {
        throw new Error("当前证据缺少知识库范围，无法预览。");
      }

      const response = await previewItem(item, selectedKbId);
      return readApiData(response) || null;
    },
    onMutate: () => {
      setChatPreviewError("");
    },
    onSuccess: (preview) => {
      setChatPreview(preview);
    },
    onError: (error) => {
      setChatPreview(null);
      setChatPreviewError(error.message || "证据预览失败，请稍后重试。");
    },
  });

  const handlePreviewEvidence = useCallback(
    (item) => {
      previewMutation.mutate(item);
    },
    [previewMutation],
  );

  const handleExperienceChange = useCallback((nextExperience) => {
    setExperience(nextExperience);
    setChatError("");
    setPendingQuestion("");
  }, []);

  const handleChatSubmit = useCallback(
    (event) => {
      event.preventDefault();
      if (!modelReady) {
        setChatError("请先到模型配置页启用一个模型，再开始问答。");
        return;
      }

      try {
        const payload = buildChatPayload({
          experience,
          question: chatQuestion,
          sessionId,
          selectedKbId,
        });
        chatMutation.mutate(payload);
      } catch (error) {
        setChatError(error.message || "提问参数无效。");
      }
    },
    [chatMutation, chatQuestion, experience, modelReady, selectedKbId, sessionId],
  );

  if (experience === "agent") {
    return (
      <div className="qa-page-frame">
        <ExperienceTabs experience={experience} onChange={handleExperienceChange} />
        <AgentRuntimePanel selectedKbId={selectedKbId} selectedKb={selectedKb} />
      </div>
    );
  }

  return (
    <div className="qa-page-frame">
      <ExperienceTabs experience={experience} onChange={handleExperienceChange} />
      <QaWorkbench
        experience={experience}
        selectedKb={selectedKb}
        selectedKbId={selectedKbId}
        kbList={activeKbList}
        kbLoading={kbLoading}
        onSelectKb={selectKb}
        currentModelLabel={currentModelLabel}
        modelHealthSummary={modelHealthSummary}
        modelReady={modelReady}
        question={chatQuestion}
        onQuestionChange={setChatQuestion}
        onSubmit={handleChatSubmit}
        messages={chatMessages}
        sources={chatSources}
        evidence={chatEvidence}
        pendingQuestion={pendingQuestion}
        error={chatError}
        historyLoading={historyQuery.isLoading || historyQuery.isFetching}
        chatBusy={chatMutation.isPending}
        preview={chatPreview}
        previewLoading={previewMutation.isPending}
        previewError={chatPreviewError}
        onPreviewEvidence={handlePreviewEvidence}
      />
    </div>
  );
}

export default function AgentPage() {
  return (
    <KbProvider>
      <AgentPageContent />
    </KbProvider>
  );
}
