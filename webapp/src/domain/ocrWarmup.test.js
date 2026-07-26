/**
 * 文件功能：
 * - 回归 OCR 预热状态的前端展示文案映射，避免 Knowledge Workspace 头部散落硬编码。
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { buildOcrWarmupSummary } from './ocrWarmup.js';

test('buildOcrWarmupSummary 会把 ready 状态映射为可展示摘要', () => {
  const summary = buildOcrWarmupSummary({
    state: 'ready',
    is_ready: true,
    last_duration_ms: 26099.456,
  });

  assert.equal(summary.state, 'ready');
  assert.equal(summary.tone, 'success');
  assert.equal(summary.title, 'OCR 已就绪');
  assert.match(summary.summary, /图片 OCR 可直接复用已加载实例/);
  assert.match(summary.detail, /26099 ms/);
  assert.equal(summary.isReady, true);
});

test('buildOcrWarmupSummary 会把 warming 状态映射为预热中提示', () => {
  const summary = buildOcrWarmupSummary({
    state: 'warming',
    attempt_count: 1,
  });

  assert.equal(summary.state, 'warming');
  assert.equal(summary.tone, 'warning');
  assert.equal(summary.title, 'OCR 预热中');
  assert.match(summary.summary, /后台加载 OCR 模型/);
  assert.match(summary.detail, /attempt 1/i);
});

test('buildOcrWarmupSummary 会把 failed 状态映射为错误提示并回显错误原因', () => {
  const summary = buildOcrWarmupSummary({
    state: 'failed',
    last_error: 'PaddleOCR init timeout',
  });

  assert.equal(summary.state, 'failed');
  assert.equal(summary.tone, 'danger');
  assert.equal(summary.title, 'OCR 预热失败');
  assert.match(summary.summary, /首次图片导入/);
  assert.match(summary.detail, /PaddleOCR init timeout/);
});

test('buildOcrWarmupSummary 在缺少状态时会回退为未预热', () => {
  const summary = buildOcrWarmupSummary(null);

  assert.equal(summary.state, 'idle');
  assert.equal(summary.tone, 'muted');
  assert.equal(summary.title, 'OCR 未预热');
  assert.match(summary.summary, /首次图片导入会承担模型初始化耗时/);
  assert.equal(summary.detail, '等待后台预热或首张图片导入触发加载');
});
