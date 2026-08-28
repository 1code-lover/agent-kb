/* eslint-disable no-console */
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const {
  PYTHON_OVERRIDE_KEYS,
  defaultPythonCandidates: sharedDefaultPythonCandidates,
  resolveExplicitPythonCommand,
} = require("../src/python-runtime-resolution");

const projectRoot = path.resolve(__dirname, "..", "..");
const MAX_DIAGNOSTIC_LENGTH = 500;
const SECRET_ENV_KEY_PATTERN = /(?:TOKEN|SECRET|PASSWORD|API_KEY|APP_SPECIFIC|CREDENTIAL|PRIVATE_KEY)/i;
const REQUIRED_MODULES = ["fastapi", "uvicorn", "llama_index", "sentence_transformers", "httpx"];
// Keep the release verifier aligned with requirements-runtime.txt: lock the core package
// and import probes, but do not require the top-level llama-index metapackage that the
// default runtime baseline intentionally avoids.
const LOCKED_PACKAGES = {
  "llama-index-core": "0.11.19",
  "httpx": "0.27.2",
};

const PROBE_SOURCE = [
  "import importlib.metadata as metadata",
  "import importlib.util",
  "import json",
  "import platform",
  "import sys",
  `modules = ${JSON.stringify(REQUIRED_MODULES)}`,
  `packages = ${JSON.stringify(Object.keys(LOCKED_PACKAGES))}`,
  "missing_modules = [name for name in modules if importlib.util.find_spec(name) is None]",
  "package_versions = {}",
  "for package in packages:",
  "    try:",
  "        package_versions[package] = metadata.version(package)",
  "    except metadata.PackageNotFoundError:",
  "        package_versions[package] = None",
  "print(json.dumps({",
  "    'implementation': platform.python_implementation(),",
  "    'version': '.'.join(str(part) for part in sys.version_info[:3]),",
  "    'missingModules': missing_modules,",
  "    'packageVersions': package_versions,",
  "}, sort_keys=True))",
].join("\n");

function outputText(value) {
  if (value === undefined || value === null) {
    return "";
  }
  return Buffer.isBuffer(value) ? value.toString("utf8") : String(value);
}

function collectSecretValues(env = {}) {
  return [
    ...new Set(
      Object.entries(env)
        .filter(([key, value]) => SECRET_ENV_KEY_PATTERN.test(key) && typeof value === "string" && value.length >= 4)
        .map(([, value]) => value),
    ),
  ].sort((left, right) => right.length - left.length);
}

function redactSecretValues(value, env = {}) {
  let redacted = outputText(value);
  for (const secret of collectSecretValues(env)) {
    redacted = redacted.split(secret).join("[REDACTED]");
  }
  return redacted;
}

function summarizeDiagnostic(value, limit = MAX_DIAGNOSTIC_LENGTH, env = {}) {
  const collapsed = redactSecretValues(value, env).replace(/\s+/g, " ").trim();
  if (collapsed.length <= limit) {
    return collapsed;
  }
  return collapsed.slice(0, limit);
}

function defaultPythonCandidates(platform = process.platform, root = projectRoot, env = process.env) {
  return sharedDefaultPythonCandidates(root, { platform, env });
}

function resolvePythonCandidates(options = {}) {
  const env = options.env || process.env;
  const explicitPython = resolveExplicitPythonCommand(env);
  if (explicitPython.command) {
    return {
      candidates: [explicitPython.command],
      explicit: true,
      overrideKey: explicitPython.overrideKey,
    };
  }
  return {
    candidates: options.candidates || defaultPythonCandidates(options.platform, options.projectRoot, env),
    explicit: false,
    overrideKey: null,
  };
}

function emptyResult(explicit = false) {
  return {
    ok: false,
    pythonCommand: "",
    explicit,
    implementation: "",
    version: "",
    missingModules: [],
    packageVersions: {},
    pipCheck: "not_run",
    attempts: [],
    failures: [],
  };
}

function runCommand(spawn, command, args, options = {}) {
  try {
    const result = spawn(command, args, {
      encoding: "utf8",
      env: options.env,
      timeout: options.timeoutMs || 120000,
    });
    if (result?.error) {
      return {
        ok: false,
        status: result.status,
        stdout: outputText(result.stdout),
        stderr: outputText(result.stderr),
        error: summarizeDiagnostic(result.error.message || result.error, MAX_DIAGNOSTIC_LENGTH, options.env),
      };
    }
    return {
      ok: result?.status === 0,
      status: result?.status,
      stdout: outputText(result?.stdout),
      stderr: outputText(result?.stderr),
      error: "",
    };
  } catch (error) {
    return {
      ok: false,
      status: null,
      stdout: "",
      stderr: "",
      error: summarizeDiagnostic(error?.message || error, MAX_DIAGNOSTIC_LENGTH, options.env),
    };
  }
}

function failure(message, env = {}) {
  return summarizeDiagnostic(message, MAX_DIAGNOSTIC_LENGTH, env);
}

function inspectCandidate(pythonCommand, options = {}) {
  const spawn = options.spawn || spawnSync;
  const attempt = {
    ok: false,
    pythonCommand,
    implementation: "",
    version: "",
    missingModules: [],
    packageVersions: {},
    pipCheck: "not_run",
    failures: [],
  };

  const probeResult = runCommand(spawn, pythonCommand, ["-c", PROBE_SOURCE], options);
  if (!probeResult.ok) {
    const detail = probeResult.error || probeResult.stderr || probeResult.stdout || `exit status ${probeResult.status}`;
    attempt.failures.push(failure(`Python probe failed: ${detail}`, options.env));
    return attempt;
  }

  let probe;
  try {
    probe = JSON.parse(probeResult.stdout.trim());
  } catch (error) {
    const detail =
      summarizeDiagnostic(probeResult.stdout, MAX_DIAGNOSTIC_LENGTH, options.env)
      || summarizeDiagnostic(error.message, MAX_DIAGNOSTIC_LENGTH, options.env);
    attempt.failures.push(failure(`Python probe returned invalid JSON: ${detail}`, options.env));
    return attempt;
  }

  attempt.implementation = typeof probe?.implementation === "string" ? probe.implementation : "";
  attempt.version = typeof probe?.version === "string" ? probe.version : "";
  attempt.missingModules = Array.isArray(probe?.missingModules)
    ? probe.missingModules.filter((name) => typeof name === "string")
    : [...REQUIRED_MODULES];
  attempt.packageVersions =
    probe?.packageVersions && typeof probe.packageVersions === "object" && !Array.isArray(probe.packageVersions)
      ? probe.packageVersions
      : {};

  if (attempt.implementation !== "CPython") {
    attempt.failures.push(failure(`Python implementation must be CPython, got ${attempt.implementation || "unknown"}`, options.env));
  }
  if (!/^3\.12(?:\.|$)/.test(attempt.version)) {
    attempt.failures.push(failure(`Python version must be 3.12, got ${attempt.version || "unknown"}`, options.env));
  }
  if (attempt.missingModules.length > 0) {
    attempt.failures.push(failure(`Required Python modules missing: ${attempt.missingModules.join(", ")}`, options.env));
  }
  for (const [packageName, expectedVersion] of Object.entries(LOCKED_PACKAGES)) {
    const actualVersion = attempt.packageVersions[packageName];
    if (actualVersion !== expectedVersion) {
      attempt.failures.push(
        failure(
          `${packageName} must be ${expectedVersion}, got ${actualVersion === null || actualVersion === undefined ? "missing" : actualVersion}`,
          options.env,
        ),
      );
    }
  }
  if (attempt.failures.length > 0) {
    return attempt;
  }

  const pipResult = runCommand(spawn, pythonCommand, ["-m", "pip", "check"], options);
  const pipDetail = summarizeDiagnostic(
    pipResult.stdout || pipResult.stderr || pipResult.error,
    MAX_DIAGNOSTIC_LENGTH,
    options.env,
  );
  if (!pipResult.ok) {
    attempt.pipCheck = pipDetail || `exit status ${pipResult.status}`;
    attempt.failures.push(failure(`pip check failed: ${attempt.pipCheck}`, options.env));
    return attempt;
  }

  attempt.ok = true;
  attempt.pipCheck = pipDetail || "passed";
  return attempt;
}

function applyAttempt(result, attempt) {
  result.pythonCommand = attempt.pythonCommand;
  result.implementation = attempt.implementation;
  result.version = attempt.version;
  result.missingModules = attempt.missingModules;
  result.packageVersions = attempt.packageVersions;
  result.pipCheck = attempt.pipCheck;
}

function runVerifier(options = {}) {
  const resolution = resolvePythonCandidates(options);
  const result = emptyResult(resolution.explicit);

  if (!Array.isArray(resolution.candidates) || resolution.candidates.length === 0) {
    result.failures.push("No Python runtime candidates configured");
    return result;
  }

  for (const pythonCommand of resolution.candidates) {
    const attempt = inspectCandidate(pythonCommand, {
      ...options,
      env: options.env || process.env,
    });
    result.attempts.push(attempt);
    applyAttempt(result, attempt);
    if (attempt.ok) {
      result.ok = true;
      result.failures = [];
      return result;
    }
    if (resolution.explicit) {
      break;
    }
  }

  result.failures = result.attempts.flatMap((attempt) =>
    attempt.failures.map((message) => failure(`${attempt.pythonCommand}: ${message}`, options.env || process.env)),
  );
  return result;
}

function main() {
  const result = runVerifier();
  const serialized = JSON.stringify(result);
  if (!result.ok) {
    console.error(`[verify-python-runtime] ${serialized}`);
    process.exitCode = 1;
    return;
  }
  console.log(`[verify-python-runtime] ${serialized}`);
}

if (require.main === module) {
  main();
}

module.exports = {
  LOCKED_PACKAGES,
  MAX_DIAGNOSTIC_LENGTH,
  PROBE_SOURCE,
  PYTHON_OVERRIDE_KEYS,
  REQUIRED_MODULES,
  collectSecretValues,
  defaultPythonCandidates,
  inspectCandidate,
  redactSecretValues,
  resolvePythonCandidates,
  runVerifier,
  summarizeDiagnostic,
};
