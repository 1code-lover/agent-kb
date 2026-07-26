/**
 * 文件功能：
 * - 将前端 File / FileList 选择结果归一化为知识库导入对象。
 * - 统一表达平铺导入（flatten）与保留目录导入（preserve_tree）两种模式。
 */

export const KB_IMPORT_MODES = Object.freeze({
  FLATTEN: 'flatten',
  PRESERVE_TREE: 'preserve_tree',
});

function toFileArray(fileList) {
  return Array.from(fileList || []).filter(Boolean);
}

export function normalizeUploadRelativePath(relativePath) {
  if (typeof relativePath !== 'string') {
    return '';
  }

  return relativePath
    .trim()
    .replace(/\\/g, '/')
    .replace(/^\/+/, '')
    .replace(/\/{2,}/g, '/');
}

export function buildUploadEntries(fileList) {
  return toFileArray(fileList).map((file) => {
    const normalizedRelativePath = normalizeUploadRelativePath(file?.webkitRelativePath || '');
    return {
      file,
      relativePath: normalizedRelativePath || null,
    };
  });
}

export function getUploadEntryLabel(entry) {
  return normalizeUploadRelativePath(entry?.relativePath || '') || entry?.file?.name || '未命名文件';
}

export function buildImportPayload(entries, importMode = KB_IMPORT_MODES.FLATTEN) {
  const normalizedEntries = Array.isArray(entries) ? entries.filter((entry) => entry?.file) : [];
  const files = normalizedEntries.map((entry) => entry.file);
  const effectiveMode = importMode === KB_IMPORT_MODES.PRESERVE_TREE
    ? KB_IMPORT_MODES.PRESERVE_TREE
    : KB_IMPORT_MODES.FLATTEN;

  if (effectiveMode === KB_IMPORT_MODES.PRESERVE_TREE) {
    return {
      importMode: effectiveMode,
      files,
      relativePaths: normalizedEntries.map((entry) => (
        normalizeUploadRelativePath(entry.relativePath || '') || entry.file.name
      )),
    };
  }

  return {
    importMode: KB_IMPORT_MODES.FLATTEN,
    files,
    relativePaths: [],
  };
}