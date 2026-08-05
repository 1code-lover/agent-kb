/**
 * 导入回执摘要组件
 * - 统一展示知识库最近一次导入回执，供对象区与详情区复用
 */

function formatReceiptTime(value) {
  if (!value) {
    return '\u521a\u521a';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '\u521a\u521a';
  }
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function MetricBadges({ metrics, className = 'kb-receipt-metrics' }) {
  if (!Array.isArray(metrics) || metrics.length === 0) {
    return null;
  }
  return (
    <div className={className}>
      {metrics.map((item) => (
        <span key={item.key} className='kb-receipt-badge'>
          {item.label} {item.value} {item.unit}
        </span>
      ))}
    </div>
  );
}

function StatusBadges({ receiptSummary }) {
  const badges = [];

  if (receiptSummary.hasBlockers) {
    badges.push({
      key: 'blocker',
      className: 'kb-receipt-status-pill is-blocker',
      label: '\u6709\u963b\u65ad',
    });
  } else if (receiptSummary.hasWarnings) {
    badges.push({
      key: 'warning',
      className: 'kb-receipt-status-pill is-warning',
      label: '\u9700\u5173\u6ce8',
    });
  } else {
    badges.push({
      key: 'success',
      className: 'kb-receipt-status-pill is-success',
      label: '\u5df2\u5b8c\u6210',
    });
  }

  if (receiptSummary.hasDependencyIssues) {
    badges.push({
      key: 'dependency',
      className: 'kb-receipt-status-pill is-warning',
      label: '\u4f9d\u8d56\u7f3a\u5931',
    });
  }

  return (
    <div className='kb-receipt-status-row'>
      {badges.map((badge) => (
        <span key={badge.key} className={badge.className}>{badge.label}</span>
      ))}
    </div>
  );
}

function ActionList({ actions }) {
  if (!Array.isArray(actions) || actions.length === 0) {
    return null;
  }

  return (
    <ul className='kb-receipt-action-list'>
      {actions.map((item) => (
        <li key={item.key}>{item.label}</li>
      ))}
    </ul>
  );
}

export default function KbReceiptSummary({ receiptSummary, emptyMessage = '\u5f53\u524d\u77e5\u8bc6\u5e93\u8fd8\u6ca1\u6709\u5bfc\u5165\u56de\u6267\u3002' }) {
  if (!receiptSummary) {
    return <div className='kb-receipt-summary kb-receipt-summary-empty'>{emptyMessage}</div>;
  }

  const emptyReasonMetrics = Array.isArray(receiptSummary.emptyReasonMetrics)
    ? receiptSummary.emptyReasonMetrics
    : [];
  const topMissingDependencyMetrics = Array.isArray(receiptSummary.topMissingDependencyMetrics)
    ? receiptSummary.topMissingDependencyMetrics
    : [];
  const nextActions = Array.isArray(receiptSummary.nextActions) ? receiptSummary.nextActions : [];
  const batchStageMetrics = Array.isArray(receiptSummary.batchStageMetrics)
    ? receiptSummary.batchStageMetrics.slice(0, 5)
    : [];
  const ingestionMetrics = Array.isArray(receiptSummary.ingestionMetrics)
    ? receiptSummary.ingestionMetrics.slice(0, 6)
    : [];
  const batchIndexStageMetrics = Array.isArray(receiptSummary.batchIndexStageMetrics)
    ? receiptSummary.batchIndexStageMetrics.slice(0, 5)
    : [];
  const primaryText = receiptSummary.userMessage || receiptSummary.summaryText;

  return (
    <section className={'kb-receipt-summary ' + (receiptSummary.status === 'warning' ? 'warning' : 'success')}>
      <div className='kb-receipt-summary-head'>
        <div>
          <p className='kb-receipt-eyebrow'>{'\u6700\u8fd1\u56de\u6267'}</p>
          <h3>{receiptSummary.title}</h3>
        </div>
        <div className='kb-receipt-summary-head-side'>
          <StatusBadges receiptSummary={receiptSummary} />
          <span className='kb-receipt-time'>{formatReceiptTime(receiptSummary.createdAt)}</span>
        </div>
      </div>

      {receiptSummary.headline ? <p className='kb-receipt-headline'>{receiptSummary.headline}</p> : null}
      <p className='kb-receipt-text'>{primaryText}</p>
      {receiptSummary.userMessage && receiptSummary.summaryText ? (
        <p className='kb-receipt-subtext'>{'\u6982\u89c8\uff1a'}{receiptSummary.summaryText}</p>
      ) : null}
      {receiptSummary.receiptId ? <p className='kb-receipt-meta'>{'\u56de\u6267 ID\uff1a'}{receiptSummary.receiptId}</p> : null}
      {receiptSummary.batchStageSummaryText ? (
        <p className='kb-receipt-subtext'>{'\u6279\u6b21\u8017\u65f6\uff1a'}{receiptSummary.batchStageSummaryText}</p>
      ) : null}
      {receiptSummary.batchIndexStageSummaryText ? (
        <p className='kb-receipt-subtext'>{'\u7d22\u5f15\u7ec6\u5206\uff1a'}{receiptSummary.batchIndexStageSummaryText}</p>
      ) : null}

      <MetricBadges metrics={receiptSummary.metrics} />

      {topMissingDependencyMetrics.length > 0 ? (
        <div className='kb-receipt-section'>
          <p className='kb-receipt-section-title'>{'\u7f3a\u5931\u4f9d\u8d56'}</p>
          <MetricBadges metrics={topMissingDependencyMetrics} className='kb-receipt-metrics kb-receipt-metrics-secondary' />
        </div>
      ) : null}

      {nextActions.length > 0 ? (
        <div className='kb-receipt-section'>
          <p className='kb-receipt-section-title'>{'\u5efa\u8bae\u52a8\u4f5c'}</p>
          <ActionList actions={nextActions} />
        </div>
      ) : null}

      {ingestionMetrics.length > 0 ? (
        <div className='kb-receipt-section'>
          <p className='kb-receipt-section-title'>{'\u89e3\u6790\u4e0e\u8282\u70b9'}</p>
          <MetricBadges metrics={ingestionMetrics} className='kb-receipt-metrics kb-receipt-metrics-secondary' />
        </div>
      ) : null}

      {emptyReasonMetrics.length > 0 ? (
        <div className='kb-receipt-section'>
          <p className='kb-receipt-section-title'>{'\u7a7a\u7ed3\u679c\u539f\u56e0'}</p>
          <MetricBadges metrics={emptyReasonMetrics} className='kb-receipt-metrics kb-receipt-metrics-secondary' />
        </div>
      ) : null}

      {batchStageMetrics.length > 0 ? (
        <div className='kb-receipt-section'>
          <p className='kb-receipt-section-title'>{'\u5bfc\u5165\u9636\u6bb5\u8017\u65f6'}</p>
          <MetricBadges metrics={batchStageMetrics} className='kb-receipt-metrics kb-receipt-metrics-secondary' />
        </div>
      ) : null}

      {batchIndexStageMetrics.length > 0 ? (
        <div className='kb-receipt-section'>
          <p className='kb-receipt-section-title'>{'\u7d22\u5f15\u7ec6\u5206\u8017\u65f6'}</p>
          <MetricBadges metrics={batchIndexStageMetrics} className='kb-receipt-metrics kb-receipt-metrics-secondary' />
        </div>
      ) : null}
    </section>
  );
}
