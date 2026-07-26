/**
 * 文件功能：
 * - 回归 health API 封装，确保 OCR 预热状态查询统一走 /api/health。
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import client from './client.js';
import { getHealthStatus } from './health.js';

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
