import { create } from "zustand";
import {
  appendTimelineEvent,
  buildManualTimeline,
  createWorkspaceState,
  mapAgentRunToTimeline,
  mapSessionSnapshot,
  mergeApprovalTimeline,
  mergeReceipts,
  replaceTimeline
} from "./agentState";

const useAppStore = create((set) => ({
  sessionId: "desktop-default",
  ...createWorkspaceState(),
  setSessionId: (sessionId) => set({ sessionId }),
  setCurrentMode: (currentMode) => set({ currentMode }),
  setKnowledgeScope: (knowledgeScope) => set({ knowledgeScope }),
  setTaskGoal: (taskGoal) => set({ taskGoal }),
  setDraftQuestion: (draftQuestion) => set({ draftQuestion }),
  setRunState: (runState) => set({ runState }),
  setPlan: (plan) => set({ plan: plan || [] }),
  setEvidence: (evidence) => set({ evidence: evidence || [] }),
  setReceipts: (receipts) => set({ receipts: mergeReceipts(receipts) }),
  setTaskState: (taskState) => set({ taskState }),
  setPendingActions: (pendingActions) => set({ pendingActions: pendingActions || [] }),
  setApprovalMessage: (approvalMessage) => set({ approvalMessage }),
  setLastAnswer: (lastAnswer) => set({ lastAnswer }),
  setAttachedFiles: (attachedFiles) => set({ attachedFiles: attachedFiles || [] }),
  setEnabledSkills: (enabledSkills) => set({ enabledSkills: enabledSkills || [] }),
  setActiveDetail: (activeDetail) => set({ activeDetail }),
  setShowDetails: (showDetails) => set({ showDetails }),
  markSessionLoaded: () => set({ sessionLoaded: true }),
  resetWorkspace: () => set((state) => ({ sessionId: state.sessionId, ...createWorkspaceState(), sessionLoaded: true })),
  hydrateSessionSnapshot: (snapshot) => set({ ...mapSessionSnapshot(snapshot) }),
  appendTimeline: (event) =>
    set((state) => ({
      timeline: appendTimelineEvent(state.timeline, event)
    })),
  replaceTimeline: (timeline) => set({ timeline: replaceTimeline(timeline) }),
  bootstrapTask: ({ question, mode }) =>
    set({
      taskGoal: question,
      draftQuestion: question,
      runState: "running",
      approvalMessage: "",
      timeline: replaceTimeline(buildManualTimeline(question, mode))
    }),
  hydrateFromAgentRun: (runData) =>
    set((state) => ({
      timeline: mapAgentRunToTimeline(runData),
      plan: runData?.plan || [],
      evidence: runData?.evidence || [],
      receipts: mergeReceipts(runData?.receipts || []),
      taskState: runData?.task_state || null,
      pendingActions: runData?.pending_actions || [],
      lastAnswer: runData?.answer || "",
      runState: runData?.task_state?.status || "completed",
      draftQuestion: "",
      taskGoal: runData?.question || state.taskGoal,
      showDetails:
        state.showDetails ||
        (runData?.pending_actions || []).length > 0 ||
        (runData?.receipts || []).length > 0 ||
        (runData?.evidence || []).length > 0,
      activeDetail: (runData?.pending_actions || []).length > 0 ? "approvals" : state.activeDetail
    })),
  hydrateFromApproval: (result) =>
    set((state) => ({
      timeline: mergeApprovalTimeline(state.timeline, result),
      plan: result?.plan || state.plan,
      receipts: mergeReceipts(result?.receipts || state.receipts),
      taskState: result?.task_state || state.taskState,
      pendingActions: result?.pending_actions || [],
      lastAnswer: result?.answer || state.lastAnswer,
      approvalMessage: result?.status ? `审批结果：${result.status}` : state.approvalMessage,
      runState: result?.task_state?.status || state.runState,
      showDetails: true,
      activeDetail: "receipts"
    }))
}));

export default useAppStore;

