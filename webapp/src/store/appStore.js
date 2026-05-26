/**
 * 文件功能：
 * - 管理 Agent 工作台的全局会话状态。
 *
 * 执行逻辑：
 * 1. 维护 sessionId 与工作台运行态。
 * 2. 提供时间线、审批、任务目标的读写动作。
 */

import { create } from "zustand";
import {
  appendTimelineEvent,
  createWorkspaceState,
  mapAgentRunToTimeline
} from "./agentState";

const useAppStore = create((set) => ({
  sessionId: "desktop-default",
  ...createWorkspaceState(),
  setSessionId: (sessionId) => set({ sessionId }),
  setTaskGoal: (taskGoal) => set({ taskGoal }),
  setRunState: (runState) => set({ runState }),
  setPlan: (plan) => set({ plan }),
  setEvidence: (evidence) => set({ evidence }),
  setTaskState: (taskState) => set({ taskState }),
  setPendingActions: (pendingActions) => set({ pendingActions }),
  setApprovalMessage: (approvalMessage) => set({ approvalMessage }),
  resetWorkspace: () => set(createWorkspaceState()),
  appendTimeline: (event) =>
    set((state) => ({
      timeline: appendTimelineEvent(state.timeline, event)
    })),
  appendTimelineBatch: (events) =>
    set((state) => {
      let timeline = state.timeline;
      for (const event of events) {
        timeline = appendTimelineEvent(timeline, event);
      }
      return { timeline };
    }),
  hydrateFromAgentRun: (question, runData) =>
    set((state) => {
      const events = mapAgentRunToTimeline(question, runData);
      let timeline = state.timeline;
      for (const event of events) {
        timeline = appendTimelineEvent(timeline, event);
      }
      return {
        timeline,
        plan: runData?.plan || [],
        evidence: runData?.evidence || [],
        taskState: runData?.task_state || null
      };
    })
}));

export default useAppStore;
