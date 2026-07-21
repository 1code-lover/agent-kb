import test from "node:test";
import assert from "node:assert/strict";

import {
  AGENT_EXPERIENCES,
  buildChatPayload,
  buildChatSessionId,
  buildExperienceSummary,
} from "./agentExperience.js";

test("experiences expose three user-facing modes", () => {
  assert.deepEqual(
    AGENT_EXPERIENCES.map((item) => item.value),
    ["basic", "knowledge", "agent"],
  );
});

test("basic chat payload omits kb_ids", () => {
  assert.deepEqual(
    buildChatPayload({
      experience: "basic",
      question: "你好",
      sessionId: "desktop-default",
    }),
    {
      question: "你好",
      session_id: "desktop-default-chat-all",
    },
  );
});

test("knowledge chat payload pins selected kb", () => {
  assert.deepEqual(
    buildChatPayload({
      experience: "knowledge",
      question: "粮仓是什么",
      sessionId: "desktop-default",
      selectedKbId: "grain-knowledge-base",
    }),
    {
      question: "粮仓是什么",
      session_id: "desktop-default-chat-grain-knowledge-base",
      kb_ids: ["grain-knowledge-base"],
    },
  );
});

test("knowledge chat requires an explicit kb", () => {
  assert.throws(
    () => buildChatPayload({
      experience: "knowledge",
      question: "测试",
      sessionId: "desktop-default",
      selectedKbId: "",
    }),
    /必须先选择目标知识库/,
  );
});

test("session id helper separates basic and scoped chat threads", () => {
  assert.equal(buildChatSessionId({ experience: "basic", sessionId: "desktop-default" }), "desktop-default-chat-all");
  assert.equal(
    buildChatSessionId({
      experience: "knowledge",
      sessionId: "desktop-default",
      selectedKbId: "intern-kb",
    }),
    "desktop-default-chat-intern-kb",
  );
});

test("experience summary surfaces scope text", () => {
  assert.match(buildExperienceSummary({ experience: "basic" }), /全部知识范围/);
  assert.match(
    buildExperienceSummary({
      experience: "knowledge",
      selectedKb: { kb_id: "grain-knowledge-base", kb_name: "Grain Knowledge Base" },
    }),
    /Grain Knowledge Base/,
  );
  assert.match(buildExperienceSummary({ experience: "agent" }), /高级 Agent/);
});
