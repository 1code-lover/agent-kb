/* eslint-disable no-console */
const fs = require("node:fs");
const path = require("node:path");

const desktopRoot = path.resolve(__dirname, "..");
const packageJsonPath = path.join(desktopRoot, "package.json");

const requiredExtraResources = [
  { from: "../webapp/dist", to: "webapp/dist" },
  { from: "../api", to: "api" },
  { from: "../server", to: "server" },
  { from: "../utils", to: "utils" },
  { from: "../config.py", to: "config.py" },
  { from: "../run_api.py", to: "run_api.py" },
  { from: "../requirements.txt", to: "requirements.txt" },
];

function loadPackageJson(packagePath = packageJsonPath) {
  return JSON.parse(fs.readFileSync(packagePath, "utf8"));
}

function includesAll(values, required) {
  return required.every((item) => values.includes(item));
}

function hasExtraResource(resources, expected) {
  return resources.some((item) => item?.from === expected.from && item?.to === expected.to);
}

function verifyReleaseConfig(pkg) {
  const failures = [];
  const build = pkg?.build || {};
  const mac = build.mac || {};
  const scripts = pkg?.scripts || {};
  const files = Array.isArray(build.files) ? build.files : [];
  const extraResources = Array.isArray(build.extraResources) ? build.extraResources : [];
  const macTargets = Array.isArray(mac.target) ? mac.target : [];

  if (build.afterSign !== "scripts/notarize-mac.js") {
    failures.push("build.afterSign must run scripts/notarize-mac.js");
  }
  if (build.asar !== true) {
    failures.push("build.asar must be true");
  }
  if (build.compression !== "maximum") {
    failures.push('build.compression must be "maximum"');
  }
  if (!files.includes("!src/*.test.js")) {
    failures.push("build.files must exclude src/*.test.js");
  }
  if (mac.hardenedRuntime !== true) {
    failures.push("build.mac.hardenedRuntime must be true");
  }
  if (mac.entitlements !== "resources/entitlements.mac.plist") {
    failures.push("build.mac.entitlements must use resources/entitlements.mac.plist");
  }
  if (mac.entitlementsInherit !== "resources/entitlements.mac.inherit.plist") {
    failures.push("build.mac.entitlementsInherit must use resources/entitlements.mac.inherit.plist");
  }
  if (!includesAll(macTargets, ["dmg", "zip"])) {
    failures.push("build.mac.target must include dmg and zip");
  }

  for (const expected of requiredExtraResources) {
    if (!hasExtraResource(extraResources, expected)) {
      failures.push(`build.extraResources must include ${expected.from} -> ${expected.to}`);
    }
  }

  const releaseMac = scripts["release:mac"] || "";
  if (!releaseMac.includes("build:preflight")) {
    failures.push("scripts.release:mac must run build:preflight");
  }
  if (!releaseMac.includes("release:preflight")) {
    failures.push("scripts.release:mac must run release:preflight");
  }
  if (!releaseMac.includes("NORTHAGENT_REQUIRE_NOTARIZE=1")) {
    failures.push("scripts.release:mac must require notarization");
  }
  if (!releaseMac.includes("electron-builder/cli.js --mac")) {
    failures.push("scripts.release:mac must run electron-builder --mac");
  }

  return {
    ok: failures.length === 0,
    failures,
  };
}

function fail(message) {
  console.error(`[verify-release-config] ${message}`);
  process.exit(1);
}

function main() {
  const result = verifyReleaseConfig(loadPackageJson());
  if (!result.ok) {
    fail(result.failures.join("\n[verify-release-config] "));
  }
  console.log("[verify-release-config] release config looks ready");
}

if (require.main === module) {
  main();
}

module.exports = {
  loadPackageJson,
  requiredExtraResources,
  verifyReleaseConfig,
};
