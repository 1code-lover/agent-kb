/**
 * 文件功能：
 * - 封装“问答成功后尽力同步历史”的前端工作流。
 * - 统一 history 失败/延迟时的提示文案与本地消息兜底逻辑。
 */

const HISTORY_SYNC_STALE_MESSAGE = "历史仍在刷新，已先展示当前回答。";

export async function queryChatWithBestEffortHistory({
  payload,
  queryChatRequest,
  getHistoryRequest,
  readApiData,
}) {
  const queryResponse = await queryChatRequest(payload);
  const queryData = readApiData(queryResponse) || {};
  let historyMessages = null;
  let historySyncError = "";

  try {
    const historyResponse = await getHistoryRequest(queryData.session_id || payload.session_id);
    const historyData = readApiData(historyResponse) || { messages: [] };
    const nextHistoryMessages = historyData.messages || [];
    const optimisticResult = {
      requestedQuestion: payload.question,
      answer: queryData.answer,
    };

    if (historyIncludesOptimisticResult({ historyMessages: nextHistoryMessages, optimisticResult })) {
      historyMessages = nextHistoryMessages;
    } else {
      historySyncError = HISTORY_SYNC_STALE_MESSAGE;
    }
  } catch (error) {
    historySyncError = error?.message || "历史同步失败，请稍后重试。";
  }

  return {
    ...queryData,
    requestedQuestion: payload.question,
    session_id: queryData.session_id || payload.session_id,
    messages: historyMessages,
    historySyncError,
  };
}

export function buildHistorySyncNotice(historySyncError) {
  if (!historySyncError) {
    return "";
  }
  if (historySyncError === HISTORY_SYNC_STALE_MESSAGE) {
    return `回答已生成，${historySyncError}`;
  }
  return `回答已生成，但历史同步失败：${historySyncError}`;
}

export function resolveChatMessages({ currentMessages = [], result, createLocalMessage }) {
  if (Array.isArray(result?.messages)) {
    return result.messages;
  }

  const nextMessages = Array.isArray(currentMessages) ? [...currentMessages] : [];
  if (result?.requestedQuestion) {
    nextMessages.push(createLocalMessage("user", result.requestedQuestion));
  }
  if (result?.answer) {
    nextMessages.push(createLocalMessage("assistant", result.answer));
  }
  return nextMessages;
}

function normalizeMessageContent(value) {
  return typeof value === "string" ? value.trim() : "";
}

export function historyIncludesOptimisticResult({ historyMessages, optimisticResult }) {
  if (!Array.isArray(historyMessages) || !optimisticResult) {
    return false;
  }

  const expectedQuestion = normalizeMessageContent(optimisticResult.requestedQuestion);
  const expectedAnswer = normalizeMessageContent(optimisticResult.answer);
  if (!expectedQuestion && !expectedAnswer) {
    return true;
  }

  let questionIndex = -1;
  if (expectedQuestion) {
    questionIndex = historyMessages.findIndex(
      (message) => message?.role === "user" && normalizeMessageContent(message?.content) === expectedQuestion,
    );
    if (questionIndex < 0) {
      return false;
    }
  }

  if (!expectedAnswer) {
    return true;
  }

  return historyMessages.some(
    (message, index) =>
      index > questionIndex &&
      message?.role === "assistant" &&
      normalizeMessageContent(message?.content) === expectedAnswer,
  );
}

export function resolveHistoryMessages({ currentMessages = [], historyMessages, optimisticResult = null }) {
  if (!Array.isArray(historyMessages)) {
    return Array.isArray(currentMessages) ? currentMessages : [];
  }

  if (!optimisticResult) {
    return historyMessages;
  }

  return historyIncludesOptimisticResult({ historyMessages, optimisticResult })
    ? historyMessages
    : (Array.isArray(currentMessages) ? currentMessages : []);
}
