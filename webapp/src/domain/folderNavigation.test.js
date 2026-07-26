/**
 * 文件功能：
 * - 回归文件夹范围导航规则，确保目录选项、范围标签与子树匹配逻辑稳定。
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  ALL_FOLDER_SCOPE,
  ROOT_FOLDER_SCOPE,
  buildFolderOptions,
  getFolderScopeLabel,
  hasFolderOption,
  matchesFolderScope,
} from './folderNavigation.js';

test('buildFolderOptions 会补齐全部目录与根目录，并对目录路径去重排序', () => {
  const options = buildFolderOptions([
    { path: 'docs/images' },
    { path: 'ops' },
    { path: 'docs' },
    { path: 'docs' },
  ]);

  assert.deepEqual(
    options.map((item) => item.value),
    [ALL_FOLDER_SCOPE, ROOT_FOLDER_SCOPE, 'docs', 'ops', 'docs/images'],
  );
  assert.equal(options[0].label, '全部目录');
  assert.equal(options[1].label, '根目录');
  assert.equal(options[4].depth, 2);
});

test('matchesFolderScope 会按目录子树匹配对象路径，并单独处理根目录', () => {
  assert.equal(matchesFolderScope('', ALL_FOLDER_SCOPE), true);
  assert.equal(matchesFolderScope('docs', ALL_FOLDER_SCOPE), true);
  assert.equal(matchesFolderScope('', ROOT_FOLDER_SCOPE), true);
  assert.equal(matchesFolderScope('docs', ROOT_FOLDER_SCOPE), false);
  assert.equal(matchesFolderScope('docs', 'docs'), true);
  assert.equal(matchesFolderScope('docs/images', 'docs'), true);
  assert.equal(matchesFolderScope('docs\\images', 'docs'), true);
  assert.equal(matchesFolderScope('ops/runbook', 'docs'), false);
});

test('getFolderScopeLabel 与 hasFolderOption 会返回稳定的人类可读结果', () => {
  const options = buildFolderOptions([{ path: 'docs' }]);

  assert.equal(hasFolderOption(options, ALL_FOLDER_SCOPE), true);
  assert.equal(hasFolderOption(options, ROOT_FOLDER_SCOPE), true);
  assert.equal(hasFolderOption(options, 'docs'), true);
  assert.equal(hasFolderOption(options, 'missing'), false);
  assert.equal(getFolderScopeLabel(options, ALL_FOLDER_SCOPE), '全部目录');
  assert.equal(getFolderScopeLabel(options, ROOT_FOLDER_SCOPE), '根目录');
  assert.equal(getFolderScopeLabel(options, 'docs'), 'docs（含子目录）');
  assert.equal(getFolderScopeLabel(options, 'missing'), 'missing（含子目录）');
});
