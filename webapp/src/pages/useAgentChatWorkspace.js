import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { getHistory, queryChat } from "../api/chat.js";
import { getSettings } from "../api/settings.js";
import { previewItem } from "../api/evidence.js";
import { getModelOptions } from "../api/models.js";
import { readApiData } from "../api/response.js";
import { buildChatPayload, buildChatSessionId, CHAT_RESPONSE_MODES } from "../domain/agentExperience.js";
import { buildModelHealthSummary } from "../domain/modelHealth.js";
import {
  buildHistorySyncNotice,
  historyIncludesOptimisticResult,
  queryChatWithBestEffortHistory,
  resolveChatMessages,
  resolveHistoryMessages,
} from "../domain/chatWorkflow.js";

function safeBuildChatSessionId({ experience, sessionId, selectedKbId }) {
  try {
    return buildChatSessionId({ experience, sessionId, selectedKbId });
  } catch {
    return "";
  }
}

function createLocalChatMessage(role, content) {
  return {
    id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    content,
    created_at: new Date().toISOString(),
  };
}

function buildChatRequestOptions(settings) {
  if (!settings) {
    return {
      top_k: "",
      response_mode: "",
      use_reranker: undefined,
      top_n: "",
      reranker_model: "",
    };
  }

  const responseMode = typeof settings.response_mode === "string" && CHAT_RESPONSE_MODES.includes(settings.response_mode)
    ? settings.response_mode
    : "";

  return {
    top_k: settings.top_k ?? "",
    response_mode: responseMode,
    use_reranker: typeof settings.use_reranker === "boolean" ? settings.use_reranker : undefined,
    top_n: settings.top_n ?? "",
    reranker_model: settings.reranker_model ?? "",
  };
}

export function useAgentChatWorkspace({ experience, sessionId, selectedKbId }) {
  const [chatQuestion, setChatQuestion] = useState("");
  const [chatMessages, setChatMessages] = useState([]);
  const [chatSources, setChatSources] = useState([]);
  const [chatEvidence, setChatEvidence] = useState([]);
  const [chatPreview, setChatPreview] = useState(null);
  const [chatPreviewError, setChatPreviewError] = useState("");
  const [chatError, setChatError] = useState("");
  const [chatNotice, setChatNotice] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState("");
  const [optimisticHistoryResult, setOptimisticHistoryResult] = useState(null);
  const [chatRequestOptions, setChatRequestOptions] = useState(() => buildChatRequestOptions(null));
  const [requestOptionsHydrated, setRequestOptionsHydrated] = useState(false);

  const settingsQuery = useQuery({
    queryKey: ["agent-chat-request-settings"],
    queryFn: getSettings,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 60000,
  });

  const modelOptionsQuery = useQuery({
    queryKey: ["agent-model-options"],
    queryFn: getModelOptions,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 60000,
  });

  useEffect(() => {
    const settings = readApiData(settingsQuery.data)?.settings || null;
    if (settings && !requestOptionsHydrated) {
      setChatRequestOptions(buildChatRequestOptions(settings));
      setRequestOptionsHydrated(true);
    }
  }, [requestOptionsHydrated, settingsQuery.data]);

  const currentModel = modelOptionsQuery.data?.current_llm_info || null;
  const modelHealthSummary = useMemo(
    () => buildModelHealthSummary(modelOptionsQuery.data?.model_health || null),
    [modelOptionsQuery.data?.model_health],
  );
  const currentModelLabel =
    currentModel?.service_provider && currentModel?.model
      ? currentModel.service_provider + " / " + currentModel.model
      : "未启用模型";
  const modelReady = Boolean(currentModel?.service_provider && currentModel?.model);

  const chatSessionId = useMemo(
    () => safeBuildChatSessionId({ experience, sessionId, selectedKbId }),
    [experience, selectedKbId, sessionId],
  );

  const historyQuery = useQuery({
    queryKey: ["agent-chat-history", chatSessionId],
    enabled: experience !== "agent" && Boolean(chatSessionId),
    queryFn: async () => {
      const response = await getHistory(chatSessionId);
      return readApiData(response) || { session_id: chatSessionId, messages: [] };
    },
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 0,
  });

  useEffect(() => {
    const historyMessages = historyQuery.data?.messages;
    const containsOptimisticResult = historyIncludesOptimisticResult({
      historyMessages,
      optimisticResult: optimisticHistoryResult,
    });

    setChatMessages((currentMessages) => resolveHistoryMessages({
      currentMessages,
      historyMessages,
      optimisticResult: optimisticHistoryResult,
    }));

    if (containsOptimisticResult) {
      setOptimisticHistoryResult(null);
    }
  }, [historyQuery.data, optimisticHistoryResult]);

  useEffect(() => {
    setChatMessages([]);
    setChatError("");
    setChatNotice("");
    setPendingQuestion("");
    setOptimisticHistoryResult(null);
    setChatSources([]);
    setChatEvidence([]);
    setChatPreview(null);
    setChatPreviewError("");
  }, [chatSessionId, experience]);

  const chatMutation = useMutation({
    mutationFn: async (payload) => queryChatWithBestEffortHistory({
      payload,
      queryChatRequest: queryChat,
      getHistoryRequest: getHistory,
      readApiData,
    }),
    onMutate: (payload) => {
      setChatError("");
      setChatNotice("");
      setPendingQuestion(payload.question);
      setChatPreview(null);
      setChatPreviewError("");
    },
    onSuccess: async (result) => {
      setPendingQuestion("");
      setChatQuestion("");
      setChatSources(result.sources || []);
      setChatEvidence(result.evidence || []);
      setChatMessages((current) => resolveChatMessages({
        currentMessages: current,
        result,
        createLocalMessage: createLocalChatMessage,
      }));
      setOptimisticHistoryResult(
        Array.isArray(result.messages)
          ? null
          : {
            requestedQuestion: result.requestedQuestion,
            answer: result.answer,
          },
      );
      setChatNotice(buildHistorySyncNotice(result.historySyncError));
      historyQuery.refetch();
      await modelOptionsQuery.refetch();
    },
    onError: (error) => {
      setPendingQuestion("");
      setChatNotice("");
      setChatError(error.message || "问答请求失败，请稍后重试。");
    },
  });

  const previewMutation = useMutation({
    mutationFn: async (item) => {
      const targetKbId = item?.kb_id || selectedKbId;
      if (!targetKbId) {
        throw new Error("当前证据缺少知识库范围，无法预览。");
      }

      const response = await previewItem(item, targetKbId);
      return readApiData(response) || null;
    },
    onMutate: () => {
      setChatPreviewError("");
    },
    onSuccess: (preview) => {
      setChatPreview(preview);
    },
    onError: (error) => {
      setChatPreview(null);
      setChatPreviewError(error.message || "证据预览失败，请稍后重试。");
    },
  });

  const handlePreviewEvidence = useCallback(
    (item) => {
      previewMutation.mutate(item);
    },
    [previewMutation],
  );

  const handleChatSubmit = useCallback(
    (event) => {
      event?.preventDefault?.();
      if (!modelReady) {
        setChatError("请先到模型配置页启用一个模型，再开始问答。");
        return;
      }

      try {
        const payload = buildChatPayload({
          experience,
          question: chatQuestion,
          sessionId,
          selectedKbId,
          requestOptions: chatRequestOptions,
        });
        chatMutation.mutate(payload);
      } catch (error) {
        setChatError(error.message || "提问参数无效。");
      }
    },
    [chatMutation, chatQuestion, chatRequestOptions, experience, modelReady, selectedKbId, sessionId],
  );

  return {
    currentModelLabel,
    modelHealthSummary,
    modelReady,
    question: chatQuestion,
    setQuestion: setChatQuestion,
    requestOptions: chatRequestOptions,
    setRequestOptions: setChatRequestOptions,
    resetRequestOptions: () => {
      setChatRequestOptions(buildChatRequestOptions(readApiData(settingsQuery.data)?.settings || null));
      setRequestOptionsHydrated(true);
    },
    requestOptionsLoading: settingsQuery.isLoading || settingsQuery.isFetching,
    messages: chatMessages,
    sources: chatSources,
    evidence: chatEvidence,
    pendingQuestion,
    error: chatError,
    chatNotice,
    historyLoading: historyQuery.isLoading || historyQuery.isFetching,
    chatBusy: chatMutation.isPending,
    preview: chatPreview,
    previewLoading: previewMutation.isPending,
    previewError: chatPreviewError,
    submitChat: handleChatSubmit,
    previewEvidence: handlePreviewEvidence,
  };
}
