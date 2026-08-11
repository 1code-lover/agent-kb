function resolveUrlOrigin(value) {
  try {
    return new URL(value).origin;
  } catch {
    return "";
  }
}

function buildContentSecurityPolicy(rendererEntry) {
  const rendererOrigin = rendererEntry.type === "url" ? resolveUrlOrigin(rendererEntry.value) : "";
  const connectSources = [
    "'self'",
    "http://127.0.0.1:18080",
    "http://localhost:18080",
    "ws://127.0.0.1:5173",
    "ws://localhost:5173",
    rendererOrigin,
  ].filter(Boolean);

  return [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: file:",
    "font-src 'self' data:",
    "media-src 'self' blob: file:",
    `connect-src ${connectSources.join(" ")}`,
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

module.exports = {
  buildContentSecurityPolicy,
  resolveUrlOrigin,
};
