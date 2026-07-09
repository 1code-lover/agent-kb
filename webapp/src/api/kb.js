/**
 * 文件功能：
 * - 封装知识库管理相关 API 调用，包含 KB CRUD 和文档管理。
 */

import client from "./client";

/** 获取全部知识库列表 */
export async function listKbs() {
  return client.get("/api/kb");
}

/** 创建知识库 */
export async function createKb(data) {
  return client.post("/api/kb", data);
}

/** 更新知识库名称 */
export async function updateKb(kbId, data) {
  return client.put(`/api/kb/${kbId}`, data);
}

/** 删除知识库 */
export async function deleteKb(kbId) {
  return client.delete(`/api/kb/${kbId}`);
}

/** 查询文档列表（可选按 kb_id 过滤） */
export async function listDocs(kbId) {
  const params = kbId && kbId !== "default" ? { kb_id: kbId } : {};
  return client.get("/api/kb/list", { params });
}

/** 上传文件并导入到指定知识库 */
export async function importFiles(formData, kbId) {
  formData.append("kb_id", kbId || "default");
  return client.post("/api/kb/file/import", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });
}

/** 导入网页到指定知识库 */
export async function importWeb(payload) {
  return client.post("/api/kb/web/import", payload);
}

/** 批量删除文档 */
export async function deleteDocs(payload) {
  return client.delete("/api/kb/docs", { data: payload });
}
