const fs = require("node:fs");
const path = require("node:path");

function getLogFile(projectRoot) {
  return path.join(projectRoot, "storage", "logs", "desktop_runtime.log");
}

function ensureLogDir(projectRoot) {
  fs.mkdirSync(path.join(projectRoot, "storage", "logs"), { recursive: true });
}

function logRuntime(projectRoot, event, payload = {}) {
  try {
    ensureLogDir(projectRoot);
    const line = JSON.stringify({
      logged_at: new Date().toISOString(),
      event,
      ...payload
    });
    fs.appendFileSync(getLogFile(projectRoot), `${line}\n`, "utf8");
  } catch (error) {
    console.error("[desktop-runtime-log] failed", error);
  }
}

module.exports = {
  getLogFile,
  logRuntime
};
