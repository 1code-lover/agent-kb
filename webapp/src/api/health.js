/**
 * 文件功能：
 * - 封装服务级 health 查询，供 Workspace 与系统页复用。
 */

import client from './client.js';

/** 获取服务健康状态与 OCR 预热状态 */
export async function getHealthStatus() {
  return client.get('/api/health');
}

/** 获取 embedding 缓存恢复任务状态 */
export async function getEmbeddingCacheStatus() {
  return client.get('/api/embedding/cache');
}

/** 通过白名单 ModelScope 来源准备 embedding 本地缓存 */
export async function prepareEmbeddingCache() {
  return client.post('/api/embedding/cache/prepare', { provider: 'modelscope' });
}

/** 执行 embedding 缓存磁盘空间预检 */
export async function preflightEmbeddingCache() {
  return client.post('/api/embedding/cache/preflight', { provider: 'modelscope' });
}

/** 协作式取消当前 embedding 缓存下载 */
export async function cancelEmbeddingCache() {
  return client.post('/api/embedding/cache/cancel');
}
