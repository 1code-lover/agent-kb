/**
 * 桌面桥接契约：集中维护 preload 暴露名与 IPC 通道，避免主进程 / preload 各自散落一份兼容映射。
 */
const DESKTOP_BRIDGE_KEYS = ["kbDesktop", "northAgentDesktop", "thinkragDesktop", "foxgloveDesktop"];
const PICK_FILES_CHANNELS = ["kb:pick-files", "northagent:pick-files"];

function exposeDesktopBridge(contextBridge, bridge) {
  for (const key of DESKTOP_BRIDGE_KEYS) {
    contextBridge.exposeInMainWorld(key, bridge);
  }
}

function registerPickFilesHandlers(ipcMain, handler) {
  for (const channel of PICK_FILES_CHANNELS) {
    ipcMain.handle(channel, handler);
  }
}

module.exports = {
  DESKTOP_BRIDGE_KEYS,
  PICK_FILES_CHANNELS,
  exposeDesktopBridge,
  registerPickFilesHandlers,
};
