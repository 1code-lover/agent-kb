/**
 * 文件功能：
 * - 封装服务级 health 查询，供 Workspace 与系统页复用。
 */

import client from './client.js';

/** 获取服务健康状态与 OCR 预热状态 */
export async function getHealthStatus() {
  return client.get('/api/health');
}
