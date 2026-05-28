/**
 * Manage the local Python API child process lifecycle.
 */
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

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
    return pythonProcess;
  }

  const cmd = resolvePythonCommand(projectRoot);
  const script = path.join(projectRoot, "run_api.py");
  pythonProcess = spawn(cmd, [script], {
    cwd: projectRoot,
    stdio: "pipe",
    windowsHide: true
  });

  pythonProcess.stdout.on("data", (data) => {
    // eslint-disable-next-line no-console
    console.log(`[python-api] ${data}`.trim());
  });

  pythonProcess.stderr.on("data", (data) => {
    // eslint-disable-next-line no-console
    console.error(`[python-api:err] ${data}`.trim());
  });

  pythonProcess.on("exit", () => {
    pythonProcess = null;
  });

  return pythonProcess;
}

function stopPythonApi() {
  if (!pythonProcess) {
    return;
  }
  pythonProcess.kill();
  pythonProcess = null;
}

async function waitForApiReady(retries = 20, intervalMs = 500) {
  for (let i = 0; i < retries; i += 1) {
    try {
      const response = await fetch("http://127.0.0.1:18080/api/health");
      if (response.ok) {
        return true;
      }
    } catch (error) {
      // ignore and retry
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  return false;
}

module.exports = {
  startPythonApi,
  stopPythonApi,
  waitForApiReady,
  resolvePythonCommand
};
