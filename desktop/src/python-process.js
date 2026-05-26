/**
 * 管理 Python API 子进程生命周期。
 */
const { spawn } = require("node:child_process");
const path = require("node:path");

let pythonProcess = null;

function getPythonCommand() {
  if (process.platform === "win32") {
    return "python";
  }
  return "python3";
}

function startPythonApi(projectRoot) {
  if (pythonProcess) {
    return pythonProcess;
  }

  const cmd = getPythonCommand();
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
  waitForApiReady
};
