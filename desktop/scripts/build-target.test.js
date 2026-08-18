const assert = require("node:assert/strict");
const test = require("node:test");

const { runBuildTarget } = require("./build-target");

function normalizePath(value) {
  return String(value).replaceAll("\\", "/");
}

test("runBuildTarget on macOS runs config, Python, release preflight, then electron-builder", () => {
  const calls = [];
  const result = runBuildTarget({
    platform: "darwin",
    spawn: (_cmd, args) => {
      calls.push(args.join(" "));
      return { status: 0 };
    },
    stdio: "pipe",
  });

  assert.equal(result.status, 0);
  assert.equal(calls.length, 4);
  assert.match(normalizePath(calls[0]), /desktop\/scripts\/verify-release-config\.js$/);
  assert.match(normalizePath(calls[1]), /desktop\/scripts\/verify-python-runtime\.js$/);
  assert.match(normalizePath(calls[2]), /desktop\/scripts\/release-preflight\.js$/);
  assert.match(normalizePath(calls[3]), /desktop\/node_modules\/electron-builder\/cli\.js --mac$/);
  assert.equal(result.stage, "electron-builder");
});

test("runBuildTarget stops when Python runtime verification fails", () => {
  const calls = [];
  const result = runBuildTarget({
    platform: "darwin",
    spawn: (_cmd, args) => {
      calls.push(args.join(" "));
      if (args[0].includes("verify-python-runtime.js")) {
        return { status: 3 };
      }
      return { status: 0 };
    },
    stdio: "pipe",
  });

  assert.equal(result.status, 3);
  assert.equal(result.stage, "python-runtime");
  assert.equal(calls.length, 2);
  assert.match(normalizePath(calls[1]), /desktop\/scripts\/verify-python-runtime\.js$/);
});

test("runBuildTarget stops when macOS build preflight fails", () => {
  const calls = [];
  const result = runBuildTarget({
    platform: "darwin",
    spawn: (_cmd, args) => {
      calls.push(args.join(" "));
      if (args[0].includes("verify-release-config.js")) {
        return { status: 2 };
      }
      return { status: 0 };
    },
    stdio: "pipe",
  });

  assert.equal(result.status, 2);
  assert.equal(result.stage, "build-preflight");
  assert.equal(calls.length, 1);
  assert.match(normalizePath(calls[0]), /desktop\/scripts\/verify-release-config\.js$/);
});

test("runBuildTarget on non-mac platforms only invokes electron-builder", () => {
  const calls = [];
  const result = runBuildTarget({
    platform: "win32",
    spawn: (_cmd, args) => {
      calls.push(args.join(" "));
      return { status: 0 };
    },
    stdio: "pipe",
  });

  assert.equal(result.status, 0);
  assert.equal(calls.length, 1);
  assert.match(normalizePath(calls[0]), /desktop\/node_modules\/electron-builder\/cli\.js --win$/);
  assert.equal(result.stage, "electron-builder");
  assert.equal(result.target, "--win");
});
