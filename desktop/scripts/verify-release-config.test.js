const assert = require("node:assert/strict");
const test = require("node:test");

const { verifyReleaseConfig } = require("./verify-release-config");

function buildPackage(overrides = {}) {
  const pkg = {
    scripts: {
      "verify:mac-release": "node scripts/verify-mac-release.js --strict",
      "release:mac":
        "npm run build:web && npm run build:preflight && npm run release:preflight && NORTHAGENT_REQUIRE_NOTARIZE=1 node ./node_modules/electron-builder/cli.js --mac && npm run verify:package && npm run verify:mac-release",
    },
    build: {
      afterSign: "scripts/notarize-mac.js",
      asar: true,
      compression: "maximum",
      files: ["src/**/*", "!src/*.test.js", "resources/**/*"],
      extraResources: [
        { from: "../webapp/dist", to: "webapp/dist", filter: ["**/*"] },
        { from: "../api", to: "api", filter: ["**/*.py"] },
        { from: "../server", to: "server", filter: ["**/*.py"] },
        { from: "../utils", to: "utils", filter: ["**/*.py"] },
        { from: "../config.py", to: "config.py" },
        { from: "../run_api.py", to: "run_api.py" },
        { from: "../requirements.txt", to: "requirements.txt" },
      ],
      mac: {
        notarize: false,
        hardenedRuntime: true,
        entitlements: "resources/entitlements.mac.plist",
        entitlementsInherit: "resources/entitlements.mac.inherit.plist",
        target: ["dmg", "zip"],
      },
    },
  };
  return {
    ...pkg,
    ...overrides,
    scripts: { ...pkg.scripts, ...(overrides.scripts || {}) },
    build: { ...pkg.build, ...(overrides.build || {}) },
  };
}

test("verifyReleaseConfig accepts the expected mac release configuration", () => {
  const result = verifyReleaseConfig(buildPackage());

  assert.equal(result.ok, true);
  assert.deepEqual(result.failures, []);
});

test("verifyReleaseConfig rejects missing notarize hook and hardened runtime", () => {
  const result = verifyReleaseConfig(
    buildPackage({
      build: {
        afterSign: "",
        hardenedRuntime: false,
        mac: {
          hardenedRuntime: false,
          entitlements: "",
          entitlementsInherit: "",
          target: ["zip"],
        },
      },
      scripts: {
        "release:mac": "node ./node_modules/electron-builder/cli.js --mac",
        "verify:mac-release": "node scripts/verify-mac-release.js",
      },
    }),
  );

  assert.equal(result.ok, false);
  assert.match(result.failures.join("\n"), /afterSign/);
  assert.match(result.failures.join("\n"), /hardenedRuntime/);
  assert.match(result.failures.join("\n"), /entitlements/);
  assert.match(result.failures.join("\n"), /notarization/);
  assert.match(result.failures.join("\n"), /build:preflight/);
  assert.match(result.failures.join("\n"), /release:preflight/);
  assert.match(result.failures.join("\n"), /packaged runtime contents/);
  assert.match(result.failures.join("\n"), /mac release signature and notarization/);
  assert.match(result.failures.join("\n"), /verify-mac-release\.js --strict/);
});

test("verifyReleaseConfig rejects missing packaged runtime resources", () => {
  const pkg = buildPackage();
  pkg.build.extraResources = pkg.build.extraResources.filter((item) => item.to !== "server");

  const result = verifyReleaseConfig(pkg);

  assert.equal(result.ok, false);
  assert.match(result.failures.join("\n"), /\.\.\/server -> server/);
});

test("verifyReleaseConfig requires electron-builder built-in notarization to be explicitly disabled", () => {
  const missing = buildPackage();
  delete missing.build.mac.notarize;
  const enabled = buildPackage();
  enabled.build.mac.notarize = true;

  const missingResult = verifyReleaseConfig(missing);
  const enabledResult = verifyReleaseConfig(enabled);

  assert.equal(missingResult.ok, false);
  assert.match(missingResult.failures.join("\n"), /build\.mac\.notarize must be false/);
  assert.equal(enabledResult.ok, false);
  assert.match(enabledResult.failures.join("\n"), /build\.mac\.notarize must be false/);
});
