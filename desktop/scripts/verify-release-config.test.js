const assert = require("node:assert/strict");
const test = require("node:test");

const { verifyReleaseConfig } = require("./verify-release-config");

function buildPackage(overrides = {}) {
  const pkg = {
    scripts: {
      "release:mac":
        "npm run build:web && npm run release:preflight && NORTHAGENT_REQUIRE_NOTARIZE=1 node ./node_modules/electron-builder/cli.js --mac",
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
      },
    }),
  );

  assert.equal(result.ok, false);
  assert.match(result.failures.join("\n"), /afterSign/);
  assert.match(result.failures.join("\n"), /hardenedRuntime/);
  assert.match(result.failures.join("\n"), /entitlements/);
  assert.match(result.failures.join("\n"), /notarization/);
  assert.match(result.failures.join("\n"), /release:preflight/);
});

test("verifyReleaseConfig rejects missing packaged runtime resources", () => {
  const pkg = buildPackage();
  pkg.build.extraResources = pkg.build.extraResources.filter((item) => item.to !== "server");

  const result = verifyReleaseConfig(pkg);

  assert.equal(result.ok, false);
  assert.match(result.failures.join("\n"), /\.\.\/server -> server/);
});
