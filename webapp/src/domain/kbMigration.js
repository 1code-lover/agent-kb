/** 历史知识库迁移计划的展示与门禁。 */
export function buildMigrationView(plan = null, status = {}, options = {}) {
  const items = Array.isArray(plan?.knowledge_bases) ? plan.knowledge_bases : [];
  const anomalies = Array.isArray(plan?.anomalies) ? plan.anomalies : [];
  const hasConflict = items.some((item) => item.target_exists && !item.target_source_digest);
  const missingEmbeddings = items.reduce((sum, item) => sum + Number(item.missing_embedding_count || 0), 0);
  const requiresEmbeddingConfirmation = missingEmbeddings > 0 && !options.allowRecompute;
  const isRunning = status?.state === 'running';
  const total = Number(status?.total_kb_count || items.length || 0);
  const completed = Number(status?.completed_kb_count || 0);
  return {
    items, anomalies, hasConflict, missingEmbeddings, requiresEmbeddingConfirmation, isRunning,
    canStart: Boolean(plan?.plan_digest) && items.length > 0 && !hasConflict && !requiresEmbeddingConfirmation && !isRunning,
    progressPercent: total > 0 ? Math.min(100, Math.round(completed * 100 / total)) : 0,
    summary: `${items.length} 个知识库、${items.reduce((sum, item) => sum + Number(item.node_count || 0), 0)} 个节点、${anomalies.length} 个异常`,
  };
}
