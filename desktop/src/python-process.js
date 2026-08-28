const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { logRuntime } = require("./runtime-log");
const { ensureRuntimeRoot } = require("./runtime-paths");
const {
  resolveApiBaseUrl,
  resolveApiHealthUrl,
  resolveApiPort,
  resolveExplicitApiBaseUrlState,
  shouldAutoStartLocalApi,
} = require("./runtime-config");
const { PYTHON_OVERRIDE_KEYS, defaultPythonCandidates, resolveExplicitPythonCommand } = require("./python-runtime-resolution");

let pythonProcess = null;

function normalizeRuntimePaths(runtimePaths) {
  if (typeof runtimePaths === "string") {
    return {
      modelRoot: path.join(runtimePaths, "localmodels"),
      resourceRoot: runtimePaths,
      runtimeRoot: runtimePaths,
    };
  }
  if (!runtimePaths?.resourceRoot || !runtimePaths?.runtimeRoot || !runtimePaths?.modelRoot) {
    throw new Error("runtime paths must include resourceRoot, runtimeRoot and modelRoot");
  }
  return runtimePaths;
}

function buildDefaultPythonCandidates(resourceRoot, env = process.env, platform = process.platform) {
  return defaultPythonCandidates(resourceRoot, { env, platform });
}

function resolvePythonCommand(resourceRoot, env = process.env, platform = process.platform) {
  const { command: explicitPython } = resolveExplicitPythonCommand(env);
  if (explicitPython) {
    return explicitPython;
  }

  const candidates = buildDefaultPythonCandidates(resourceRoot, env, platform);
  for (const candidate of candidates) {
    if (!candidate.includes(path.sep) || fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return platform === "win32" ? "python" : "python3";
}

function startPythonApi(runtimePaths, options = {}) {
  const paths = normalizeRuntimePaths(runtimePaths);
  if (pythonProcess) {
    logRuntime(paths.runtimeRoot, "python_api_already_running", {
      pid: pythonProcess.pid
    });
    return pythonProcess;
  }

  const childEnv = options.env || process.env;
  const cmd = resolvePythonCommand(paths.resourceRoot, childEnv);
  const script = path.join(paths.resourceRoot, "run_api.py");
  const apiBaseUrl = options.apiBaseUrl || resolveApiBaseUrl(childEnv);
  logRuntime(paths.runtimeRoot, "python_api_starting", {
    command: cmd,
    script,
    cwd: paths.runtimeRoot,
    api_base_url: apiBaseUrl
  });

  const spawnImpl = options.spawnImpl || spawn;
  pythonProcess = spawnImpl(cmd, [script], {
    cwd: paths.runtimeRoot,
    stdio: "pipe",
    windowsHide: true,
    env: {
      ...process.env,
      ...options.env,
      KB_API_PORT: String(resolveApiPort(childEnv)),
      KB_DATA_ROOT: paths.runtimeRoot,
      KB_MODEL_ROOT: paths.modelRoot,
      NORTHAGENT_DATA_ROOT: paths.runtimeRoot,
      NORTHAGENT_MODEL_ROOT: paths.modelRoot,
      THINKRAG_DATA_ROOT: paths.runtimeRoot,
      THINKRAG_MODEL_ROOT: paths.modelRoot,
      FOXGLOVE_DATA_ROOT: paths.runtimeRoot,
      FOXGLOVE_MODEL_ROOT: paths.modelRoot,
      PYTHONDONTWRITEBYTECODE: "1",
      PYTHONIOENCODING: "utf-8",
    }
  });

  pythonProcess.stdout.on("data", (data) => {
    const message = data.toString();
    logRuntime(paths.runtimeRoot, "python_api_stdout", {
      pid: pythonProcess?.pid || null,
      message: message.trim()
    });
    console.log(`[python-api] ${message}`.trim());
  });

  pythonProcess.stderr.on("data", (data) => {
    const message = data.toString();
    logRuntime(paths.runtimeRoot, "python_api_stderr", {
      pid: pythonProcess?.pid || null,
      message: message.trim()
    });
    console.error(`[python-api:err] ${message}`.trim());
  });

  pythonProcess.on("error", (error) => {
    logRuntime(paths.runtimeRoot, "python_api_spawn_error", {
      message: error.message,
      stack: error.stack || ""
    });
  });

  pythonProcess.on("exit", (code, signal) => {
    logRuntime(paths.runtimeRoot, "python_api_exit", {
      pid: pythonProcess?.pid || null,
      code,
      signal
    });
    pythonProcess = null;
  });

  return pythonProcess;
}

function stopPythonApi(runtimePaths) {
  const paths = normalizeRuntimePaths(runtimePaths);
  if (!pythonProcess) {
    return;
  }
  logRuntime(paths.runtimeRoot, "python_api_stopping", {
    pid: pythonProcess.pid
  });
  pythonProcess.kill();
  pythonProcess = null;
}

async function waitForApiReady(runtimePaths, retries = 20, intervalMs = 500, options = {}) {
  const paths = normalizeRuntimePaths(runtimePaths);
  const fetchImpl = options.fetchImpl || fetch;
  const sleep = options.sleep || ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));
  const apiHealthUrl = options.apiHealthUrl || resolveApiHealthUrl(options.env || process.env);
  for (let i = 0; i < retries; i += 1) {
    try {
      const response = await fetchImpl(apiHealthUrl);
      if (response.ok) {
        logRuntime(paths.runtimeRoot, "python_api_ready", {
          attempt: i + 1,
          retries,
          status: response.status,
          url: apiHealthUrl
        });
        return true;
      }
    } catch (error) {
      if (i === retries - 1) {
        logRuntime(paths.runtimeRoot, "python_api_health_failed", {
          attempt: i + 1,
          retries,
          message: error.message,
          url: apiHealthUrl
        });
      }
    }
    await sleep(intervalMs);
  }
  logRuntime(paths.runtimeRoot, "python_api_not_ready", {
    retries,
    interval_ms: intervalMs,
    url: apiHealthUrl
  });
  return false;
}

async function ensurePythonApi(runtimePaths, options = {}) {
  const paths = normalizeRuntimePaths(runtimePaths);
  const childEnv = options.env || process.env;
  const explicitApiBaseUrl = resolveExplicitApiBaseUrlState(childEnv);
  const autoStartLocalApi = options.autoStartLocalApi ?? shouldAutoStartLocalApi(options.apiBaseUrl || childEnv);
  ensureRuntimeRoot(paths.runtimeRoot, options);

  if (explicitApiBaseUrl.invalid) {
    logRuntime(paths.runtimeRoot, "python_api_autostart_skipped", {
      reason: "explicit_invalid_api_base",
      url: explicitApiBaseUrl.raw,
    });
    return false;
  }

  const apiHealthUrl = options.apiHealthUrl || resolveApiHealthUrl(childEnv);
  const alreadyReady = await waitForApiReady(paths, 1, 0, { ...options, apiHealthUrl });
  if (alreadyReady) {
    logRuntime(paths.runtimeRoot, "python_api_reusing_existing", {
      url: apiHealthUrl
    });
    return true;
  }
  if (!autoStartLocalApi) {
    logRuntime(paths.runtimeRoot, "python_api_autostart_skipped", {
      reason: "explicit_non_local_api_base",
      url: apiHealthUrl,
    });
    return false;
  }
  startPythonApi(paths, options);
  return waitForApiReady(paths, options.retries || 20, options.intervalMs || 500, { ...options, apiHealthUrl });
}

module.exports = {
  PYTHON_OVERRIDE_KEYS,
  ensurePythonApi,
  startPythonApi,
  stopPythonApi,
  waitForApiReady,
  resolvePythonCommand,
  buildDefaultPythonCandidates
};
