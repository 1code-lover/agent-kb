/**
 * 文件功能：
 * - 定义 Knowledge Workspace 的视图模式、动作模式与显示元数据，避免页面层散落硬编码。
 */

export const KB_WORKSPACE_VIEW_MODES = Object.freeze({
  DOCUMENTS: 'documents',
  RECENT_IMPORTS: 'recent_imports',
  ASSETS: 'assets',
  FAILED_ITEMS: 'failed_items',
});

export const KB_WORKSPACE_ACTION_MODES = Object.freeze({
  NONE: 'none',
  UPLOAD: 'upload',
  DIRECTORY_IMPORT: 'directory_import',
  WEB_IMPORT: 'web_import',
});

const VIEW_META = Object.freeze({
  [KB_WORKSPACE_VIEW_MODES.DOCUMENTS]: {
    key: KB_WORKSPACE_VIEW_MODES.DOCUMENTS,
    label: '文档',
    description: '浏览当前知识库中的正式文档对象，并按相对路径感知文件夹层级。',
    implemented: true,
  },
  [KB_WORKSPACE_VIEW_MODES.RECENT_IMPORTS]: {
    key: KB_WORKSPACE_VIEW_MODES.RECENT_IMPORTS,
    label: '最近导入',
    description: '查看最近一次导入回执与诊断摘要，确认索引结果是否符合预期。',
    implemented: true,
  },
  [KB_WORKSPACE_VIEW_MODES.ASSETS]: {
    key: KB_WORKSPACE_VIEW_MODES.ASSETS,
    label: '资产',
    description: '浏览当前知识库中的独立资产与内嵌资产，并支持按相对路径分组与独立预览。',
    implemented: true,
  },
  [KB_WORKSPACE_VIEW_MODES.FAILED_ITEMS]: {
    key: KB_WORKSPACE_VIEW_MODES.FAILED_ITEMS,
    label: '失败项',
    description: '后续将承载导入失败与待修复对象，本轮先提供稳定占位。',
    implemented: false,
  },
});

const ACTION_META = Object.freeze({
  [KB_WORKSPACE_ACTION_MODES.NONE]: {
    key: KB_WORKSPACE_ACTION_MODES.NONE,
    label: '无动作',
    title: '对象浏览',
    description: '当前处于对象浏览态，可以切换视图或选择对象查看详情。',
    implemented: true,
  },
  [KB_WORKSPACE_ACTION_MODES.UPLOAD]: {
    key: KB_WORKSPACE_ACTION_MODES.UPLOAD,
    label: '导入文件',
    title: '导入文件',
    description: '上传本地文件并写入当前知识库。',
    implemented: true,
  },
  [KB_WORKSPACE_ACTION_MODES.DIRECTORY_IMPORT]: {
    key: KB_WORKSPACE_ACTION_MODES.DIRECTORY_IMPORT,
    label: '导入目录',
    title: '导入目录',
    description: '目录级导入将在下一阶段进入主线，本轮先保留产品位。',
    implemented: false,
  },
  [KB_WORKSPACE_ACTION_MODES.WEB_IMPORT]: {
    key: KB_WORKSPACE_ACTION_MODES.WEB_IMPORT,
    label: '导入网页',
    title: '导入网页',
    description: '批量导入网页内容并写入当前知识库。',
    implemented: true,
  },
});

export function listWorkspaceViews() {
  return Object.values(VIEW_META);
}

export function getWorkspaceViewMeta(viewMode) {
  return VIEW_META[viewMode] || VIEW_META[KB_WORKSPACE_VIEW_MODES.DOCUMENTS];
}

export function getWorkspaceActionMeta(actionMode) {
  return ACTION_META[actionMode] || ACTION_META[KB_WORKSPACE_ACTION_MODES.NONE];
}
