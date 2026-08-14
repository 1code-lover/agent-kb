/**
 * 文件功能：
 * - 将 /api/model/options 返回的 model_health 归一为页面可直接展示的摘要对象。
 */

function normalizeModelHealthState(rawState) {
  if (typeof rawState !== "string") {
    return "unknown";
  }

  const nextState = rawState.trim().toLowerCase();
  return nextState || "unknown";
}

function formatModelLabel(info) {
  const providerSource = typeof info?.service_provider === "string" ? info.service_provider : info?.current_provider;
  const modelSource = typeof info?.model === "string" ? info.model : info?.current_model;
  const provider = typeof providerSource === "string" ? providerSource.trim() : "";
  const model = typeof modelSource === "string" ? modelSource.trim() : "";
  if (!provider && !model) {
    return "";
  }
  if (!provider) {
    return model;
  }
  if (!model) {
    return provider;
  }
  return `${provider} / ${model}`;
}

function formatReason(kind) {
  const normalized = typeof kind === "string" ? kind.trim().toLowerCase() : "";
  if (!normalized) {
    return "";
  }

  const labels = {
    quota_exhausted: "额度耗尽",
    forbidden: "403 禁止访问",
    unauthorized: "401 未授权",
    model_unavailable: "模型不可用",
    network_error: "网络异常",
    request_incompatible: "请求超出模型能力",
    unknown: "未知错误",
  };
  return labels[normalized] || normalized;
}

function formatFallbackAttempts(attempts, attemptSummary) {
  const summaryTotal = Number.isInteger(attemptSummary?.total) ? attemptSummary.total : 0;
  if (summaryTotal > 0) {
    const reachableCount = Number.isInteger(attemptSummary?.reachable_count) ? attemptSummary.reachable_count : 0;
    const failedCount = Number.isInteger(attemptSummary?.failed_count) ? attemptSummary.failed_count : 0;
    const ollamaCount = Number.isInteger(attemptSummary?.ollama_candidate_count) ? attemptSummary.ollama_candidate_count : 0;
    const ollamaHint = ollamaCount ? `，Ollama 候选 ${ollamaCount} 个` : "";
    const lastLabel = formatModelLabel({
      service_provider: attemptSummary?.last_provider,
      model: attemptSummary?.last_model,
    });
    const lastDetail = typeof attemptSummary?.last_detail === "string" ? attemptSummary.last_detail.trim() : "";
    const lastText = lastLabel ? `；最近一次：${lastLabel}${lastDetail ? `（${lastDetail}）` : ""}` : "";
    return `已探测 ${summaryTotal} 个候选：${reachableCount} 个可用，${failedCount} 个不可用${ollamaHint}${lastText}`;
  }

  if (!Array.isArray(attempts) || attempts.length === 0) {
    return "";
  }

  const lastAttempt = attempts[attempts.length - 1] || {};
  const attemptedCount = attempts.length;
  const lastLabel = formatModelLabel(lastAttempt);
  const lastStatus = lastAttempt.reachable ? "可用" : lastAttempt.detail || "不可用";
  const hasOllamaCandidate = attempts.some((item) => item?.service_provider === "Ollama");
  const ollamaHint = hasOllamaCandidate ? "，包含本地 Ollama 候选" : "";
  if (!lastLabel) {
    return `已探测 ${attemptedCount} 个候选${ollamaHint}，最近一次结果：${lastStatus}`;
  }
  return `已探测 ${attemptedCount} 个候选${ollamaHint}，最近一次：${lastLabel}（${lastStatus}）`;
}

function formatOllamaUnavailableHint(attemptSummary) {
  const lastDetail = typeof attemptSummary?.last_detail === "string" ? attemptSummary.last_detail.trim() : "";
  const lastModel = typeof attemptSummary?.last_model === "string" ? attemptSummary.last_model.trim() : "";
  if (lastDetail === "ollama_no_models") {
    return "Ollama 已连接但没有可切换模型，请先运行 ollama pull qwen2.5:7b，或在模型配置里填入已安装模型。";
  }
  if (lastDetail === "model_not_found" && lastModel) {
    return `Ollama 已连接但 ${lastModel} 未安装，请运行 ollama pull ${lastModel}，或选择已安装模型。`;
  }
  if (lastDetail === "ollama_unreachable" || lastDetail.startsWith("ollama_http_")) {
    return "请先启动 Ollama，确认 http://localhost:11434 可访问，或在模型配置中修正 Ollama 地址；也可以切换到云端可用供应商。";
  }
  return "本地 Ollama 候选暂不可用，请确认 Ollama 已启动且目标模型已拉取；也可以补齐云端可用供应商后重试。";
}

export function buildModelHealthSummary(modelHealth) {
  const state = normalizeModelHealthState(modelHealth?.state);
  const currentLabel = formatModelLabel(modelHealth);
  const fallbackFrom = formatModelLabel(modelHealth?.fallback_from);
  const fallbackTo = formatModelLabel(modelHealth?.fallback_to);
  const lastError = typeof modelHealth?.last_error === "string" ? modelHealth.last_error.trim() : "";
  const reason = formatReason(modelHealth?.last_error_kind);
  const candidateCount = Number.isInteger(modelHealth?.candidate_count) ? modelHealth.candidate_count : 0;
  const fallbackAttempts = Array.isArray(modelHealth?.fallback_attempts) ? modelHealth.fallback_attempts : [];
  const attemptSummary = modelHealth?.fallback_attempt_summary || {};
  const probeSummary = formatFallbackAttempts(fallbackAttempts, attemptSummary);
  const ollamaCandidateCount = Number.isInteger(attemptSummary?.ollama_candidate_count) ? attemptSummary.ollama_candidate_count : 0;
  const ollamaReachableCount = Number.isInteger(attemptSummary?.ollama_reachable_count) ? attemptSummary.ollama_reachable_count : 0;

  if (state === "healthy") {
    return {
      state,
      tone: "success",
      chipLabel: "模型健康",
      title: "模型已就绪",
      summary: currentLabel ? `当前启用 ${currentLabel}` : "当前模型已就绪",
      detail: "最近一次检查没有发现可恢复错误。",
      currentLabel,
    };
  }

  if (state === "fallback_applied") {
    const fallbackToProvider = typeof modelHealth?.fallback_to?.service_provider === "string" ? modelHealth.fallback_to.service_provider : "";
    const fallbackHint =
      fallbackToProvider === "Ollama"
        ? "已自动切换到本地 Ollama 候选模型，后续请求会继续沿用当前配置。"
        : "已自动切换到可用模型，后续请求会继续沿用当前配置。";
    return {
      state,
      tone: "warning",
      chipLabel: "已自动切换",
      title: "模型已自动切换",
      summary: currentLabel ? `当前正在使用 ${currentLabel}` : "当前正在使用备用模型",
      actionHint: fallbackHint,
      detail:
        [fallbackFrom ? `已从 ${fallbackFrom} 切换` : "", fallbackTo ? `到 ${fallbackTo}` : "", reason ? `原因：${reason}` : ""]
          .filter(Boolean)
          .join("，") || "已完成自动 fallback。",
      probeSummary: probeSummary || (candidateCount ? `已探测 ${candidateCount} 个候选。` : ""),
      currentLabel,
      fallbackFrom,
      fallbackTo,
      transitionLabel: fallbackFrom || fallbackTo ? `${fallbackFrom || "未知来源"} → ${fallbackTo || "未知目标"}` : "",
    };
  }

  if (state === "degraded") {
    return {
      state,
      tone: "warning",
      chipLabel: "模型异常",
      title: "模型出现异常",
      summary: currentLabel ? `当前启用 ${currentLabel}` : "当前模型出现异常",
      actionHint: "请检查额度、权限或网络，必要时手动切换到可用模型。",
      detail:
        [reason ? `最近错误类型：${reason}` : "", lastError ? `最近错误：${lastError}` : ""]
          .filter(Boolean)
          .join("，") || "模型最近一次调用出现异常，但仍保留当前配置。",
      probeSummary: probeSummary || (candidateCount ? `已探测 ${candidateCount} 个候选。` : ""),
      currentLabel,
    };
  }

  if (state === "unavailable") {
    const unavailableHint =
      ollamaCandidateCount > 0 && ollamaReachableCount === 0
        ? formatOllamaUnavailableHint(attemptSummary)
        : "先补齐可用供应商或修复当前模型，再重试问答。";
    return {
      state,
      tone: "danger",
      chipLabel: "无可用模型",
      title: "当前无可用模型",
      summary: "未找到可直接切换的可用模型，请先检查配置或补齐供应商。",
      actionHint: unavailableHint,
      detail:
        [reason ? `最近错误类型：${reason}` : "", lastError ? `最近错误：${lastError}` : "", candidateCount ? `候选数：${candidateCount}` : ""]
          .filter(Boolean)
          .join("，") || "自动探活后没有找到可用候选。",
      probeSummary: probeSummary || (candidateCount ? `已探测 ${candidateCount} 个候选。` : ""),
      currentLabel,
    };
  }

  return {
    state: "unknown",
    tone: "muted",
    chipLabel: "状态未知",
    title: "模型状态未知",
    summary: currentLabel ? `当前启用 ${currentLabel}` : "尚未读取到可用模型状态",
    actionHint: "先按当前配置继续使用，必要时到模型配置页重新探活。",
    detail: "还没有写入健康检查结果，先按当前配置继续使用。",
    probeSummary: probeSummary || "",
    currentLabel,
  };
}
