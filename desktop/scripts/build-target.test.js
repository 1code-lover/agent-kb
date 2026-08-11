const assert = require("node:assert/strict");
const test = require("node:test");

const { runBuildTarget } = require("./build-target");

test("runBuildTarget on macOS runs build preflight before electron-builder", () => {
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
  assert.equal(calls.length, 3);
  assert.match(calls[0], /desktop\/scripts\/verify-release-config\.js$/);
  assert.match(calls[1], /desktop\/scripts\/release-preflight\.js$/);
  assert.match(calls[2], /desktop\/node_modules\/electron-builder\/cli\.js --mac$/);
  assert.equal(result.stage, "electron-builder");
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
  assert.match(calls[0], /desktop\/scripts\/verify-release-config\.js$/);
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
  assert.match(calls[0], /desktop\/node_modules\/electron-builder\/cli\.js --win$/);
  assert.equal(result.stage, "electron-builder");
  assert.equal(result.target, "--win");
});
