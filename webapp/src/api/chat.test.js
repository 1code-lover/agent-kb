/**
 * 文件功能：
 * - 回归聊天 evidence 透传与 preview API 封装。
 */

import test from "node:test";
import assert from "node:assert/strict";

import client from "./client.js";
import { queryChat } from "./chat.js";
import { previewDoc, previewEvidence } from "./evidence.js";


test("queryChat 会透传 evidence 字段", async () => {
  const originalPost = client.post;
  const calls = [];
  const payload = { question: "what", kb_ids: ["kb-a"] };
  const response = {
    code: 0,
    data: {
      answer: "done",
      evidence: [{ id: "ev-1", title: "manual.pdf", doc_id: "doc-1" }],
    },
  };
  client.post = async (...args) => {
    calls.push(args);
    return response;
  };

  try {
    const result = await queryChat(payload);
    assert.deepEqual(result, response);
    assert.deepEqual(result.data.evidence, response.data.evidence);
    assert.deepEqual(calls[0], ["/api/chat/query", payload]);
  } finally {
    client.post = originalPost;
  }
});


test("previewEvidence 会正确拼装 /api/kb/preview 请求", async () => {
  const originalPost = client.post;
  const calls = [];
  client.post = async (...args) => {
    calls.push(args);
    return { code: 0, data: { preview_type: "text_excerpt" } };
  };

  try {
    const result = await previewEvidence({
      kb_id: "kb-a",
      evidence_id: "ev:encoded",
      preview_locator: { page: "7" },
    });
    assert.deepEqual(result, { code: 0, data: { preview_type: "text_excerpt" } });
    assert.deepEqual(calls[0], [
      "/api/kb/preview",
      { kb_id: "kb-a", evidence_id: "ev:encoded", preview_locator: { page: "7" } },
    ]);
  } finally {
    client.post = originalPost;
  }
});


test("previewDoc 会正确拼装 doc 预览请求", async () => {
  const originalPost = client.post;
  const calls = [];
  client.post = async (...args) => {
    calls.push(args);
    return { code: 0, data: { doc_id: "doc-1", preview_type: "text_excerpt" } };
  };

  try {
    const result = await previewDoc("kb-a", "doc-1", { page: "12" });
    assert.deepEqual(result, { code: 0, data: { doc_id: "doc-1", preview_type: "text_excerpt" } });
    assert.deepEqual(calls[0], [
      "/api/kb/preview",
      { kb_id: "kb-a", doc_id: "doc-1", preview_locator: { page: "12" } },
    ]);
  } finally {
    client.post = originalPost;
  }
});
