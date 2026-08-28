import test from "node:test";
import assert from "node:assert/strict";

import {
  DEFAULT_API_BASE_URL,
  extractApiErrorMessage,
  normalizeApiBaseUrl,
  resolveApiBaseUrl,
} from "./client.js";

test("normalizeApiBaseUrl trims whitespace, trailing slash, and wildcard loopback hosts", () => {
  assert.equal(normalizeApiBaseUrl(" http://127.0.0.1:19090/ "), "http://127.0.0.1:19090");
  assert.equal(normalizeApiBaseUrl("http://0.0.0.0:19091/"), "http://127.0.0.1:19091");
  assert.equal(normalizeApiBaseUrl(""), "");
});

test("normalizeApiBaseUrl ignores invalid and unsupported browser API base URLs", () => {
  assert.equal(normalizeApiBaseUrl("not-a-valid-url"), "");
  assert.equal(normalizeApiBaseUrl("/api"), "");
  assert.equal(normalizeApiBaseUrl("ftp://kb.example.com/api"), "");
});

test("extractApiErrorMessage prefers FastAPI detail payload", () => {
  assert.equal(
    extractApiErrorMessage({ response: { data: { detail: "knowledge base missing" } } }),
    "knowledge base missing",
  );
});

test("extractApiErrorMessage falls back to unified response message", () => {
  assert.equal(
    extractApiErrorMessage({ response: { data: { code: 400, message: "validation_error" } } }),
    "validation_error",
  );
});

test("extractApiErrorMessage supports string payload and nested error message", () => {
  assert.equal(
    extractApiErrorMessage({ response: { data: "temporary unavailable" } }),
    "temporary unavailable",
  );
  assert.equal(
    extractApiErrorMessage({ response: { data: { error: { message: "downstream timeout" } } } }),
    "downstream timeout",
  );
});

test("extractApiErrorMessage falls back to generic text when nothing useful exists", () => {
  assert.equal(extractApiErrorMessage({}), "请求失败");
});

test("resolveApiBaseUrl prefers kbDesktop bridge over legacy aliases and vite env", () => {
  assert.equal(
    resolveApiBaseUrl({
      bridgeTarget: {
        kbDesktop: { apiBaseUrl: "http://127.0.0.1:19090/" },
        northAgentDesktop: { apiBaseUrl: "http://127.0.0.1:19091/" },
      },
      viteEnv: { VITE_API_BASE_URL: "http://127.0.0.1:19092/" },
    }),
    "http://127.0.0.1:19090",
  );
});

test("resolveApiBaseUrl prefers ThinkRAG bridge alias over Foxglove to match runtime contract order", () => {
  assert.equal(
    resolveApiBaseUrl({
      bridgeTarget: {
        thinkragDesktop: { apiBaseUrl: "http://127.0.0.1:19093/" },
        foxgloveDesktop: { apiBaseUrl: "http://127.0.0.1:19094/" },
      },
      viteEnv: { VITE_API_BASE_URL: "http://127.0.0.1:19095/" },
    }),
    "http://127.0.0.1:19093",
  );
});

test("resolveApiBaseUrl skips malformed earlier bridge aliases and keeps scanning later compatibility keys", () => {
  assert.equal(
    resolveApiBaseUrl({
      bridgeTarget: {
        kbDesktop: { apiBaseUrl: "not-a-valid-url" },
        thinkragDesktop: { apiBaseUrl: "http://127.0.0.1:19093/" },
      },
      viteEnv: { VITE_API_BASE_URL: "http://127.0.0.1:19095/" },
    }),
    "http://127.0.0.1:19093",
  );
});

test("resolveApiBaseUrl normalizes wildcard loopback overrides from bridge and vite env", () => {
  assert.equal(
    resolveApiBaseUrl({
      bridgeTarget: { kbDesktop: { apiBaseUrl: "http://0.0.0.0:19090/" } },
      viteEnv: { VITE_API_BASE_URL: "http://0.0.0.0:19092/" },
    }),
    "http://127.0.0.1:19090",
  );

  assert.equal(
    resolveApiBaseUrl({
      bridgeTarget: {},
      viteEnv: { VITE_API_BASE_URL: "http://0.0.0.0:19092/" },
    }),
    "http://127.0.0.1:19092",
  );
});

test("resolveApiBaseUrl ignores invalid bridge and vite overrides before falling back", () => {
  assert.equal(
    resolveApiBaseUrl({
      bridgeTarget: { kbDesktop: { apiBaseUrl: "not-a-valid-url" } },
      viteEnv: { VITE_API_BASE_URL: "also-invalid" },
    }),
    DEFAULT_API_BASE_URL,
  );

  assert.equal(
    resolveApiBaseUrl({
      bridgeTarget: { kbDesktop: { apiBaseUrl: "ftp://kb.example.com/api" } },
      viteEnv: { VITE_API_BASE_URL: "/api" },
    }),
    DEFAULT_API_BASE_URL,
  );
});

test("resolveApiBaseUrl falls back to vite env when desktop bridge is unavailable", () => {
  assert.equal(
    resolveApiBaseUrl({
      bridgeTarget: {},
      viteEnv: { VITE_API_BASE_URL: " https://kb.example.com:18443/ " },
    }),
    "https://kb.example.com:18443",
  );
});

test("resolveApiBaseUrl keeps vite env as browser-only contract and finally falls back to default", () => {
  assert.equal(resolveApiBaseUrl({ bridgeTarget: null, viteEnv: {} }), DEFAULT_API_BASE_URL);
  assert.equal(resolveApiBaseUrl({ bridgeTarget: { kbDesktop: { apiBaseUrl: "   " } }, viteEnv: {} }), DEFAULT_API_BASE_URL);
});

test("client prefers kbDesktop bridge base URL over legacy aliases at module init", async () => {
  const originalKbDesktop = globalThis.kbDesktop;
  const originalNorthAgentDesktop = globalThis.northAgentDesktop;

  try {
    globalThis.kbDesktop = { apiBaseUrl: "http://127.0.0.1:19090" };
    globalThis.northAgentDesktop = { apiBaseUrl: "http://127.0.0.1:19091" };
    const module = await import(`./client.js?case=kb-bridge-${Date.now()}`);
    assert.equal(module.default.defaults.baseURL, "http://127.0.0.1:19090");
  } finally {
    if (originalKbDesktop === undefined) {
      delete globalThis.kbDesktop;
    } else {
      globalThis.kbDesktop = originalKbDesktop;
    }
    if (originalNorthAgentDesktop === undefined) {
      delete globalThis.northAgentDesktop;
    } else {
      globalThis.northAgentDesktop = originalNorthAgentDesktop;
    }
  }
});

test("client module init skips malformed earlier bridge aliases before using later valid ones", async () => {
  const originalKbDesktop = globalThis.kbDesktop;
  const originalThinkragDesktop = globalThis.thinkragDesktop;

  try {
    globalThis.kbDesktop = { apiBaseUrl: "not-a-valid-url" };
    globalThis.thinkragDesktop = { apiBaseUrl: "http://127.0.0.1:19093" };
    const module = await import(`./client.js?case=invalid-kb-bridge-${Date.now()}`);
    assert.equal(module.default.defaults.baseURL, "http://127.0.0.1:19093");
  } finally {
    if (originalKbDesktop === undefined) {
      delete globalThis.kbDesktop;
    } else {
      globalThis.kbDesktop = originalKbDesktop;
    }
    if (originalThinkragDesktop === undefined) {
      delete globalThis.thinkragDesktop;
    } else {
      globalThis.thinkragDesktop = originalThinkragDesktop;
    }
  }
});
