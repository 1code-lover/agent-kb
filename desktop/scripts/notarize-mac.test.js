const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const notarizeMac = require("./notarize-mac");

function normalizePath(value) {
  return String(value).replaceAll("\\", "/");
}

function normalizePayload(payload) {
  return {
    ...payload,
    appPath: normalizePath(payload.appPath),
  };
}

function buildContext(overrides = {}) {
  return {
    electronPlatformName: "darwin",
    appOutDir: path.join("/tmp", "dist", "mac"),
    packager: {
      appInfo: {
        appId: "com.northagent.desktop",
        productFilename: "NorthAgent",
      },
    },
    ...overrides,
  };
}

test("notarizeMac skips non-mac builds", async () => {
  const result = await notarizeMac(buildContext({ electronPlatformName: "win32" }), {
    platform: "darwin",
    logger: { log() {} },
  });

  assert.deepEqual(result, { skipped: true, reason: "not_macos" });
});

test("notarizeMac skips missing credentials unless notarization is required", async () => {
  const result = await notarizeMac(buildContext(), {
    env: {},
    platform: "darwin",
    logger: { log() {} },
  });

  assert.equal(result.skipped, true);
  assert.equal(result.reason, "missing_env");
  assert.deepEqual(result.missing, [
    { strategy: "keychain_profile", missing: ["APPLE_KEYCHAIN_PROFILE"] },
    { strategy: "api_key", missing: ["APPLE_API_KEY", "APPLE_API_KEY_ID", "APPLE_API_ISSUER"] },
    { strategy: "apple_id", missing: ["APPLE_ID", "APPLE_APP_SPECIFIC_PASSWORD", "APPLE_TEAM_ID"] },
  ]);
});

test("notarizeMac fails missing credentials when notarization is required", async () => {
  await assert.rejects(
    () =>
      notarizeMac(buildContext(), {
        env: { NORTHAGENT_REQUIRE_NOTARIZE: "1" },
        platform: "darwin",
        logger: { log() {} },
      }),
    /missing notarization env/
  );
});

test("notarizeMac submits expected notarization payload", async () => {
  const calls = [];
  const result = await notarizeMac(buildContext(), {
    env: {
      APPLE_ID: "release@example.com",
      APPLE_APP_SPECIFIC_PASSWORD: "app-password",
      APPLE_TEAM_ID: "TEAM123456",
    },
    platform: "darwin",
    logger: { log() {} },
    notarizeFn: async (payload) => {
      calls.push(payload);
    },
  });

  assert.deepEqual(calls.map(normalizePayload), [
    {
      appBundleId: "com.northagent.desktop",
      appPath: "/tmp/dist/mac/NorthAgent.app",
      appleId: "release@example.com",
      appleIdPassword: "app-password",
      teamId: "TEAM123456",
    },
  ]);
  assert.equal(normalizePath(result.appPath), "/tmp/dist/mac/NorthAgent.app");
  assert.equal(result.skipped, false);
});

test("notarizeMac submits with a Keychain profile and optional keychain", async () => {
  const calls = [];
  const messages = [];
  const result = await notarizeMac(buildContext(), {
    env: {
      APPLE_KEYCHAIN_PROFILE: "northagent-notary",
      APPLE_KEYCHAIN: "/Users/release/Library/Keychains/release.keychain-db",
    },
    platform: "darwin",
    logger: { log: (message) => messages.push(message) },
    notarizeFn: async (payload) => calls.push(payload),
  });

  assert.deepEqual(calls.map(normalizePayload), [
    {
      appBundleId: "com.northagent.desktop",
      appPath: "/tmp/dist/mac/NorthAgent.app",
      keychainProfile: "northagent-notary",
      keychain: "/Users/release/Library/Keychains/release.keychain-db",
    },
  ]);
  assert.equal(normalizePath(result.appPath), "/tmp/dist/mac/NorthAgent.app");
  assert.equal(result.strategy, "keychain_profile");
  assert.match(messages.join("\n"), /keychain_profile/);
  assert.doesNotMatch(messages.join("\n"), /northagent-notary/);
  assert.doesNotMatch(messages.join("\n"), /release\.keychain-db/);
});

test("notarizeMac submits with App Store Connect API credentials", async () => {
  const calls = [];
  const messages = [];
  const result = await notarizeMac(buildContext(), {
    env: {
      APPLE_API_KEY: "/secure/AuthKey_SECRET.p8",
      APPLE_API_KEY_ID: "SECRET-ID",
      APPLE_API_ISSUER: "SECRET-ISSUER",
    },
    platform: "darwin",
    logger: { log: (message) => messages.push(message) },
    notarizeFn: async (payload) => calls.push(payload),
  });

  assert.deepEqual(calls.map(normalizePayload), [
    {
      appBundleId: "com.northagent.desktop",
      appPath: "/tmp/dist/mac/NorthAgent.app",
      appleApiKey: "/secure/AuthKey_SECRET.p8",
      appleApiKeyId: "SECRET-ID",
      appleApiIssuer: "SECRET-ISSUER",
    },
  ]);
  assert.equal(normalizePath(result.appPath), "/tmp/dist/mac/NorthAgent.app");
  assert.equal(result.strategy, "api_key");
  assert.match(messages.join("\n"), /api_key/);
  assert.doesNotMatch(messages.join("\n"), /SECRET/);
});

test("notarizeMac keeps Apple ID payload compatibility and reports its strategy", async () => {
  const calls = [];
  const messages = [];
  const result = await notarizeMac(buildContext(), {
    env: {
      APPLE_ID: "secret-release@example.com",
      APPLE_APP_SPECIFIC_PASSWORD: "secret-app-password",
      APPLE_TEAM_ID: "SECRETTEAM",
    },
    platform: "darwin",
    logger: { log: (message) => messages.push(message) },
    notarizeFn: async (payload) => calls.push(payload),
  });

  assert.equal(calls.length, 1);
  assert.equal(result.strategy, "apple_id");
  assert.match(messages.join("\n"), /apple_id/);
  assert.doesNotMatch(messages.join("\n"), /secret-release/);
  assert.doesNotMatch(messages.join("\n"), /secret-app-password/);
  assert.doesNotMatch(messages.join("\n"), /SECRETTEAM/);
});

test("notarizeMac required mode reports partial strategies without leaking values", async () => {
  const secret = "/secure/PRIVATE-KEY-SECRET.p8";
  await assert.rejects(
    () =>
      notarizeMac(buildContext(), {
        env: {
          NORTHAGENT_REQUIRE_NOTARIZE: "1",
          APPLE_API_KEY: secret,
          APPLE_API_KEY_ID: "KEY-ID-SECRET",
        },
        platform: "darwin",
        logger: { log() {} },
      }),
    (error) => {
      assert.match(error.message, /api_key/);
      assert.match(error.message, /APPLE_API_ISSUER/);
      assert.doesNotMatch(error.message, /PRIVATE-KEY-SECRET/);
      assert.doesNotMatch(error.message, /KEY-ID-SECRET/);
      return true;
    },
  );
});
