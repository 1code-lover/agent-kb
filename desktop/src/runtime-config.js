const DEFAULT_API_PORT = 18080;
const API_PORT_ENV_KEYS = ["KB_API_PORT", "NORTHAGENT_API_PORT", "THINKRAG_API_PORT", "FOXGLOVE_API_PORT"];
const API_BASE_URL_ENV_KEYS = ["KB_API_BASE_URL", "NORTHAGENT_API_BASE_URL", "THINKRAG_API_BASE_URL", "FOXGLOVE_API_BASE_URL"];

function firstNonEmptyValue(values) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return "";
}

function trimUrl(value) {
  return typeof value === "string" ? value.trim().replace(/\/+$/, "") : "";
}

function normalizeClientUrl(value) {
  const trimmed = trimUrl(value);
  if (!trimmed) {
    return "";
  }

  try {
    const url = new URL(trimmed);
    if (url.hostname === "0.0.0.0") {
      url.hostname = "127.0.0.1";
    }
    return url.toString().replace(/\/+$/, "");
  } catch {
    return trimmed;
  }
}

function normalizeApiBaseUrl(value) {
  const normalizedUrl = normalizeClientUrl(value);
  if (!normalizedUrl) {
    return "";
  }

  try {
    const parsed = new URL(normalizedUrl);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return "";
    }
    return parsed.toString().replace(/\/+$/, "");
  } catch {
    return "";
  }
}

function resolveExplicitApiBaseUrlSetting(env = process.env) {
  return firstNonEmptyValue(API_BASE_URL_ENV_KEYS.map((key) => env?.[key]));
}

function resolveExplicitApiBaseUrlState(env = process.env) {
  const raw = resolveExplicitApiBaseUrlSetting(env);
  const normalized = normalizeApiBaseUrl(raw);
  return {
    raw,
    normalized,
    invalid: Boolean(raw) && !normalized,
  };
}

function resolveExplicitApiBaseUrl(env = process.env) {
  return resolveExplicitApiBaseUrlState(env).normalized;
}

function resolveExplicitApiBaseUrlStateFromInput(input = process.env) {
  if (typeof input === "string") {
    const raw = input.trim();
    const normalized = normalizeApiBaseUrl(raw);
    return {
      raw,
      normalized,
      invalid: Boolean(raw) && !normalized,
    };
  }

  return resolveExplicitApiBaseUrlState(input);
}

function isLoopbackHostname(hostname) {
  const normalized = typeof hostname === "string" ? hostname.trim().toLowerCase() : "";
  return normalized === "localhost" || normalized === "127.0.0.1" || normalized === "::1" || normalized === "0.0.0.0";
}

function shouldAutoStartLocalApi(input = process.env) {
  const explicitBaseUrl = resolveExplicitApiBaseUrlStateFromInput(input);
  if (!explicitBaseUrl.raw) {
    return true;
  }
  if (explicitBaseUrl.invalid) {
    return false;
  }

  try {
    return isLoopbackHostname(new URL(explicitBaseUrl.normalized).hostname);
  } catch {
    return false;
  }
}

function resolveApiPort(env = process.env) {
  const explicitBaseUrl = resolveExplicitApiBaseUrl(env);
  if (explicitBaseUrl) {
    try {
      const parsed = new URL(explicitBaseUrl);
      if (parsed.port) {
        return Number.parseInt(parsed.port, 10);
      }
      return parsed.protocol === "https:" ? 443 : 80;
    } catch {
      return DEFAULT_API_PORT;
    }
  }

  const rawPort = firstNonEmptyValue(API_PORT_ENV_KEYS.map((key) => env?.[key]));
  const parsedPort = Number.parseInt(rawPort, 10);
  return Number.isFinite(parsedPort) && parsedPort > 0 ? parsedPort : DEFAULT_API_PORT;
}

function resolveApiBaseUrl(env = process.env) {
  const explicitBaseUrl = resolveExplicitApiBaseUrl(env);
  if (explicitBaseUrl) {
    return explicitBaseUrl;
  }
  return `http://127.0.0.1:${resolveApiPort(env)}`;
}

function resolveApiHealthUrl(env = process.env) {
  return `${resolveApiBaseUrl(env)}/api/health`;
}

function toWebSocketOrigin(value) {
  try {
    const url = new URL(value);
    if (url.protocol === "http:") {
      url.protocol = "ws:";
      return url.origin;
    }
    if (url.protocol === "https:") {
      url.protocol = "wss:";
      return url.origin;
    }
  } catch {
    // ignore invalid input
  }
  return "";
}

module.exports = {
  API_BASE_URL_ENV_KEYS,
  API_PORT_ENV_KEYS,
  DEFAULT_API_PORT,
  normalizeClientUrl,
  normalizeApiBaseUrl,
  resolveExplicitApiBaseUrlSetting,
  resolveExplicitApiBaseUrlState,
  resolveExplicitApiBaseUrl,
  shouldAutoStartLocalApi,
  resolveApiPort,
  resolveApiBaseUrl,
  resolveApiHealthUrl,
  toWebSocketOrigin,
};
