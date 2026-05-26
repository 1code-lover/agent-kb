/**
 * Electron 主进程入口。
 */
const path = require("node:path");
const { app, BrowserWindow, dialog } = require("electron");
const { startPythonApi, stopPythonApi, waitForApiReady } = require("./python-process");

const projectRoot = path.resolve(__dirname, "..", "..");

function createWindow() {
  const win = new BrowserWindow({
    width: 1366,
    height: 900,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  const webUrl = process.env.THINKRAG_WEB_URL || "http://127.0.0.1:5173";
  win.loadURL(webUrl);
}

app.whenReady().then(async () => {
  startPythonApi(projectRoot);
  const ready = await waitForApiReady();
  if (!ready) {
    await dialog.showErrorBox("ThinkRAG", "Python API 启动失败，请检查依赖与日志。");
    app.quit();
    return;
  }
  createWindow();
});

app.on("window-all-closed", () => {
  stopPythonApi();
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  stopPythonApi();
});
