/* eslint-disable no-console */
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const projectRoot = path.resolve(__dirname, "..", "..");
const electronAppPath = path.join(projectRoot, "desktop", "node_modules", "electron", "dist", "Electron.app");
const appBuilderBinaryPath = path.join(projectRoot, "desktop", "node_modules", "app-builder-bin", "mac", "app-builder_arm64");
const strictMode = process.argv.includes("--strict");
const requiredReleaseEnv = ["APPLE_ID", "APPLE_APP_SPECIFIC_PASSWORD", "APPLE_TEAM_ID"];

function runXattr(args) {
  const result = spawnSync("xattr", args, { stdio: "pipe" });
  return {
    ok: result.status === 0,
    stdout: result.stdout ? result.stdout.toString("utf8").trim() : "",
    stderr: result.stderr ? result.stderr.toString("utf8").trim() : "",
  };
}

function report(message) {
  console.log(`[release-preflight] ${message}`);
}

function fail(message) {
  console.error(`[release-preflight] ${message}`);
  process.exit(1);
}

function getMissingReleaseEnv(env = process.env) {
  return requiredReleaseEnv.filter((name) => !env[name]);
}

function ensureExecutable(targetPath, logger = report) {
  if (!fs.existsSync(targetPath)) {
    return { ok: false, reason: "missing" };
  }
  const stat = fs.statSync(targetPath);
  const desiredMode = stat.mode | 0o755;
  if ((stat.mode & 0o111) === 0) {
    fs.chmodSync(targetPath, desiredMode);
    logger(`fixed execute bit for ${targetPath}`);
    return { ok: true, repaired: true };
  }
  return { ok: true, repaired: false };
}

function findDeveloperIdApplicationIdentities(spawn = spawnSync) {
  const result = spawn("security", ["find-identity", "-v", "-p", "codesigning"], { stdio: "pipe" });
  const stdout = result.stdout ? result.stdout.toString("utf8") : "";
  if (result.status !== 0) {
    return { ok: false, identities: [], detail: result.stderr ? result.stderr.toString("utf8").trim() : stdout.trim() };
  }
  const identities = stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.includes("Developer ID Application:"))
    .map((line) => {
      const match = line.match(/"([^"]+)"/);
      return match ? match[1] : line;
    });
  return { ok: identities.length > 0, identities, detail: stdout.trim() };
}

function checkNotaryTool(spawn = spawnSync) {
  const result = spawn("xcrun", ["--find", "notarytool"], { stdio: "pipe" });
  const stdout = result.stdout ? result.stdout.toString("utf8").trim() : "";
  const stderr = result.stderr ? result.stderr.toString("utf8").trim() : "";
  return {
    ok: result.status === 0 && Boolean(stdout),
    path: stdout,
    detail: stderr,
  };
}

function runPreflight(options = {}) {
  const isDarwin = options.platform || process.platform;
  const env = options.env || process.env;
  const strict = options.strict ?? strictMode;
  const spawn = options.spawn || spawnSync;

  if (!fs.existsSync(electronAppPath)) {
    fail(`Electron.app not found at ${electronAppPath}`);
  }

  if (isDarwin === "darwin") {
    ensureExecutable(appBuilderBinaryPath, report);

    const sanitizeTargets = [electronAppPath];
    for (const target of sanitizeTargets) {
      const removedQuarantine = runXattr(["-dr", "com.apple.quarantine", target]);
      const removedProvenance = runXattr(["-dr", "com.apple.provenance", target]);
      if (!removedQuarantine.ok && removedQuarantine.stderr) {
        report(`quarantine cleanup skipped for ${target}: ${removedQuarantine.stderr}`);
      }
      if (!removedProvenance.ok && removedProvenance.stderr) {
        report(`provenance cleanup skipped for ${target}: ${removedProvenance.stderr}`);
      }
    }

    const missingReleaseEnv = getMissingReleaseEnv(env);
    if (missingReleaseEnv.length > 0) {
      const message = `mac release signing/notarization env missing: ${missingReleaseEnv.join(", ")}`;
      if (strict) {
        fail(message);
      }
      report(message);
    } else {
      report("mac signing/notarization env looks ready");
    }

    const identityCheck = findDeveloperIdApplicationIdentities(spawn);
    if (!identityCheck.ok) {
      const message = "Developer ID Application signing identity missing";
      if (strict) {
        fail(message);
      }
      report(message);
    } else {
      report(`Developer ID Application identity ready: ${identityCheck.identities[0]}`);
    }

    const notaryTool = checkNotaryTool(spawn);
    if (!notaryTool.ok) {
      const message = "xcrun notarytool not available";
      if (strict) {
        fail(message);
      }
      report(message);
    } else {
      report(`notarytool ready: ${notaryTool.path}`);
    }
  }

  report(`Electron bundle present: ${electronAppPath}`);
}

if (require.main === module) {
  runPreflight();
}

module.exports = {
  checkNotaryTool,
  ensureExecutable,
  findDeveloperIdApplicationIdentities,
  getMissingReleaseEnv,
  runPreflight,
};
