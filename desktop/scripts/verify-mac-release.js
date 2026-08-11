/* eslint-disable no-console */
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const { resolvePackageLayout } = require("./verify-package");

function resolveAppPath(layout) {
  const resourcesRoot = layout?.resourcesRoot || "";
  if (!resourcesRoot) {
    return "";
  }
  return path.resolve(resourcesRoot, "..", "..");
}

function runCheck({ args, label, spawn = spawnSync }) {
  const result = spawn(args[0], args.slice(1), { stdio: "pipe" });
  const stdout = result.stdout ? result.stdout.toString("utf8").trim() : "";
  const stderr = result.stderr ? result.stderr.toString("utf8").trim() : "";
  return {
    command: args.join(" "),
    detail: stderr || stdout,
    label,
    ok: result.status === 0,
    status: result.status,
  };
}

function verifyMacRelease(options = {}) {
  const platform = options.platform || process.platform;
  const strict = options.strict ?? false;
  const fsModule = options.fs || fs;
  const spawn = options.spawn || spawnSync;
  const layout = options.layout || resolvePackageLayout(options.packageOptions || {});
  const appPath = options.appPath || resolveAppPath(layout);
  const checks = [];
  const failures = [];

  if (platform !== "darwin") {
    return {
      appPath,
      checks,
      failures,
      ok: true,
      platform,
      skipped: true,
      skippedReason: "not_macos",
      strict,
    };
  }

  if (!appPath || !fsModule.existsSync(appPath)) {
    failures.push(`missing macOS app bundle: ${appPath || "(unresolved)"}`);
    return {
      appPath,
      checks,
      failures,
      ok: false,
      platform,
      skipped: false,
      strict,
    };
  }

  const releaseChecks = [
    {
      args: ["codesign", "--verify", "--deep", "--strict", "--verbose=2", appPath],
      label: "codesign",
    },
    {
      args: ["spctl", "--assess", "--type", "execute", "--verbose=4", appPath],
      label: "gatekeeper",
    },
    {
      args: ["xcrun", "stapler", "validate", appPath],
      label: "stapler",
    },
  ];

  for (const check of releaseChecks) {
    const result = runCheck({ ...check, spawn });
    checks.push(result);
    if (!result.ok) {
      failures.push(`${result.label} failed for ${appPath}: ${result.detail || `exit ${result.status}`}`);
    }
  }

  return {
    appPath,
    checks,
    failures,
    ok: failures.length === 0,
    platform,
    skipped: false,
    strict,
  };
}

function fail(message) {
  console.error(`[verify-mac-release] ${message}`);
  process.exit(1);
}

function main() {
  const strict = process.argv.includes("--strict");
  const result = verifyMacRelease({ strict });
  if (result.skipped) {
    console.log(`[verify-mac-release] skipped: ${result.skippedReason}`);
    return;
  }
  if (!result.ok) {
    const message = result.failures.join("\n[verify-mac-release] ");
    if (strict) {
      fail(message);
    }
    console.log(`[verify-mac-release] ${message}`);
    return;
  }
  console.log("[verify-mac-release] mac release signature and notarization look ready");
}

if (require.main === module) {
  main();
}

module.exports = {
  resolveAppPath,
  runCheck,
  verifyMacRelease,
};
