import test from "node:test";
import assert from "node:assert/strict";

import {
  AGENT_EXPERIENCES,
  CHAT_REQUEST_LIMITS,
  CHAT_RESPONSE_MODES,
  buildChatPayload,
  buildChatSessionId,
  buildExperienceSummary,
  experienceRequiresKb,
  normalizeChatRequestOptions,
} from "./agentExperience.js";

test("experiences expose three user-facing modes", () => {
  assert.deepEqual(
    AGENT_EXPERIENCES.map((item) => item.value),
    ["basic", "knowledge", "agent"],
  );
});

test("chat response modes stay aligned with advanced settings options", () => {
  assert.deepEqual(CHAT_RESPONSE_MODES, [
    "compact",
    "refine",
    "tree_summarize",
    "simple_summarize",
    "accumulate",
    "compact_accumulate",
  ]);
});

test("chat request limits stay aligned with backend query contract", () => {
  assert.deepEqual(CHAT_REQUEST_LIMITS, {
    topKMin: 1,
    topKMax: 50,
    topNMin: 1,
    topNMax: 50,
    rerankerModelMaxLength: 128,
  });
});

test("basic and knowledge modes both require an explicit kb target", () => {
  assert.equal(experienceRequiresKb("basic"), true);
  assert.equal(experienceRequiresKb("knowledge"), true);
  assert.equal(experienceRequiresKb("agent"), false);
});

test("basic chat payload pins the selected kb", () => {
  assert.deepEqual(
    buildChatPayload({
      experience: "basic",
      question: "你好",
      sessionId: "desktop-default",
      selectedKbId: "grain-knowledge-base",
    }),
    {
      question: "你好",
      session_id: "desktop-default-basic-grain-knowledge-base",
      kb_ids: ["grain-knowledge-base"],
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
      session_id: "desktop-default-knowledge-grain-knowledge-base",
      kb_ids: ["grain-knowledge-base"],
    },
  );
});

test("chat payload carries request-level rag overrides", () => {
  assert.deepEqual(
    buildChatPayload({
      experience: "knowledge",
      question: "粮仓是什么",
      sessionId: "desktop-default",
      selectedKbId: "grain-knowledge-base",
      requestOptions: {
        top_k: "9",
        response_mode: "tree_summarize",
        use_reranker: false,
        top_n: 2,
        reranker_model: " bge-reranker-v2-m3 ",
      },
    }),
    {
      question: "粮仓是什么",
      session_id: "desktop-default-knowledge-grain-knowledge-base",
      kb_ids: ["grain-knowledge-base"],
      top_k: 9,
      response_mode: "tree_summarize",
      use_reranker: false,
      top_n: 2,
      reranker_model: "bge-reranker-v2-m3",
    },
  );
});

test("scoped chat modes require an explicit kb", () => {
  assert.throws(
    () => buildChatPayload({
      experience: "knowledge",
      question: "测试",
      sessionId: "desktop-default",
      selectedKbId: "",
    }),
    /必须先选择目标知识库/,
  );
  assert.throws(
    () => buildChatPayload({
      experience: "basic",
      question: "测试",
      sessionId: "desktop-default",
      selectedKbId: "",
    }),
    /必须先选择目标知识库/,
  );
});

test("session id helper separates basic and scoped chat threads", () => {
  assert.equal(
    buildChatSessionId({ experience: "basic", sessionId: "desktop-default", selectedKbId: "kb-a" }),
    "desktop-default-basic-kb-a",
  );
  assert.equal(
    buildChatSessionId({
      experience: "knowledge",
      sessionId: "desktop-default",
      selectedKbId: "intern-kb",
    }),
    "desktop-default-knowledge-intern-kb",
  );
});

test("experience summary surfaces single-kb scope text", () => {
  assert.match(buildExperienceSummary({ experience: "basic" }), /先选择一个 active 知识库/);
  assert.doesNotMatch(buildExperienceSummary({ experience: "basic" }), /全部知识范围/);
  assert.match(
    buildExperienceSummary({
      experience: "knowledge",
      selectedKb: { kb_id: "grain-knowledge-base", kb_name: "Grain Knowledge Base" },
    }),
    /Grain Knowledge Base/,
  );
  assert.match(buildExperienceSummary({ experience: "agent" }), /高级 Agent/);
});


test("normalizeChatRequestOptions drops invalid values but preserves boolean overrides", () => {
  assert.deepEqual(
    normalizeChatRequestOptions({
      top_k: 0,
      response_mode: "   ",
      use_reranker: false,
      top_n: "-1",
      reranker_model: "",
    }),
    { use_reranker: false },
  );
});

test("normalizeChatRequestOptions keeps only backend-compatible values", () => {
  assert.deepEqual(
    normalizeChatRequestOptions({
      top_k: 51,
      response_mode: "unsupported-mode",
      use_reranker: true,
      top_n: "99",
      reranker_model: "x".repeat(129),
    }),
    { use_reranker: true },
  );
});

test("buildChatPayload drops frontend-invalid request overrides before sending", () => {
  assert.deepEqual(
    buildChatPayload({
      experience: "knowledge",
      question: "粮仓是什么",
      sessionId: "desktop-default",
      selectedKbId: "grain-knowledge-base",
      requestOptions: {
        top_k: 999,
        response_mode: "unsupported-mode",
        use_reranker: false,
        top_n: 88,
        reranker_model: "x".repeat(129),
      },
    }),
    {
      question: "粮仓是什么",
      session_id: "desktop-default-knowledge-grain-knowledge-base",
      kb_ids: ["grain-knowledge-base"],
      use_reranker: false,
    },
  );
});
