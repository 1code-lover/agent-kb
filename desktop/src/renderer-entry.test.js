const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const {
  DEFAULT_RENDERER_PORT,
  WEB_PORT_ENV_KEYS,
  WEB_URL_ENV_KEYS,
  resolveRendererDevUrl,
  resolveRendererEntry,
  resolveRendererPort,
} = require("./renderer-entry");

test("renderer env keys prefer KB aliases first, then NorthAgent, ThinkRAG, and finally Foxglove", () => {
  assert.deepEqual(WEB_URL_ENV_KEYS, ["KB_WEB_URL", "NORTHAGENT_WEB_URL", "THINKRAG_WEB_URL", "FOXGLOVE_WEB_URL"]);
  assert.deepEqual(WEB_PORT_ENV_KEYS, ["KB_WEB_PORT", "NORTHAGENT_WEB_PORT", "THINKRAG_WEB_PORT", "FOXGLOVE_WEB_PORT", "VITE_PORT"]);
});

test("resolveRendererPort falls back to the default Vite port", () => {
  assert.equal(resolveRendererPort({}), DEFAULT_RENDERER_PORT);
});

test("resolveRendererEntry prefers explicit KB renderer URL env even when dist exists", () => {
  const entry = resolveRendererEntry({
    env: { KB_WEB_URL: "http://127.0.0.1:5188/" },
    resourceRoot: "/repo",
    fsModule: { existsSync: () => true },
  });

  assert.deepEqual(entry, {
    type: "url",
    value: "http://127.0.0.1:5188",
    source: "kb-env",
  });
});

test("resolveRendererEntry rewrites wildcard loopback URLs before loading the renderer", () => {
  const entry = resolveRendererEntry({
    env: { KB_WEB_URL: "http://0.0.0.0:5188/" },
    resourceRoot: "/repo",
    fsModule: { existsSync: () => false },
  });

  assert.deepEqual(entry, {
    type: "url",
    value: "http://127.0.0.1:5188",
    source: "kb-env",
  });
  assert.equal(resolveRendererDevUrl({ KB_WEB_URL: "http://0.0.0.0:5188/" }), "http://127.0.0.1:5188");
});

test("resolveRendererEntry fails closed for an invalid explicit KB renderer URL", () => {
  assert.throws(
    () => resolveRendererEntry({
      env: { KB_WEB_URL: "127.0.0.1:5188" },
      resourceRoot: "/repo",
      fsModule: { existsSync: () => true },
    }),
    /renderer URL from KB_WEB_URL is invalid: 127\.0\.0\.1:5188/,
  );
});

test("resolveRendererEntry uses packaged dist when no renderer URL override is provided", () => {
  const expectedDistPath = path.join("/repo", "webapp", "dist", "index.html");
  const entry = resolveRendererEntry({
    env: {},
    resourceRoot: "/repo",
    fsModule: { existsSync: (value) => value === expectedDistPath },
  });

  assert.deepEqual(entry, {
    type: "file",
    value: expectedDistPath,
    source: "dist",
  });
});


test("resolveRendererEntry fails closed when a packaged app is missing webapp/dist", () => {
  assert.throws(
    () => resolveRendererEntry({
      env: {},
      resourceRoot: "/repo",
      isPackaged: true,
      fsModule: { existsSync: () => false },
    }),
    /packaged renderer entry is missing: .*webapp[\\/]dist[\\/]index\.html/,
  );
});

test("resolveRendererDevUrl and resolveRendererEntry honor a custom KB renderer port", () => {
  assert.equal(resolveRendererDevUrl({ KB_WEB_PORT: "5191" }), "http://127.0.0.1:5191");

  const entry = resolveRendererEntry({
    env: { KB_WEB_PORT: "5191" },
    resourceRoot: "/repo",
    fsModule: { existsSync: () => false },
  });

  assert.deepEqual(entry, {
    type: "url",
    value: "http://127.0.0.1:5191",
    source: "port-env",
  });
});

test("resolveRendererDevUrl accepts foxglove renderer port alias for compatibility", () => {
  assert.equal(resolveRendererDevUrl({ FOXGLOVE_WEB_PORT: "5299" }), "http://127.0.0.1:5299");
});

test("resolveRendererEntry keeps NorthAgent alias compatibility", () => {
  const entry = resolveRendererEntry({
    env: { NORTHAGENT_WEB_URL: "http://127.0.0.1:5288/" },
    resourceRoot: "/repo",
    fsModule: { existsSync: () => false },
  });

  assert.deepEqual(entry, {
    type: "url",
    value: "http://127.0.0.1:5288",
    source: "northagent-env",
  });
});

test("resolveRendererEntry prefers ThinkRAG alias over Foxglove when both are present", () => {
  const entry = resolveRendererEntry({
    env: {
      THINKRAG_WEB_URL: "http://127.0.0.1:5291/",
      FOXGLOVE_WEB_URL: "http://127.0.0.1:5292/",
    },
    resourceRoot: "/repo",
    fsModule: { existsSync: () => false },
  });

  assert.deepEqual(entry, {
    type: "url",
    value: "http://127.0.0.1:5291",
    source: "thinkrag-env",
  });
});

test("resolveRendererPort prefers ThinkRAG port alias before Foxglove to match shared startup helpers", () => {
  assert.equal(
    resolveRendererPort({ THINKRAG_WEB_PORT: "5291", FOXGLOVE_WEB_PORT: "5292" }),
    5291,
  );
});
