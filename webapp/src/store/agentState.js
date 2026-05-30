export const AGENT_MODES = [
  { value: "agent", label: "Agent" },
  { value: "kb_search", label: "知识检索" },
  { value: "read_file", label: "读文件" },
  { value: "run_cmd", label: "命令执行" }
];

function normalizeTimelineItem(item, index) {
  return {
    seq: index + 1,
    type: item?.type || "status",
    content: item?.content || "",
    meta: item?.meta || null
  };
}

export function createWorkspaceState() {
  return {
    currentMode: "agent",
    knowledgeScope: {
      kb_id: "default",
      kb_name: "NorthAgent Workspace"
    },
    taskGoal: "",
    draftQuestion: "",
    runState: "idle",
    timeline: [],
    plan: [],
    evidence: [],
    receipts: [],
    taskState: null,
    pendingActions: [],
    approvalMessage: "",
    lastAnswer: "",
    attachedFiles: [],
    enabledSkills: ["planner", "file_context", "safe_command"],
    activeDetail: "receipts",
    showDetails: false,
    sessionLoaded: false
  };
}

export function appendTimelineEvent(timeline, event) {
  return [...timeline, normalizeTimelineItem(event, timeline.length)];
}

export function replaceTimeline(timeline) {
  return (timeline || []).map((item, index) => normalizeTimelineItem(item, index));
}

export function buildManualTimeline(question, mode) {
  return [
    {
      type: "user",
      content: question,
      meta: {
        mode,
        stage: "submitted"
      }
    },
    {
      type: "status",
      content: "任务已提交，正在等待 Agent Runtime 执行。",
      meta: {
        mode
      }
    }
  ];
}

export function mapAgentRunToTimeline(runData) {
  const remoteTimeline = replaceTimeline(runData?.timeline || []);
  if (remoteTimeline.length > 0) {
    return remoteTimeline;
  }

  const fallback = [];
  if (runData?.question) {
    fallback.push({ type: "user", content: runData.question });
  }
  if (runData?.answer) {
    fallback.push({ type: "assistant", content: runData.answer });
  }

  for (const step of runData?.steps || []) {
    fallback.push({
      type: "step",
      content: step?.summary || step?.title || step?.step || "unknown-step",
      meta: {
        name: step?.step || "",
        title: step?.title || "",
        status: step?.status || "pending",
        riskLevel: step?.risk_level || null,
        receiptId: step?.receipt_id || null,
        actionId: step?.action_id || null,
        evidenceIds: step?.evidence_ids || []
      }
    });
  }

  return replaceTimeline(fallback);
}

export function mergeReceipts(receipts) {
  return [...(receipts || [])].sort((left, right) => {
    const leftTime = Date.parse(left?.created_at || 0);
    const rightTime = Date.parse(right?.created_at || 0);
    return rightTime - leftTime;
  });
}

export function mergeApprovalTimeline(existingTimeline, result) {
  const merged = [...(existingTimeline || [])];
  const approvalTimeline = replaceTimeline(result?.timeline || []);
  for (const item of approvalTimeline) {
    merged.push({
      type: item.type,
      content: item.content,
      meta: item.meta
    });
  }
  return replaceTimeline(merged);
}

export function buildReadFileTemplate() {
  return "C:\\\\path\\\\to\\\\file.txt";
}

export function mapSessionSnapshot(snapshot) {
  const workspace = snapshot?.workspace || {};
  const uiState = snapshot?.ui_state || {};
  return {
    currentMode: workspace.current_mode || "agent",
    knowledgeScope: workspace.knowledge_scope || { kb_id: "default", kb_name: "NorthAgent Workspace" },
    taskGoal: workspace.task_goal || "",
    draftQuestion: workspace.draft_question || "",
    runState: workspace.run_state || "idle",
    timeline: replaceTimeline(snapshot?.timeline || []),
    plan: snapshot?.plan || [],
    evidence: snapshot?.evidence || [],
    receipts: mergeReceipts(snapshot?.receipts || []),
    taskState: snapshot?.task_state || null,
    pendingActions: snapshot?.pending_actions || [],
    approvalMessage: snapshot?.approval_message || "",
    lastAnswer: workspace.last_answer || "",
    attachedFiles: workspace.attached_files || [],
    enabledSkills: workspace.enabled_skills || ["planner", "file_context", "safe_command"],
    activeDetail: uiState.active_detail || "receipts",
    showDetails: Boolean(uiState.show_details),
    sessionLoaded: true
  };
}

