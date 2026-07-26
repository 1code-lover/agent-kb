/**
 * 上传导入对象模型测试
 * - 覆盖目录相对路径归一化、平铺模式默认值与 preserve_tree 载荷构造。
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildImportPayload,
  buildUploadEntries,
  getUploadEntryLabel,
  KB_IMPORT_MODES,
  normalizeUploadRelativePath,
} from './uploadImport.js';

function createFakeFile(name, webkitRelativePath = '') {
  return {
    name,
    size: 1024,
    lastModified: 1700000000000,
    webkitRelativePath,
  };
}

test('normalizeUploadRelativePath 会统一分隔符并移除前导斜杠', () => {
  assert.equal(normalizeUploadRelativePath('\\docs\\spec\\readme.md'), 'docs/spec/readme.md');
  assert.equal(normalizeUploadRelativePath('/images//flow.png'), 'images/flow.png');
  assert.equal(normalizeUploadRelativePath('   '), '');
});

test('buildUploadEntries 会保留目录文件的 webkitRelativePath', () => {
  const entries = buildUploadEntries([
    createFakeFile('readme.md', 'docs/readme.md'),
    createFakeFile('flow.png', 'docs\\images\\flow.png'),
    createFakeFile('note.md'),
  ]);

  assert.equal(entries.length, 3);
  assert.equal(entries[0].relativePath, 'docs/readme.md');
  assert.equal(entries[1].relativePath, 'docs/images/flow.png');
  assert.equal(entries[2].relativePath, null);
});

test('getUploadEntryLabel 会优先显示 relativePath，其次回退到文件名', () => {
  const directoryEntry = buildUploadEntries([createFakeFile('readme.md', 'docs/readme.md')])[0];
  const flatEntry = buildUploadEntries([createFakeFile('summary.md')])[0];

  assert.equal(getUploadEntryLabel(directoryEntry), 'docs/readme.md');
  assert.equal(getUploadEntryLabel(flatEntry), 'summary.md');
});

test('buildImportPayload 在默认模式下生成 flatten 载荷且不附带 relative_paths', () => {
  const entries = buildUploadEntries([
    createFakeFile('a.md'),
    createFakeFile('b.md', 'docs/b.md'),
  ]);

  const payload = buildImportPayload(entries);

  assert.equal(payload.importMode, KB_IMPORT_MODES.FLATTEN);
  assert.deepEqual(payload.files.map((file) => file.name), ['a.md', 'b.md']);
  assert.deepEqual(payload.relativePaths, []);
});

test('buildImportPayload 在 preserve_tree 模式下会回显逐文件 relative_paths', () => {
  const entries = buildUploadEntries([
    createFakeFile('readme.md', 'docs/readme.md'),
    createFakeFile('loose.md'),
  ]);

  const payload = buildImportPayload(entries, KB_IMPORT_MODES.PRESERVE_TREE);

  assert.equal(payload.importMode, KB_IMPORT_MODES.PRESERVE_TREE);
  assert.deepEqual(payload.files.map((file) => file.name), ['readme.md', 'loose.md']);
  assert.deepEqual(payload.relativePaths, ['docs/readme.md', 'loose.md']);
});