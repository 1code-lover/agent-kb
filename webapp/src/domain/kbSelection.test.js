/**
 * 文件功能：
 * - 验证知识库目标选择规则，防止上传与网页导入静默回退到 default。
 */

import test from "node:test";
import assert from "node:assert/strict";

import {
  EMPTY_KB_SELECTION,
  canUseKbTarget,
  reconcileKbSelection,
  requireKbTarget,
  selectionAfterCreate,
  selectionAfterDelete,
} from "./kbSelection.js";

const kbList = [
  { kb_id: "default", kb_name: "默认知识库", status: "active" },
  { kb_id: "grain-knowledge-base", kb_name: "粮仓知识库", status: "active" },
  { kb_id: "disabled-kb", kb_name: "停用知识库", status: "disabled" },
];

test("初始目标必须为空，不能静默选择 default", () => {
  assert.equal(EMPTY_KB_SELECTION, "");
  assert.equal(canUseKbTarget(kbList, EMPTY_KB_SELECTION), false);
});

test("只有已登记且 active 的知识库可以作为导入目标", () => {
  assert.equal(canUseKbTarget(kbList, "default"), true);
  assert.equal(canUseKbTarget(kbList, "grain-knowledge-base"), true);
  assert.equal(canUseKbTarget(kbList, "disabled-kb"), false);
  assert.equal(canUseKbTarget(kbList, "missing-kb"), false);
});

test("刷新列表后应清理不存在或非 active 的当前选择", () => {
  assert.equal(reconcileKbSelection(kbList, "grain-knowledge-base"), "grain-knowledge-base");
  assert.equal(reconcileKbSelection(kbList, "disabled-kb"), "");
  assert.equal(reconcileKbSelection(kbList, "missing-kb"), "");
});

test("创建 active 知识库成功后自动选中新知识库", () => {
  assert.equal(selectionAfterCreate({ kb_id: "new-kb", status: "active" }), "new-kb");
  assert.equal(selectionAfterCreate({ kb_id: "new-kb", status: "disabled" }), "");
});

test("删除当前知识库后清空选择，删除其他知识库不影响当前选择", () => {
  assert.equal(selectionAfterDelete("grain-knowledge-base", "grain-knowledge-base"), "");
  assert.equal(selectionAfterDelete("grain-knowledge-base", "default"), "grain-knowledge-base");
});

test("API 调用缺少明确目标时必须立即失败", () => {
  assert.equal(requireKbTarget("grain-knowledge-base"), "grain-knowledge-base");
  assert.throws(() => requireKbTarget(""), /必须先选择目标知识库/);
  assert.throws(() => requireKbTarget(null), /必须先选择目标知识库/);
});
