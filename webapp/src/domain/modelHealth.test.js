/**
 * 文件功能：
 * - 回归模型健康状态的前端展示文案映射，保证模型页和 Agent 页使用同一套口径。
 */

import test from "node:test";
import assert from "node:assert/strict";

import { buildModelHealthSummary } from "./modelHealth.js";

test("buildModelHealthSummary 会把 healthy 映射为健康摘要", () => {
  const summary = buildModelHealthSummary({
    state: "healthy",
    current_provider: "阿里百炼",
    current_model: "qwen-plus",
  });

  assert.equal(summary.state, "healthy");
  assert.equal(summary.tone, "success");
  assert.equal(summary.chipLabel, "模型健康");
  assert.match(summary.summary, /阿里百炼 \/ qwen-plus/);
});

test("buildModelHealthSummary 会展示自动 fallback 的来源和目标", () => {
  const summary = buildModelHealthSummary({
    state: "fallback_applied",
    current_provider: "阿里百炼",
    current_model: "qwen-plus",
    last_error_kind: "quota_exhausted",
    fallback_from: { service_provider: "OpenAI", model: "gpt-4o" },
    fallback_to: { service_provider: "阿里百炼", model: "qwen-plus" },
    fallback_attempts: [
      { service_provider: "OpenAI", model: "gpt-4o", reachable: false, detail: "http_401" },
      { service_provider: "Ollama", model: "qwen2.5:7b", reachable: true, detail: "reachable" },
    ],
  });

  assert.equal(summary.state, "fallback_applied");
  assert.equal(summary.chipLabel, "已自动切换");
  assert.match(summary.detail, /OpenAI \/ gpt-4o/);
  assert.match(summary.detail, /阿里百炼 \/ qwen-plus/);
  assert.match(summary.detail, /额度耗尽/);
  assert.match(summary.actionHint, /已自动切换到可用模型/);
  assert.equal(summary.transitionLabel, "OpenAI / gpt-4o → 阿里百炼 / qwen-plus");
  assert.match(summary.probeSummary, /已探测 2 个候选/);
  assert.match(summary.probeSummary, /Ollama \/ qwen2.5:7b/);
  assert.match(summary.probeSummary, /本地 Ollama 候选/);
});

test("buildModelHealthSummary 会把 degraded 映射为异常提示", () => {
  const summary = buildModelHealthSummary({
    state: "degraded",
    current_provider: "OpenAI",
    current_model: "gpt-test",
    last_error_kind: "forbidden",
    last_error: "Error code: 403",
  });

  assert.equal(summary.state, "degraded");
  assert.equal(summary.tone, "warning");
  assert.equal(summary.chipLabel, "模型异常");
  assert.match(summary.actionHint, /检查额度、权限或网络/);
  assert.match(summary.detail, /403 禁止访问/);
  assert.match(summary.detail, /Error code: 403/);
});

test("buildModelHealthSummary 会把 unavailable 映射为不可用提示", () => {
  const summary = buildModelHealthSummary({
    state: "unavailable",
    last_error_kind: "model_unavailable",
    candidate_count: 3,
  });

  assert.equal(summary.state, "unavailable");
  assert.equal(summary.tone, "danger");
  assert.equal(summary.chipLabel, "无可用模型");
  assert.match(summary.actionHint, /补齐可用供应商/);
  assert.match(summary.detail, /模型不可用/);
  assert.match(summary.detail, /候选数：3/);
});

test("buildModelHealthSummary 缺少状态时会回退为未知", () => {
  const summary = buildModelHealthSummary(null);

  assert.equal(summary.state, "unknown");
  assert.equal(summary.tone, "muted");
  assert.equal(summary.chipLabel, "状态未知");
  assert.equal(summary.title, "模型状态未知");
  assert.match(summary.actionHint, /重新探活/);
});

test("buildModelHealthSummary 会在不可用状态展示候选探测摘要", () => {
  const summary = buildModelHealthSummary({
    state: "unavailable",
    candidate_count: 2,
    fallback_attempts: [
      { service_provider: "Ollama", model: "qwen2.5:7b", reachable: false, detail: "ollama_unreachable" },
      { service_provider: "OpenAI", model: "gpt-4o", reachable: false, detail: "http_403" },
    ],
  });

  assert.equal(summary.state, "unavailable");
  assert.match(summary.probeSummary, /已探测 2 个候选/);
  assert.match(summary.probeSummary, /OpenAI \/ gpt-4o/);
});

test("buildModelHealthSummary 会优先展示结构化候选探测摘要", () => {
  const summary = buildModelHealthSummary({
    state: "unavailable",
    last_error_kind: "model_unavailable",
    candidate_count: 2,
    fallback_attempt_summary: {
      total: 2,
      reachable_count: 0,
      failed_count: 2,
      ollama_candidate_count: 1,
      ollama_reachable_count: 0,
      last_provider: "Ollama",
      last_model: "qwen2.5:7b",
      last_detail: "model_not_found",
    },
  });

  assert.equal(summary.state, "unavailable");
  assert.match(summary.probeSummary, /已探测 2 个候选：0 个可用，2 个不可用/);
  assert.match(summary.probeSummary, /Ollama 候选 1 个/);
  assert.match(summary.probeSummary, /Ollama \/ qwen2.5:7b/);
  assert.match(summary.probeSummary, /model_not_found/);
  assert.match(summary.actionHint, /确认 Ollama 已启动/);
  assert.match(summary.actionHint, /目标模型已拉取/);
});

test("buildModelHealthSummary 会在 Ollama fallback 时提示本地候选模型", () => {
  const summary = buildModelHealthSummary({
    state: "fallback_applied",
    fallback_to: { service_provider: "Ollama", model: "qwen2.5:7b" },
    fallback_attempts: [
      { service_provider: "OpenAI", model: "gpt-4o", reachable: false, detail: "http_401" },
      { service_provider: "Ollama", model: "qwen2.5:7b", reachable: true, detail: "reachable" },
    ],
  });

  assert.equal(summary.state, "fallback_applied");
  assert.match(summary.actionHint, /本地 Ollama 候选模型/);
  assert.match(summary.probeSummary, /本地 Ollama 候选/);
});
