const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { logRuntime } = require("./runtime-log");

let pythonProcess = null;

function resolvePythonCommand(projectRoot) {
  const candidates =
    process.platform === "win32"
      ? [
          path.join(projectRoot, ".venv", "Scripts", "python.exe"),
          path.join(projectRoot, "venv", "Scripts", "python.exe"),
          "python"
        ]
      : [
          path.join(projectRoot, ".venv", "bin", "python"),
          path.join(projectRoot, "venv", "bin", "python"),
          "python3"
        ];

  for (const candidate of candidates) {
    if (!candidate.includes(path.sep) || fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return process.platform === "win32" ? "python" : "python3";
}

function startPythonApi(projectRoot) {
  if (pythonProcess) {
    logRuntime(projectRoot, "python_api_already_running", {
      pid: pythonProcess.pid
    });
    return pythonProcess;
  }

  const cmd = resolvePythonCommand(projectRoot);
  const script = path.join(projectRoot, "run_api.py");
  logRuntime(projectRoot, "python_api_starting", {
    command: cmd,
    script,
    cwd: projectRoot
  });

  pythonProcess = spawn(cmd, [script], {
    cwd: projectRoot,
    stdio: "pipe",
    windowsHide: true,
    env: {
      ...process.env,
      PYTHONIOENCODING: "utf-8"
    }
  });

  pythonProcess.stdout.on("data", (data) => {
    const message = data.toString();
    logRuntime(projectRoot, "python_api_stdout", {
      pid: pythonProcess?.pid || null,
      message: message.trim()
    });
    console.log(`[python-api] ${message}`.trim());
  });

  pythonProcess.stderr.on("data", (data) => {
    const message = data.toString();
    logRuntime(projectRoot, "python_api_stderr", {
      pid: pythonProcess?.pid || null,
      message: message.trim()
    });
    console.error(`[python-api:err] ${message}`.trim());
  });

  pythonProcess.on("error", (error) => {
    logRuntime(projectRoot, "python_api_spawn_error", {
      message: error.message,
      stack: error.stack || ""
    });
  });

  pythonProcess.on("exit", (code, signal) => {
    logRuntime(projectRoot, "python_api_exit", {
      pid: pythonProcess?.pid || null,
      code,
      signal
    });
    pythonProcess = null;
  });

  return pythonProcess;
}

function stopPythonApi(projectRoot) {
  if (!pythonProcess) {
    return;
  }
  logRuntime(projectRoot, "python_api_stopping", {
    pid: pythonProcess.pid
  });
  pythonProcess.kill();
  pythonProcess = null;
}

async function waitForApiReady(projectRoot, retries = 20, intervalMs = 500) {
  for (let i = 0; i < retries; i += 1) {
    try {
      const response = await fetch("http://127.0.0.1:18080/api/health");
      if (response.ok) {
        logRuntime(projectRoot, "python_api_ready", {
          attempt: i + 1,
          retries,
          status: response.status
        });
        return true;
      }
    } catch (error) {
      if (i === retries - 1) {
        logRuntime(projectRoot, "python_api_health_failed", {
          attempt: i + 1,
          retries,
          message: error.message
        });
      }
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  logRuntime(projectRoot, "python_api_not_ready", {
    retries,
    interval_ms: intervalMs
  });
  return false;
}

module.exports = {
  startPythonApi,
  stopPythonApi,
  waitForApiReady,
  resolvePythonCommand
};
