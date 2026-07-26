/**
 * 文件功能：
 * - 回归聊天 evidence 透传。
 * - 校验证据 / 文档 / 资产预览 API 的封装与优先级。
 */

import test from "node:test";
import assert from "node:assert/strict";

import client from "./client.js";
import { queryChat } from "./chat.js";
import {
  buildPreviewRequest,
  previewAsset,
  previewDoc,
  previewEvidence,
  previewItem,
} from "./evidence.js";


test("queryChat 会透传 evidence 字段", async () => {
  const originalPost = client.post;
  const calls = [];
  const payload = { question: "what", kb_ids: ["kb-a"] };
  const response = {
    code: 0,
    data: {
      answer: "done",
      evidence: [{ id: "ev-1", title: "manual.pdf", doc_id: "doc-1", asset_id: "asset-1" }],
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
    assert.equal(result.data.evidence[0].asset_id, "asset-1");
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


test("previewAsset 会正确拼装资产预览请求", async () => {
  const originalGet = client.get;
  const calls = [];
  client.get = async (...args) => {
    calls.push(args);
    return { code: 0, data: { asset_id: "asset:1/2", status: "active" } };
  };

  try {
    const result = await previewAsset("kb-a", "asset:1/2");
    assert.deepEqual(result, { code: 0, data: { asset_id: "asset:1/2", status: "active" } });
    assert.deepEqual(calls[0], [
      "/api/kb/assets/asset%3A1%2F2",
      { params: { kb_id: "kb-a" } },
    ]);
  } finally {
    client.get = originalGet;
  }
});


test("buildPreviewRequest 会优先选择资产预览", () => {
  assert.deepEqual(
    buildPreviewRequest({
      kb_id: "kb-a",
      asset_id: "asset-1",
      doc_id: "doc-1",
      id: "ev-1",
      preview_locator: { page: "3" },
    }),
    {
      kind: "asset",
      kb_id: "kb-a",
      asset_id: "asset-1",
    },
  );
});


test("previewItem 遇到 asset_id 时应优先调用资产预览接口", async () => {
  const originalGet = client.get;
  const originalPost = client.post;
  const getCalls = [];
  const postCalls = [];
  client.get = async (...args) => {
    getCalls.push(args);
    return { code: 0, data: { asset_id: "asset-1", asset_role: "embedded" } };
  };
  client.post = async (...args) => {
    postCalls.push(args);
    return { code: 0, data: { preview_type: "text_excerpt" } };
  };

  try {
    const result = await previewItem({
      kb_id: "kb-a",
      asset_id: "asset-1",
      doc_id: "doc-1",
      id: "ev-1",
      preview_locator: { page: "9" },
    });
    assert.deepEqual(result, { code: 0, data: { asset_id: "asset-1", asset_role: "embedded" } });
    assert.equal(getCalls.length, 1);
    assert.equal(postCalls.length, 0);
    assert.deepEqual(getCalls[0], [
      "/api/kb/assets/asset-1",
      { params: { kb_id: "kb-a" } },
    ]);
  } finally {
    client.get = originalGet;
    client.post = originalPost;
  }
});


test("previewItem 在没有 asset_id 时回退到文档预览", async () => {
  const originalGet = client.get;
  const originalPost = client.post;
  const getCalls = [];
  const postCalls = [];
  client.get = async (...args) => {
    getCalls.push(args);
    return { code: 0, data: {} };
  };
  client.post = async (...args) => {
    postCalls.push(args);
    return { code: 0, data: { doc_id: "doc-2", preview_type: "text_excerpt" } };
  };

  try {
    const result = await previewItem({
      kb_id: "kb-a",
      doc_id: "doc-2",
      id: "ev-2",
      preview_locator: { page: "11" },
    });
    assert.deepEqual(result, { code: 0, data: { doc_id: "doc-2", preview_type: "text_excerpt" } });
    assert.equal(getCalls.length, 0);
    assert.deepEqual(postCalls[0], [
      "/api/kb/preview",
      { kb_id: "kb-a", doc_id: "doc-2", preview_locator: { page: "11" } },
    ]);
  } finally {
    client.get = originalGet;
    client.post = originalPost;
  }
});
