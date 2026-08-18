/** 历史知识库迁移 API 封装测试。 */
import test from 'node:test';
import assert from 'node:assert/strict';
import client from './client.js';
import { getMigrationStatus, rollbackMigration, scanMigration, startMigration } from './migration.js';

test('migration API 使用固定只读扫描与受控执行路径', async () => {
  const oldGet = client.get; const oldPost = client.post; const calls = [];
  client.get = async (...args) => { calls.push(['get', ...args]); return {}; };
  client.post = async (...args) => { calls.push(['post', ...args]); return {}; };
  try {
    await getMigrationStatus(); await scanMigration();
    await startMigration({ planDigest: 'abc1234567890123', kbIds: ['finance'], recomputeMissingEmbeddings: true });
    await rollbackMigration('batch-1');
    assert.deepEqual(calls, [
      ['get', '/api/kb/migration/status'],
      ['post', '/api/kb/migration/scan'],
      ['post', '/api/kb/migration/start', { plan_digest: 'abc1234567890123', kb_ids: ['finance'], retry_failed_only: false, recompute_missing_embeddings: true }],
      ['post', '/api/kb/migration/rollback', { batch_id: 'batch-1' }],
    ]);
  } finally { client.get = oldGet; client.post = oldPost; }
});
