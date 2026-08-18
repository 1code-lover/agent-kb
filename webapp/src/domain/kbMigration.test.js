/** 历史迁移计划 UI 门禁测试。 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { buildMigrationView } from './kbMigration.js';

test('缺 embedding 或目标冲突时默认阻止迁移', () => {
  const view = buildMigrationView({ knowledge_bases: [
    { kb_id: 'finance', node_count: 3, missing_embedding_count: 1, target_exists: false },
    { kb_id: 'hr', node_count: 2, missing_embedding_count: 0, target_exists: true, target_source_digest: null },
  ], anomalies: [{ reason: 'unknown_kb' }], plan_digest: 'digest' }, {});
  assert.equal(view.canStart, false);
  assert.equal(view.requiresEmbeddingConfirmation, true);
  assert.equal(view.hasConflict, true);
  assert.match(view.summary, /2 个知识库/);
});

test('确认重算后仅无冲突计划可执行并显示进度', () => {
  const plan = { knowledge_bases: [{ kb_id: 'finance', node_count: 3, missing_embedding_count: 1, target_exists: false }], anomalies: [], plan_digest: 'digest' };
  const view = buildMigrationView(plan, { state: 'running', completed_kb_count: 1, total_kb_count: 2 }, { allowRecompute: true });
  assert.equal(view.canStart, false);
  assert.equal(view.progressPercent, 50);
  assert.equal(view.isRunning, true);
  const ready = buildMigrationView(plan, { state: 'idle' }, { allowRecompute: true });
  assert.equal(ready.canStart, true);
});
