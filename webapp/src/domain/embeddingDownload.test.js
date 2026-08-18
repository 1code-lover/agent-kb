/**
 * 文件功能：
 * - 验证 Embedding 下载状态到 UI 门禁、进度与文案的纯函数映射。
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { buildEmbeddingDownloadView, formatBytes } from './embeddingDownload.js';

test('formatBytes 以可读单位展示空间', () => {
  assert.equal(formatBytes(0), '0 B');
  assert.equal(formatBytes(1536), '1.5 KiB');
  assert.equal(formatBytes(2 * 1024 ** 3), '2 GiB');
});

test('未预检时只允许检查空间', () => {
  const view = buildEmbeddingDownloadView({ state: 'idle', enough_space: null });
  assert.equal(view.canPreflight, true);
  assert.equal(view.canStart, false);
  assert.equal(view.canCancel, false);
});

test('estimated 下载明确标记估算进度并允许取消', () => {
  const view = buildEmbeddingDownloadView({
    state: 'downloading',
    phase: 'downloading',
    progress_mode: 'estimated',
    progress_percent: 42.5,
    bytes_downloaded: 850,
    bytes_total: 2000,
    current_file: 'model.safetensors',
    enough_space: true,
  });
  assert.equal(view.progressPercent, 42.5);
  assert.match(view.progressLabel, /估算/);
  assert.match(view.detail, /model\.safetensors/);
  assert.equal(view.canCancel, true);
  assert.equal(view.canStart, false);
});

test('空间不足时显示缺口且禁止开始', () => {
  const view = buildEmbeddingDownloadView({
    state: 'idle',
    phase: 'checking_space',
    enough_space: false,
    free_bytes: 100,
    required_bytes: 200,
    reserve_bytes: 50,
    shortfall_bytes: 150,
  });
  assert.equal(view.canStart, false);
  assert.equal(view.canPreflight, true);
  assert.match(view.detail, /还缺/);
});

test('取消或失败后可以重新预检和重试', () => {
  for (const state of ['cancelled', 'failed']) {
    const view = buildEmbeddingDownloadView({ state, enough_space: true, last_error: 'network' });
    assert.equal(view.canStart, true);
    assert.equal(view.canPreflight, true);
    assert.equal(view.isRetry, true);
  }
});
