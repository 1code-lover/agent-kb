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
import { getModelOptions, selectModel } from "../api/models";
import { KbProvider, useKb } from "../components/kb/KbContext";
import {
  DEFAULT_KNOWLEDGE_SCOPE,
  canUseKbTarget,
  resolveKnowledgeScope,
} from "../domain/kbSelection";
import {
  buildAgentWorkbenchLink,
  buildKnowledgeWorkspaceLink,
  parseAgentWorkbenchEntry,
} from "../domain/kbNavigation";
import { AGENT_EXPERIENCES } from "../domain/agentExperience";
import { buildModelHealthSummary } from "../domain/modelHealth";
import { getDesktopBridge } from "../domain/desktopBridge.js";
import QaWorkbench from "./agent-page/QaWorkbench.jsx";
import { useAgentChatWorkspace } from "./useAgentChatWorkspace.js";
import useAppStore from "../store/appStore";
import "./agent-page.css";

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

function AgentRuntimePanel({ selectedKbId, selectedKb, resolvedKnowledgeScope }) {
  const sessionId = useAppStore((state) => state.sessionId);
  const currentMode = useAppStore((state) => state.currentMode);
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
          knowledge_scope: resolvedKnowledgeScope,
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
    resolvedKnowledgeScope,
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
      formData.append("kb_id", resolvedKnowledgeScope.kb_id);
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
          (result.kb_id || resolvedKnowledgeScope.kb_id) +
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
  const uploadTargetText =
    (resolvedKnowledgeScope.kb_name || DEFAULT_KNOWLEDGE_SCOPE.kb_name) +
    "（kb_id=" +
    resolvedKnowledgeScope.kb_id +
    "）";

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
      knowledge_scope: resolvedKnowledgeScope,
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
    const desktopBridge = getDesktopBridge(window);
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
          <p className="qa-inline-tip">{modelHealthSummary.actionHint || "当前模型可继续使用。"}</p>
          {modelHealthSummary.probeSummary ? <p className="qa-inline-tip">{modelHealthSummary.probeSummary}</p> : null}
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
          : "当前使用知识范围：" + resolvedKnowledgeScope.kb_name + "。如果要定向到某个知识库，可先切换到“知识库问答”选择目标。"}
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
  const setKnowledgeScope = useAppStore((state) => state.setKnowledgeScope);

  const location = useLocation();
  const navigate = useNavigate();
  const { kbList, selectedKbId, selectedKb, loading: kbLoading, selectKb } = useKb();
  const routeIntentAppliedRef = useRef("");
  const routeIntent = useMemo(() => parseAgentWorkbenchEntry(location.search), [location.search]);
  const isRouteIntentPending = Boolean(location.search) && routeIntentAppliedRef.current !== location.search;

  const [experience, setExperience] = useState(routeIntent.requestedExperience || "basic");
  const resolvedKnowledgeScope = useMemo(
    () => resolveKnowledgeScope({ selectedKb, selectedKbId, fallbackScope: knowledgeScope }),
    [knowledgeScope, selectedKb, selectedKbId],
  );
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

    const target = experience === "agent"
      ? "/agent"
      : buildAgentWorkbenchLink({ experience, kbId: selectedKbId });
    const current = location.pathname + location.search;
    if (target !== current) {
      navigate(target, { replace: true });
    }
  }, [experience, isRouteIntentPending, location.pathname, location.search, navigate, selectedKbId]);

  useEffect(() => {
    if (
      knowledgeScope?.kb_id !== resolvedKnowledgeScope.kb_id ||
      knowledgeScope?.kb_name !== resolvedKnowledgeScope.kb_name
    ) {
      setKnowledgeScope(resolvedKnowledgeScope);
    }
  }, [knowledgeScope, resolvedKnowledgeScope, setKnowledgeScope]);

  const chatWorkspace = useAgentChatWorkspace({
    experience,
    sessionId,
    selectedKbId,
  });

  const handleExperienceChange = useCallback((nextExperience) => {
    setExperience(nextExperience);
  }, []);

  if (experience === "agent") {
    return (
      <div className="qa-page-frame">
        <ExperienceTabs experience={experience} onChange={handleExperienceChange} />
        <AgentRuntimePanel selectedKbId={selectedKbId} selectedKb={selectedKb} resolvedKnowledgeScope={resolvedKnowledgeScope} />
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
        currentModelLabel={chatWorkspace.currentModelLabel}
        modelHealthSummary={chatWorkspace.modelHealthSummary}
        modelReady={chatWorkspace.modelReady}
        question={chatWorkspace.question}
        onQuestionChange={chatWorkspace.setQuestion}
        requestOptions={chatWorkspace.requestOptions}
        requestOptionsLoading={chatWorkspace.requestOptionsLoading}
        onRequestOptionsChange={chatWorkspace.setRequestOptions}
        onRequestOptionsReset={chatWorkspace.resetRequestOptions}
        onSubmit={chatWorkspace.submitChat}
        messages={chatWorkspace.messages}
        sources={chatWorkspace.sources}
        evidence={chatWorkspace.evidence}
        pendingQuestion={chatWorkspace.pendingQuestion}
        error={chatWorkspace.error}
        chatNotice={chatWorkspace.chatNotice}
        historyLoading={chatWorkspace.historyLoading}
        chatBusy={chatWorkspace.chatBusy}
        preview={chatWorkspace.preview}
        previewLoading={chatWorkspace.previewLoading}
        previewError={chatWorkspace.previewError}
        onPreviewEvidence={chatWorkspace.previewEvidence}
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

