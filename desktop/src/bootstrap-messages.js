const { resolveApiBaseUrl, resolveExplicitApiBaseUrlState, shouldAutoStartLocalApi } = require("./runtime-config");

function resolveApiStartupFailure({ env = process.env } = {}) {
  const explicitApiBaseUrl = resolveExplicitApiBaseUrlState(env);
  const autoStartLocalApi = shouldAutoStartLocalApi(env);
  return {
    reason: autoStartLocalApi ? "local_python_api_not_ready" : "explicit_remote_api_unavailable",
    apiBaseUrl: explicitApiBaseUrl.invalid ? explicitApiBaseUrl.raw : resolveApiBaseUrl(env),
    autoStartLocalApi,
  };
}

function buildApiStartupFailureMessage({ logFile, env = process.env } = {}) {
  const failure = resolveApiStartupFailure({ env });
  if (!failure.autoStartLocalApi) {
    return `配置的外部 API 不可用或地址无效：${failure.apiBaseUrl}
请确认 KB_API_BASE_URL 指向的服务已启动且当前机器可访问；桌面端不会自动回退到本地 run_api.py。
日志：${logFile}`;
  }

  return `Python API 启动失败，请检查日志：${logFile}`;
}

function buildRendererStartupFailureMessage({ error, logFile } = {}) {
  const detail = error?.message || "未知错误";
  return `桌面前端入口不可用，无法启动：${detail}
请确认已构建 webapp/dist，或显式设置 KB_WEB_URL 指向可访问的前端入口。
日志：${logFile}`;
}

module.exports = {
  buildApiStartupFailureMessage,
  buildRendererStartupFailureMessage,
  resolveApiStartupFailure,
};
