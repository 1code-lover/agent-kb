const fs = require("node:fs");
const path = require("node:path");
const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const { bootDesktopApp, resolveDevProjectRoot } = require("./desktop-bootstrap");
const { ensurePythonApi, stopPythonApi } = require("./python-process");
const { buildApiStartupFailureMessage, buildRendererStartupFailureMessage, resolveApiStartupFailure } = require("./bootstrap-messages");
const { resolveDesktopHeadless } = require("./desktop-launch-config");
const { getLogFile, logRuntime } = require("./runtime-log");
const { buildContentSecurityPolicy, resolveUrlOrigin } = require("./csp");
const { resolveRendererEntry } = require("./renderer-entry");
const { ensureRuntimeRoot, resolveRuntimePaths } = require("./runtime-paths");
const { registerPickFilesHandlers } = require("./desktop-bridge-contract");

const devProjectRoot = resolveDevProjectRoot();
const resourceRoot = app.isPackaged ? process.resourcesPath : devProjectRoot;
let activeRuntimePaths = null;
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

function attachWindowLifecycleLogging(win, runtimePaths, { headless, rendererEntry }) {
  win.webContents.on("did-finish-load", () => {
    logRuntime(runtimePaths.runtimeRoot, "renderer_loaded", {
      headless,
      source: rendererEntry.source,
      url: win.webContents.getURL(),
    });
  });

  win.webContents.on("did-fail-load", (_, errorCode, errorDescription, validatedURL) => {
    logRuntime(runtimePaths.runtimeRoot, "renderer_load_failed", {
      headless,
      source: rendererEntry.source,
      error_code: errorCode,
      error_description: errorDescription,
      url: validatedURL,
    });
  });
}

function createWindow(runtimePaths, options = {}) {
  const headless = options.headless ?? resolveDesktopHeadless(options.env || process.env);
  const desktopIconPath = desktopIconCandidates.find((candidate) => fs.existsSync(candidate));
  const win = new BrowserWindow({
    width: 1366,
    height: 900,
    show: !headless,
    icon: desktopIconPath,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  const rendererEntry = resolveRendererEntry({ resourceRoot, env: options.env || process.env, isPackaged: app.isPackaged });
  logRuntime(runtimePaths.runtimeRoot, "renderer_resolved", {
    ...rendererEntry,
    headless,
  });
  attachWindowLifecycleLogging(win, runtimePaths, { headless, rendererEntry });
  applySecurityHeaders(win, rendererEntry);

  if (rendererEntry.type === "file") {
    win.loadFile(rendererEntry.value);
    return win;
  }

  win.loadURL(rendererEntry.value);
  return win;
}

async function handlePickFiles(_, options = {}) {
  const result = await dialog.showOpenDialog({
    title: options.title || "选择文件",
    properties: ["openFile", ...(options.multiSelections ? ["multiSelections"] : [])],
    filters: Array.isArray(options.filters) ? options.filters : undefined
  });

  return {
    canceled: result.canceled,
    filePaths: result.filePaths || []
  };
}

registerPickFilesHandlers(ipcMain, handlePickFiles);

app.whenReady().then(async () => {
  await bootDesktopApp({
    app,
    dialog,
    env: process.env,
    processResourcesPath: process.resourcesPath,
    devProjectRoot,
    onRuntimePaths: (runtimePaths) => {
      activeRuntimePaths = runtimePaths;
    },
    resolveRuntimePaths,
    ensureRuntimeRoot,
    getLogFile,
    logRuntime,
    ensurePythonApi,
    resolveApiStartupFailure,
    buildApiStartupFailureMessage,
    buildRendererStartupFailureMessage,
    createWindow,
  });
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
  attachWindowLifecycleLogging,
  bootDesktopApp,
  buildContentSecurityPolicy,
  createWindow,
  resolveDevProjectRoot,
  resolveRendererEntry,
  resolveUrlOrigin,
};
