export const AGENT_MODES = [
  { value: "agent", label: "Agent" },
  { value: "kb_search", label: "KB Search" },
  { value: "read_file", label: "Read File" },
  { value: "run_cmd", label: "Run Command" }
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
      kb_name: "foxglove_beifen"
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
    lastAnswer: ""
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
      type: "task",
      content: question,
      meta: {
        mode,
        stage: "submitted"
      }
    },
    {
      type: "status",
      content: "Task submitted. Waiting for Agent Runtime.",
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
