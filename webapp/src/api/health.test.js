/**
 * 文件功能：
 * - 回归 health API 封装，确保 OCR 预热状态查询统一走 /api/health。
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import client from './client.js';
import { getEmbeddingCacheStatus, getHealthStatus, prepareEmbeddingCache } from './health.js';

test('getHealthStatus 会调用 /api/health', async () => {
  const originalGet = client.get;
  const calls = [];
  client.get = async (...args) => {
    calls.push(args);
    return { code: 0, data: { status: 'ok' } };
  };

  try {
    const response = await getHealthStatus();

    assert.deepEqual(response, { code: 0, data: { status: 'ok' } });
    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0], ['/api/health']);
  } finally {
    client.get = originalGet;
  }
});


test('embedding 缓存恢复 API 固定使用 ModelScope 白名单来源', async () => {
  const originalGet = client.get;
  const originalPost = client.post;
  const calls = [];
  client.get = async (...args) => { calls.push(['get', ...args]); return { code: 0, data: { state: 'idle' } }; };
  client.post = async (...args) => { calls.push(['post', ...args]); return { code: 0, data: { started: true } }; };

  try {
    await getEmbeddingCacheStatus();
    await prepareEmbeddingCache();

    assert.deepEqual(calls, [
      ['get', '/api/embedding/cache'],
      ['post', '/api/embedding/cache/prepare', { provider: 'modelscope' }],
    ]);
  } finally {
    client.get = originalGet;
    client.post = originalPost;
  }
});
