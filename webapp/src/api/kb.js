/**
 * 文件功能：
 * - 封装知识库管理相关 API 调用，包含 KB CRUD 和文档管理。
 */

import client from "./client.js";
import { requireKbTarget } from "../domain/kbSelection.js";

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

/** 查询文档列表，必须绑定显式选择的知识库 */
export async function listDocs(kbId) {
  const targetKbId = requireKbTarget(kbId);
  return client.get("/api/kb/list", { params: { kb_id: targetKbId } });
}

/** 上传文件并导入到指定知识库 */
export async function importFiles(formData, kbId) {
  const targetKbId = requireKbTarget(kbId);
  formData.append("kb_id", targetKbId);
  // 不能手动覆盖 multipart/form-data，否则浏览器不会自动补 boundary，后端会报 400。
  return client.post("/api/kb/file/import", formData);
}

/** 导入网页到指定知识库 */
export async function importWeb(payload) {
  const targetKbId = requireKbTarget(payload?.kb_id);
  return client.post("/api/kb/web/import", { ...payload, kb_id: targetKbId });
}

/** 批量删除指定知识库下的文档 */
export async function deleteDocs(payload) {
  const targetKbId = requireKbTarget(payload?.kb_id);
  return client.delete("/api/kb/docs", { data: { ...payload, kb_id: targetKbId } });
}
