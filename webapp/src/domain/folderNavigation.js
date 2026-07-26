/**
 * 文件功能：
 * - 封装 Knowledge Workspace 中文件夹范围选择的纯规则，供对象区头部与列表过滤复用。
 * - 明确“文件夹是组织层，不是安全边界”，这里只处理浏览范围与展示文案。
 */

import { getFolderLabel, normalizeWorkspacePath } from './folderTree.js';

export const ALL_FOLDER_SCOPE = '__all__';
export const ROOT_FOLDER_SCOPE = '';

function compareFolderOption(left, right) {
  if (left.depth !== right.depth) {
    return left.depth - right.depth;
  }
  return left.value.localeCompare(right.value, undefined, {
    numeric: true,
    sensitivity: 'base',
  });
}

export function normalizeFolderScope(value) {
  if (value === ALL_FOLDER_SCOPE) {
    return ALL_FOLDER_SCOPE;
  }
  return normalizeWorkspacePath(value);
}

export function buildFolderOptions(folders = []) {
  const uniquePaths = new Set();

  folders.forEach((item) => {
    const rawPath = typeof item === 'string' ? item : item?.path;
    const normalized = normalizeWorkspacePath(rawPath);
    if (normalized) {
      uniquePaths.add(normalized);
    }
  });

  const folderOptions = Array.from(uniquePaths)
    .map((path) => ({
      key: 'folder:' + path,
      value: path,
      label: getFolderLabel(path),
      depth: path.split('/').length,
      kind: 'folder',
    }))
    .sort(compareFolderOption);

  return [
    {
      key: 'folder:all',
      value: ALL_FOLDER_SCOPE,
      label: '全部目录',
      depth: -1,
      kind: 'all',
    },
    {
      key: 'folder:root',
      value: ROOT_FOLDER_SCOPE,
      label: getFolderLabel(ROOT_FOLDER_SCOPE),
      depth: 0,
      kind: 'root',
    },
    ...folderOptions,
  ];
}

export function hasFolderOption(folderOptions = [], selectedFolderScope = ALL_FOLDER_SCOPE) {
  const normalized = normalizeFolderScope(selectedFolderScope);
  return folderOptions.some((option) => option.value === normalized);
}

export function getFolderScopeLabel(folderOptions = [], selectedFolderScope = ALL_FOLDER_SCOPE) {
  const normalized = normalizeFolderScope(selectedFolderScope);
  const matched = folderOptions.find((option) => option.value === normalized);
  if (matched) {
    if (matched.kind === 'folder') {
      return matched.label + '（含子目录）';
    }
    return matched.label;
  }
  if (normalized === ALL_FOLDER_SCOPE) {
    return '全部目录';
  }
  if (!normalized) {
    return getFolderLabel(ROOT_FOLDER_SCOPE);
  }
  return getFolderLabel(normalized) + '（含子目录）';
}

export function matchesFolderScope(itemFolderPath, selectedFolderScope = ALL_FOLDER_SCOPE) {
  const normalizedScope = normalizeFolderScope(selectedFolderScope);
  if (normalizedScope === ALL_FOLDER_SCOPE) {
    return true;
  }

  const normalizedItemFolder = normalizeWorkspacePath(itemFolderPath);
  if (normalizedScope === ROOT_FOLDER_SCOPE) {
    return normalizedItemFolder === ROOT_FOLDER_SCOPE;
  }

  return normalizedItemFolder === normalizedScope || normalizedItemFolder.startsWith(normalizedScope + '/');
}
