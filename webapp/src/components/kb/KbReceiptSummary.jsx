/**
 * 导入回执摘要组件
 * - 统一展示知识库最近一次导入回执，供对象区与详情区复用
 */

function formatReceiptTime(value) {
  if (!value) {
    return '刚刚';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '刚刚';
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

export default function KbReceiptSummary({ receiptSummary, emptyMessage = '当前知识库还没有导入回执。' }) {
  if (!receiptSummary) {
    return <div className='kb-receipt-summary kb-receipt-summary-empty'>{emptyMessage}</div>;
  }

  const emptyReasonMetrics = Array.isArray(receiptSummary.emptyReasonMetrics)
    ? receiptSummary.emptyReasonMetrics
    : [];
  const batchStageMetrics = Array.isArray(receiptSummary.batchStageMetrics)
    ? receiptSummary.batchStageMetrics.slice(0, 5)
    : [];
  const ingestionMetrics = Array.isArray(receiptSummary.ingestionMetrics)
    ? receiptSummary.ingestionMetrics.slice(0, 6)
    : [];
  const batchIndexStageMetrics = Array.isArray(receiptSummary.batchIndexStageMetrics)
    ? receiptSummary.batchIndexStageMetrics.slice(0, 5)
    : [];

  return (
    <section className={'kb-receipt-summary ' + (receiptSummary.status === 'warning' ? 'warning' : 'success')}>
      <div className='kb-receipt-summary-head'>
        <div>
          <p className='kb-receipt-eyebrow'>最近回执</p>
          <h3>{receiptSummary.title}</h3>
        </div>
        <span className='kb-receipt-time'>{formatReceiptTime(receiptSummary.createdAt)}</span>
      </div>

      <p className='kb-receipt-text'>{receiptSummary.summaryText}</p>
      {receiptSummary.receiptId ? <p className='kb-receipt-meta'>回执 ID：{receiptSummary.receiptId}</p> : null}
      {receiptSummary.batchStageSummaryText ? (
        <p className='kb-receipt-subtext'>批次耗时：{receiptSummary.batchStageSummaryText}</p>
      ) : null}
      {receiptSummary.batchIndexStageSummaryText ? (
        <p className='kb-receipt-subtext'>索引细分：{receiptSummary.batchIndexStageSummaryText}</p>
      ) : null}

      <MetricBadges metrics={receiptSummary.metrics} />

      {ingestionMetrics.length > 0 ? (
        <div className='kb-receipt-section'>
          <p className='kb-receipt-section-title'>解析与节点</p>
          <MetricBadges metrics={ingestionMetrics} className='kb-receipt-metrics kb-receipt-metrics-secondary' />
        </div>
      ) : null}

      {emptyReasonMetrics.length > 0 ? (
        <div className='kb-receipt-section'>
          <p className='kb-receipt-section-title'>空结果原因</p>
          <MetricBadges metrics={emptyReasonMetrics} className='kb-receipt-metrics kb-receipt-metrics-secondary' />
        </div>
      ) : null}

      {batchStageMetrics.length > 0 ? (
        <div className='kb-receipt-section'>
          <p className='kb-receipt-section-title'>导入阶段耗时</p>
          <MetricBadges metrics={batchStageMetrics} className='kb-receipt-metrics kb-receipt-metrics-secondary' />
        </div>
      ) : null}

      {batchIndexStageMetrics.length > 0 ? (
        <div className='kb-receipt-section'>
          <p className='kb-receipt-section-title'>索引细分耗时</p>
          <MetricBadges metrics={batchIndexStageMetrics} className='kb-receipt-metrics kb-receipt-metrics-secondary' />
        </div>
      ) : null}
    </section>
  );
}
