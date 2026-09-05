const assert = require("node:assert/strict");
const test = require("node:test");

const { buildApiStartupFailureMessage, buildRendererStartupFailureMessage, resolveApiStartupFailure } = require("./bootstrap-messages");

test("resolveApiStartupFailure distinguishes local boot failures from explicit remote failures", () => {
  assert.deepEqual(resolveApiStartupFailure({ env: {} }), {
    reason: "local_python_api_not_ready",
    apiBaseUrl: "http://127.0.0.1:18080",
    autoStartLocalApi: true,
  });

  assert.deepEqual(resolveApiStartupFailure({
    env: { KB_API_BASE_URL: "https://api.example.com:18443" },
  }), {
    reason: "explicit_remote_api_unavailable",
    apiBaseUrl: "https://api.example.com:18443",
    autoStartLocalApi: false,
  });
});

test("resolveApiStartupFailure keeps the raw invalid explicit API base for diagnostics", () => {
  assert.deepEqual(resolveApiStartupFailure({
    env: { KB_API_BASE_URL: "not-a-valid-url", KB_API_PORT: "19090" },
  }), {
    reason: "explicit_remote_api_unavailable",
    apiBaseUrl: "not-a-valid-url",
    autoStartLocalApi: false,
  });
});

test("buildApiStartupFailureMessage keeps local startup failures generic", () => {
  const message = buildApiStartupFailureMessage({
    logFile: "/tmp/runtime.log",
    env: {},
  });

  assert.equal(message, "Python API 启动失败，请检查日志：/tmp/runtime.log");
});

test("buildApiStartupFailureMessage explains explicit external API failures", () => {
  const message = buildApiStartupFailureMessage({
    logFile: "/tmp/runtime.log",
    env: { KB_API_BASE_URL: "https://api.example.com:18443" },
  });

  assert.match(message, /配置的外部 API 不可用或地址无效：https:\/\/api\.example\.com:18443/);
  assert.match(message, /KB_API_BASE_URL/);
  assert.match(message, /不会自动回退到本地 run_api\.py/);
  assert.match(message, /日志：\/tmp\/runtime\.log/);
});

test("buildApiStartupFailureMessage shows the raw invalid explicit API base", () => {
  const message = buildApiStartupFailureMessage({
    logFile: "/tmp/runtime.log",
    env: { KB_API_BASE_URL: "not-a-valid-url", KB_API_PORT: "19090" },
  });

  assert.match(message, /配置的外部 API 不可用或地址无效：not-a-valid-url/);
  assert.doesNotMatch(message, /127\.0\.0\.1:19090/);
  assert.match(message, /KB_API_BASE_URL/);
  assert.match(message, /不会自动回退到本地 run_api\.py/);
});


test("buildRendererStartupFailureMessage explains packaged renderer bootstrap failures", () => {
  const message = buildRendererStartupFailureMessage({
    error: new Error("packaged renderer entry is missing: /repo/webapp/dist/index.html"),
    logFile: "/tmp/runtime.log",
  });

  assert.match(message, /桌面前端入口不可用/);
  assert.match(message, /webapp\/dist\/index\.html/);
  assert.match(message, /KB_WEB_URL/);
  assert.match(message, /日志：\/tmp\/runtime\.log/);
});
