/**
 * 文件功能：
 * - 验证 Agent 工作台状态辅助函数的行为。
 */

import test from "node:test";
import assert from "node:assert/strict";

import {
  createWorkspaceState,
  appendTimelineEvent,
  mapAgentRunToTimeline
} from "./agentState.js";

test("createWorkspaceState should return default workspace shape", () => {
  const state = createWorkspaceState();
  assert.equal(state.runState, "idle");
  assert.deepEqual(state.timeline, []);
  assert.deepEqual(state.plan, []);
  assert.deepEqual(state.evidence, []);
  assert.equal(state.taskState, null);
  assert.deepEqual(state.pendingActions, []);
});

test("appendTimelineEvent should append event with monotonic seq", () => {
  const first = appendTimelineEvent([], { type: "user", content: "hello" });
  const second = appendTimelineEvent(first, { type: "assistant", content: "world" });

  assert.equal(first.length, 1);
  assert.equal(first[0].seq, 1);
  assert.equal(second.length, 2);
  assert.equal(second[1].seq, 2);
});

test("mapAgentRunToTimeline should include user message and step events", () => {
  const timeline = mapAgentRunToTimeline("fix bug", {
    answer: "done",
    steps: [
      {
        step: "kb_search",
        title: "检索知识库",
        status: "completed",
        risk_level: "low",
        receipt_id: "r1",
        evidence_ids: ["ev-1"],
        summary: "命中 1 条证据"
      },
      { step: "patch file" }
    ]
  });

  assert.equal(timeline[0].type, "user");
  assert.equal(timeline[0].content, "fix bug");
  assert.equal(timeline[1].type, "assistant");
  assert.equal(timeline[1].content, "done");
  assert.equal(timeline[2].type, "step");
  assert.equal(timeline[2].content, "命中 1 条证据");
  assert.equal(timeline[2].meta.status, "completed");
  assert.equal(timeline[2].meta.evidenceIds[0], "ev-1");
  assert.equal(timeline[3].content, "patch file");
});
