const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { resolveAppPath, runCheck, verifyMacRelease } = require("./verify-mac-release");

function normalizePath(value) {
  return String(value).replaceAll("\\", "/");
}

function createAppFixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "verify-mac-release-"));
  const appPath = path.join(root, "dist", "mac-arm64", "NorthAgent.app");
  const resourcesRoot = path.join(appPath, "Contents", "Resources");
  fs.mkdirSync(resourcesRoot, { recursive: true });
  return {
    appPath,
    layout: { resourcesRoot },
    root,
  };
}

test("resolveAppPath derives the .app bundle from a resources root", () => {
  const appPath = resolveAppPath({
    resourcesRoot: "/tmp/dist/mac-arm64/NorthAgent.app/Contents/Resources",
  });

  assert.match(normalizePath(appPath), /\/tmp\/dist\/mac-arm64\/NorthAgent\.app$/);
});

test("runCheck captures command status and stderr detail", () => {
  const result = runCheck({
    args: ["codesign", "--verify", "NorthAgent.app"],
    label: "codesign",
    spawn: () => ({
      status: 1,
      stderr: Buffer.from("bundle format is ambiguous"),
      stdout: Buffer.from(""),
    }),
  });

  assert.equal(result.ok, false);
  assert.equal(result.label, "codesign");
  assert.equal(result.detail, "bundle format is ambiguous");
  assert.match(result.command, /codesign --verify NorthAgent\.app/);
});

test("verifyMacRelease accepts signed and stapled macOS app bundles", () => {
  const { appPath, layout } = createAppFixture();
  const calls = [];

  const result = verifyMacRelease({
    fs,
    layout,
    platform: "darwin",
    spawn: (command, args) => {
      calls.push([command, ...args].join(" "));
      return { status: 0, stdout: Buffer.from("ok"), stderr: Buffer.from("") };
    },
  });

  assert.equal(result.ok, true);
  assert.equal(result.appPath, appPath);
  assert.deepEqual(result.failures, []);
  assert.equal(calls.length, 3);
  assert.match(calls[0], /^codesign --verify --deep --strict --verbose=2 /);
  assert.match(calls[1], /^spctl --assess --type execute --verbose=4 /);
  assert.match(calls[2], /^xcrun stapler validate /);
});

test("verifyMacRelease reports missing app bundles before shelling out", () => {
  const calls = [];
  const result = verifyMacRelease({
    fs,
    layout: { resourcesRoot: "/tmp/missing/NorthAgent.app/Contents/Resources" },
    platform: "darwin",
    spawn: (command, args) => {
      calls.push([command, ...args].join(" "));
      return { status: 0 };
    },
  });

  assert.equal(result.ok, false);
  assert.match(result.failures.join("\n"), /missing macOS app bundle/);
  assert.deepEqual(calls, []);
});

test("verifyMacRelease reports signature, gatekeeper, and stapler failures", () => {
  const { layout } = createAppFixture();
  const statuses = new Map([
    ["codesign", { status: 1, stderr: Buffer.from("invalid signature") }],
    ["spctl", { status: 1, stderr: Buffer.from("rejected") }],
    ["xcrun", { status: 1, stderr: Buffer.from("ticket not stapled") }],
  ]);

  const result = verifyMacRelease({
    fs,
    layout,
    platform: "darwin",
    spawn: (command) => ({
      stdout: Buffer.from(""),
      ...statuses.get(command),
    }),
  });

  const failures = result.failures.join("\n");
  assert.equal(result.ok, false);
  assert.match(failures, /codesign failed/);
  assert.match(failures, /invalid signature/);
  assert.match(failures, /gatekeeper failed/);
  assert.match(failures, /rejected/);
  assert.match(failures, /stapler failed/);
  assert.match(failures, /ticket not stapled/);
});

test("verifyMacRelease skips command checks on non-macOS platforms", () => {
  const { layout } = createAppFixture();
  const result = verifyMacRelease({
    fs,
    layout,
    platform: "win32",
    spawn: () => {
      throw new Error("spawn should not be called");
    },
  });

  assert.equal(result.ok, true);
  assert.equal(result.skipped, true);
  assert.equal(result.skippedReason, "not_macos");
});
