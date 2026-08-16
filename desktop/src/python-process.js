const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { logRuntime } = require("./runtime-log");
const { ensureRuntimeRoot } = require("./runtime-paths");

let pythonProcess = null;
const API_HEALTH_URL = "http://127.0.0.1:18080/api/health";

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

function resolvePythonCommand(resourceRoot) {
  const explicitPython = process.env.NORTHAGENT_PYTHON || process.env.THINKRAG_PYTHON || process.env.FOXGLOVE_PYTHON;
  if (explicitPython) {
    return explicitPython;
  }

  const candidates =
    process.platform === "win32"
      ? [
          path.join(resourceRoot, ".venv", "Scripts", "python.exe"),
          path.join(resourceRoot, "venv", "Scripts", "python.exe"),
          "python"
        ]
      : [
          "/opt/miniconda3/envs/agent-kb/bin/python",
          path.join(resourceRoot, ".venv", "bin", "python"),
          path.join(resourceRoot, "venv", "bin", "python"),
          "python3"
        ];

  for (const candidate of candidates) {
    if (!candidate.includes(path.sep) || fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return process.platform === "win32" ? "python" : "python3";
}

function startPythonApi(runtimePaths, options = {}) {
  const paths = normalizeRuntimePaths(runtimePaths);
  if (pythonProcess) {
    logRuntime(paths.runtimeRoot, "python_api_already_running", {
      pid: pythonProcess.pid
    });
    return pythonProcess;
  }

  const cmd = resolvePythonCommand(paths.resourceRoot);
  const script = path.join(paths.resourceRoot, "run_api.py");
  logRuntime(paths.runtimeRoot, "python_api_starting", {
    command: cmd,
    script,
    cwd: paths.runtimeRoot
  });

  const spawnImpl = options.spawnImpl || spawn;
  pythonProcess = spawnImpl(cmd, [script], {
    cwd: paths.runtimeRoot,
    stdio: "pipe",
    windowsHide: true,
    env: {
      ...process.env,
      NORTHAGENT_DATA_ROOT: paths.runtimeRoot,
      NORTHAGENT_MODEL_ROOT: paths.modelRoot,
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
  for (let i = 0; i < retries; i += 1) {
    try {
      const response = await fetchImpl(API_HEALTH_URL);
      if (response.ok) {
        logRuntime(paths.runtimeRoot, "python_api_ready", {
          attempt: i + 1,
          retries,
          status: response.status
        });
        return true;
      }
    } catch (error) {
      if (i === retries - 1) {
        logRuntime(paths.runtimeRoot, "python_api_health_failed", {
          attempt: i + 1,
          retries,
          message: error.message
        });
      }
    }
    await sleep(intervalMs);
  }
  logRuntime(paths.runtimeRoot, "python_api_not_ready", {
    retries,
    interval_ms: intervalMs
  });
  return false;
}

async function ensurePythonApi(runtimePaths, options = {}) {
  const paths = normalizeRuntimePaths(runtimePaths);
  ensureRuntimeRoot(paths.runtimeRoot, options);
  const alreadyReady = await waitForApiReady(paths, 1, 0, options);
  if (alreadyReady) {
    logRuntime(paths.runtimeRoot, "python_api_reusing_existing", {
      url: API_HEALTH_URL
    });
    return true;
  }
  startPythonApi(paths, options);
  return waitForApiReady(paths, options.retries || 20, options.intervalMs || 500, options);
}

module.exports = {
  ensurePythonApi,
  startPythonApi,
  stopPythonApi,
  waitForApiReady,
  resolvePythonCommand
};
