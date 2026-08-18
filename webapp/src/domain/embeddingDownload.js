/**
 * 文件功能：
 * - 将 Embedding 下载状态转换为可展示文案、进度与操作门禁。
 */

const ACTIVE_STATES = new Set(['checking_space', 'downloading', 'verifying', 'cancelling']);

/** 把字节数格式化为紧凑的二进制单位。 */
export function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return '0 B';
  }
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const amount = bytes / (1024 ** index);
  return `${Number(amount.toFixed(amount >= 10 || index === 0 ? 0 : 1))} ${units[index]}`;
}

/** 构建下载卡片视图模型。 */
export function buildEmbeddingDownloadView(status = {}, error = null) {
  const state = status?.state || 'idle';
  const active = ACTIVE_STATES.has(state);
  const enoughSpace = status?.enough_space;
  const progressPercent = Math.max(0, Math.min(100, Number(status?.progress_percent) || 0));
  const estimated = status?.progress_mode !== 'exact';
  const progressLabel = `${estimated ? '估算 ' : ''}${progressPercent.toFixed(progressPercent % 1 ? 1 : 0)}%`;
  const currentFile = status?.current_file ? ` · ${status.current_file}` : '';
  const downloaded = formatBytes(status?.bytes_downloaded);
  const total = formatBytes(status?.bytes_total);
  let title = 'Embedding 缓存下载';
  let detail = '请先检查磁盘空间，再开始下载。';

  if (active) {
    const labels = {
      checking_space: '正在检查磁盘空间',
      downloading: '正在下载模型缓存',
      verifying: '正在校验完整性',
      cancelling: '正在取消下载',
    };
    title = labels[state] || title;
    detail = `${downloaded} / ${total} · ${progressLabel}${currentFile}`;
  } else if (enoughSpace === false) {
    title = '磁盘空间不足';
    detail = `可用 ${formatBytes(status.free_bytes)}，下载与预留共需 ${formatBytes((status.required_bytes || 0) + (status.reserve_bytes || 0))}，还缺 ${formatBytes(status.shortfall_bytes)}。`;
  } else if (state === 'ready') {
    title = 'Embedding 缓存已就绪';
    detail = '完整性校验通过，已触发运行时重新加载。';
  } else if (state === 'cancelled') {
    title = '下载已取消';
    detail = status.last_error || '本次临时文件已清理，可以重新开始。';
  } else if (state === 'failed') {
    title = '下载失败';
    detail = status.last_error || error || '可重新检查空间后重试。';
  } else if (enoughSpace === true) {
    title = '磁盘空间检查通过';
    detail = `可用 ${formatBytes(status.free_bytes)}，预计需要 ${formatBytes(status.required_bytes)}，另预留 ${formatBytes(status.reserve_bytes)}。`;
  }

  return {
    state,
    title,
    detail,
    progressPercent,
    progressLabel,
    showProgress: active || state === 'ready',
    canPreflight: !active && state !== 'ready',
    canStart: !active && enoughSpace === true && state !== 'ready',
    canCancel: ['downloading', 'verifying', 'cancelling'].includes(state),
    isRetry: ['cancelled', 'failed'].includes(state),
    error: error || null,
  };
}
