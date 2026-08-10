const assert = require("node:assert/strict");
const test = require("node:test");

const notarizeMac = require("./notarize-mac");

function buildContext(overrides = {}) {
  return {
    electronPlatformName: "darwin",
    appOutDir: "/tmp/dist/mac",
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
  assert.deepEqual(result.missing, ["APPLE_ID", "APPLE_APP_SPECIFIC_PASSWORD", "APPLE_TEAM_ID"]);
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

  assert.deepEqual(calls, [
    {
      appBundleId: "com.northagent.desktop",
      appPath: "/tmp/dist/mac/NorthAgent.app",
      appleId: "release@example.com",
      appleIdPassword: "app-password",
      teamId: "TEAM123456",
    },
  ]);
  assert.equal(result.skipped, false);
});
