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
  });

  assert.equal(summary.state, "fallback_applied");
  assert.equal(summary.chipLabel, "已自动切换");
  assert.match(summary.detail, /OpenAI \/ gpt-4o/);
  assert.match(summary.detail, /阿里百炼 \/ qwen-plus/);
  assert.match(summary.detail, /额度耗尽/);
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
  assert.match(summary.detail, /模型不可用/);
  assert.match(summary.detail, /候选数：3/);
});

test("buildModelHealthSummary 缺少状态时会回退为未知", () => {
  const summary = buildModelHealthSummary(null);

  assert.equal(summary.state, "unknown");
  assert.equal(summary.tone, "muted");
  assert.equal(summary.chipLabel, "状态未知");
  assert.equal(summary.title, "模型状态未知");
});
