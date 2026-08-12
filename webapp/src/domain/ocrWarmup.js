/**
 * 文件功能：
 * - 将 /api/health 返回的 OCR 与 embedding 预热状态归一为 Workspace 头部可直接展示的摘要对象。
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

export function buildEmbeddingWarmupSummary(embeddingWarmup, embeddingDiagnostics) {
  const state = normalizeState(embeddingWarmup?.state, embeddingWarmup?.is_ready);
  const durationText = formatDurationMs(embeddingWarmup?.last_duration_ms);
  const attemptCount = Number.isInteger(embeddingWarmup?.attempt_count) ? embeddingWarmup.attempt_count : null;
  const lastError = typeof embeddingWarmup?.last_error === 'string' ? embeddingWarmup.last_error.trim() : '';
  const localPath = typeof embeddingDiagnostics?.local_path === 'string' ? embeddingDiagnostics.local_path.trim() : '';
  const localPathExists = embeddingDiagnostics?.local_path_exists === true;
  const allowRemoteDownload = embeddingDiagnostics?.allow_remote_download === true;

  if (state === 'ready') {
    return {
      state,
      tone: 'success',
      title: 'Embedding 已就绪',
      summary: '检索向量模型已加载，知识库导入和问答可以直接执行。',
      detail: durationText ? `上次预热 ${durationText}` : '后台预热已完成',
      isReady: true,
    };
  }

  if (state === 'warming') {
    return {
      state,
      tone: 'warning',
      title: 'Embedding 预热中',
      summary: '后台正在加载检索向量模型，导入和问答会等待模型就绪。',
      detail: attemptCount ? `后台 attempt ${attemptCount} 正在执行` : '后台预热任务已启动',
      isReady: false,
    };
  }

  if (!localPathExists && !allowRemoteDownload && localPath) {
    return {
      state: state === 'failed' ? 'failed' : state,
      tone: 'danger',
      title: 'Embedding 缓存缺失',
      summary: '本地向量模型缓存不存在，运行时已禁止远程下载以避免桌面启动卡住。',
      detail: `请先准备 ${localPath}`,
      isReady: false,
    };
  }

  if (state === 'failed') {
    return {
      state,
      tone: 'danger',
      title: 'Embedding 预热失败',
      summary: '检索向量模型未加载，知识库导入、检索和问答会不可用。',
      detail: lastError ? `最近错误：${lastError}` : '最近一次预热失败，但未返回详细错误信息',
      isReady: false,
    };
  }

  return {
    state: 'idle',
    tone: 'muted',
    title: 'Embedding 未预热',
    summary: '首次导入或问答前需要加载检索向量模型。',
    detail: '等待后台预热或手动触发模型加载',
    isReady: false,
  };
}
