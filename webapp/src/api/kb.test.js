/**
 * 文件功能：
 * - 回归上传 API 不得显式覆盖 multipart/form-data 头，避免 boundary 丢失导致 400。
 */

import test from "node:test";
import assert from "node:assert/strict";

import client from "./client.js";
import { importFiles } from "./kb.js";
import { uploadFilesToKnowledge } from "./agent.js";

function createFakeFormData(initialEntries = []) {
  return {
    entries: [...initialEntries],
    append(name, value) {
      this.entries.push([name, value]);
    },
  };
}

test("importFiles 会追加 kb_id 且不会显式传 multipart 头", async () => {
  const originalPost = client.post;
  const calls = [];
  client.post = async (...args) => {
    calls.push(args);
    return { code: 0, data: {} };
  };

  try {
    const formData = createFakeFormData([["files", "fake-file"]]);
    await importFiles(formData, "kb-a");

    assert.deepEqual(formData.entries, [["files", "fake-file"], ["kb_id", "kb-a"]]);
    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0], ["/api/kb/file/import", formData]);
  } finally {
    client.post = originalPost;
  }
});

test("uploadFilesToKnowledge 不会显式传 multipart 头", async () => {
  const originalPost = client.post;
  const calls = [];
  client.post = async (...args) => {
    calls.push(args);
    return { code: 0, data: { ok: true } };
  };

  try {
    const formData = createFakeFormData([["files", "agent-upload"]]);
    const result = await uploadFilesToKnowledge(formData);

    assert.deepEqual(result, { ok: true });
    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0], ["/api/kb/file/import", formData]);
  } finally {
    client.post = originalPost;
  }
});
