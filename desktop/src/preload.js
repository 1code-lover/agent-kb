/**
 * Electron preload，最小能力暴露。
 */
const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("thinkragDesktop", {
  runtime: "desktop"
});
