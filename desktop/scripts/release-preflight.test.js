const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  checkNotaryTool,
  ensureExecutable,
  findDeveloperIdApplicationIdentities,
  getMissingReleaseEnv,
  runPreflight,
} = require("./release-preflight");

function createFakeElectronApp() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "release-preflight-app-"));
  const electronAppPath = path.join(tmpDir, "Electron.app");
  fs.mkdirSync(electronAppPath);
  return { tmpDir, electronAppPath };
}

function createFakeAppBuilder(tmpDir) {
  const appBuilderBinaryPath = path.join(tmpDir, "app-builder_arm64");
  fs.writeFileSync(appBuilderBinaryPath, "binary");
  fs.chmodSync(appBuilderBinaryPath, 0o755);
  return appBuilderBinaryPath;
}

function buildReadySpawn() {
  return (_cmd, args) => {
    if (args.includes("find-identity")) {
      return {
        status: 0,
        stdout: Buffer.from('  1) ABCDEF1234567890 "Developer ID Application: NorthAgent Inc. (TEAM12345)"\n'),
        stderr: Buffer.from(""),
      };
    }
    if (args.includes("notarytool")) {
      return {
        status: 0,
        stdout: Buffer.from("/Applications/Xcode.app/Contents/Developer/usr/bin/notarytool\n"),
        stderr: Buffer.from(""),
      };
    }
    return { status: 1, stdout: Buffer.from(""), stderr: Buffer.from("unexpected command") };
  };
}

test("ensureExecutable repairs a non-executable file", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "release-preflight-"));
  const target = path.join(tmpDir, "binary");
  fs.writeFileSync(target, "data");
  fs.chmodSync(target, 0o644);

  const result = ensureExecutable(target, () => {});

  assert.equal(result.ok, true);
  assert.equal(result.repaired, true);
  const mode = fs.statSync(target).mode & 0o777;
  assert.equal(mode & 0o111, 0o111);
});

test("ensureExecutable reports missing files", () => {
  const result = ensureExecutable(path.join(os.tmpdir(), "missing-binary"), () => {});

  assert.deepEqual(result, { ok: false, reason: "missing" });
});

test("getMissingReleaseEnv reports only absent notarization variables", () => {
  const result = getMissingReleaseEnv({
    APPLE_ID: "dev@example.com",
    APPLE_TEAM_ID: "TEAM12345",
  });

  assert.deepEqual(result, ["APPLE_APP_SPECIFIC_PASSWORD"]);
});

test("findDeveloperIdApplicationIdentities parses valid security output", () => {
  const fakeSpawn = () => ({
    status: 0,
    stdout: Buffer.from(
      [
        '  1) ABCDEF1234567890 "Developer ID Application: NorthAgent Inc. (TEAM12345)"',
        '  2) 1234567890ABCDEF "Apple Development: Dev User (TEAM12345)"',
        "     2 valid identities found",
      ].join("\n"),
    ),
    stderr: Buffer.from(""),
  });

  const result = findDeveloperIdApplicationIdentities(fakeSpawn);

  assert.equal(result.ok, true);
  assert.deepEqual(result.identities, ["Developer ID Application: NorthAgent Inc. (TEAM12345)"]);
});

test("findDeveloperIdApplicationIdentities reports missing Developer ID identity", () => {
  const fakeSpawn = () => ({
    status: 0,
    stdout: Buffer.from('  1) 1234567890ABCDEF "Apple Development: Dev User (TEAM12345)"\n'),
    stderr: Buffer.from(""),
  });

  const result = findDeveloperIdApplicationIdentities(fakeSpawn);

  assert.equal(result.ok, false);
  assert.deepEqual(result.identities, []);
});

test("checkNotaryTool accepts xcrun lookup output", () => {
  const fakeSpawn = () => ({
    status: 0,
    stdout: Buffer.from("/Applications/Xcode.app/Contents/Developer/usr/bin/notarytool\n"),
    stderr: Buffer.from(""),
  });

  const result = checkNotaryTool(fakeSpawn);

  assert.equal(result.ok, true);
  assert.match(result.path, /notarytool$/);
});

test("checkNotaryTool reports xcrun lookup failure", () => {
  const fakeSpawn = () => ({
    status: 1,
    stdout: Buffer.from(""),
    stderr: Buffer.from("xcrun: error: unable to find utility \"notarytool\""),
  });

  const result = checkNotaryTool(fakeSpawn);

  assert.equal(result.ok, false);
  assert.match(result.detail, /unable to find utility/);
});

test("runPreflight reports all missing release gates in non-strict mode", () => {
  const { electronAppPath } = createFakeElectronApp();
  const messages = [];
  const fakeSpawn = (_cmd, args) => {
    if (args.includes("find-identity")) {
      return {
        status: 0,
        stdout: Buffer.from('  1) 1234567890ABCDEF "Apple Development: Dev User (TEAM12345)"\n'),
        stderr: Buffer.from(""),
      };
    }
    return {
      status: 1,
      stdout: Buffer.from(""),
      stderr: Buffer.from("xcrun: error: unable to find utility \"notarytool\""),
    };
  };

  const summary = runPreflight({
    platform: "darwin",
    env: {},
    electronAppPath,
    appBuilderBinaryPath: path.join(os.tmpdir(), "missing-app-builder"),
    spawn: fakeSpawn,
    runXattr: () => ({ ok: true, stdout: "", stderr: "" }),
    report: (message) => messages.push(message),
    fail: (message) => {
      throw new Error(message);
    },
  });

  assert.equal(summary.ok, false);
  assert.deepEqual(summary.missingReleaseEnv, ["APPLE_ID", "APPLE_APP_SPECIFIC_PASSWORD", "APPLE_TEAM_ID"]);
  assert.equal(summary.developerIdReady, false);
  assert.equal(summary.notaryToolReady, false);
  assert.equal(summary.appBuilderExecutable.ok, false);
  assert.match(messages.join("\n"), /app-builder binary missing/);
  assert.match(messages.join("\n"), /Developer ID Application signing identity missing/);
  assert.match(messages.join("\n"), /xcrun notarytool not available/);
});

test("runPreflight fails strict mode when signing env is missing", () => {
  const { tmpDir, electronAppPath } = createFakeElectronApp();
  const appBuilderBinaryPath = createFakeAppBuilder(tmpDir);

  assert.throws(
    () =>
      runPreflight({
        platform: "darwin",
        strict: true,
        env: { APPLE_ID: "release@example.com", APPLE_TEAM_ID: "TEAM12345" },
        electronAppPath,
        appBuilderBinaryPath,
        spawn: buildReadySpawn(),
        runXattr: () => ({ ok: true, stdout: "", stderr: "" }),
        report: () => {},
        fail: (message) => {
          throw new Error(message);
        },
      }),
    /APPLE_APP_SPECIFIC_PASSWORD/
  );
});

test("runPreflight passes strict mode when mac release gates are ready", () => {
  const { tmpDir, electronAppPath } = createFakeElectronApp();
  const appBuilderBinaryPath = createFakeAppBuilder(tmpDir);
  const xattrCalls = [];
  const messages = [];

  const summary = runPreflight({
    platform: "darwin",
    strict: true,
    env: {
      APPLE_ID: "release@example.com",
      APPLE_APP_SPECIFIC_PASSWORD: "app-password",
      APPLE_TEAM_ID: "TEAM12345",
    },
    electronAppPath,
    appBuilderBinaryPath,
    spawn: buildReadySpawn(),
    runXattr: (args) => {
      xattrCalls.push(args);
      return { ok: true, stdout: "", stderr: "" };
    },
    report: (message) => messages.push(message),
    fail: (message) => {
      throw new Error(message);
    },
  });

  assert.equal(summary.ok, true);
  assert.equal(summary.developerIdReady, true);
  assert.equal(summary.notaryToolReady, true);
  assert.deepEqual(summary.missingReleaseEnv, []);
  assert.equal(xattrCalls.length, 2);
  assert.match(messages.join("\n"), /mac signing\/notarization env looks ready/);
  assert.match(messages.join("\n"), /Electron bundle present/);
});

test("runPreflight fails when Electron bundle is missing", () => {
  assert.throws(
    () =>
      runPreflight({
        platform: "darwin",
        electronAppPath: path.join(os.tmpdir(), "missing-electron-app"),
        appBuilderBinaryPath: path.join(os.tmpdir(), "missing-app-builder"),
        report: () => {},
        fail: (message) => {
          throw new Error(message);
        },
      }),
    /Electron\.app not found/
  );
});
