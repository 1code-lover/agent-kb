import { useEffect, useMemo } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import AgentApprovalPanel from "../components/agent/AgentApprovalPanel";
import AgentEvidencePanel from "../components/agent/AgentEvidencePanel";
import AgentInputPanel from "../components/agent/AgentInputPanel";
import AgentReceiptsPanel from "../components/agent/AgentReceiptsPanel";
import AgentTaskStateBar from "../components/agent/AgentTaskStateBar";
import AgentTimeline from "../components/agent/AgentTimeline";
import { approveAgentAction, getAgentReceipts, getPendingActions, runAgent } from "../api/agent";
import { getModelOptions, selectModel } from "../api/models";
import useAppStore from "../store/appStore";

export default function AgentPage() {
  const sessionId = useAppStore((state) => state.sessionId);
  const currentMode = useAppStore((state) => state.currentMode);
  const knowledgeScope = useAppStore((state) => state.knowledgeScope);
  const draftQuestion = useAppStore((state) => state.draftQuestion);
  const taskGoal = useAppStore((state) => state.taskGoal);
  const runState = useAppStore((state) => state.runState);
  const timeline = useAppStore((state) => state.timeline);
  const evidence = useAppStore((state) => state.evidence);
  const receipts = useAppStore((state) => state.receipts);
  const taskState = useAppStore((state) => state.taskState);
  const pendingActions = useAppStore((state) => state.pendingActions);
  const approvalMessage = useAppStore((state) => state.approvalMessage);

  const setCurrentMode = useAppStore((state) => state.setCurrentMode);
  const setDraftQuestion = useAppStore((state) => state.setDraftQuestion);
  const setReceipts = useAppStore((state) => state.setReceipts);
  const setPendingActions = useAppStore((state) => state.setPendingActions);
  const setApprovalMessage = useAppStore((state) => state.setApprovalMessage);
  const setRunState = useAppStore((state) => state.setRunState);
  const appendTimeline = useAppStore((state) => state.appendTimeline);
  const bootstrapTask = useAppStore((state) => state.bootstrapTask);
  const hydrateFromAgentRun = useAppStore((state) => state.hydrateFromAgentRun);
  const hydrateFromApproval = useAppStore((state) => state.hydrateFromApproval);

  const receiptsQuery = useQuery({
    queryKey: ["agent-receipts", sessionId],
    queryFn: () => getAgentReceipts(sessionId, 20)
  });

  const pendingQuery = useQuery({
    queryKey: ["agent-pending", sessionId],
    queryFn: () => getPendingActions(sessionId)
  });

  const modelOptionsQuery = useQuery({
    queryKey: ["agent-model-options"],
    queryFn: getModelOptions
  });

  const currentModel = modelOptionsQuery.data?.current_llm_info || null;
  const providers = modelOptionsQuery.data?.providers || {};
  const currentProviderModels = currentModel?.service_provider
    ? providers[currentModel.service_provider]?.models || []
    : [];

  const currentModelLabel = useMemo(() => {
    if (!currentModel?.service_provider || !currentModel?.model) {
      return "";
    }
    return `${currentModel.service_provider} / ${currentModel.model}`;
  }, [currentModel]);

  useEffect(() => {
    if (receiptsQuery.data?.receipts) {
      setReceipts(receiptsQuery.data.receipts);
    }
  }, [receiptsQuery.data, setReceipts]);

  useEffect(() => {
    if (pendingQuery.data?.pending_actions) {
      setPendingActions(pendingQuery.data.pending_actions);
    }
  }, [pendingQuery.data, setPendingActions]);

  const runMutation = useMutation({
    mutationFn: (payload) => runAgent(payload),
    onSuccess: (data) => {
      hydrateFromAgentRun(data);
    },
    onError: (error) => {
      setRunState("failed");
      appendTimeline({
        type: "error",
        content: error.message || "Task failed."
      });
    }
  });

  const approvalMutation = useMutation({
    mutationFn: (payload) => approveAgentAction(payload),
    onSuccess: (result) => {
      setApprovalMessage(`Approval processed: ${result.status}`);
      hydrateFromApproval(result);
    },
    onError: (error) => {
      setApprovalMessage(error.message || "Approval failed.");
    }
  });

  const quickSwitchMutation = useMutation({
    mutationFn: (payload) => selectModel(payload),
    onSuccess: async () => {
      await modelOptionsQuery.refetch();
    }
  });

  const isBusy = runMutation.isPending || approvalMutation.isPending;

  function handleSubmit(event) {
    event.preventDefault();
    const question = draftQuestion.trim();
    if (!question) {
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

  return (
    <section className="agent-workspace">
      <header className="workspace-hero">
        <div>
          <p className="hero-eyebrow">Desktop Agent Workspace</p>
          <h2>Foxglove Desktop Agent</h2>
          <p className="hero-copy">
            The home page now focuses on task execution. Agent mode uses the currently selected
            model directly. Knowledge lookup stays available as the `kb_search` tool.
          </p>
        </div>
      </header>

      <AgentTaskStateBar
        sessionId={sessionId}
        runState={runState}
        taskGoal={taskGoal}
        taskState={taskState}
        approvalCount={pendingActions.length}
        currentModelLabel={currentModelLabel}
      />

      {currentModel && currentProviderModels.length > 0 && (
        <section className="agent-panel">
          <div className="panel-heading">
            <div>
              <p className="panel-eyebrow">Quick Switch</p>
              <h3>Switch Current Model</h3>
            </div>
          </div>
          <div className="mode-switcher">
            {currentProviderModels.map((modelName) => (
              <button
                key={modelName}
                type="button"
                className={modelName === currentModel.model ? "mode-chip active" : "mode-chip"}
                disabled={quickSwitchMutation.isPending}
                onClick={() =>
                  quickSwitchMutation.mutate({
                    service_provider: currentModel.service_provider,
                    model: modelName,
                    api_base: currentModel.api_base,
                    api_key: currentModel.api_key
                  })
                }
              >
                {modelName}
              </button>
            ))}
          </div>
        </section>
      )}

      <div className="agent-main-grid">
        <div className="agent-primary-column">
          <AgentInputPanel
            question={draftQuestion}
            mode={currentMode}
            knowledgeScope={knowledgeScope}
            disabled={isBusy}
            onQuestionChange={setDraftQuestion}
            onModeChange={setCurrentMode}
            onSubmit={handleSubmit}
          />
          <AgentTimeline timeline={timeline} />
        </div>

        <div className="agent-secondary-column">
          <AgentApprovalPanel
            pendingActions={pendingActions}
            approvalMessage={approvalMessage}
            disabled={approvalMutation.isPending}
            onReview={(payload) => approvalMutation.mutate(payload)}
          />
          <AgentEvidencePanel evidence={evidence} />
          <AgentReceiptsPanel receipts={receipts} />
        </div>
      </div>
    </section>
  );
}
