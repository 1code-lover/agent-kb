const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  checkNotaryTool,
  describePreflightMode,
  ensureExecutable,
  findDeveloperIdApplicationIdentities,
  getMissingReleaseEnv,
  resolveLegacyAppBuilderBinaryPath,
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
  if (process.platform === "win32") {
    assert.equal(fs.existsSync(target), true);
    return;
  }
  assert.equal(result.repaired, true);
  const mode = fs.statSync(target).mode & 0o777;
  assert.equal(mode & 0o111, 0o111);
});

test("ensureExecutable reports missing files", () => {
  const result = ensureExecutable(path.join(os.tmpdir(), "missing-binary"), () => {});

  assert.deepEqual(result, { ok: false, reason: "missing" });
});

test("resolveLegacyAppBuilderBinaryPath returns empty when electron-builder no longer ships app-builder-bin", () => {
  const result = resolveLegacyAppBuilderBinaryPath([path.join(os.tmpdir(), "missing-app-builder")]);

  assert.equal(result, "");
});

test("getMissingReleaseEnv reports only absent notarization variables", () => {
  const result = getMissingReleaseEnv({
    APPLE_ID: "dev@example.com",
    APPLE_TEAM_ID: "TEAM12345",
  });

  assert.deepEqual(result, [
    { strategy: "keychain_profile", missing: ["APPLE_KEYCHAIN_PROFILE"] },
    { strategy: "api_key", missing: ["APPLE_API_KEY", "APPLE_API_KEY_ID", "APPLE_API_ISSUER"] },
    { strategy: "apple_id", missing: ["APPLE_APP_SPECIFIC_PASSWORD"] },
  ]);
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
  assert.deepEqual(summary.missingReleaseEnv, [
    { strategy: "keychain_profile", missing: ["APPLE_KEYCHAIN_PROFILE"] },
    { strategy: "api_key", missing: ["APPLE_API_KEY", "APPLE_API_KEY_ID", "APPLE_API_ISSUER"] },
    { strategy: "apple_id", missing: ["APPLE_ID", "APPLE_APP_SPECIFIC_PASSWORD", "APPLE_TEAM_ID"] },
  ]);
  assert.equal(summary.developerIdReady, false);
  assert.equal(summary.notaryToolReady, false);
  assert.equal(summary.appBuilderExecutable.ok, false);
  assert.match(messages.join("\n"), /non-strict build preflight/);
  assert.match(messages.join("\n"), /does not prove the final app is already signed\/notarized/);
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
  assert.equal(summary.notarizationStrategy, "apple_id");
  assert.equal(xattrCalls.length, 2);
  assert.match(messages.join("\n"), /strict release preflight/);
  assert.match(messages.join("\n"), /does not prove the final app is already signed\/notarized/);
  assert.match(messages.join("\n"), /mac signing\/notarization env looks ready/);
  assert.match(messages.join("\n"), /Electron bundle present/);
});

test("runPreflight skips legacy app-builder executable when upgraded electron-builder does not install it", () => {
  const { electronAppPath } = createFakeElectronApp();
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
    appBuilderBinaryCandidates: [path.join(os.tmpdir(), "missing-app-builder")],
    spawn: buildReadySpawn(),
    runXattr: () => ({ ok: true, stdout: "", stderr: "" }),
    report: (message) => messages.push(message),
    fail: (message) => {
      throw new Error(message);
    },
  });

  assert.equal(summary.ok, true);
  assert.deepEqual(summary.appBuilderExecutable, {
    ok: true,
    skipped: true,
    reason: "app-builder-bin not installed",
  });
  assert.match(messages.join("\n"), /skipping execute-bit repair/);
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

test("runPreflight accepts Keychain profile credentials in strict mode", () => {
  const { tmpDir, electronAppPath } = createFakeElectronApp();
  const summary = runPreflight({
    platform: "darwin",
    strict: true,
    env: { APPLE_KEYCHAIN_PROFILE: "northagent-notary" },
    electronAppPath,
    appBuilderBinaryPath: createFakeAppBuilder(tmpDir),
    spawn: buildReadySpawn(),
    runXattr: () => ({ ok: true, stdout: "", stderr: "" }),
    report: () => {},
    fail: (message) => {
      throw new Error(message);
    },
  });

  assert.equal(summary.ok, true);
  assert.equal(summary.notarizationStrategy, "keychain_profile");
  assert.deepEqual(summary.missingReleaseEnv, []);
});

test("runPreflight accepts App Store Connect API credentials in strict mode", () => {
  const { tmpDir, electronAppPath } = createFakeElectronApp();
  const summary = runPreflight({
    platform: "darwin",
    strict: true,
    env: {
      APPLE_API_KEY: "/secure/AuthKey_TEST123.p8",
      APPLE_API_KEY_ID: "TEST123",
      APPLE_API_ISSUER: "issuer-uuid",
    },
    electronAppPath,
    appBuilderBinaryPath: createFakeAppBuilder(tmpDir),
    spawn: buildReadySpawn(),
    runXattr: () => ({ ok: true, stdout: "", stderr: "" }),
    report: () => {},
    fail: (message) => {
      throw new Error(message);
    },
  });

  assert.equal(summary.ok, true);
  assert.equal(summary.notarizationStrategy, "api_key");
  assert.deepEqual(summary.missingReleaseEnv, []);
});

test("runPreflight warns about a partial higher-priority strategy while using a complete lower strategy", () => {
  const { tmpDir, electronAppPath } = createFakeElectronApp();
  const messages = [];
  const summary = runPreflight({
    platform: "darwin",
    strict: true,
    env: {
      APPLE_API_KEY: "/secure/PRIVATE-KEY-SECRET.p8",
      APPLE_ID: "secret-release@example.com",
      APPLE_APP_SPECIFIC_PASSWORD: "secret-password",
      APPLE_TEAM_ID: "SECRETTEAM",
    },
    electronAppPath,
    appBuilderBinaryPath: createFakeAppBuilder(tmpDir),
    spawn: buildReadySpawn(),
    runXattr: () => ({ ok: true, stdout: "", stderr: "" }),
    report: (message) => messages.push(message),
    fail: (message) => {
      throw new Error(message);
    },
  });

  const output = messages.join("\n");
  assert.equal(summary.ok, true);
  assert.equal(summary.notarizationStrategy, "apple_id");
  assert.deepEqual(summary.partialNotarizationStrategies, [
    { strategy: "api_key", missing: ["APPLE_API_KEY_ID", "APPLE_API_ISSUER"] },
  ]);
  assert.match(output, /api_key/);
  assert.match(output, /APPLE_API_KEY_ID/);
  assert.match(output, /apple_id/);
  assert.doesNotMatch(output, /PRIVATE-KEY-SECRET/);
  assert.doesNotMatch(output, /secret-release@example\.com/);
  assert.doesNotMatch(output, /secret-password/);
  assert.doesNotMatch(output, /SECRETTEAM/);
});

test("runPreflight strict mode reports all independent mac release gate failures", () => {
  const { electronAppPath } = createFakeElectronApp();
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
      stderr: Buffer.from('xcrun: error: unable to find utility "notarytool"'),
    };
  };

  assert.throws(
    () =>
      runPreflight({
        platform: "darwin",
        strict: true,
        env: {},
        electronAppPath,
        appBuilderBinaryPath: "",
        spawn: fakeSpawn,
        runXattr: () => ({ ok: true, stdout: "", stderr: "" }),
        report: () => {},
        fail: (message) => {
          throw new Error(message);
        },
      }),
    (error) => {
      assert.match(error.message, /keychain_profile/);
      assert.match(error.message, /APPLE_KEYCHAIN_PROFILE/);
      assert.match(error.message, /api_key/);
      assert.match(error.message, /apple_id/);
      assert.match(error.message, /Developer ID Application signing identity missing/);
      assert.match(error.message, /xcrun notarytool not available/);
      return true;
    },
  );
});

test("preflight and notarize hook resolve the same credential strategy", async () => {
  const notarizeMac = require("./notarize-mac");
  const { tmpDir, electronAppPath } = createFakeElectronApp();
  const env = {
    APPLE_KEYCHAIN: "/Users/release/Library/Keychains/release.keychain-db",
    APPLE_API_KEY: "/secure/AuthKey_TEST123.p8",
    APPLE_API_KEY_ID: "TEST123",
    APPLE_API_ISSUER: "issuer-uuid",
    APPLE_ID: "release@example.com",
    APPLE_APP_SPECIFIC_PASSWORD: "app-password",
    APPLE_TEAM_ID: "TEAM12345",
  };
  const preflight = runPreflight({
    platform: "darwin",
    strict: true,
    env,
    electronAppPath,
    appBuilderBinaryPath: createFakeAppBuilder(tmpDir),
    spawn: buildReadySpawn(),
    runXattr: () => ({ ok: true, stdout: "", stderr: "" }),
    report: () => {},
    fail: (message) => {
      throw new Error(message);
    },
  });
  const hook = await notarizeMac(
    {
      electronPlatformName: "darwin",
      appOutDir: "/tmp/dist/mac",
      packager: {
        appInfo: { appId: "com.northagent.desktop", productFilename: "NorthAgent" },
      },
    },
    {
      platform: "darwin",
      env,
      logger: { log() {} },
      notarizeFn: async () => {},
    },
  );

  assert.equal(preflight.notarizationStrategy, "api_key");
  assert.equal(hook.strategy, preflight.notarizationStrategy);
});


test("describePreflightMode exposes strict vs non-strict lane names", () => {
  assert.equal(describePreflightMode(false), "non-strict build preflight");
  assert.equal(describePreflightMode(true), "strict release preflight");
});
