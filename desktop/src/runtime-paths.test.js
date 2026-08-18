const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const { ensureRuntimeRoot, resolveRuntimePaths } = require("./runtime-paths");

function normalizePath(value) {
  return String(value).replaceAll("\\", "/");
}

function normalizePaths(record) {
  return Object.fromEntries(Object.entries(record).map(([key, value]) => [key, normalizePath(value)]));
}

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
