/**
 * 文件功能：
 * - 封装知识库管理相关 API 调用。
 *
 * 执行逻辑：
 * 1. 提供文档列表查询。
 * 2. 提供文件导入、网页导入。
 * 3. 提供文档删除能力。
 */

import client from "./client";

/**
 * 功能：查询知识库文档列表。
 * 输入：无。
 * 输出：Promise<object> - 文档列表结果。
 */
export async function listDocs() {
  return client.get("/api/kb/list");
}

/**
 * 功能：上传文件并导入知识库。
 * 输入：formData(FormData) - 包含文件数据。
 * 输出：Promise<object> - 导入结果。
 */
export async function importFiles(formData) {
  return client.post("/api/kb/file/import", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });
}

/**
 * 功能：导入网页内容到知识库。
 * 输入：payload(object) - 网页 URL 与附加参数。
 * 输出：Promise<object> - 导入结果。
 */
export async function importWeb(payload) {
  return client.post("/api/kb/web/import", payload);
}

/**
 * 功能：批量删除知识库文档。
 * 输入：payload(object) - 待删除文档标识集合。
 * 输出：Promise<object> - 删除结果。
 */
export async function deleteDocs(payload) {
  return client.delete("/api/kb/docs", { data: payload });
}
