const { resolveApiBaseUrl, toWebSocketOrigin } = require("./runtime-config");

function resolveUrlOrigin(value) {
  try {
    return new URL(value).origin;
  } catch {
    return "";
  }
}

function buildLoopbackOrigins(origin) {
  if (!origin) {
    return [];
  }
  const origins = new Set([origin]);
  try {
    const url = new URL(origin);
    if (url.hostname === "127.0.0.1") {
      url.hostname = "localhost";
      origins.add(url.origin);
    } else if (url.hostname === "localhost") {
      url.hostname = "127.0.0.1";
      origins.add(url.origin);
    }
  } catch {
    // ignore invalid input
  }
  return [...origins];
}

function buildContentSecurityPolicy(rendererEntry, options = {}) {
  const apiBaseUrl = options.apiBaseUrl || resolveApiBaseUrl(options.env || process.env);
  const rendererOrigin = rendererEntry.type === "url" ? resolveUrlOrigin(rendererEntry.value) : "";
  const rendererWsOrigin = rendererEntry.type === "url" ? toWebSocketOrigin(rendererEntry.value) : "";
  const connectSources = new Set([
    "'self'",
    ...buildLoopbackOrigins(resolveUrlOrigin(apiBaseUrl)),
    ...buildLoopbackOrigins(rendererOrigin),
    ...buildLoopbackOrigins(rendererWsOrigin),
  ].filter(Boolean));

  return [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: file:",
    "font-src 'self' data:",
    "media-src 'self' blob: file:",
    `connect-src ${[...connectSources].join(" ")}`,
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

module.exports = {
  buildContentSecurityPolicy,
  resolveUrlOrigin,
};
