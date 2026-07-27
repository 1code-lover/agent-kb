/**
 * 导入回执领域模型
 * - 负责把后端导入回执统一整理成前端可消费的摘要对象
 * - 同时兼容文件导入、内嵌资产、URL 导入三类结果
 */

import { getFolderPathFromObjectPath } from './folderTree.js';

function toSafeNumber(value) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : 0;
}

function toSafeText(value) {
  return typeof value === 'string' ? value : '';
}

function resolveItemCount(result, diagnostics) {
  const totalFiles = Number(diagnostics?.total_files);
  const totalUrls = Number(diagnostics?.total_urls);
  const hasTotalFiles = Number.isFinite(totalFiles);
  const hasTotalUrls = Number.isFinite(totalUrls);

  if (hasTotalFiles || hasTotalUrls) {
    return (hasTotalFiles ? totalFiles : 0) + (hasTotalUrls ? totalUrls : 0);
  }
  if (Array.isArray(result?.file_results) || Array.isArray(result?.url_results)) {
    return (Array.isArray(result?.file_results) ? result.file_results.length : 0)
      + (Array.isArray(result?.url_results) ? result.url_results.length : 0);
  }
  if (Array.isArray(result?.files) || Array.isArray(result?.urls)) {
    return (Array.isArray(result?.files) ? result.files.length : 0)
      + (Array.isArray(result?.urls) ? result.urls.length : 0);
  }
  return 0;
}

function buildOptionalMetrics(diagnostics) {
  const optionalMetrics = [
    {
      key: 'standalone_asset_candidate_count',
      label: '独立资产候选',
      value: toSafeNumber(diagnostics.standalone_asset_candidate_count),
      unit: '项',
    },
    {
      key: 'skip_standalone_asset_count',
      label: '被接管图片',
      value: toSafeNumber(diagnostics.skip_standalone_asset_count),
      unit: '项',
    },
    {
      key: 'embedded_asset_count',
      label: '内嵌资产',
      value: toSafeNumber(diagnostics.embedded_asset_count),
      unit: '项',
    },
    {
      key: 'asset_warning_count',
      label: '资产告警',
      value: toSafeNumber(diagnostics.asset_warning_count),
      unit: '项',
    },
    {
      key: 'ocr_success_count',
      label: 'OCR 成功',
      value: toSafeNumber(diagnostics.ocr_success_count),
      unit: '项',
    },
    {
      key: 'ocr_failed_count',
      label: 'OCR 失败',
      value: toSafeNumber(diagnostics.ocr_failed_count),
      unit: '项',
    },
    {
      key: 'embedded_ocr_success_count',
      label: '内嵌 OCR 成功',
      value: toSafeNumber(diagnostics.embedded_ocr_success_count),
      unit: '项',
    },
    {
      key: 'embedded_ocr_failed_count',
      label: '内嵌 OCR 失败',
      value: toSafeNumber(diagnostics.embedded_ocr_failed_count),
      unit: '项',
    },
    {
      key: 'embedded_ocr_no_text_count',
      label: '内嵌 OCR 无文本',
      value: toSafeNumber(diagnostics.embedded_ocr_no_text_count),
      unit: '项',
    },
    {
      key: 'embedded_indexed_from_ocr_count',
      label: '内嵌 OCR 入索引',
      value: toSafeNumber(diagnostics.embedded_indexed_from_ocr_count),
      unit: '项',
    },
  ];

  return optionalMetrics.filter((item) => item.value > 0);
}

function formatMetric(metric) {
  return metric.label + ' ' + metric.value + ' ' + metric.unit;
}

function hasOwnMetricField(source, key) {
  return Boolean(source) && Object.prototype.hasOwnProperty.call(source, key);
}

function buildDiagnosticMetric(source, key, label, unit) {
  if (!hasOwnMetricField(source, key)) {
    return null;
  }
  return {
    key,
    label,
    value: toSafeNumber(source[key]),
    unit,
  };
}

function buildIngestionMetrics(diagnostics) {
  return [
    buildDiagnosticMetric(diagnostics, 'document_count', '\u89e3\u6790\u6587\u6863', '\u7bc7'),
    buildDiagnosticMetric(diagnostics, 'empty_document_count', '\u7a7a\u6587\u6863', '\u7bc7'),
    buildDiagnosticMetric(diagnostics, 'input_text_chars', '\u8f93\u5165\u6587\u672c', '\u5b57\u7b26'),
    buildDiagnosticMetric(diagnostics, 'node_count', '\u8282\u70b9', '\u4e2a'),
    buildDiagnosticMetric(diagnostics, 'nodes_with_embedding_count', '\u542b\u5411\u91cf\u8282\u70b9', '\u4e2a'),
    buildDiagnosticMetric(diagnostics, 'nodes_without_embedding_count', '\u65e0\u5411\u91cf\u8282\u70b9', '\u4e2a'),
  ].filter(Boolean);
}

const EMPTY_REASON_LABELS = {
  ocr_failed: 'OCR 执行失败',
  ocr_skipped: '未执行 OCR',
  no_extractable_text: '未提取到文本',
  embedded_ocr_failed: '内嵌 OCR 失败',
  embedded_no_extractable_text: '内嵌图片无文本',
  embedded_ocr_no_nodes: '内嵌 OCR 未生成节点',
  no_nodes_generated: '未生成索引节点',
  shadowed_by_embedded_asset: '被内嵌资产接管',
};

const STAGE_TIMING_LABELS = {
  total_ms: '总耗时',
  ensure_models_ready_ms: '模型检查',
  get_index_manager_ms: '索引管理器',
  file_save_ms: '文件保存',
  persist_ms: '文件保存',
  standalone_ocr_ms: '独立 OCR',
  primary_index_ms: '主索引',
  embedded_asset_extract_ms: '内嵌抽取',
  embedded_asset_ocr_ms: '内嵌 OCR',
  embedded_asset_index_ms: '内嵌索引',
  index_storage_persist_ms: '索引落盘',
  doc_count_update_ms: '文档计数',
  register_assets_ms: '资产登记',
  receipt_store_ms: '回执落盘',
  result_build_ms: '结果组装',
};

const STAGE_TIMING_ORDER = [
  'total_ms',
  'file_save_ms',
  'persist_ms',
  'primary_index_ms',
  'embedded_asset_extract_ms',
  'embedded_asset_ocr_ms',
  'embedded_asset_index_ms',
  'standalone_ocr_ms',
  'index_storage_persist_ms',
  'doc_count_update_ms',
  'register_assets_ms',
  'receipt_store_ms',
  'result_build_ms',
  'ensure_models_ready_ms',
  'get_index_manager_ms',
];

const INDEX_STAGE_TIMING_LABELS = {
  total_ms: '\u7d22\u5f15\u603b\u8017\u65f6',
  document_load_ms: '\u6587\u6863\u52a0\u8f7d',
  chunking_ms: '\u6587\u672c\u5207\u5206',
  embedding_ms: 'Embedding',
  title_extract_ms: '\u6807\u9898\u63d0\u53d6',
  vector_store_ms: '\u5411\u91cf\u5199\u5e93',
  docstore_ms: '\u6587\u6863\u5199\u5e93',
  index_insert_ms: '\u7d22\u5f15\u767b\u8bb0',
};

const INDEX_STAGE_TIMING_ORDER = [
  'total_ms',
  'document_load_ms',
  'chunking_ms',
  'embedding_ms',
  'title_extract_ms',
  'vector_store_ms',
  'docstore_ms',
  'index_insert_ms',
];

function getEmptyReasonLabel(reason) {
  return EMPTY_REASON_LABELS[reason] || reason || '';
}

function buildEmptyReasonCounts(result, diagnostics) {
  const source = diagnostics?.empty_reason_counts;
  if (source && typeof source === 'object' && !Array.isArray(source)) {
    return Object.fromEntries(
      Object.entries(source).map(([key, value]) => [key, toSafeNumber(value)]).filter(([, value]) => value > 0),
    );
  }

  const counts = {};
  const fileResults = Array.isArray(result?.file_results) ? result.file_results : [];
  for (const fileResult of fileResults) {
    const reason = fileResult?.diagnostics?.empty_reason;
    if (!reason) {
      continue;
    }
    counts[reason] = toSafeNumber(counts[reason]) + 1;
  }
  return counts;
}

function buildEmptyReasonMetrics(emptyReasonCounts) {
  return Object.entries(emptyReasonCounts)
    .filter(([, value]) => toSafeNumber(value) > 0)
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .map(([key, value]) => ({
      key,
      label: getEmptyReasonLabel(key),
      value: toSafeNumber(value),
      unit: '项',
    }));
}

function buildTimingMetrics(stageTimings, order, labels, maxItems = null) {
  const metrics = order
    .filter((key) => !(key === 'persist_ms' && hasOwnMetricField(stageTimings, 'file_save_ms')))
    .map((key) => ({
      key,
      label: labels[key] || key,
      value: toSafeNumber(stageTimings?.[key]),
      unit: 'ms',
    }))
    .filter((item) => item.value > 0);

  if (typeof maxItems === 'number') {
    return metrics.slice(0, maxItems);
  }
  return metrics;
}

function formatTimingSummary(stageTimings, order, labels, maxItems = 4) {
  return buildTimingMetrics(stageTimings, order, labels, maxItems).map(formatMetric).join(' ? ');
}

function buildStageTimingMetrics(stageTimings, maxItems = null) {
  return buildTimingMetrics(stageTimings, STAGE_TIMING_ORDER, STAGE_TIMING_LABELS, maxItems);
}

function formatStageTimingSummary(stageTimings, maxItems = 4) {
  return formatTimingSummary(stageTimings, STAGE_TIMING_ORDER, STAGE_TIMING_LABELS, maxItems);
}

function buildIndexStageTimingMetrics(stageTimings, maxItems = null) {
  return buildTimingMetrics(stageTimings, INDEX_STAGE_TIMING_ORDER, INDEX_STAGE_TIMING_LABELS, maxItems);
}

function formatIndexStageTimingSummary(stageTimings, maxItems = 4) {
  return formatTimingSummary(stageTimings, INDEX_STAGE_TIMING_ORDER, INDEX_STAGE_TIMING_LABELS, maxItems);
}

function buildImportFileItem(fileResult, kbId, index) {
  const diagnostics = fileResult?.diagnostics || {};
  const relativePath = toSafeText(fileResult?.relative_path);
  const sourcePath = toSafeText(fileResult?.path);
  const folderPath = toSafeText(fileResult?.folder_path) || getFolderPathFromObjectPath(relativePath || sourcePath);
  const embeddedAssets = Array.isArray(fileResult?.embedded_assets)
    ? fileResult.embedded_assets.map((asset, assetIndex) => buildEmbeddedAssetItem(asset, kbId, fileResult, assetIndex))
    : [];

  return {
    key: 'file:' + index + ':' + (relativePath || fileResult?.name || 'unknown'),
    type: 'import-file',
    id: relativePath || sourcePath || String(index),
    name: fileResult?.name || '未命名文件',
    path: relativePath || sourcePath || '',
    relativePath,
    folderPath,
    sourcePath,
    kbId,
    docType: fileResult?.type || '',
    status: fileResult?.status || 'unknown',
    indexedChunks: toSafeNumber(fileResult?.indexed_chunks),
    message: toSafeText(fileResult?.message),
    assetWarningCount: toSafeNumber(fileResult?.asset_warning_count),
    fileKind: diagnostics.file_kind || '',
    emptyReason: diagnostics.empty_reason || '',
    ocrAttempted: Boolean(diagnostics.ocr_attempted),
    ocrStatus: diagnostics.ocr_status || '',
    ocrTextLength: toSafeNumber(diagnostics.ocr_text_length),
    ocrError: toSafeText(diagnostics.ocr_error),
    ocrEngine: toSafeText(diagnostics.ocr_engine),
    indexedFromOcr: Boolean(diagnostics.indexed_from_ocr),
    assetRegistered: Boolean(diagnostics.asset_registered),
    standaloneAssetCandidate: Boolean(diagnostics.standalone_asset_candidate),
    skipStandaloneAsset: Boolean(diagnostics.skip_standalone_asset),
    documentCount: toSafeNumber(diagnostics.document_count),
    emptyDocumentCount: toSafeNumber(diagnostics.empty_document_count),
    inputTextChars: toSafeNumber(diagnostics.input_text_chars),
    nodeCount: toSafeNumber(diagnostics.node_count),
    nodesWithEmbeddingCount: toSafeNumber(diagnostics.nodes_with_embedding_count),
    nodesWithoutEmbeddingCount: toSafeNumber(diagnostics.nodes_without_embedding_count),
    ingestionMetrics: buildIngestionMetrics(diagnostics),
    stageTimings: diagnostics.stage_timings || {},
    stageTimingMetrics: buildStageTimingMetrics(diagnostics.stage_timings),
    stageTimingSummaryText: formatStageTimingSummary(diagnostics.stage_timings, 4),
    indexStageTimings: diagnostics.index_stage_timings || {},
    indexStageMetrics: buildIndexStageTimingMetrics(diagnostics.index_stage_timings),
    indexStageSummaryText: formatIndexStageTimingSummary(diagnostics.index_stage_timings, 4),
    embeddedAssetCount: toSafeNumber(diagnostics.embedded_asset_count),
    embeddedAssetReadyCount: toSafeNumber(diagnostics.embedded_asset_ready_count),
    embeddedAssetMissingCount: toSafeNumber(diagnostics.embedded_asset_missing_count),
    embeddedAssetInvalidCount: toSafeNumber(diagnostics.embedded_asset_invalid_count),
    embeddedOcrAttemptedCount: toSafeNumber(diagnostics.embedded_ocr_attempted_count),
    embeddedOcrSuccessCount: toSafeNumber(diagnostics.embedded_ocr_success_count),
    embeddedOcrNoTextCount: toSafeNumber(diagnostics.embedded_ocr_no_text_count),
    embeddedOcrFailedCount: toSafeNumber(diagnostics.embedded_ocr_failed_count),
    embeddedIndexedFromOcrCount: toSafeNumber(diagnostics.embedded_indexed_from_ocr_count),
    embeddedAssets,
    raw: fileResult,
  };
}

function buildEmbeddedAssetItem(asset, kbId, fileResult, index) {
  const ocrDiagnostics = asset?.ocr_diagnostics || {};
  const relativePath = toSafeText(asset?.resolved_relative_path || asset?.relative_path);
  const sourcePath = toSafeText(asset?.path);
  const displayPath = relativePath || sourcePath || toSafeText(asset?.referenced_path);
  const displayName = displayPath ? displayPath.split('/').at(-1) : '未命名资产';

  return {
    key: 'asset:' + (asset?.asset_id || index + ':' + displayPath),
    type: 'asset',
    id: asset?.asset_id || '',
    name: displayName,
    path: displayPath,
    relativePath,
    folderPath: getFolderPathFromObjectPath(relativePath || displayPath),
    sourcePath,
    kbId,
    status: asset?.status || 'unknown',
    mimeType: asset?.mime_type || '',
    assetRole: asset?.asset_role || 'embedded',
    sourceDocRelativePath: asset?.source_doc_relative_path || fileResult?.relative_path || '',
    referencedPath: asset?.referenced_path || '',
    indexedChunks: toSafeNumber(asset?.indexed_chunks),
    indexedFromOcr: Boolean(asset?.indexed_from_ocr || ocrDiagnostics.indexed_from_ocr),
    ocrStatus: ocrDiagnostics.ocr_status || '',
    ocrTextLength: toSafeNumber(ocrDiagnostics.ocr_text_length),
    ocrError: toSafeText(ocrDiagnostics.ocr_error),
    ocrEngine: toSafeText(ocrDiagnostics.ocr_engine),
    raw: asset,
  };
}

function buildImportUrlItem(urlResult, kbId, index) {
  const url = toSafeText(urlResult?.url);
  return {
    key: 'url:' + (url || String(index)),
    type: 'import-url',
    id: url || String(index),
    name: url || '未命名 URL',
    url,
    path: url,
    kbId,
    status: urlResult?.status || 'unknown',
    indexedChunks: toSafeNumber(urlResult?.indexed_chunks),
    message: toSafeText(urlResult?.message),
    raw: urlResult,
  };
}

export function buildReceiptObjectItems(result) {
  const kbId = result?.kb_id || '';
  const items = [];
  const fileResults = Array.isArray(result?.file_results) ? result.file_results : [];
  const urlResults = Array.isArray(result?.url_results) ? result.url_results : [];

  fileResults.forEach((fileResult, index) => {
    items.push(buildImportFileItem(fileResult, kbId, index));
  });
  urlResults.forEach((urlResult, index) => {
    items.push(buildImportUrlItem(urlResult, kbId, index));
  });
  return items;
}

export function buildImportReceiptSummary(result, sourceLabel, createdAt = new Date().toISOString()) {
  const diagnostics = result?.diagnostics || {};
  const itemCount = resolveItemCount(result, diagnostics);
  const indexedFiles = toSafeNumber(diagnostics.indexed_files ?? result?.success_count);
  const emptyFiles = toSafeNumber(diagnostics.empty_files ?? result?.empty_count);
  const failedFiles = toSafeNumber(diagnostics.failed_files ?? result?.failed_count);
  const indexedChunks = toSafeNumber(result?.indexed_chunks);
  const metrics = buildOptionalMetrics(diagnostics);
  const items = buildReceiptObjectItems(result);
  const emptyReasonCounts = buildEmptyReasonCounts(result, diagnostics);
  const ingestionMetrics = buildIngestionMetrics(diagnostics);
  const batchStageTimings = diagnostics?.stage_timings || {};
  const batchIndexStageTimings = diagnostics?.index_stage_timings || {};
  const baseMetrics = [
    { key: 'item_count', label: '对象', value: itemCount, unit: '项' },
    { key: 'indexed_files', label: '已索引', value: indexedFiles, unit: '项' },
    { key: 'empty_files', label: '空导入', value: emptyFiles, unit: '项' },
    { key: 'failed_files', label: '失败', value: failedFiles, unit: '项' },
    { key: 'indexed_chunks', label: '切片', value: indexedChunks, unit: '个' },
  ];
  const summaryText = [...baseMetrics, ...metrics].map(formatMetric).join(' · ');
  const isoCreatedAt = createdAt instanceof Date ? createdAt.toISOString() : String(createdAt);
  const hasWarnings = emptyFiles > 0 || failedFiles > 0;

  return {
    kbId: result?.kb_id || '',
    sourceLabel,
    title: sourceLabel + '回执',
    createdAt: isoCreatedAt,
    status: hasWarnings ? 'warning' : 'success',
    itemCount,
    indexedFiles,
    emptyFiles,
    failedFiles,
    indexedChunks,
    metrics,
    items,
    summaryText,
    receiptId: result?.receipt_id || '',
    documentCount: toSafeNumber(diagnostics.document_count),
    emptyDocumentCount: toSafeNumber(diagnostics.empty_document_count),
    inputTextChars: toSafeNumber(diagnostics.input_text_chars),
    nodeCount: toSafeNumber(diagnostics.node_count),
    nodesWithEmbeddingCount: toSafeNumber(diagnostics.nodes_with_embedding_count),
    nodesWithoutEmbeddingCount: toSafeNumber(diagnostics.nodes_without_embedding_count),
    ingestionMetrics,
    emptyReasonCounts,
    emptyReasonMetrics: buildEmptyReasonMetrics(emptyReasonCounts),
    batchStageTimings,
    batchStageMetrics: buildStageTimingMetrics(batchStageTimings),
    batchStageSummaryText: formatStageTimingSummary(batchStageTimings, 5),
    batchIndexStageTimings,
    batchIndexStageMetrics: buildIndexStageTimingMetrics(batchIndexStageTimings),
    batchIndexStageSummaryText: formatIndexStageTimingSummary(batchIndexStageTimings, 5),
  };
}


export function buildPersistedImportReceiptSummary(receipt) {
  const result = receipt?.result;
  if (!result || typeof result !== 'object') {
    return null;
  }
  return buildImportReceiptSummary(
    result,
    toSafeText(receipt?.source_label) || '导入',
    receipt?.created_at || new Date().toISOString(),
  );
}

export function resolveVisibleReceiptSummary(selectedKbId, inMemorySummary, persistedSummary) {
  if (inMemorySummary?.kbId && inMemorySummary.kbId === selectedKbId) {
    return inMemorySummary;
  }
  if (persistedSummary?.kbId && persistedSummary.kbId === selectedKbId) {
    return persistedSummary;
  }
  return null;
}

export function buildImportNotice(result, sourceLabel, createdAt) {
  const receiptSummary = buildImportReceiptSummary(result, sourceLabel, createdAt);

  return {
    kbId: receiptSummary.kbId,
    receiptSummary,
    message: sourceLabel + '已完成，kb_id=' + (receiptSummary.kbId || '-') + '：' + receiptSummary.summaryText + '。',
  };
}
