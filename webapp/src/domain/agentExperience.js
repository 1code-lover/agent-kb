/**
 * 文件功能：
 * - 定义问答工作台的体验模式、问答 payload 和范围摘要规则。
 */

import { requireKbTarget } from "./kbSelection.js";

export const CHAT_RESPONSE_MODES = [
  "compact",
  "refine",
  "tree_summarize",
  "simple_summarize",
  "accumulate",
  "compact_accumulate",
];

export const CHAT_REQUEST_LIMITS = {
  topKMin: 1,
  topKMax: 50,
  topNMin: 1,
  topNMax: 50,
  rerankerModelMaxLength: 128,
};

export const AGENT_EXPERIENCES = [
  {
    value: "basic",
    label: "基础问答",
    description: "保留纯问答体验，但仍需显式选择一个 active 知识库。",
  },
  {
    value: "knowledge",
    label: "知识库问答",
    description: "强调知识库边界、证据和会话范围的单知识库问答。",
  },
  {
    value: "agent",
    label: "Agent 高级模式",
    description: "保留工具、审批、回执与证据等运行时能力。",
  },
];

export function experienceRequiresKb(experience) {
  return experience === "basic" || experience === "knowledge";
}

export function buildChatSessionId({ experience, sessionId, selectedKbId }) {
  const baseSessionId = (sessionId || "desktop-default").trim() || "desktop-default";
  if (experienceRequiresKb(experience)) {
    return `${baseSessionId}-${experience}-${requireKbTarget(selectedKbId)}`;
  }
  return `${baseSessionId}-agent-runtime`;
}

function normalizePositiveInteger(value, { min = 1, max = Number.MAX_SAFE_INTEGER } = {}) {
  const normalized = Number(value);
  if (!Number.isFinite(normalized) || normalized < min || normalized > max) {
    return undefined;
  }
  return Math.floor(normalized);
}

function normalizeOptionalString(value, { maxLength } = {}) {
  if (typeof value !== "string") {
    return undefined;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  if (Number.isFinite(maxLength) && trimmed.length > maxLength) {
    return undefined;
  }
  return trimmed;
}

function normalizeResponseMode(value) {
  const normalized = normalizeOptionalString(value);
  if (!normalized) {
    return undefined;
  }
  return CHAT_RESPONSE_MODES.includes(normalized) ? normalized : undefined;
}

export function normalizeChatRequestOptions(requestOptions = {}) {
  const normalized = {};
  const topK = normalizePositiveInteger(requestOptions.top_k, {
    min: CHAT_REQUEST_LIMITS.topKMin,
    max: CHAT_REQUEST_LIMITS.topKMax,
  });
  const responseMode = normalizeResponseMode(requestOptions.response_mode);
  const topN = normalizePositiveInteger(requestOptions.top_n, {
    min: CHAT_REQUEST_LIMITS.topNMin,
    max: CHAT_REQUEST_LIMITS.topNMax,
  });
  const rerankerModel = normalizeOptionalString(requestOptions.reranker_model, {
    maxLength: CHAT_REQUEST_LIMITS.rerankerModelMaxLength,
  });

  if (topK !== undefined) {
    normalized.top_k = topK;
  }
  if (responseMode !== undefined) {
    normalized.response_mode = responseMode;
  }
  if (typeof requestOptions.use_reranker === "boolean") {
    normalized.use_reranker = requestOptions.use_reranker;
  }
  if (topN !== undefined) {
    normalized.top_n = topN;
  }
  if (rerankerModel !== undefined) {
    normalized.reranker_model = rerankerModel;
  }

  return normalized;
}

export function buildChatPayload({ experience, question, sessionId, selectedKbId, requestOptions }) {
  const trimmedQuestion = typeof question === "string" ? question.trim() : "";
  if (!trimmedQuestion) {
    throw new Error("问题不能为空");
  }

  const payload = {
    question: trimmedQuestion,
    session_id: buildChatSessionId({ experience, sessionId, selectedKbId }),
  };

  if (experienceRequiresKb(experience)) {
    payload.kb_ids = [requireKbTarget(selectedKbId)];
  }

  return {
    ...payload,
    ...normalizeChatRequestOptions(requestOptions),
  };
}

export function buildExperienceSummary({ experience, selectedKb }) {
  if (experience === "basic") {
    if (selectedKb?.kb_id) {
      return `当前为基础问答，只在知识库“${selectedKb.kb_name || selectedKb.kb_id}”范围内检索并回答（kb_id=${selectedKb.kb_id}）。`;
    }
    return "当前为基础问答，请先选择一个 active 知识库后再提问。";
  }
  if (experience === "knowledge") {
    if (selectedKb?.kb_id) {
      return `当前只在知识库“${selectedKb.kb_name || selectedKb.kb_id}”范围内回答，并保留证据与会话范围（kb_id=${selectedKb.kb_id}）。`;
    }
    return "当前为知识库问答，请先选择一个 active 知识库后再提问。";
  }
  if (experience === "agent") {
    return "当前为高级 Agent 模式，可执行工具链、审批和运行时诊断。";
  }
  return "当前问答需要显式绑定一个 active 知识库。";
}
