const assert = require("node:assert/strict");
const test = require("node:test");

const { buildContentSecurityPolicy, resolveUrlOrigin } = require("./csp");

test("resolveUrlOrigin returns the origin for valid URLs", () => {
  assert.equal(resolveUrlOrigin("http://127.0.0.1:5173/path?q=1"), "http://127.0.0.1:5173");
});

test("resolveUrlOrigin returns empty string for invalid URLs", () => {
  assert.equal(resolveUrlOrigin("not-a-url"), "");
});

test("buildContentSecurityPolicy keeps packaged app and configurable local API sources", () => {
  const csp = buildContentSecurityPolicy(
    { type: "file", value: "/tmp/webapp/dist/index.html" },
    { apiBaseUrl: "http://127.0.0.1:18095" },
  );

  assert.match(csp, /default-src 'self'/);
  assert.match(csp, /connect-src .*http:\/\/127\.0\.0\.1:18095/);
  assert.match(csp, /connect-src .*http:\/\/localhost:18095/);
});

test("buildContentSecurityPolicy adds renderer origin and derived websocket origin when loading from URL", () => {
  const csp = buildContentSecurityPolicy({ type: "url", value: "http://127.0.0.1:5176/index.html" });

  assert.match(csp, /connect-src .*http:\/\/127\.0\.0\.1:5176/);
  assert.match(csp, /connect-src .*ws:\/\/127\.0\.0\.1:5176/);
  assert.match(csp, /connect-src .*ws:\/\/localhost:5176/);
});
