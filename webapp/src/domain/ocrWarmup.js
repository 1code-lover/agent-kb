/**
 * 文件功能：
 * - 将 /api/health 返回的 OCR 预热状态归一为 Workspace 头部可直接展示的摘要对象。
 */

function formatDurationMs(value) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
    return '';
  }
  return `${Math.round(value)} ms`;
}

function normalizeState(rawState, isReady) {
  if (isReady === true) {
    return 'ready';
  }
  if (typeof rawState !== 'string') {
    return 'idle';
  }
  const nextState = rawState.trim().toLowerCase();
  return nextState || 'idle';
}

export function buildOcrWarmupSummary(ocrWarmup) {
  const state = normalizeState(ocrWarmup?.state, ocrWarmup?.is_ready);
  const durationText = formatDurationMs(ocrWarmup?.last_duration_ms);
  const attemptCount = Number.isInteger(ocrWarmup?.attempt_count) ? ocrWarmup.attempt_count : null;
  const lastError = typeof ocrWarmup?.last_error === 'string' ? ocrWarmup.last_error.trim() : '';

  if (state === 'ready') {
    return {
      state,
      tone: 'success',
      title: 'OCR 已就绪',
      summary: '图片 OCR 可直接复用已加载实例，首张图片导入不会再等待模型初始化。',
      detail: durationText ? `上次预热 ${durationText}` : '后台预热已完成',
      isReady: true,
    };
  }

  if (state === 'warming') {
    return {
      state,
      tone: 'warning',
      title: 'OCR 预热中',
      summary: '后台加载 OCR 模型中，首次图片导入会在就绪后明显更快。',
      detail: attemptCount ? `后台 attempt ${attemptCount} 正在执行` : '后台预热任务已启动',
      isReady: false,
    };
  }

  if (state === 'failed') {
    return {
      state,
      tone: 'danger',
      title: 'OCR 预热失败',
      summary: '后台预热未完成，首次图片导入可能回退为同步初始化，整体耗时会明显变长。',
      detail: lastError ? `最近错误：${lastError}` : '最近一次预热失败，但未返回详细错误信息',
      isReady: false,
    };
  }

  return {
    state: 'idle',
    tone: 'muted',
    title: 'OCR 未预热',
    summary: '首次图片导入会承担模型初始化耗时，建议等待后台预热完成后再做首张图片导入。',
    detail: '等待后台预热或首张图片导入触发加载',
    isReady: false,
  };
}
