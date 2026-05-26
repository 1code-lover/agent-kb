/**
 * 文件功能：
 * - 封装系统设置与存储信息接口。
 *
 * 执行逻辑：
 * 1. 获取当前系统设置。
 * 2. 更新系统设置。
 * 3. 获取当前存储状态信息。
 */

import client from "./client";

/**
 * 功能：获取当前系统设置。
 * 输入：无。
 * 输出：Promise<object> - 设置详情。
 */
export async function getSettings() {
  return client.get("/api/settings");
}

/**
 * 功能：更新系统设置。
 * 输入：payload(object) - 需要更新的设置项。
 * 输出：Promise<object> - 更新结果。
 */
export async function updateSettings(payload) {
  return client.put("/api/settings", payload);
}

/**
 * 功能：获取存储使用信息。
 * 输入：无。
 * 输出：Promise<object> - 存储状态和统计信息。
 */
export async function getStorageInfo() {
  return client.get("/api/storage/info");
}
