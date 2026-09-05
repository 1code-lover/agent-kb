import test from "node:test";
import assert from "node:assert/strict";

import {
  buildHistorySyncNotice,
  historyIncludesOptimisticResult,
  queryChatWithBestEffortHistory,
  resolveChatMessages,
  resolveHistoryMessages,
} from "./chatWorkflow.js";

test("queryChatWithBestEffortHistory returns server history when sync succeeds", async () => {
  const result = await queryChatWithBestEffortHistory({
    payload: { question: "what", session_id: "fallback-session" },
    queryChatRequest: async () => ({ data: { session_id: "server-session", answer: "done" } }),
    getHistoryRequest: async (sessionId) => {
      assert.equal(sessionId, "server-session");
      return {
        data: {
          messages: [
            { id: "m-1", role: "user", content: "what" },
            { id: "m-2", role: "assistant", content: "done" },
          ],
        },
      };
    },
    readApiData: (response) => response?.data ?? null,
  });

  assert.deepEqual(result, {
    session_id: "server-session",
    answer: "done",
    requestedQuestion: "what",
    messages: [
      { id: "m-1", role: "user", content: "what" },
      { id: "m-2", role: "assistant", content: "done" },
    ],
    historySyncError: "",
  });
});

test("queryChatWithBestEffortHistory keeps query success when history sync fails", async () => {
  const result = await queryChatWithBestEffortHistory({
    payload: { question: "what", session_id: "fallback-session" },
    queryChatRequest: async () => ({ data: { answer: "done" } }),
    getHistoryRequest: async () => {
      throw new Error("network down");
    },
    readApiData: (response) => response?.data ?? null,
  });

  assert.deepEqual(result, {
    answer: "done",
    requestedQuestion: "what",
    session_id: "fallback-session",
    messages: null,
    historySyncError: "network down",
  });
});

test("queryChatWithBestEffortHistory keeps optimistic fallback when synced history is stale", async () => {
  const result = await queryChatWithBestEffortHistory({
    payload: { question: "what", session_id: "fallback-session" },
    queryChatRequest: async () => ({ data: { session_id: "server-session", answer: "done" } }),
    getHistoryRequest: async () => ({
      data: {
        messages: [
          { id: "m-1", role: "user", content: "older" },
          { id: "m-2", role: "assistant", content: "older answer" },
        ],
      },
    }),
    readApiData: (response) => response?.data ?? null,
  });

  assert.deepEqual(result, {
    session_id: "server-session",
    answer: "done",
    requestedQuestion: "what",
    messages: null,
    historySyncError: "历史仍在刷新，已先展示当前回答。",
  });
});

test("resolveChatMessages prefers server history when available", () => {
  const messages = resolveChatMessages({
    currentMessages: [{ id: "local-1", role: "user", content: "stale" }],
    result: { messages: [{ id: "srv-1", role: "assistant", content: "fresh" }] },
    createLocalMessage: () => {
      throw new Error("should not create local messages when server history exists");
    },
  });

  assert.deepEqual(messages, [{ id: "srv-1", role: "assistant", content: "fresh" }]);
});

test("resolveChatMessages appends local fallback messages when history is unavailable", () => {
  const created = [];
  const messages = resolveChatMessages({
    currentMessages: [{ id: "m-1", role: "assistant", content: "older" }],
    result: { requestedQuestion: "what", answer: "done", messages: null },
    createLocalMessage: (role, content) => {
      const message = { id: `${role}-${content}`, role, content };
      created.push(message);
      return message;
    },
  });

  assert.deepEqual(created, [
    { id: "user-what", role: "user", content: "what" },
    { id: "assistant-done", role: "assistant", content: "done" },
  ]);
  assert.deepEqual(messages, [
    { id: "m-1", role: "assistant", content: "older" },
    { id: "user-what", role: "user", content: "what" },
    { id: "assistant-done", role: "assistant", content: "done" },
  ]);
});

test("buildHistorySyncNotice formats the warning text only when needed", () => {
  assert.equal(buildHistorySyncNotice("network down"), "回答已生成，但历史同步失败：network down");
  assert.equal(buildHistorySyncNotice("历史仍在刷新，已先展示当前回答。"), "回答已生成，历史仍在刷新，已先展示当前回答。");
  assert.equal(buildHistorySyncNotice(""), "");
});


test("historyIncludesOptimisticResult waits for matching user and assistant messages", () => {
  assert.equal(
    historyIncludesOptimisticResult({
      historyMessages: [
        { id: "h-1", role: "user", content: "旧问题" },
        { id: "h-2", role: "assistant", content: "旧答案" },
      ],
      optimisticResult: { requestedQuestion: "新问题", answer: "新答案" },
    }),
    false,
  );

  assert.equal(
    historyIncludesOptimisticResult({
      historyMessages: [
        { id: "h-1", role: "user", content: "新问题" },
        { id: "h-2", role: "assistant", content: "新答案" },
      ],
      optimisticResult: { requestedQuestion: "新问题", answer: "新答案" },
    }),
    true,
  );
});

test("resolveHistoryMessages keeps optimistic fallback when history is stale", () => {
  const currentMessages = [
    { id: "m-1", role: "assistant", content: "更早的回答" },
    { id: "m-2", role: "user", content: "新问题" },
    { id: "m-3", role: "assistant", content: "新答案" },
  ];

  const historyMessages = [
    { id: "h-1", role: "assistant", content: "更早的回答" },
  ];

  assert.deepEqual(
    resolveHistoryMessages({
      currentMessages,
      historyMessages,
      optimisticResult: { requestedQuestion: "新问题", answer: "新答案" },
    }),
    currentMessages,
  );
});

test("resolveHistoryMessages switches back to server history once it catches up", () => {
  const currentMessages = [
    { id: "m-1", role: "assistant", content: "更早的回答" },
    { id: "m-2", role: "user", content: "新问题" },
    { id: "m-3", role: "assistant", content: "新答案" },
  ];

  const historyMessages = [
    { id: "h-1", role: "assistant", content: "更早的回答" },
    { id: "h-2", role: "user", content: "新问题" },
    { id: "h-3", role: "assistant", content: "新答案" },
  ];

  assert.deepEqual(
    resolveHistoryMessages({
      currentMessages,
      historyMessages,
      optimisticResult: { requestedQuestion: "新问题", answer: "新答案" },
    }),
    historyMessages,
  );
});
