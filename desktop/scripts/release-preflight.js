/* eslint-disable no-console */
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const {
  formatNotarizationCredentialDiagnostics,
  resolveNotarizationCredentials,
} = require("./notarization-credentials");

const projectRoot = path.resolve(__dirname, "..", "..");
const electronAppPath = path.join(projectRoot, "desktop", "node_modules", "electron", "dist", "Electron.app");
const legacyAppBuilderBinaryCandidates = [
  path.join(projectRoot, "desktop", "node_modules", "app-builder-bin", "mac", "app-builder_arm64"),
  path.join(projectRoot, "desktop", "node_modules", "app-builder-bin", "mac", "app-builder_x64"),
];
const strictMode = process.argv.includes("--strict");

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
  return resolveNotarizationCredentials(env).missing;
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

function resolveLegacyAppBuilderBinaryPath(candidates = legacyAppBuilderBinaryCandidates) {
  return candidates.find((candidate) => fs.existsSync(candidate)) || "";
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
  const currentElectronAppPath = options.electronAppPath || electronAppPath;
  const currentAppBuilderBinaryPath =
    options.appBuilderBinaryPath === undefined
      ? resolveLegacyAppBuilderBinaryPath(options.appBuilderBinaryCandidates)
      : options.appBuilderBinaryPath;
  const reportFn = options.report || report;
  const failFn = options.fail || fail;
  const runXattrFn = options.runXattr || runXattr;

  const summary = {
    ok: true,
    platform: isDarwin,
    strict,
    electronAppPath: currentElectronAppPath,
    appBuilderBinaryPath: currentAppBuilderBinaryPath,
    appBuilderExecutable: null,
    failures: [],
    missingReleaseEnv: [],
    notarizationStrategy: null,
    partialNotarizationStrategies: [],
    developerIdReady: null,
    developerIdIdentities: [],
    notaryToolReady: null,
    notaryToolPath: "",
  };

  if (!fs.existsSync(currentElectronAppPath)) {
    summary.ok = false;
    failFn(`Electron.app not found at ${currentElectronAppPath}`);
    return summary;
  }

  if (isDarwin === "darwin") {
    if (currentAppBuilderBinaryPath) {
      const executableCheck = ensureExecutable(currentAppBuilderBinaryPath, reportFn);
      summary.appBuilderExecutable = executableCheck;
      if (!executableCheck.ok) {
        const message = `app-builder binary missing at ${currentAppBuilderBinaryPath}`;
        summary.ok = false;
        summary.failures.push(message);
        reportFn(message);
      }
    } else {
      summary.appBuilderExecutable = { ok: true, skipped: true, reason: "app-builder-bin not installed" };
      reportFn("legacy app-builder-bin executable not installed; skipping execute-bit repair");
    }

    const sanitizeTargets = [currentElectronAppPath];
    for (const target of sanitizeTargets) {
      const removedQuarantine = runXattrFn(["-dr", "com.apple.quarantine", target]);
      const removedProvenance = runXattrFn(["-dr", "com.apple.provenance", target]);
      if (!removedQuarantine.ok && removedQuarantine.stderr) {
        reportFn(`quarantine cleanup skipped for ${target}: ${removedQuarantine.stderr}`);
      }
      if (!removedProvenance.ok && removedProvenance.stderr) {
        reportFn(`provenance cleanup skipped for ${target}: ${removedProvenance.stderr}`);
      }
    }

    const credentialResolution = resolveNotarizationCredentials(env);
    const credentialDiagnostics = formatNotarizationCredentialDiagnostics(credentialResolution);
    summary.missingReleaseEnv = credentialResolution.missing;
    summary.notarizationStrategy = credentialResolution.strategy;
    summary.partialNotarizationStrategies = credentialResolution.partial;
    for (const diagnostic of credentialDiagnostics) {
      reportFn(diagnostic);
    }
    if (!credentialResolution.strategy) {
      const message = `mac release notarization credentials missing: ${credentialDiagnostics.join("; ")}`;
      summary.ok = false;
      summary.failures.push(message);
      reportFn(message);
    } else {
      reportFn(`mac signing/notarization env looks ready with strategy ${credentialResolution.strategy}`);
    }

    const identityCheck = findDeveloperIdApplicationIdentities(spawn);
    summary.developerIdReady = identityCheck.ok;
    summary.developerIdIdentities = identityCheck.identities;
    if (!identityCheck.ok) {
      const message = "Developer ID Application signing identity missing";
      summary.ok = false;
      summary.failures.push(message);
      reportFn(message);
    } else {
      reportFn(`Developer ID Application identity ready: ${identityCheck.identities[0]}`);
    }

    const notaryTool = checkNotaryTool(spawn);
    summary.notaryToolReady = notaryTool.ok;
    summary.notaryToolPath = notaryTool.path || "";
    if (!notaryTool.ok) {
      const message = "xcrun notarytool not available";
      summary.ok = false;
      summary.failures.push(message);
      reportFn(message);
    } else {
      reportFn(`notarytool ready: ${notaryTool.path}`);
    }
  }

  reportFn(`Electron bundle present: ${currentElectronAppPath}`);
  if (strict && summary.failures.length > 0) {
    failFn(summary.failures.join("; "));
  }
  return summary;
}

if (require.main === module) {
  runPreflight();
}

module.exports = {
  checkNotaryTool,
  ensureExecutable,
  findDeveloperIdApplicationIdentities,
  getMissingReleaseEnv,
  resolveLegacyAppBuilderBinaryPath,
  runPreflight,
};
