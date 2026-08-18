/**
 * 文件功能：
 * - Knowledge Workspace 头部，聚合当前知识库摘要、运行时状态与核心动作入口。
 */

import { Link } from '../../router';
import { buildKnowledgeAgentLink } from '../../domain/kbNavigation';
import { KB_WORKSPACE_ACTION_MODES } from '../../domain/knowledgeWorkspace';
import { buildEmbeddingDownloadView } from '../../domain/embeddingDownload';

function formatDocCount(value) {
  if (typeof value !== 'number') {
    return '-';
  }
  return String(value);
}

export default function KbWorkspaceHeader({
  selectedKb,
  selectedKbId,
  hasSelectedKb,
  actionMode,
  onToggleActionMode,
  embeddingWarmupSummary,
  embeddingCacheStatus,
  embeddingCacheError,
  onPreflightEmbeddingCache,
  onPrepareEmbeddingCache,
  onCancelEmbeddingCache,
  isPreparingEmbeddingCache,
  ocrWarmupSummary,
}) {
  const rootPath = hasSelectedKb ? 'data/' + selectedKbId + '/' : '选择知识库后显示';
  const statusLabel = hasSelectedKb ? (selectedKb?.status || 'active') : '未选择';
  const docCount = hasSelectedKb ? formatDocCount(selectedKb?.doc_count) : '-';
  const uploadButtonClass = 'kb-action-button' + (actionMode === KB_WORKSPACE_ACTION_MODES.UPLOAD ? ' active' : '');
  const webButtonClass = 'kb-action-button' + (actionMode === KB_WORKSPACE_ACTION_MODES.WEB_IMPORT ? ' active' : '');
  const linkClass = 'kb-link-button' + (hasSelectedKb ? '' : ' disabled');
  const embeddingRuntimeClassName = `kb-runtime-status ${embeddingWarmupSummary?.tone || 'muted'}`;
  const ocrRuntimeClassName = `kb-runtime-status ${ocrWarmupSummary?.tone || 'muted'}`;
  const embeddingDownloadView = buildEmbeddingDownloadView(embeddingCacheStatus, embeddingCacheError);

  return (
    <section className='kb-workspace-header'>
      <div className='kb-workspace-header-copy'>
        <p className='kb-workspace-eyebrow'>Knowledge Workspace</p>
        <div className='kb-workspace-title-row'>
          <h2>{hasSelectedKb ? selectedKb?.kb_name : '请选择知识库'}</h2>
          {hasSelectedKb ? <span className='kb-status-pill'>active</span> : null}
        </div>
        <p className='kb-workspace-description'>
          {hasSelectedKb
            ? '在当前知识库中集中完成导入、浏览、回执确认与后续问答衔接。'
            : '请先在左侧显式选择一个 active 知识库，再开始导入和管理资料。'}
        </p>

        <div className='kb-workspace-meta-grid'>
          <span className='kb-meta-pill'>kb_id: {hasSelectedKb ? selectedKbId : '未选择'}</span>
          <span className='kb-meta-pill'>状态: {statusLabel}</span>
          <span className='kb-meta-pill'>文档数: {docCount}</span>
          <span className='kb-meta-pill'>根目录: {rootPath}</span>
        </div>

        <div className='kb-runtime-status-grid'>
          <div className={embeddingRuntimeClassName} role='status' aria-live='polite'>
            <div className='kb-runtime-status-head'>
              <strong>{embeddingWarmupSummary?.title || 'Embedding 状态未知'}</strong>
              <span>{embeddingWarmupSummary?.detail || '等待后台返回运行状态'}</span>
            </div>
            <p className='kb-runtime-status-text'>
              {embeddingWarmupSummary?.summary || '导入和问答前会先检查向量模型状态。'}
            </p>
            {embeddingWarmupSummary?.canPrepareCache || embeddingCacheStatus?.state !== 'idle' ? (
              <div className='kb-runtime-recovery'>
                <div className='kb-embedding-download-head'>
                  <strong>{embeddingDownloadView.title}</strong>
                  <span>{embeddingDownloadView.detail}</span>
                </div>
                {embeddingDownloadView.showProgress ? (
                  <div className='kb-embedding-progress' aria-label={embeddingDownloadView.progressLabel}>
                    <span style={{ width: `${embeddingDownloadView.progressPercent}%` }} />
                  </div>
                ) : null}
                <div className='kb-runtime-recovery-actions'>
                  {embeddingDownloadView.canPreflight ? (
                    <button
                      type='button'
                      className='kb-runtime-recovery-button secondary'
                      disabled={isPreparingEmbeddingCache}
                      onClick={onPreflightEmbeddingCache}
                    >
                      {isPreparingEmbeddingCache ? '正在检查…' : '检查下载空间'}
                    </button>
                  ) : null}
                  {embeddingDownloadView.canStart ? (
                    <button
                      type='button'
                      className='kb-runtime-recovery-button'
                      disabled={isPreparingEmbeddingCache}
                      onClick={onPrepareEmbeddingCache}
                    >
                      {embeddingDownloadView.isRetry ? '重新下载' : '开始 ModelScope 下载'}
                    </button>
                  ) : null}
                  {embeddingDownloadView.canCancel ? (
                    <button
                      type='button'
                      className='kb-runtime-recovery-button danger'
                      disabled={embeddingCacheStatus?.state === 'cancelling'}
                      onClick={onCancelEmbeddingCache}
                    >
                      {embeddingCacheStatus?.state === 'cancelling' ? '正在取消…' : '取消下载'}
                    </button>
                  ) : null}
                </div>
                {embeddingDownloadView.error ? <span role='alert'>{embeddingDownloadView.error}</span> : null}
              </div>
            ) : null}
          </div>
          <div className={ocrRuntimeClassName} role='status' aria-live='polite'>
            <div className='kb-runtime-status-head'>
              <strong>{ocrWarmupSummary?.title || 'OCR 状态未知'}</strong>
              <span>{ocrWarmupSummary?.detail || '等待后台返回运行状态'}</span>
            </div>
            <p className='kb-runtime-status-text'>
              {ocrWarmupSummary?.summary || '导入图片前会先检查 OCR 运行时状态。'}
            </p>
          </div>
        </div>
      </div>

      <div className='kb-workspace-action-group'>
        <button
          type='button'
          className={uploadButtonClass}
          disabled={!hasSelectedKb}
          onClick={() => onToggleActionMode(KB_WORKSPACE_ACTION_MODES.UPLOAD)}
        >
          导入文件
        </button>
        <button
          type='button'
          className='kb-action-button muted'
          disabled
          title='目录导入将在下一阶段支持'
        >
          导入目录（即将支持）
        </button>
        <button
          type='button'
          className={webButtonClass}
          disabled={!hasSelectedKb}
          onClick={() => onToggleActionMode(KB_WORKSPACE_ACTION_MODES.WEB_IMPORT)}
        >
          导入网页
        </button>
        <Link
          to={buildKnowledgeAgentLink(selectedKbId)}
          className={linkClass}
          aria-disabled={!hasSelectedKb}
          onClick={(event) => {
            if (!hasSelectedKb) {
              event.preventDefault();
            }
          }}
        >
          在当前知识库中提问
        </Link>
      </div>
    </section>
  );
}
