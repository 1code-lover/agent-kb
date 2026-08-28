/**
 * Electron preload exposes a minimal desktop bridge.
 */
const { contextBridge, ipcRenderer } = require("electron");
const { resolveApiBaseUrl, resolveApiHealthUrl } = require("./runtime-config");
const { exposeDesktopBridge } = require("./desktop-bridge-contract");

const desktopBridge = {
  runtime: "desktop",
  appName: "agent-kb",
  apiBaseUrl: resolveApiBaseUrl(),
  apiHealthUrl: resolveApiHealthUrl(),
  pickFiles: (options) => ipcRenderer.invoke("kb:pick-files", options),
};

exposeDesktopBridge(contextBridge, desktopBridge);
