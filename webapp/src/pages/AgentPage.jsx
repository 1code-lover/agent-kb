import { useEffect, useMemo, useRef } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
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
  uploadFilesToKnowledge
} from "../api/agent";
import { getModelOptions, selectModel } from "../api/models";
import useAppStore from "../store/appStore";

function createAttachmentFromPath(path, index = 0) {
  const normalizedPath = path || "";
  const name = normalizedPath.split(/[/\\]/).pop() || normalizedPath;
  return {
    id: `local-${Date.now()}-${index}`,
    name,
    path: normalizedPath,
    source: "desktop_pick",
    status: "selected"
  };
}

function createAttachmentFromImportedFile(file, index = 0) {
  return {
    id: `import-${Date.now()}-${index}`,
    name: file.name,
    path: file.path || "",
    source: "upload_import",
    status: "imported",
    size: file.size,
    content_type: file.type
  };
}

function mergeAttachments(existingFiles, nextFiles) {
  const merged = [...existingFiles];
  for (const nextFile of nextFiles) {
    const exists = merged.some((item) => item.path && nextFile.path && item.path === nextFile.path);
    if (!exists) {
      merged.push(nextFile);
    }
  }
  return merged;
}

export default function AgentPage() {
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

  const saveTimerRef = useRef(null);

  const sessionQuery = useQuery({
    queryKey: ["agent-session", sessionId],
    queryFn: () => getAgentSession(sessionId),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 30000
  });

  const receiptsQuery = useQuery({
    queryKey: ["agent-receipts", sessionId],
    queryFn: () => getAgentReceipts(sessionId, 20),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 30000
  });

  const pendingQuery = useQuery({
    queryKey: ["agent-pending", sessionId],
    queryFn: () => getPendingActions(sessionId),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 30000
  });

  const skillsQuery = useQuery({
    queryKey: ["agent-skills"],
    queryFn: getAgentSkills,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 300000
  });

  const modelOptionsQuery = useQuery({
    queryKey: ["agent-model-options"],
    queryFn: getModelOptions,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 60000
  });

  const currentModel = modelOptionsQuery.data?.current_llm_info || null;
  const sessionProvider = sessionQuery.data?.snapshot?.workspace?.provider || null;
  const providers = modelOptionsQuery.data?.providers || {};

  const providerItems = useMemo(() => {
    const names = Object.keys(providers);
    const currentProviderName = currentModel?.service_provider || sessionProvider?.name || "";
    const ordered = currentProviderName && names.includes(currentProviderName)
      ? [currentProviderName, ...names.filter((item) => item !== currentProviderName)]
      : names;

    return ordered.map((providerName) => ({
      value: providerName,
      label: providerName,
      models: providers[providerName]?.models || []
    }));
  }, [providers, currentModel, sessionProvider]);

  const selectedProvider = useMemo(() => {
    const currentProviderName = currentModel?.service_provider || sessionProvider?.name || "";
    if (currentProviderName && providers[currentProviderName]) {
      return {
        name: currentProviderName,
        ...providers[currentProviderName]
      };
    }
    const firstProviderName = providerItems[0]?.value;
    if (!firstProviderName) {
      return null;
    }
    return {
      name: firstProviderName,
      ...providers[firstProviderName]
    };
  }, [providerItems, providers, currentModel, sessionProvider]);

  const providerOptions = useMemo(
    () => ({
      items: providerItems,
      value: selectedProvider?.name || "",
      disabled: providerItems.length === 0
    }),
    [providerItems, selectedProvider]
  );

  const modelItems = useMemo(() => {
    if (!selectedProvider) {
      return [];
    }
    return (selectedProvider.models || []).map((modelName) => ({
      value: modelName,
      label: modelName
    }));
  }, [selectedProvider]);

  const modelOptions = useMemo(() => {
    const currentModelName = currentModel?.model || sessionProvider?.model || "";
    const nextValue = modelItems.some((item) => item.value === currentModelName) ? currentModelName : modelItems[0]?.value || "";

    return {
      items: modelItems,
      value: nextValue,
      disabled: modelItems.length === 0
    };
  }, [modelItems, currentModel, sessionProvider]);

  const currentModelLabel = useMemo(() => {
    const providerName = currentModel?.service_provider || sessionProvider?.name || "";
    const modelName = currentModel?.model || sessionProvider?.model || "";
    if (!providerName || !modelName) {
      return "未启用模型";
    }
    return `${providerName} / ${modelName}`;
  }, [currentModel, sessionProvider]);

  const hasDetailContent = receipts.length > 0 || evidence.length > 0 || pendingActions.length > 0 || approvalMessage;

  useEffect(() => {
    if (sessionQuery.data?.snapshot) {
      hydrateSessionSnapshot(sessionQuery.data.snapshot);
    }
  }, [sessionQuery.data, hydrateSessionSnapshot]);

  useEffect(() => {
    if (skillsQuery.data?.skills?.length && enabledSkills.length === 0) {
      setEnabledSkills(skillsQuery.data.skills.filter((item) => item.status === "enabled").map((item) => item.id));
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
      return;
    }

    if (saveTimerRef.current) {
      window.clearTimeout(saveTimerRef.current);
    }

    const providerPatch = currentModel
      ? {
          name: currentModel.service_provider || "",
          base_url: currentModel.api_base || "",
          model: currentModel.model || ""
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
          enabled_skills: enabledSkills
        },
        ui_state: {
          active_detail: activeDetail,
          show_details: showDetails
        }
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
    sessionProvider
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
        content: error.message || "任务执行失败。"
      });
    }
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
    }
  });

  const quickSwitchMutation = useMutation({
    mutationFn: (payload) => selectModel(payload),
    onSuccess: async () => {
      await modelOptionsQuery.refetch();
    }
  });

  const uploadMutation = useMutation({
    mutationFn: async (files) => {
      const formData = new FormData();
      for (const file of files) {
        formData.append("files", file);
      }
      formData.append("chunk_size", "2048");
      formData.append("chunk_overlap", "512");
      return uploadFilesToKnowledge(formData);
    },
    onSuccess: (result) => {
      const importedAttachments = (result.files || []).map((file, index) => createAttachmentFromImportedFile(file, index));
      setAttachedFiles(mergeAttachments(attachedFiles, importedAttachments));
      appendTimeline({
        type: "status",
        content: `已导入 ${result.files?.length || 0} 个文件，可在知识检索模式中使用。`
      });
    },
    onError: (error) => {
      appendTimeline({
        type: "error",
        content: error.message || "文件导入失败。"
      });
    }
  });

  const isBusy = runMutation.isPending || approvalMutation.isPending || quickSwitchMutation.isPending;
  const canRunAgent = currentMode !== "agent" || Boolean(currentModel?.service_provider && currentModel?.model);

  function handleSubmit(event) {
    event.preventDefault();
    const question = draftQuestion.trim();
    if (!question) {
      return;
    }
    if (!canRunAgent) {
      appendTimeline({
        type: "error",
        content: "先去模型配置页启用一个模型。"
      });
      return;
    }

    bootstrapTask({ question, mode: currentMode });
    runMutation.mutate({
      question,
      session_id: sessionId,
      mode: currentMode,
      knowledge_scope: knowledgeScope
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
      session_id: sessionId
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
      session_id: sessionId
    });
  }

  async function handlePickLocalFiles() {
    const desktopBridge = window.northAgentDesktop || window.foxgloveDesktop || window.thinkragDesktop;
    if (!desktopBridge?.pickFiles) {
      appendTimeline({
        type: "error",
        content: "当前环境不支持桌面文件选择，请使用上传并导入。"
      });
      return;
    }

    const result = await desktopBridge.pickFiles({
      title: "选择本地文件",
      multiSelections: true
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
      content: `已选择 ${result.filePaths.length} 个本地文件，读文件模式将优先读取第一项。`
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
    <section className="agent-chat-page rebuilt">
      <header className="agent-chat-toolbar">
        <div className="agent-chat-toolbar-left">
          <span className="toolbar-pill">{currentModelLabel}</span>
        </div>
        <div className="agent-chat-toolbar-right">
          <button
            type="button"
            className="secondary-button subtle-button"
            onClick={() => setShowDetails(!showDetails)}
          >
            {showDetails ? "隐藏详情" : "查看详情"}
          </button>
          <Link className="secondary-button subtle-button link-button" to="/models">
            模型配置
          </Link>
        </div>
      </header>

      <div className={showDetails && hasDetailContent ? "agent-chat-layout rebuilt with-drawer" : "agent-chat-layout rebuilt"}>
        <div className="agent-chat-main rebuilt">
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
          <aside className="agent-detail-drawer rebuilt">
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
  );
}

