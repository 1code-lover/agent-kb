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
              file_save_ms: 6,
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
          file_save_ms: 6,
          persist_ms: 6,
          standalone_ocr_ms: 0,
          primary_index_ms: 0,
          embedded_asset_extract_ms: 4,
          embedded_asset_ocr_ms: 12,
          embedded_asset_index_ms: 8,
          index_storage_persist_ms: 5,
          doc_count_update_ms: 2,
          register_assets_ms: 3,
          receipt_store_ms: 1,
          result_build_ms: 2,
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
  assert.ok(summary.batchStageMetrics.some((item) => item.label === '文件保存' && item.value === 6));
  assert.ok(summary.batchStageMetrics.some((item) => item.label === '索引落盘' && item.value === 5));
  assert.ok(summary.batchStageMetrics.some((item) => item.label === '文档计数' && item.value === 2));
  assert.ok(summary.batchStageMetrics.some((item) => item.label === '回执落盘' && item.value === 1));
  assert.ok(summary.batchStageMetrics.some((item) => item.label === '结果组装' && item.value === 2));
  assert.ok(summary.batchStageSummaryText.includes('\u603b\u8017\u65f6 36 ms \u00b7 \u6587\u4ef6\u4fdd\u5b58 6 ms'));
  assert.ok(summary.batchStageSummaryText.includes('\u6587\u4ef6\u4fdd\u5b58 6 ms'));
  assert.ok(summary.batchIndexStageMetrics.some((item) => item.label === '\u7d22\u5f15\u603b\u8017\u65f6' && item.value === 5));
  assert.ok(summary.batchIndexStageMetrics.some((item) => item.label === '\u6587\u6863\u52a0\u8f7d' && item.value === 2));
  assert.ok(summary.batchIndexStageSummaryText.includes('\u7d22\u5f15\u603b\u8017\u65f6 5 ms \u00b7 \u6587\u6863\u52a0\u8f7d 2 ms'));
  assert.equal(summary.items[0].skipStandaloneAsset, true);
  assert.ok(summary.items[0].stageTimingSummaryText.includes('\u603b\u8017\u65f6 6 ms'));
  assert.ok(summary.items[0].stageTimingSummaryText.includes('\u6587\u4ef6\u4fdd\u5b58 6 ms'));
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


test('buildImportReceiptSummary \u4f1a\u4f18\u5148\u6d88\u8d39\u540e\u7aef display_summary \u751f\u6210\u7ed3\u6784\u5316\u6458\u8981', () => {
  const summary = buildImportReceiptSummary(
    {
      kb_id: 'kb-f',
      indexed_chunks: 1,
      success_count: 9,
      empty_count: 0,
      failed_count: 0,
      diagnostics: {
        indexed_files: 0,
        empty_files: 0,
        failed_files: 0,
        asset_warning_count: 1,
      },
      display_summary: {
        source_kind: 'file_import',
        total_items: 3,
        indexed_items: 1,
        empty_items: 1,
        failed_items: 0,
        asset_registered_count: 2,
        asset_registered_but_not_indexed_count: 1,
        asset_warning_count: 1,
        dependency_missing_count: 2,
        top_missing_dependencies: [
          { dependency: 'paddleocr', count: 2 },
        ],
        top_empty_reasons: [
          { reason: 'no_extractable_text', count: 1 },
        ],
        has_blockers: true,
        has_dependency_issues: true,
        has_warnings: true,
        next_actions: [
          { action: 'install_dependency', dependency: 'paddleocr', count: 2 },
          { action: 'review_empty_assets', count: 1 },
        ],
      },
    },
    '\u6587\u4ef6\u5bfc\u5165',
    '2026-07-28T10:00:00.000Z',
  );

  assert.equal(summary.itemCount, 3);
  assert.equal(summary.indexedFiles, 1);
  assert.equal(summary.emptyFiles, 1);
  assert.equal(summary.failedFiles, 0);
  assert.equal(summary.status, 'warning');
  assert.equal(summary.headline, '\u6709 2 \u9879\u5bf9\u8c61\u56e0\u4f9d\u8d56\u7f3a\u5931\u672a\u5b8c\u6210\u6587\u4ef6\u5bfc\u5165');
  assert.equal(summary.userMessage, '\u8bf7\u5148\u5b89\u88c5\u7f3a\u5931\u4f9d\u8d56\uff0c\u518d\u91cd\u65b0\u5bfc\u5165\u6216\u91cd\u8bd5\u53d7\u5f71\u54cd\u5bf9\u8c61\u3002');
  assert.ok(summary.summaryText.includes('\u5bf9\u8c61 3 \u9879'));
  assert.ok(summary.metrics.some((item) => item.label === '\u5df2\u767b\u8bb0\u8d44\u4ea7' && item.value === 2));
  assert.ok(summary.metrics.some((item) => item.label === '\u5df2\u767b\u8bb0\u672a\u5165\u7d22\u5f15\u8d44\u4ea7' && item.value === 1));
  assert.ok(summary.metrics.some((item) => item.label === '\u4f9d\u8d56\u7f3a\u5931' && item.value === 2));
  assert.ok(summary.emptyReasonMetrics.some((item) => item.label === '\u672a\u63d0\u53d6\u5230\u6587\u672c' && item.value === 1));
  assert.deepEqual(summary.topMissingDependencyMetrics, [
    {
      key: 'dependency:paddleocr:0',
      label: 'paddleocr',
      value: 2,
      unit: '\u9879',
    },
  ]);
  assert.equal(summary.nextActions[0].label, '\u5b89\u88c5\u7f3a\u5931\u4f9d\u8d56 paddleocr\uff08\u5f71\u54cd 2 \u9879\uff09');
  assert.equal(summary.nextActions[1].label, '\u68c0\u67e5\u672a\u5165\u7d22\u5f15\u56fe\u7247\uff0c\u91cd\u70b9\u5173\u6ce8 OCR \u6216\u56fe\u7247\u6587\u672c\u8d28\u91cf\uff081 \u9879\uff09');
});



test('buildImportReceiptSummary \u4f1a\u628a mixed batch display_summary \u6620\u5c04\u4e3a\u7a7a\u7ed3\u679c\u4e0e\u9636\u6bb5\u8017\u65f6\u6458\u8981', () => {
  const summary = buildImportReceiptSummary(
    {
      kb_id: 'kb-mixed',
      receipt_id: 'receipt-mixed-1',
      indexed_chunks: 4,
      success_count: 3,
      empty_count: 1,
      failed_count: 0,
      diagnostics: {
        total_files: 4,
        indexed_files: 3,
        empty_files: 1,
        failed_files: 0,
        stage_timings: {
          prepare_ms: 1.5,
          storage_persist_ms: 2.5,
          receipt_store_ms: 0.5,
          total_ms: 4.5,
        },
        index_stage_timings: {
          docstore_ms: 1.1,
          vector_store_ms: 0.9,
          total_ms: 2.0,
        },
      },
      display_summary: {
        source_kind: 'file_import',
        item_label: '\u6587\u4ef6',
        total_items: 4,
        indexed_items: 3,
        empty_items: 1,
        failed_items: 0,
        asset_registered_count: 2,
        asset_registered_but_not_indexed_count: 0,
        asset_warning_count: 0,
        dependency_missing_count: 0,
        top_missing_dependencies: [],
        top_empty_reasons: [
          { reason: 'shadowed_by_embedded_asset', count: 1 },
        ],
        has_blockers: false,
        has_dependency_issues: false,
        has_warnings: true,
        next_actions: [
          {
            action: 'review_empty_items',
            count: 1,
            top_empty_reasons: [{ reason: 'shadowed_by_embedded_asset', count: 1 }],
          },
        ],
      },
      file_results: [
        { name: 'cutover.md', status: 'indexed', indexed_chunks: 1, diagnostics: { asset_registered: true } },
        { name: 'vendor-cutover.pdf', status: 'indexed', indexed_chunks: 1, diagnostics: {} },
        { name: 'preview-board.png', status: 'indexed', indexed_chunks: 2, diagnostics: { asset_registered: true } },
        {
          name: 'escalation-board.png',
          status: 'empty',
          indexed_chunks: 0,
          diagnostics: {
            empty_reason: 'shadowed_by_embedded_asset',
            skip_standalone_asset: true,
            asset_registered: false,
          },
        },
      ],
    },
    '\u6587\u4ef6\u5bfc\u5165',
    '2026-07-31T12:00:00.000Z',
  );

  assert.equal(summary.status, 'warning');
  assert.equal(summary.headline, '\u6709 1 \u9879\u5bf9\u8c61\u6587\u4ef6\u5bfc\u5165\u540e\u4e3a\u7a7a');
  assert.equal(summary.userMessage, '\u5bf9\u8c61\u5df2\u5165\u5e93\uff0c\u4f46\u6682\u672a\u63d0\u53d6\u5230\u53ef\u7d22\u5f15\u5185\u5bb9\uff0c\u53ef\u91cd\u70b9\u68c0\u67e5 OCR \u6216\u89e3\u6790\u914d\u7f6e\u3002');
  assert.ok(summary.summaryText.includes('\u5bf9\u8c61 4 \u9879'));
  assert.ok(summary.summaryText.includes('\u5df2\u7d22\u5f15 3 \u9879'));
  assert.ok(summary.summaryText.includes('\u7a7a\u5bfc\u5165 1 \u9879'));
  assert.ok(summary.emptyReasonMetrics.some((item) => item.label === '\u88ab\u5185\u5d4c\u8d44\u4ea7\u63a5\u7ba1' && item.value === 1));
  assert.equal(summary.nextActions.length, 1);
  assert.equal(summary.nextActions[0].label, '\u68c0\u67e5\u7a7a\u7ed3\u679c\u5bf9\u8c61\uff0c\u786e\u8ba4\u662f\u5426\u9700\u8981 OCR \u6216\u5176\u4ed6\u89e3\u6790\u65b9\u5f0f\uff081 \u9879\uff09');
  assert.equal(summary.batchStageSummaryText, '\u603b\u8017\u65f6 4.5 ms \u00b7 \u56de\u6267\u843d\u76d8 0.5 ms');
  assert.equal(summary.batchIndexStageSummaryText, '\u7d22\u5f15\u603b\u8017\u65f6 2 ms \u00b7 \u5411\u91cf\u5199\u5e93 0.9 ms \u00b7 \u6587\u6863\u5199\u5e93 1.1 ms');
});


test('buildImportReceiptSummary \u4f1a\u5728 display_summary \u6210\u529f\u573a\u666f\u4e0b\u751f\u6210\u9762\u5411\u7528\u6237\u7684\u6458\u8981\u6587\u6848', () => {
  const summary = buildImportReceiptSummary(
    {
      kb_id: 'kb-g',
      indexed_chunks: 4,
      display_summary: {
        source_kind: 'url_import',
        total_items: 2,
        indexed_items: 2,
        empty_items: 0,
        failed_items: 0,
        asset_registered_count: 0,
        asset_registered_but_not_indexed_count: 0,
        asset_warning_count: 0,
        dependency_missing_count: 0,
        top_missing_dependencies: [],
        top_empty_reasons: [],
        has_blockers: false,
        has_dependency_issues: false,
        has_warnings: false,
        next_actions: [],
      },
      url_results: [
        { url: 'https://example.com/a', status: 'indexed', indexed_chunks: 2 },
        { url: 'https://example.com/b', status: 'indexed', indexed_chunks: 2 },
      ],
    },
    'URL \u5bfc\u5165',
    '2026-07-28T11:00:00.000Z',
  );

  assert.equal(summary.status, 'success');
  assert.equal(summary.headline, '\u5df2\u6210\u529f\u5b8c\u6210 2 \u9879URL \u5bfc\u5165');
  assert.equal(summary.userMessage, '\u5bf9\u8c61\u5df2\u5b8c\u6210\u89e3\u6790\u5e76\u8fdb\u5165\u7d22\u5f15\uff0c\u53ef\u4ee5\u76f4\u63a5\u7528\u4e8e\u68c0\u7d22\u4e0e\u95ee\u7b54\u3002');
  assert.equal(summary.nextActions.length, 0);
  assert.equal(summary.topMissingDependencyMetrics.length, 0);
});
