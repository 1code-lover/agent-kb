/**
 * 文件功能：
 * - 基于对象相对路径生成文件夹分组结果，供文档视图与资产视图复用。
 * - 明确约定文件夹只承担组织与浏览职责，不承担知识库安全边界。
 */

function compareDisplayText(left, right) {
  return String(left || '').localeCompare(String(right || ''), undefined, {
    numeric: true,
    sensitivity: 'base',
  });
}

export function normalizeWorkspacePath(path) {
  if (typeof path !== 'string') {
    return '';
  }

  return path
    .trim()
    .replace(/\\/g, '/')
    .replace(/\/+/g, '/')
    .replace(/^\/+/, '')
    .replace(/\/+$/, '');
}

export function getFolderPathFromObjectPath(path) {
  const normalized = normalizeWorkspacePath(path);
  if (!normalized) {
    return '';
  }

  const parts = normalized.split('/').filter(Boolean);
  if (parts.length <= 1) {
    return '';
  }
  return parts.slice(0, -1).join('/');
}

export function getFolderLabel(folderPath) {
  const normalized = normalizeWorkspacePath(folderPath);
  return normalized || '根目录';
}

function defaultResolvePath(item) {
  return item?.relative_path || item?.path || '';
}

function defaultResolveName(item) {
  return item?.name || item?.title || '';
}

function defaultResolveKey(item, index) {
  return item?.id || item?.asset_id || item?.path || String(index);
}

export function buildFolderGroups(items, options = {}) {
  const resolvePath = options.resolvePath || defaultResolvePath;
  const resolveName = options.resolveName || defaultResolveName;
  const resolveKey = options.resolveKey || defaultResolveKey;
  const safeItems = Array.isArray(items) ? items : [];

  const groups = new Map();
  safeItems.forEach((item, index) => {
    const displayPath = normalizeWorkspacePath(resolvePath(item));
    const folderPath = getFolderPathFromObjectPath(displayPath);
    const groupKey = folderPath;
    const nextEntry = {
      key: resolveKey(item, index),
      item,
      name: resolveName(item),
      displayPath,
      folderPath,
    };

    if (!groups.has(groupKey)) {
      groups.set(groupKey, {
        key: groupKey || '__root__',
        path: folderPath,
        label: getFolderLabel(folderPath),
        depth: folderPath ? folderPath.split('/').length : 0,
        items: [],
      });
    }

    groups.get(groupKey).items.push(nextEntry);
  });

  return Array.from(groups.values())
    .sort((left, right) => {
      if (!left.path && right.path) {
        return -1;
      }
      if (left.path && !right.path) {
        return 1;
      }
      return compareDisplayText(left.path, right.path);
    })
    .map((group) => ({
      ...group,
      itemCount: group.items.length,
      items: [...group.items].sort((left, right) => {
        const pathComparison = compareDisplayText(left.displayPath, right.displayPath);
        if (pathComparison !== 0) {
          return pathComparison;
        }
        return compareDisplayText(left.name, right.name);
      }),
    }));
}
