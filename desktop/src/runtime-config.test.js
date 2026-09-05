const assert = require("node:assert/strict");
const test = require("node:test");

const {
  API_BASE_URL_ENV_KEYS,
  API_PORT_ENV_KEYS,
  DEFAULT_API_PORT,
  normalizeApiBaseUrl,
  normalizeClientUrl,
  resolveApiBaseUrl,
  resolveApiHealthUrl,
  resolveApiPort,
  resolveExplicitApiBaseUrl,
  shouldAutoStartLocalApi,
  toWebSocketOrigin,
} = require("./runtime-config");

test("runtime config prefers KB_* API contracts before legacy aliases", () => {
  assert.deepEqual(API_PORT_ENV_KEYS, ["KB_API_PORT", "NORTHAGENT_API_PORT", "THINKRAG_API_PORT", "FOXGLOVE_API_PORT"]);
  assert.deepEqual(API_BASE_URL_ENV_KEYS, ["KB_API_BASE_URL", "NORTHAGENT_API_BASE_URL", "THINKRAG_API_BASE_URL", "FOXGLOVE_API_BASE_URL"]);
});

test("normalizeClientUrl rewrites wildcard loopback hosts to a client-safe loopback origin", () => {
  assert.equal(normalizeClientUrl(" http://0.0.0.0:19095/ "), "http://127.0.0.1:19095");
  assert.equal(normalizeClientUrl("https://kb.example.com:18443/"), "https://kb.example.com:18443");
});

test("normalizeApiBaseUrl accepts only absolute HTTP(S) API base URLs", () => {
  assert.equal(normalizeApiBaseUrl(" http://0.0.0.0:19095/ "), "http://127.0.0.1:19095");
  assert.equal(normalizeApiBaseUrl("https://kb.example.com:18443/"), "https://kb.example.com:18443");
  assert.equal(normalizeApiBaseUrl("/api"), "");
  assert.equal(normalizeApiBaseUrl("ftp://kb.example.com/api"), "");
  assert.equal(normalizeApiBaseUrl("not-a-valid-url"), "");
});

test("resolveApiBaseUrl trims KB_API_BASE_URL and resolveApiPort derives its port", () => {
  const env = { KB_API_BASE_URL: "https://kb.example.com:18443/" };
  assert.equal(resolveExplicitApiBaseUrl(env), "https://kb.example.com:18443");
  assert.equal(resolveApiBaseUrl(env), "https://kb.example.com:18443");
  assert.equal(resolveApiPort(env), 18443);
  assert.equal(resolveApiHealthUrl(env), "https://kb.example.com:18443/api/health");
});

test("resolveApiBaseUrl normalizes wildcard loopback overrides before the desktop uses them", () => {
  const env = { KB_API_BASE_URL: "http://0.0.0.0:18095/" };
  assert.equal(resolveApiBaseUrl(env), "http://127.0.0.1:18095");
  assert.equal(resolveApiPort(env), 18095);
  assert.equal(shouldAutoStartLocalApi(env), true);
});

test("resolveApiBaseUrl still accepts foxglove compatibility alias", () => {
  const env = { FOXGLOVE_API_BASE_URL: "http://127.0.0.1:18123/" };
  assert.equal(resolveApiBaseUrl(env), "http://127.0.0.1:18123");
  assert.equal(resolveApiPort(env), 18123);
});

test("invalid explicit API base URL no longer pollutes resolved desktop base URLs", () => {
  const env = {
    KB_API_BASE_URL: "not-a-valid-url",
    KB_API_PORT: "19090",
  };

  assert.equal(resolveExplicitApiBaseUrl(env), "");
  assert.equal(resolveApiBaseUrl(env), "http://127.0.0.1:19090");
  assert.equal(resolveApiHealthUrl(env), "http://127.0.0.1:19090/api/health");
  assert.equal(resolveApiPort(env), 19090);
  assert.equal(shouldAutoStartLocalApi(env), false);
});

test("invalid explicit API base URL falls back to the default desktop port when no valid override exists", () => {
  const env = {
    KB_API_BASE_URL: "not-a-valid-url",
  };

  assert.equal(resolveApiBaseUrl(env), "http://127.0.0.1:18080");
  assert.equal(resolveApiPort(env), DEFAULT_API_PORT);
  assert.equal(shouldAutoStartLocalApi(env), false);
});

test("resolveApiPort falls back to KB_API_PORT and then the default port", () => {
  assert.equal(resolveApiPort({ KB_API_PORT: "19090" }), 19090);
  assert.equal(resolveApiPort({ KB_API_PORT: "invalid" }), DEFAULT_API_PORT);
  assert.equal(resolveApiPort({}), DEFAULT_API_PORT);
});

test("shouldAutoStartLocalApi only allows loopback explicit API bases", () => {
  assert.equal(shouldAutoStartLocalApi({}), true);
  assert.equal(shouldAutoStartLocalApi({ KB_API_BASE_URL: "http://127.0.0.1:19095/" }), true);
  assert.equal(shouldAutoStartLocalApi({ KB_API_BASE_URL: "http://localhost:18080" }), true);
  assert.equal(shouldAutoStartLocalApi({ KB_API_BASE_URL: "https://api.example.com:18443" }), false);
  assert.equal(shouldAutoStartLocalApi({ KB_API_BASE_URL: "not-a-valid-url" }), false);
});

test("toWebSocketOrigin maps HTTP(S) origins to WS(S)", () => {
  assert.equal(toWebSocketOrigin("http://127.0.0.1:18080"), "ws://127.0.0.1:18080");
  assert.equal(toWebSocketOrigin("https://kb.example.com"), "wss://kb.example.com");
  assert.equal(toWebSocketOrigin("not-a-url"), "");
});
