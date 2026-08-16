const fs = require("node:fs");
const path = require("node:path");
const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const { ensurePythonApi, stopPythonApi } = require("./python-process");
const { getLogFile, logRuntime } = require("./runtime-log");
const { buildContentSecurityPolicy, resolveUrlOrigin } = require("./csp");
const { ensureRuntimeRoot, resolveRuntimePaths } = require("./runtime-paths");

const devProjectRoot = path.resolve(__dirname, "..", "..");
const resourceRoot = app.isPackaged ? process.resourcesPath : devProjectRoot;
let activeRuntimePaths = null;
const distIndexPath = path.join(resourceRoot, "webapp", "dist", "index.html");
const desktopIconCandidates = [
  path.join(resourceRoot, "desktop", "resources", "icon.png"),
  path.join(__dirname, "..", "resources", "icon.png"),
];

function applySecurityHeaders(win, rendererEntry) {
  const csp = buildContentSecurityPolicy(rendererEntry);
  win.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    const responseHeaders = {
      ...details.responseHeaders,
      "Content-Security-Policy": [csp]
    };
    callback({ responseHeaders });
  });
}

function resolveRendererEntry() {
  if (process.env.NORTHAGENT_WEB_URL || process.env.FOXGLOVE_WEB_URL || process.env.THINKRAG_WEB_URL) {
    return {
      type: "url",
      value: process.env.NORTHAGENT_WEB_URL || process.env.FOXGLOVE_WEB_URL || process.env.THINKRAG_WEB_URL,
      source: process.env.NORTHAGENT_WEB_URL ? "northagent-env" : process.env.FOXGLOVE_WEB_URL ? "foxglove-env" : "legacy-env"
    };
  }

  if (fs.existsSync(distIndexPath)) {
    return {
      type: "file",
      value: distIndexPath,
      source: "dist"
    };
  }

  return {
    type: "url",
    value: "http://127.0.0.1:5173",
    source: "dev-server"
  };
}

function createWindow(runtimePaths) {
  const desktopIconPath = desktopIconCandidates.find((candidate) => fs.existsSync(candidate));
  const win = new BrowserWindow({
    width: 1366,
    height: 900,
    icon: desktopIconPath,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  const rendererEntry = resolveRendererEntry();
  logRuntime(runtimePaths.runtimeRoot, "renderer_resolved", rendererEntry);
  applySecurityHeaders(win, rendererEntry);

  if (rendererEntry.type === "file") {
    win.loadFile(rendererEntry.value);
    return;
  }

  win.loadURL(rendererEntry.value);
}

ipcMain.handle("northagent:pick-files", async (_, options = {}) => {
  const result = await dialog.showOpenDialog({
    title: options.title || "选择文件",
    properties: ["openFile", ...(options.multiSelections ? ["multiSelections"] : [])],
    filters: Array.isArray(options.filters) ? options.filters : undefined
  });

  return {
    canceled: result.canceled,
    filePaths: result.filePaths || []
  };
});

app.whenReady().then(async () => {
  const runtimePaths = resolveRuntimePaths({
    devProjectRoot,
    isPackaged: app.isPackaged,
    resourcesPath: process.resourcesPath,
    userDataPath: app.getPath("userData"),
  });
  activeRuntimePaths = runtimePaths;
  const logFile = getLogFile(runtimePaths.runtimeRoot);
  try {
    ensureRuntimeRoot(runtimePaths.runtimeRoot);
  } catch (error) {
    console.error("[desktop-runtime] runtime root unavailable", error);
    dialog.showErrorBox("NorthAgent", `运行目录不可写，无法启动：${runtimePaths.runtimeRoot}\n${error.message}`);
    app.quit();
    return;
  }
  logRuntime(runtimePaths.runtimeRoot, "desktop_app_ready", { log_file: logFile });

  const ready = await ensurePythonApi(runtimePaths);
  if (!ready) {
    logRuntime(runtimePaths.runtimeRoot, "desktop_app_boot_failed", {
      reason: "python_api_not_ready",
      log_file: logFile
    });
    dialog.showErrorBox("NorthAgent", `Python API 启动失败，请检查日志：${logFile}`);
    app.quit();
    return;
  }

  createWindow(runtimePaths);
});

app.on("window-all-closed", () => {
  if (activeRuntimePaths) {
    logRuntime(activeRuntimePaths.runtimeRoot, "desktop_all_windows_closed");
    stopPythonApi(activeRuntimePaths);
  }
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  if (activeRuntimePaths) {
    logRuntime(activeRuntimePaths.runtimeRoot, "desktop_before_quit");
    stopPythonApi(activeRuntimePaths);
  }
});

module.exports = {
  applySecurityHeaders,
  buildContentSecurityPolicy,
  createWindow,
  resolveRendererEntry,
  resolveUrlOrigin,
};
