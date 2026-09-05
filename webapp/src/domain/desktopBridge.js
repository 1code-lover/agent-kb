/**
 * 文件功能：
 * - 统一解析桌面端 preload 注入的桥接对象；
 * - 让 KB 新命名优先，保留 NorthAgent / ThinkRAG / Foxglove 兼容别名。
 */

export const DESKTOP_BRIDGE_KEYS = [
  "kbDesktop",
  "northAgentDesktop",
  "thinkragDesktop",
  "foxgloveDesktop",
];

export function getDesktopBridge(target = globalThis) {
  if (!target || typeof target !== "object") {
    return null;
  }

  for (const key of DESKTOP_BRIDGE_KEYS) {
    const candidate = target[key];
    if (candidate && typeof candidate === "object") {
      return candidate;
    }
  }

  return null;
}
