const fs = require("node:fs");
const path = require("node:path");
const { normalizeClientUrl } = require("./runtime-config");

const DEFAULT_RENDERER_PORT = 5173;
const WEB_URL_ENV_KEYS = ["KB_WEB_URL", "NORTHAGENT_WEB_URL", "THINKRAG_WEB_URL", "FOXGLOVE_WEB_URL"];
const WEB_PORT_ENV_KEYS = ["KB_WEB_PORT", "NORTHAGENT_WEB_PORT", "THINKRAG_WEB_PORT", "FOXGLOVE_WEB_PORT", "VITE_PORT"];

function firstNonEmptyValue(values) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return "";
}

function normalizeUrl(value) {
  return normalizeClientUrl(value);
}

function resolveRendererPort(env = process.env) {
  const rawPort = firstNonEmptyValue(WEB_PORT_ENV_KEYS.map((key) => env?.[key]));
  const parsedPort = Number.parseInt(rawPort, 10);
  return Number.isFinite(parsedPort) && parsedPort > 0 ? parsedPort : DEFAULT_RENDERER_PORT;
}

function resolveRendererDevUrl(env = process.env) {
  const explicitUrl = normalizeUrl(firstNonEmptyValue(WEB_URL_ENV_KEYS.map((key) => env?.[key])));
  if (explicitUrl) {
    return explicitUrl;
  }
  return `http://127.0.0.1:${resolveRendererPort(env)}`;
}

function resolveRendererUrlSource(key) {
  if (key === "KB_WEB_URL") {
    return "kb-env";
  }
  if (key === "NORTHAGENT_WEB_URL") {
    return "northagent-env";
  }
  if (key === "THINKRAG_WEB_URL") {
    return "thinkrag-env";
  }
  if (key === "FOXGLOVE_WEB_URL") {
    return "foxglove-env";
  }
  return "legacy-env";
}

function resolveRendererEntry({ env = process.env, resourceRoot, fsModule = fs, isPackaged = false } = {}) {
  if (!resourceRoot) {
    throw new Error("resourceRoot is required");
  }

  for (const key of WEB_URL_ENV_KEYS) {
    const explicitUrl = normalizeUrl(env?.[key]);
    if (explicitUrl) {
      try {
        new URL(explicitUrl);
      } catch {
        throw new Error(`renderer URL from ${key} is invalid: ${explicitUrl}`);
      }
      return {
        type: "url",
        value: explicitUrl,
        source: resolveRendererUrlSource(key),
      };
    }
  }

  const distIndexPath = path.join(resourceRoot, "webapp", "dist", "index.html");
  if (fsModule.existsSync(distIndexPath)) {
    return {
      type: "file",
      value: distIndexPath,
      source: "dist",
    };
  }

  if (isPackaged) {
    throw new Error(`packaged renderer entry is missing: ${distIndexPath}; build webapp/dist or set KB_WEB_URL explicitly`);
  }

  const hasCustomPort = resolveRendererPort(env) !== DEFAULT_RENDERER_PORT;
  return {
    type: "url",
    value: resolveRendererDevUrl(env),
    source: hasCustomPort ? "port-env" : "dev-server",
  };
}

module.exports = {
  DEFAULT_RENDERER_PORT,
  WEB_PORT_ENV_KEYS,
  WEB_URL_ENV_KEYS,
  normalizeUrl,
  resolveRendererPort,
  resolveRendererDevUrl,
  resolveRendererEntry,
};
