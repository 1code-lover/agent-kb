/**
 * 文件功能：
 * - 定义问答工作台的体验模式、问答 payload 和范围摘要规则。
 */

import { requireKbTarget } from "./kbSelection.js";

export const AGENT_EXPERIENCES = [
  {
    value: "basic",
    label: "基础问答",
    description: "不限定单个知识库范围，按当前可用索引全局检索。",
  },
  {
    value: "knowledge",
    label: "知识库问答",
    description: "先选择一个 active 知识库，再在该范围内提问。",
  },
  {
    value: "agent",
    label: "Agent 高级模式",
    description: "保留工具、审批、回执与证据等运行时能力。",
  },
];

export function buildChatSessionId({ experience, sessionId, selectedKbId }) {
  const baseSessionId = (sessionId || "desktop-default").trim() || "desktop-default";
  if (experience === "knowledge") {
    return `${baseSessionId}-chat-${requireKbTarget(selectedKbId)}`;
  }
  return `${baseSessionId}-chat-all`;
}

export function buildChatPayload({ experience, question, sessionId, selectedKbId }) {
  const trimmedQuestion = typeof question === "string" ? question.trim() : "";
  if (!trimmedQuestion) {
    throw new Error("问题不能为空");
  }

  const payload = {
    question: trimmedQuestion,
    session_id: buildChatSessionId({ experience, sessionId, selectedKbId }),
  };

  if (experience === "knowledge") {
    payload.kb_ids = [requireKbTarget(selectedKbId)];
  }

  return payload;
}

export function buildExperienceSummary({ experience, selectedKb }) {
  if (experience === "knowledge") {
    if (selectedKb?.kb_id) {
      return `当前只在知识库“${selectedKb.kb_name || selectedKb.kb_id}”范围内回答（kb_id=${selectedKb.kb_id}）。`;
    }
    return "当前为知识库问答，请先选择一个 active 知识库后再提问。";
  }
  if (experience === "agent") {
    return "当前为高级 Agent 模式，可执行工具链、审批和运行时诊断。";
  }
  return "当前为基础问答，将在全部知识范围内检索并回答。";
}
