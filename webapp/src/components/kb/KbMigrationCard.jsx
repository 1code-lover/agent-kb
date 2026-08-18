/** 历史共享索引迁移预览与执行卡片。 */
import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { getMigrationStatus, rollbackMigration, scanMigration, startMigration } from '../../api/migration';
import { readApiData } from '../../api/response';
import { buildMigrationView } from '../../domain/kbMigration';

export default function KbMigrationCard() {
  const [plan, setPlan] = useState(null);
  const [allowRecompute, setAllowRecompute] = useState(false);
  const statusQuery = useQuery({
    queryKey: ['kb-migration-status'], retry: false,
    refetchInterval: (query) => query.state.data?.state === 'running' ? 1000 : false,
    queryFn: async () => readApiData(await getMigrationStatus()),
  });
  const scan = useMutation({ mutationFn: scanMigration, onSuccess: (response) => setPlan(readApiData(response)) });
  const start = useMutation({
    mutationFn: () => startMigration({ planDigest: plan.plan_digest, recomputeMissingEmbeddings: allowRecompute }),
    onSuccess: () => statusQuery.refetch(),
  });
  const rollback = useMutation({
    mutationFn: () => rollbackMigration(statusQuery.data.batch_id),
    onSuccess: () => statusQuery.refetch(),
  });
  const view = useMemo(() => buildMigrationView(plan, statusQuery.data, { allowRecompute }), [plan, statusQuery.data, allowRecompute]);
  const error = scan.error || start.error || rollback.error || statusQuery.error;
  const hasHistory = Boolean(statusQuery.data?.batch_id);

  return (
    <section className='kb-migration-card' aria-label='历史知识库迁移'>
      <div className='kb-migration-card-head'>
        <div><strong>历史知识库迁移</strong><span>先扫描预览；执行时会备份历史索引并额外占用磁盘空间。</span></div>
        <button type='button' className='kb-runtime-recovery-button secondary' disabled={scan.isPending || view.isRunning} onClick={() => scan.mutate()}>
          {scan.isPending ? '扫描中…' : '扫描历史索引'}
        </button>
      </div>
      {plan ? (
        <>
          <p className='kb-migration-summary'>{view.summary}</p>
          <div className='kb-migration-items'>
            {view.items.map((item) => <span key={item.kb_id}>{item.kb_id}: {item.node_count} 节点 / 缺 {item.missing_embedding_count} embedding{item.target_exists ? ' / 目标已存在' : ''}</span>)}
          </div>
          {view.missingEmbeddings > 0 ? (
            <label className='kb-migration-confirm'><input type='checkbox' checked={allowRecompute} onChange={(event) => setAllowRecompute(event.target.checked)} />允许重算 {view.missingEmbeddings} 个缺失 embedding（耗时更长）</label>
          ) : null}
          {view.hasConflict ? <p className='error' role='alert'>检测到非本迁移创建的目标目录，请先人工处理冲突。</p> : null}
          {view.anomalies.length ? <p className='kb-migration-note'>{view.anomalies.length} 个异常节点不会自动迁移。</p> : null}
          <button type='button' className='kb-runtime-recovery-button' disabled={!view.canStart || start.isPending} onClick={() => start.mutate()}>{start.isPending ? '启动中…' : '备份并开始迁移'}</button>
        </>
      ) : null}
      {view.isRunning ? <div className='kb-embedding-progress'><span style={{ width: `${view.progressPercent}%` }} /></div> : null}
      {hasHistory ? <p className='kb-migration-note'>最近批次 {statusQuery.data.batch_id}：{statusQuery.data.state}（{statusQuery.data.completed_kb_count}/{statusQuery.data.total_kb_count}）</p> : null}
      {hasHistory && ['completed', 'failed', 'blocked'].includes(statusQuery.data?.state) ? <button type='button' className='kb-runtime-recovery-button danger' disabled={rollback.isPending} onClick={() => rollback.mutate()}>隔离并回滚本批次目标</button> : null}
      {error ? <p className='error' role='alert'>{error.message}</p> : null}
    </section>
  );
}
