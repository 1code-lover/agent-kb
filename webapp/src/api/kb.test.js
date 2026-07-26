/**
 * 文件功能：
 * - 回归知识库上传 API 的 FormData 契约，确保不会显式覆盖 multipart 头。
 * - 验证 kb_id / import_mode / relative_paths 的追加行为与目录接口封装。
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import client from './client.js';
import { getLatestImportReceipt, importFiles, listFolders } from './kb.js';
import { uploadFilesToKnowledge } from './agent.js';

function createFakeFormData(initialEntries = []) {
  return {
    entries: [...initialEntries],
    append(name, value) {
      this.entries.push([name, value]);
    },
  };
}

test('importFiles 会默认追加 kb_id 与 import_mode=flatten，且不显式传 multipart 头', async () => {
  const originalPost = client.post;
  const calls = [];
  client.post = async (...args) => {
    calls.push(args);
    return { code: 0, data: {} };
  };

  try {
    const formData = createFakeFormData([['files', 'fake-file']]);
    await importFiles(formData, 'kb-a');

    assert.deepEqual(formData.entries, [
      ['files', 'fake-file'],
      ['kb_id', 'kb-a'],
      ['import_mode', 'flatten'],
    ]);
    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0], ['/api/kb/file/import', formData]);
  } finally {
    client.post = originalPost;
  }
});

test('importFiles 在 preserve_tree 模式下会追加多个 relative_paths', async () => {
  const originalPost = client.post;
  const calls = [];
  client.post = async (...args) => {
    calls.push(args);
    return { code: 0, data: {} };
  };

  try {
    const formData = createFakeFormData([
      ['files', 'readme.md'],
      ['files', 'flow.png'],
    ]);
    await importFiles(formData, 'kb-a', {
      importMode: 'preserve_tree',
      relativePaths: ['docs/readme.md', 'docs/images/flow.png'],
    });

    assert.deepEqual(formData.entries, [
      ['files', 'readme.md'],
      ['files', 'flow.png'],
      ['kb_id', 'kb-a'],
      ['import_mode', 'preserve_tree'],
      ['relative_paths', 'docs/readme.md'],
      ['relative_paths', 'docs/images/flow.png'],
    ]);
    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0], ['/api/kb/file/import', formData]);
  } finally {
    client.post = originalPost;
  }
});

test('importFiles 在未提供 relative_paths 时不会凭空追加该字段', async () => {
  const originalPost = client.post;
  const calls = [];
  client.post = async (...args) => {
    calls.push(args);
    return { code: 0, data: {} };
  };

  try {
    const formData = createFakeFormData([['files', 'root-file']]);
    await importFiles(formData, 'kb-a', {
      importMode: 'preserve_tree',
      relativePaths: [],
    });

    assert.deepEqual(formData.entries, [
      ['files', 'root-file'],
      ['kb_id', 'kb-a'],
      ['import_mode', 'preserve_tree'],
    ]);
    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0], ['/api/kb/file/import', formData]);
  } finally {
    client.post = originalPost;
  }
});

test('listFolders 会调用 /api/kb/folders 并显式携带 kb_id', async () => {
  const originalGet = client.get;
  const calls = [];
  client.get = async (...args) => {
    calls.push(args);
    return { code: 0, data: { folders: [] } };
  };

  try {
    const response = await listFolders('kb-a');

    assert.deepEqual(response, { code: 0, data: { folders: [] } });
    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0], ['/api/kb/folders', { params: { kb_id: 'kb-a' } }]);
  } finally {
    client.get = originalGet;
  }
});

test('uploadFilesToKnowledge 不会显式传 multipart 头', async () => {
  const originalPost = client.post;
  const calls = [];
  client.post = async (...args) => {
    calls.push(args);
    return { code: 0, data: { ok: true } };
  };

  try {
    const formData = createFakeFormData([['files', 'agent-upload']]);
    const result = await uploadFilesToKnowledge(formData);

    assert.deepEqual(result, { ok: true });
    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0], ['/api/kb/file/import', formData]);
  } finally {
    client.post = originalPost;
  }
});


test('getLatestImportReceipt ???????????? kb_id', async () => {
  const originalGet = client.get;
  const calls = [];
  client.get = async (...args) => {
    calls.push(args);
    return { code: 0, data: { receipt: null } };
  };

  try {
    const response = await getLatestImportReceipt('kb-a');

    assert.deepEqual(response, { code: 0, data: { receipt: null } });
    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0], ['/api/kb/import-receipt/latest', { params: { kb_id: 'kb-a' } }]);
  } finally {
    client.get = originalGet;
  }
});
