/**
 * 文件功能：
 * - 回归 Knowledge Workspace 视图 / 动作元数据，保证页面骨架依赖的常量与回退逻辑稳定。
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  KB_WORKSPACE_ACTION_MODES,
  KB_WORKSPACE_VIEW_MODES,
  getWorkspaceActionMeta,
  getWorkspaceViewMeta,
  listWorkspaceViews,
} from './knowledgeWorkspace.js';

test('listWorkspaceViews 会按配置返回可切换视图', () => {
  const views = listWorkspaceViews();

  assert.deepEqual(
    views.map((item) => item.key),
    [
      KB_WORKSPACE_VIEW_MODES.DOCUMENTS,
      KB_WORKSPACE_VIEW_MODES.RECENT_IMPORTS,
      KB_WORKSPACE_VIEW_MODES.ASSETS,
      KB_WORKSPACE_VIEW_MODES.FAILED_ITEMS,
    ],
  );
  assert.equal(views[0].implemented, true);
  assert.equal(views[2].implemented, true);
});

test('getWorkspaceViewMeta 在未知视图下会回退到 documents', () => {
  const meta = getWorkspaceViewMeta('unknown-view');

  assert.equal(meta.key, KB_WORKSPACE_VIEW_MODES.DOCUMENTS);
  assert.match(meta.description, /文件夹层级/);
});

test('getWorkspaceViewMeta 会为资产视图返回真实描述', () => {
  const meta = getWorkspaceViewMeta(KB_WORKSPACE_VIEW_MODES.ASSETS);

  assert.equal(meta.implemented, true);
  assert.match(meta.description, /独立资产与内嵌资产/);
});

test('getWorkspaceActionMeta 会返回动作说明并在未知动作下回退到 none', () => {
  const upload = getWorkspaceActionMeta(KB_WORKSPACE_ACTION_MODES.UPLOAD);
  const fallback = getWorkspaceActionMeta('missing');

  assert.equal(upload.title, '导入文件');
  assert.equal(upload.implemented, true);
  assert.equal(fallback.key, KB_WORKSPACE_ACTION_MODES.NONE);
  assert.match(fallback.description, /对象浏览态/);
});
