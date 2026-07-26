/**
 * 文件功能：
 * - 封装知识库相关 API 调用，包括 KB CRUD、对象列表查询与文件/网页导入。
 * - 统一追加 kb_id、import_mode、relative_paths 等导入契约字段。
 */

import client from './client.js';
import { requireKbTarget } from '../domain/kbSelection.js';
import { KB_IMPORT_MODES } from '../domain/uploadImport.js';

/** 获取全部知识库列表 */
export async function listKbs() {
  return client.get('/api/kb');
}

/** 创建知识库 */
export async function createKb(data) {
  return client.post('/api/kb', data);
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
  return client.get('/api/kb/list', { params: { kb_id: targetKbId } });
}

/** 查询文件夹节点列表，供 Workspace 目录浏览使用 */
export async function listFolders(kbId) {
  const targetKbId = requireKbTarget(kbId);
  return client.get('/api/kb/folders', { params: { kb_id: targetKbId } });
}

/** 查询资产列表，必须绑定显式选择的知识库 */
export async function listAssets(kbId) {
  const targetKbId = requireKbTarget(kbId);
  return client.get('/api/kb/assets', { params: { kb_id: targetKbId } });
}

/** ???????????????? */
export async function getLatestImportReceipt(kbId) {
  const targetKbId = requireKbTarget(kbId);
  return client.get('/api/kb/import-receipt/latest', { params: { kb_id: targetKbId } });
}

/**
 * 上传文件并导入到指定知识库。
 * - 默认显式发送 import_mode=flatten，保持现有“平铺上传”兼容语义。
 * - preserve_tree 模式下会逐项追加 relative_paths。
 */
export async function importFiles(formData, kbId, options = {}) {
  const targetKbId = requireKbTarget(kbId);
  const importMode = options.importMode === KB_IMPORT_MODES.PRESERVE_TREE
    ? KB_IMPORT_MODES.PRESERVE_TREE
    : KB_IMPORT_MODES.FLATTEN;
  const relativePaths = Array.isArray(options.relativePaths)
    ? options.relativePaths.filter((item) => typeof item === 'string' && item.trim())
    : [];

  formData.append('kb_id', targetKbId);
  formData.append('import_mode', importMode);
  relativePaths.forEach((relativePath) => formData.append('relative_paths', relativePath));

  // 不能手动覆盖 multipart/form-data，否则浏览器不会自动补 boundary，后端会报 400。
  return client.post('/api/kb/file/import', formData);
}

/** 导入网页到指定知识库 */
export async function importWeb(payload) {
  const targetKbId = requireKbTarget(payload?.kb_id);
  return client.post('/api/kb/web/import', { ...payload, kb_id: targetKbId });
}

/** 批量删除指定知识库下的文档 */
export async function deleteDocs(payload) {
  const targetKbId = requireKbTarget(payload?.kb_id);
  return client.delete('/api/kb/docs', { data: { ...payload, kb_id: targetKbId } });
}
