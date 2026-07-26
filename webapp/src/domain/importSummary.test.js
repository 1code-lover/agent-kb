/**
 * 导入回执摘要测试
 * - 覆盖 diagnostics 优先、fallback 兼容、对象展开与 URL 导入映射
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildImportNotice,
  buildImportReceiptSummary,
  buildPersistedImportReceiptSummary,
  resolveVisibleReceiptSummary,
} from './importSummary.js';

test('buildImportNotice 会优先使用 diagnostics 生成摘要', () => {
  const notice = buildImportNotice(
    {
      kb_id: 'kb-a',
      indexed_chunks: 5,
      diagnostics: {
        total_files: 3,
        indexed_files: 1,
        empty_files: 1,
        failed_files: 1,
        standalone_asset_candidate_count: 1,
        embedded_asset_count: 2,
        asset_warning_count: 1,
      },
    },
    '文件导入',
    '2026-07-25T10:00:00.000Z',
  );

  assert.equal(notice.kbId, 'kb-a');
  assert.ok(notice.message.includes('文件导入已完成，kb_id=kb-a'));
  assert.ok(notice.message.includes('对象 3 项'));
  assert.ok(notice.message.includes('已索引 1 项'));
  assert.ok(notice.message.includes('空导入 1 项'));
  assert.ok(notice.message.includes('失败 1 项'));
  assert.ok(notice.message.includes('切片 5 个'));
  assert.ok(notice.message.includes('独立资产候选 1 项'));
  assert.ok(notice.message.includes('内嵌资产 2 项'));
  assert.ok(notice.message.includes('资产告警 1 项'));
  assert.equal(notice.receiptSummary.status, 'warning');
  assert.equal(notice.receiptSummary.createdAt, '2026-07-25T10:00:00.000Z');
});

test('buildImportNotice 在缺少 diagnostics 时会回退到兼容字段', () => {
  const notice = buildImportNotice(
    {
      kb_id: 'kb-a',
      files: [{}, {}],
      indexed_chunks: 0,
      success_count: 2,
      empty_count: 0,
      failed_count: 0,
    },
    '文件导入',
  );

  assert.ok(notice.message.includes('对象 2 项'));
  assert.ok(notice.message.includes('已索引 2 项'));
  assert.ok(notice.message.includes('切片 0 个'));
  assert.ok(!notice.message.includes('独立资产候选'));
  assert.equal(notice.receiptSummary.status, 'success');
});

test('buildImportReceiptSummary 会展开文件结果并保留内嵌资产诊断信息', () => {
  const summary = buildImportReceiptSummary(
    {
      kb_id: 'kb-b',
      file_results: [
        {
          name: 'readme.md',
          type: 'text/markdown',
          path: '/workspace/data/kb-b/docs/readme.md',
          relative_path: 'docs/readme.md',
          folder_path: 'docs',
          status: 'empty',
          indexed_chunks: 0,
          diagnostics: {
            file_kind: 'markdown',
            empty_reason: 'embedded_no_extractable_text',
            document_count: 1,
            empty_document_count: 1,
            input_text_chars: 0,
            node_count: 0,
            nodes_with_embedding_count: 0,
            nodes_without_embedding_count: 0,
            index_stage_timings: {
              document_load_ms: 2,
              chunking_ms: 1,
              total_ms: 3,
            },
            embedded_asset_count: 1,
            embedded_asset_ready_count: 1,
            embedded_ocr_attempted_count: 1,
            embedded_ocr_no_text_count: 1,
          },
          embedded_assets: [
            {
              asset_id: 'asset-1',
              resolved_relative_path: 'docs/images/flow.png',
              path: '/workspace/data/kb-b/docs/images/flow.png',
              referenced_path: './images/flow.png',
              status: 'ready',
              mime_type: 'image/png',
              indexed_chunks: 0,
              indexed_from_ocr: false,
              source_doc_relative_path: 'docs/readme.md',
              ocr_diagnostics: {
                ocr_status: 'no_text',
                ocr_text_length: 0,
                indexed_from_ocr: false,
                ocr_error: '',
                ocr_engine: 'mock-paddleocr',
              },
            },
          ],
        },
      ],
      indexed_chunks: 0,
      diagnostics: {
        indexed_files: 0,
        empty_files: 1,
        failed_files: 0,
        embedded_asset_count: 1,
        embedded_ocr_no_text_count: 1,
      },
    },
    '文件导入',
    new Date('2026-07-25T12:30:00.000Z'),
  );

  assert.equal(summary.kbId, 'kb-b');
  assert.equal(summary.title, '文件导入回执');
  assert.equal(summary.status, 'warning');
  assert.equal(summary.createdAt, '2026-07-25T12:30:00.000Z');
  assert.equal(summary.itemCount, 1);
  assert.equal(summary.indexedChunks, 0);
  assert.ok(summary.metrics.some((item) => item.label === '内嵌资产' && item.value === 1));
  assert.ok(summary.metrics.some((item) => item.label === '内嵌 OCR 无文本' && item.value === 1));
  assert.ok(summary.summaryText.includes('空导入 1 项'));
  assert.equal(summary.items.length, 1);
  assert.equal(summary.items[0].type, 'import-file');
  assert.equal(summary.items[0].name, 'readme.md');
  assert.equal(summary.items[0].sourcePath, '/workspace/data/kb-b/docs/readme.md');
  assert.equal(summary.items[0].folderPath, 'docs');
  assert.equal(summary.items[0].emptyReason, 'embedded_no_extractable_text');
  assert.equal(summary.items[0].documentCount, 1);
  assert.equal(summary.items[0].emptyDocumentCount, 1);
  assert.equal(summary.items[0].nodeCount, 0);
  assert.ok(summary.items[0].indexStageSummaryText.includes('\u7d22\u5f15\u603b\u8017\u65f6 3 ms'));
  assert.equal(summary.items[0].embeddedAssets.length, 1);
  assert.equal(summary.items[0].embeddedAssets[0].type, 'asset');
  assert.equal(summary.items[0].embeddedAssets[0].id, 'asset-1');
  assert.equal(summary.items[0].embeddedAssets[0].sourcePath, '/workspace/data/kb-b/docs/images/flow.png');
  assert.equal(summary.items[0].embeddedAssets[0].ocrStatus, 'no_text');
  assert.equal(summary.items[0].embeddedAssets[0].indexedFromOcr, false);
});

test('buildImportReceiptSummary 会把 url_results 映射成导入对象', () => {
  const summary = buildImportReceiptSummary(
    {
      kb_id: 'kb-c',
      url_results: [
        { url: 'https://example.com/a', status: 'indexed', indexed_chunks: 3 },
        { url: 'https://example.com/b', status: 'failed', indexed_chunks: 0, message: 'timeout' },
      ],
      indexed_chunks: 3,
      success_count: 1,
      empty_count: 0,
      failed_count: 1,
      urls: ['https://example.com/a', 'https://example.com/b'],
    },
    'URL 导入',
  );

  assert.equal(summary.itemCount, 2);
  assert.equal(summary.status, 'warning');
  assert.equal(summary.items.length, 2);
  assert.equal(summary.items[0].type, 'import-url');
  assert.equal(summary.items[0].url, 'https://example.com/a');
  assert.equal(summary.items[0].indexedChunks, 3);
  assert.equal(summary.items[1].status, 'failed');
  assert.equal(summary.items[1].message, 'timeout');
});


test('buildImportReceiptSummary 会汇总导入诊断与阶段耗时摘要', () => {
  const summary = buildImportReceiptSummary(
    {
      receipt_id: 'kb-file-import-001',
      kb_id: 'kb-d',
      file_results: [
        {
          name: 'flow.png',
          type: 'image/png',
          path: '/workspace/data/kb-d/docs/flow.png',
          relative_path: 'docs/flow.png',
          status: 'empty',
          indexed_chunks: 0,
          diagnostics: {
            file_kind: 'image',
            empty_reason: 'shadowed_by_embedded_asset',
            skip_standalone_asset: true,
            ocr_status: 'skipped',
            stage_timings: {
              persist_ms: 6,
              standalone_ocr_ms: 0,
              primary_index_ms: 0,
              embedded_asset_extract_ms: 0,
              embedded_asset_ocr_ms: 0,
              embedded_asset_index_ms: 0,
              total_ms: 6,
            },
          },
        },
      ],
      diagnostics: {
        indexed_files: 0,
        empty_files: 1,
        failed_files: 0,
        document_count: 1,
        empty_document_count: 1,
        input_text_chars: 0,
        node_count: 0,
        nodes_with_embedding_count: 0,
        nodes_without_embedding_count: 0,
        skip_standalone_asset_count: 1,
        empty_reason_counts: {
          shadowed_by_embedded_asset: 1,
        },
        stage_timings: {
          ensure_models_ready_ms: 1,
          get_index_manager_ms: 2,
          persist_ms: 6,
          standalone_ocr_ms: 0,
          primary_index_ms: 0,
          embedded_asset_extract_ms: 4,
          embedded_asset_ocr_ms: 12,
          embedded_asset_index_ms: 8,
          register_assets_ms: 3,
          total_ms: 36,
        },
        index_stage_timings: {
          document_load_ms: 2,
          chunking_ms: 3,
          embedding_ms: 0,
          vector_store_ms: 0,
          docstore_ms: 0,
          index_insert_ms: 0,
          total_ms: 5,
        },
      },
    },
    '图片导入',
    '2026-07-26T08:00:00.000Z',
  );

  assert.equal(summary.receiptId, 'kb-file-import-001');
  assert.ok(summary.metrics.some((item) => item.label === '被接管图片' && item.value === 1));
  assert.ok(summary.emptyReasonMetrics.some((item) => item.label === '被内嵌资产接管' && item.value === 1));
  assert.ok(summary.batchStageMetrics.some((item) => item.label === '总耗时' && item.value === 36));
  assert.ok(summary.batchStageSummaryText.includes('总耗时 36 ms'));
  assert.equal(summary.items[0].skipStandaloneAsset, true);
  assert.ok(summary.items[0].stageTimingSummaryText.includes('总耗时 6 ms'));
});


test('buildPersistedImportReceiptSummary 会把后端持久化回执转换成前端摘要', () => {
  const summary = buildPersistedImportReceiptSummary({
    kb_id: 'kb-e',
    source_label: '文件上传',
    created_at: '2026-07-26T09:00:00.000Z',
    result: {
      receipt_id: 'receipt-1',
      kb_id: 'kb-e',
      indexed_chunks: 2,
      success_count: 1,
      empty_count: 0,
      failed_count: 0,
      file_results: [
        {
          name: 'notes.md',
          path: '/workspace/data/kb-e/notes.md',
          relative_path: 'notes.md',
          status: 'indexed',
          indexed_chunks: 2,
          diagnostics: {},
        },
      ],
    },
  });

  assert.equal(summary.kbId, 'kb-e');
  assert.equal(summary.title, '文件上传回执');
  assert.equal(summary.createdAt, '2026-07-26T09:00:00.000Z');
  assert.equal(summary.receiptId, 'receipt-1');
  assert.equal(summary.items[0].name, 'notes.md');
  assert.equal(summary.items[0].documentCount, 0);
  assert.equal(summary.batchIndexStageSummaryText, '');
});

test('resolveVisibleReceiptSummary 会优先使用当前页内存回执并回退到持久化回执', () => {
  const inMemorySummary = {
    kbId: 'kb-a',
    sourceLabel: '文件上传',
    title: '文件上传回执',
  };
  const persistedSummary = {
    kbId: 'kb-a',
    sourceLabel: '网页导入',
    title: '网页导入回执',
  };
  const foreignSummary = {
    kbId: 'kb-b',
    sourceLabel: '文件上传',
    title: '文件上传回执',
  };

  assert.equal(resolveVisibleReceiptSummary('kb-a', inMemorySummary, persistedSummary), inMemorySummary);
  assert.equal(resolveVisibleReceiptSummary('kb-a', null, persistedSummary), persistedSummary);
  assert.equal(resolveVisibleReceiptSummary('kb-a', foreignSummary, persistedSummary), persistedSummary);
  assert.equal(resolveVisibleReceiptSummary('kb-a', null, foreignSummary), null);
});
