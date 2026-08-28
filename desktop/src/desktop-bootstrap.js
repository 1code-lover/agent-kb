const path = require("node:path");

async function bootDesktopApp(options) {
  const {
    app,
    dialog,
    env = process.env,
    processResourcesPath,
    devProjectRoot,
    appName = "NorthAgent",
    onRuntimePaths,
    resolveRuntimePaths,
    ensureRuntimeRoot,
    getLogFile,
    logRuntime,
    ensurePythonApi,
    resolveApiStartupFailure,
    buildApiStartupFailureMessage,
    buildRendererStartupFailureMessage,
    createWindow,
    consoleImpl = console,
  } = options;

  const runtimePaths = resolveRuntimePaths({
    devProjectRoot,
    isPackaged: app.isPackaged,
    resourcesPath: processResourcesPath,
    userDataPath: app.getPath("userData"),
    env,
  });
  onRuntimePaths?.(runtimePaths);

  const logFile = getLogFile(runtimePaths.runtimeRoot);
  try {
    ensureRuntimeRoot(runtimePaths.runtimeRoot);
  } catch (error) {
    consoleImpl.error("[desktop-runtime] runtime root unavailable", error);
    dialog.showErrorBox(appName, `运行目录不可写，无法启动：${runtimePaths.runtimeRoot}
${error.message}`);
    app.quit();
    return {
      ok: false,
      reason: "runtime_root_unavailable",
      runtimePaths,
      logFile,
    };
  }

  logRuntime(runtimePaths.runtimeRoot, "desktop_app_ready", { log_file: logFile });

  const ready = await ensurePythonApi(runtimePaths, { env });
  if (!ready) {
    const apiStartupFailure = resolveApiStartupFailure({ env });
    logRuntime(runtimePaths.runtimeRoot, "desktop_app_boot_failed", {
      ...apiStartupFailure,
      log_file: logFile,
    });
    dialog.showErrorBox(appName, buildApiStartupFailureMessage({ logFile, env }));
    app.quit();
    return {
      ok: false,
      runtimePaths,
      logFile,
      ...apiStartupFailure,
    };
  }

  try {
    const window = createWindow(runtimePaths, { env });
    return {
      ok: true,
      runtimePaths,
      logFile,
      window,
    };
  } catch (error) {
    logRuntime(runtimePaths.runtimeRoot, "desktop_app_boot_failed", {
      reason: "renderer_entry_unavailable",
      message: error.message,
      log_file: logFile,
    });
    const failureMessage = typeof buildRendererStartupFailureMessage === "function"
      ? buildRendererStartupFailureMessage({ error, logFile, env })
      : `桌面前端入口不可用，无法启动：${error.message}
日志：${logFile}`;
    dialog.showErrorBox(appName, failureMessage);
    app.quit();
    return {
      ok: false,
      reason: "renderer_entry_unavailable",
      runtimePaths,
      logFile,
      errorMessage: error.message,
    };
  }
}

function resolveDevProjectRoot({ dirname = __dirname } = {}) {
  return path.resolve(dirname, "..", "..");
}

module.exports = {
  bootDesktopApp,
  resolveDevProjectRoot,
};
