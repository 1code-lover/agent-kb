const fs = require("node:fs");
const path = require("node:path");
const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const { startPythonApi, stopPythonApi, waitForApiReady } = require("./python-process");
const { getLogFile, logRuntime } = require("./runtime-log");

const projectRoot = path.resolve(__dirname, "..", "..");
const distIndexPath = path.join(projectRoot, "webapp", "dist", "index.html");
const desktopIconPath = path.join(projectRoot, "desktop", "resources", "icon.png");

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

function createWindow() {
  const win = new BrowserWindow({
    width: 1366,
    height: 900,
    icon: fs.existsSync(desktopIconPath) ? desktopIconPath : undefined,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  const rendererEntry = resolveRendererEntry();
  logRuntime(projectRoot, "renderer_resolved", rendererEntry);

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
  const logFile = getLogFile(projectRoot);
  logRuntime(projectRoot, "desktop_app_ready", { log_file: logFile });

  startPythonApi(projectRoot);
  const ready = await waitForApiReady(projectRoot);
  if (!ready) {
    logRuntime(projectRoot, "desktop_app_boot_failed", {
      reason: "python_api_not_ready",
      log_file: logFile
    });
    dialog.showErrorBox("NorthAgent", `Python API 启动失败，请检查日志：${logFile}`);
    app.quit();
    return;
  }

  createWindow();
});

app.on("window-all-closed", () => {
  logRuntime(projectRoot, "desktop_all_windows_closed");
  stopPythonApi(projectRoot);
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  logRuntime(projectRoot, "desktop_before_quit");
  stopPythonApi(projectRoot);
});
