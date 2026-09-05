const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const { RUNTIME_ROOT_ENV_KEYS, ensureRuntimeRoot, resolveRuntimePaths, resolveRuntimeRoot } = require("./runtime-paths");

function normalizePath(value) {
  return String(value).replaceAll("\\", "/");
}

function normalizePaths(record) {
  return Object.fromEntries(Object.entries(record).map(([key, value]) => [key, normalizePath(value)]));
}

test("runtime path contract prefers KB runtime root before legacy aliases", () => {
  assert.deepEqual(RUNTIME_ROOT_ENV_KEYS, ["KB_RUNTIME_ROOT", "NORTHAGENT_RUNTIME_ROOT", "THINKRAG_RUNTIME_ROOT", "FOXGLOVE_RUNTIME_ROOT"]);
});

test("resolveRuntimePaths separates packaged resources from writable runtime data", () => {
  const paths = resolveRuntimePaths({
    devProjectRoot: "/repo",
    isPackaged: true,
    resourcesPath: "/Applications/NorthAgent.app/Contents/Resources",
    userDataPath: "/Users/test/Library/Application Support/NorthAgent",
  });

  assert.deepEqual(normalizePaths(paths), {
    modelRoot: "/Applications/NorthAgent.app/Contents/Resources/localmodels",
    resourceRoot: "/Applications/NorthAgent.app/Contents/Resources",
    runtimeRoot: "/Users/test/Library/Application Support/NorthAgent/runtime",
  });
  assert.equal(paths.runtimeRoot.startsWith(paths.resourceRoot), false);
});

test("resolveRuntimeRoot accepts explicit KB runtime root override", () => {
  assert.equal(
    resolveRuntimeRoot({
      devProjectRoot: "/repo",
      isPackaged: false,
      userDataPath: "/unused",
      env: { KB_RUNTIME_ROOT: " /tmp/kb-runtime/ " },
    }),
    "/tmp/kb-runtime/"
  );
});

test("resolveRuntimePaths keeps foxglove runtime root compatibility alias", () => {
  const paths = resolveRuntimePaths({
    devProjectRoot: "/repo",
    isPackaged: false,
    resourcesPath: "/unused/resources",
    userDataPath: "/unused/user-data",
    env: { FOXGLOVE_RUNTIME_ROOT: "/tmp/foxglove-runtime" },
  });

  assert.deepEqual(paths, {
    modelRoot: path.join("/repo", "localmodels"),
    resourceRoot: "/repo",
    runtimeRoot: "/tmp/foxglove-runtime",
  });
});

test("resolveRuntimePaths keeps repository behavior in development", () => {
  const paths = resolveRuntimePaths({
    devProjectRoot: "/repo",
    isPackaged: false,
    resourcesPath: "/unused/resources",
    userDataPath: "/unused/user-data",
  });

  assert.deepEqual(paths, {
    modelRoot: path.join("/repo", "localmodels"),
    resourceRoot: "/repo",
    runtimeRoot: "/repo",
  });
});

test("ensureRuntimeRoot creates and checks the writable runtime directory", () => {
  const calls = [];
  const fsModule = {
    constants: { W_OK: 2 },
    mkdirSync: (...args) => calls.push(["mkdir", ...args]),
    accessSync: (...args) => calls.push(["access", ...args]),
  };

  ensureRuntimeRoot("/user-data/runtime", { fs: fsModule });

  assert.deepEqual(calls, [
    ["mkdir", "/user-data/runtime", { recursive: true }],
    ["access", "/user-data/runtime", 2],
  ]);
});

test("ensureRuntimeRoot fails closed when the runtime directory is not writable", () => {
  const fsModule = {
    constants: { W_OK: 2 },
    mkdirSync: () => {},
    accessSync: () => {
      throw new Error("permission denied");
    },
  };

  assert.throws(
    () => ensureRuntimeRoot("/user-data/runtime", { fs: fsModule }),
    /runtime directory is not writable.*permission denied/
  );
});
