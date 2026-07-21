/**
 * 文件功能：
 * - 验证统一 API 响应体只解包一层 data，避免知识库列表被错误读取为空。
 */

import test from "node:test";
import assert from "node:assert/strict";

import { readApiData } from "./response.js";

test("统一响应体应返回第一层 data", () => {
  const payload = { code: 0, message: "ok", data: { items: [{ kb_id: "default" }] } };
  assert.deepEqual(readApiData(payload), { items: [{ kb_id: "default" }] });
});

test("缺失 data 时返回 null", () => {
  assert.equal(readApiData(null), null);
  assert.equal(readApiData({ code: 0 }), null);
});
