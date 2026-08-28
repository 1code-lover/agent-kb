/**
 * 文件功能：
 * - 创建并导出统一的 Axios 客户端实例。
 *
 * 执行逻辑：
 * 1. 优先读取桌面端 preload 注入的 API base URL。
 * 2. 再读取 Vite 环境变量，最后回退到本地默认地址。
 * 3. 浏览器端只认 preload bridge + Vite env，不直接读取 Python/Node 侧环境变量别名。
 * 4. 如果 bridge / Vite 传入无效 URL，则忽略该值并继续走后续 fallback。
 * 5. 统一响应拦截，成功时直接返回 response.data。
 * 6. 统一错误映射，输出可读错误信息给上层调用方。
 */

import axios from "axios";
import { DESKTOP_BRIDGE_KEYS } from "../domain/desktopBridge.js";

export const DEFAULT_API_BASE_URL = "http://127.0.0.1:18080";

function normalizeLocalClientUrl(value) {
  const raw = typeof value === "string" ? value.trim() : "";
  if (!raw) {
    return "";
  }

  const trimmed = raw.replace(/\/+$/, "");
  try {
    const url = new URL(trimmed);
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return "";
    }
    if (url.hostname === "0.0.0.0") {
      url.hostname = "127.0.0.1";
    }
    return url.toString().replace(/\/+$/, "");
  } catch {
    return "";
  }
}

export function normalizeApiBaseUrl(value) {
  return normalizeLocalClientUrl(value);
}

function readDesktopApiBaseUrl(target = typeof globalThis === "object" ? globalThis : null) {
  if (!target || typeof target !== "object") {
    return "";
  }

  for (const key of DESKTOP_BRIDGE_KEYS) {
    const bridge = target[key];
    if (!bridge || typeof bridge !== "object") {
      continue;
    }

    const normalizedUrl = normalizeApiBaseUrl(bridge.apiBaseUrl);
    if (normalizedUrl) {
      return normalizedUrl;
    }
  }

  return "";
}

export function resolveApiBaseUrl(options = {}) {
  const bridgeTarget = Object.prototype.hasOwnProperty.call(options, "bridgeTarget")
    ? options.bridgeTarget
    : (typeof globalThis === "object" ? globalThis : null);
  const viteEnv = options.viteEnv ?? import.meta?.env ?? {};

  return (
    readDesktopApiBaseUrl(bridgeTarget)
    || normalizeApiBaseUrl(viteEnv?.VITE_API_BASE_URL)
    || DEFAULT_API_BASE_URL
  );
}

const client = axios.create({
  baseURL: resolveApiBaseUrl(),
  timeout: 120000
});

export function extractApiErrorMessage(error) {
  const responseData = error?.response?.data;
  if (typeof responseData === "string" && responseData.trim()) {
    return responseData.trim();
  }

  const candidates = [
    responseData?.detail,
    responseData?.message,
    responseData?.error?.message,
    error?.message,
  ];

  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
  }

  return "请求失败";
}

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    // 统一错误消息格式，避免页面层重复处理后端/网络异常结构差异。
    return Promise.reject(new Error(extractApiErrorMessage(error)));
  }
);

export default client;
