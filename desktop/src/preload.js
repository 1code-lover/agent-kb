/**
 * Electron preload exposes a minimal desktop bridge.
 */
const { contextBridge, ipcRenderer } = require("electron");

const desktopBridge = {
  runtime: "desktop",
  appName: "NorthAgent",
  pickFiles: (options) => ipcRenderer.invoke("northagent:pick-files", options),
};

contextBridge.exposeInMainWorld("northAgentDesktop", desktopBridge);
contextBridge.exposeInMainWorld("foxgloveDesktop", desktopBridge);
contextBridge.exposeInMainWorld("thinkragDesktop", desktopBridge);
