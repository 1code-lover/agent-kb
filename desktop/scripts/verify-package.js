/* eslint-disable no-console */
const fs = require("node:fs");
const path = require("node:path");
const asar = require("@electron/asar");

const desktopRoot = path.resolve(__dirname, "..");
const resourcesRoot = path.join(desktopRoot, "dist", "mac-arm64", "NorthAgent.app", "Contents", "Resources");
const asarPath = path.join(resourcesRoot, "app.asar");

const requiredRuntimeFiles = [
  "webapp/dist/index.html",
  "run_api.py",
  "config.py",
  "requirements.txt",
  "api/app.py",
  "server/index.py",
  "utils/logging_utils.py",
];

const requiredArtifacts = [
  "dist/NorthAgent-0.1.0-arm64.dmg",
  "dist/NorthAgent-0.1.0-arm64-mac.zip",
];

function fail(message) {
  console.error(`[verify-package] ${message}`);
  process.exit(1);
}

for (const artifact of requiredArtifacts) {
  const artifactPath = path.join(desktopRoot, artifact);
  if (!fs.existsSync(artifactPath)) {
    fail(`missing artifact: ${artifactPath}`);
  }
}

for (const relativePath of requiredRuntimeFiles) {
  const target = path.join(resourcesRoot, relativePath);
  if (!fs.existsSync(target)) {
    fail(`missing runtime file: ${target}`);
  }
}

if (!fs.existsSync(asarPath)) {
  fail(`missing app.asar: ${asarPath}`);
}

const asarEntries = asar.listPackage(asarPath);
const testEntries = asarEntries.filter((entry) => /\.test\.js$/.test(entry));
if (testEntries.length > 0) {
  fail(`test files should not be packaged: ${testEntries.join(", ")}`);
}

console.log("[verify-package] package contents look ready");
