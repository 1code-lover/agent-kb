import test from "node:test";
import assert from "node:assert/strict";

import {
  appendTimelineEvent,
  buildManualTimeline,
  buildReadFileTemplate,
  createWorkspaceState,
  mapAgentRunToTimeline,
  mergeApprovalTimeline,
  mergeReceipts
} from "./agentState.js";

test("createWorkspaceState should return the target desktop workspace shape", () => {
  const state = createWorkspaceState();

  assert.equal(state.currentMode, "agent");
  assert.equal(state.knowledgeScope.kb_name, "foxglove_beifen");
  assert.deepEqual(state.receipts, []);
  assert.equal(state.lastAnswer, "");
});

test("appendTimelineEvent should append event with monotonic seq", () => {
  const first = appendTimelineEvent([], { type: "user", content: "hello" });
  const second = appendTimelineEvent(first, { type: "assistant", content: "world" });

  assert.equal(first.length, 1);
  assert.equal(first[0].seq, 1);
  assert.equal(second.length, 2);
  assert.equal(second[1].seq, 2);
});

test("buildManualTimeline should create submission timeline", () => {
  const timeline = buildManualTimeline("scan workspace", "agent");

  assert.equal(timeline.length, 2);
  assert.equal(timeline[0].type, "task");
  assert.equal(timeline[0].meta.mode, "agent");
});

test("mapAgentRunToTimeline should prefer backend timeline when available", () => {
  const timeline = mapAgentRunToTimeline({
    timeline: [
      { type: "user", content: "fix issue" },
      { type: "assistant", content: "done" }
    ]
  });

  assert.equal(timeline[0].seq, 1);
  assert.equal(timeline[1].content, "done");
});

test("mapAgentRunToTimeline should fallback to steps when backend timeline missing", () => {
  const timeline = mapAgentRunToTimeline({
    question: "search kb",
    answer: "found",
    steps: [
      {
        step: "kb_search",
        title: "KB Search",
        status: "completed",
        risk_level: "low",
        receipt_id: "r1",
        evidence_ids: ["ev-1"],
        summary: "Found 1 evidence item"
      }
    ]
  });

  assert.equal(timeline[2].type, "step");
  assert.equal(timeline[2].meta.receiptId, "r1");
});

test("mergeReceipts should sort receipts by created_at descending", () => {
  const receipts = mergeReceipts([
    { id: "1", created_at: "2026-05-28T10:00:00Z" },
    { id: "2", created_at: "2026-05-28T11:00:00Z" }
  ]);

  assert.equal(receipts[0].id, "2");
});

test("mergeApprovalTimeline should append approval timeline after existing entries", () => {
  const merged = mergeApprovalTimeline(
    [
      { seq: 1, type: "task", content: "cmd" },
      { seq: 2, type: "status", content: "waiting" }
    ],
    {
      timeline: [
        { type: "step", content: "approved" },
        { type: "assistant", content: "done" }
      ]
    }
  );

  assert.equal(merged.length, 4);
  assert.equal(merged[2].content, "approved");
  assert.equal(merged[3].seq, 4);
});

test("buildReadFileTemplate should return a Windows path template", () => {
  assert.match(buildReadFileTemplate(), /^[A-Z]:\\\\/);
});
