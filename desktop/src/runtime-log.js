const fs = require("node:fs");
const path = require("node:path");

function getLogFile(runtimeRoot) {
  return path.join(runtimeRoot, "storage", "logs", "desktop_runtime.log");
}

function ensureLogDir(runtimeRoot) {
  fs.mkdirSync(path.join(runtimeRoot, "storage", "logs"), { recursive: true });
}

function logRuntime(runtimeRoot, event, payload = {}) {
  try {
    ensureLogDir(runtimeRoot);
    const line = JSON.stringify({
      logged_at: new Date().toISOString(),
      event,
      ...payload
    });
    fs.appendFileSync(getLogFile(runtimeRoot), `${line}\n`, "utf8");
  } catch (error) {
    console.error("[desktop-runtime-log] failed", error);
  }
}

module.exports = {
  getLogFile,
  logRuntime
};
