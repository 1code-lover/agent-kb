/** 历史知识库迁移 API。 */
import client from './client.js';
export async function getMigrationStatus() { return client.get('/api/kb/migration/status'); }
export async function scanMigration() { return client.post('/api/kb/migration/scan'); }
export async function startMigration({ planDigest, kbIds = null, retryFailedOnly = false, recomputeMissingEmbeddings = false }) {
  return client.post('/api/kb/migration/start', {
    plan_digest: planDigest, kb_ids: kbIds, retry_failed_only: retryFailedOnly, recompute_missing_embeddings: recomputeMissingEmbeddings,
  });
}
export async function rollbackMigration(batchId) { return client.post('/api/kb/migration/rollback', { batch_id: batchId }); }
