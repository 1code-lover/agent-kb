/**
 * 文件功能：
 * - 封装模型配置与提供商管理接口。
 *
 * 执行逻辑：
 * 1. 查询模型候选列表。
 * 2. 选择当前模型。
 * 3. 新增、测试、删除自定义模型提供商。
 */

import client from "./client";

/**
 * 功能：获取模型选项列表。
 * 输入：无。
 * 输出：Promise<object> - 模型选项数据。
 */
export async function getModelOptions() {
  return client.get("/api/model/options");
}

/**
 * 功能：设置当前使用模型。
 * 输入：payload(object) - 模型与提供商信息。
 * 输出：Promise<object> - 设置结果。
 */
export async function selectModel(payload) {
  return client.post("/api/model/select", payload);
}

/**
 * 功能：新增自定义模型提供商。
 * 输入：payload(object) - 提供商连接参数。
 * 输出：Promise<object> - 新增结果。
 */
export async function addCustomProvider(payload) {
  return client.post("/api/model/providers", payload);
}

/**
 * 功能：测试自定义模型提供商连通性。
 * 输入：payload(object) - 测试所需配置。
 * 输出：Promise<object> - 连通性测试结果。
 */
export async function testCustomProvider(payload) {
  return client.post("/api/model/providers/test", payload);
}

/**
 * 功能：删除指定名称的自定义模型提供商。
 * 输入：name(string) - 提供商名称。
 * 输出：Promise<object> - 删除结果。
 */
export async function deleteCustomProvider(name) {
  return client.delete(`/api/model/providers/${encodeURIComponent(name)}`);
}
