/* eslint-disable no-console */
const { platform } = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function runBuildTarget(options = {}) {
  const currentPlatform = options.platform || platform();
  const spawn = options.spawn || spawnSync;
  const stdio = options.stdio || "inherit";
  const target = currentPlatform === "darwin" ? "--mac" : "--win";
  const verifyReleaseConfigPath = path.join(__dirname, "verify-release-config.js");
  const verifyPythonRuntimePath = path.join(__dirname, "verify-python-runtime.js");
  const releasePreflightPath = path.join(__dirname, "release-preflight.js");
  const electronBuilderPath = path.join(__dirname, "..", "node_modules", "electron-builder", "cli.js");

  if (currentPlatform === "darwin") {
    const configPreflight = spawn("node", [verifyReleaseConfigPath], { stdio });
    if (configPreflight.status !== 0) {
      return { status: configPreflight.status ?? 1, target, platform: currentPlatform, stage: "build-preflight" };
    }

    const pythonRuntime = spawn("node", [verifyPythonRuntimePath], { stdio });
    if (pythonRuntime.status !== 0) {
      return { status: pythonRuntime.status ?? 1, target, platform: currentPlatform, stage: "python-runtime" };
    }

    const preflight = spawn("node", [releasePreflightPath], { stdio });
    if (preflight.status !== 0) {
      return { status: preflight.status ?? 1, target, platform: currentPlatform, stage: "release-preflight" };
    }
  }

  const result = spawn("node", [electronBuilderPath, target], { stdio });
  return { status: result.status ?? 1, target, platform: currentPlatform, stage: "electron-builder" };
}

if (require.main === module) {
  const result = runBuildTarget();
  if (result.status !== 0) {
    process.exit(result.status);
  }
}

module.exports = {
  runBuildTarget,
};
