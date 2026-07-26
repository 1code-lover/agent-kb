/**
 * 文件功能：
 * - 回归文件夹分组领域函数，确保路径归一化、根目录判定与分组排序稳定。
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildFolderGroups,
  getFolderLabel,
  getFolderPathFromObjectPath,
  normalizeWorkspacePath,
} from './folderTree.js';

test('normalizeWorkspacePath 会统一分隔符并去掉首尾斜杠', () => {
  assert.equal(normalizeWorkspacePath('\\docs\\guides\\intro.md\\'), 'docs/guides/intro.md');
  assert.equal(normalizeWorkspacePath('/images/flow.png'), 'images/flow.png');
  assert.equal(normalizeWorkspacePath('   '), '');
  assert.equal(normalizeWorkspacePath(null), '');
});

test('getFolderPathFromObjectPath 会返回根目录或父级 folder path', () => {
  assert.equal(getFolderPathFromObjectPath('readme.md'), '');
  assert.equal(getFolderPathFromObjectPath('docs/readme.md'), 'docs');
  assert.equal(getFolderPathFromObjectPath('docs/guides/setup.md'), 'docs/guides');
  assert.equal(getFolderLabel(''), '根目录');
  assert.equal(getFolderLabel('docs/guides'), 'docs/guides');
});

test('buildFolderGroups 会按 folder path 聚合对象并保持根目录优先', () => {
  const groups = buildFolderGroups(
    [
      { id: 'doc-3', name: 'setup.md', relative_path: 'guides/setup.md' },
      { id: 'doc-1', name: 'readme.md', relative_path: 'README.md' },
      { id: 'doc-2', name: 'intro.md', relative_path: 'docs/intro.md' },
      { id: 'doc-4', name: 'flow.png', relative_path: 'docs/images/flow.png' },
    ],
    {
      resolvePath: (item) => item.relative_path,
      resolveName: (item) => item.name,
      resolveKey: (item) => item.id,
    },
  );

  assert.deepEqual(
    groups.map((group) => group.label),
    ['根目录', 'docs', 'docs/images', 'guides'],
  );
  assert.equal(groups[0].itemCount, 1);
  assert.equal(groups[0].items[0].displayPath, 'README.md');
  assert.equal(groups[1].items[0].item.id, 'doc-2');
  assert.equal(groups[2].depth, 2);
  assert.equal(groups[3].items[0].name, 'setup.md');
});

test('buildFolderGroups 在对象缺少路径时会回退到根目录分组', () => {
  const groups = buildFolderGroups([{ asset_id: 'asset-1', title: '孤立资产' }], {
    resolvePath: (item) => item.relative_path || '',
    resolveName: (item) => item.title,
    resolveKey: (item) => item.asset_id,
  });

  assert.equal(groups.length, 1);
  assert.equal(groups[0].label, '根目录');
  assert.equal(groups[0].items[0].key, 'asset-1');
});
