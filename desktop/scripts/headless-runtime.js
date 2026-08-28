#!/usr/bin/env node

// 桌面端 headless 启动兜底：复用真实启动编排，但不依赖 Electron 图形壳。
const path = require("node:path");

const { buildApiStartupFailureMessage, resolveApiStartupFailure } = require("../src/bootstrap-messages");
const { bootDesktopApp, resolveDevProjectRoot } = require("../src/desktop-bootstrap");
const { resolveDesktopHeadless } = require("../src/desktop-launch-config");
const { ensurePythonApi } = require("../src/python-process");
const { resolveRendererEntry } = require("../src/renderer-entry");
const { getLogFile, logRuntime } = require("../src/runtime-log");
const { ensureRuntimeRoot, resolveRuntimePaths } = require("../src/runtime-paths");

function createHeadlessApp(devProjectRoot) {
  return {
    isPackaged: false,
    getPath(name) {
      if (name !== "userData") {
        throw new Error(`unsupported app path request: ${name}`);
      }
      return path.join(devProjectRoot, ".dev-runtime", "desktop-user-data");
    },
    quit() {
      // headless runner 不需要显式图形进程退出逻辑
    },
  };
}

function createHeadlessDialog() {
  return {
    showErrorBox(title, message) {
      console.error(`[desktop-headless] ${title}: ${message}`);
    },
  };
}

function createHeadlessWindow(runtimePaths, env) {
  const rendererEntry = resolveRendererEntry({ resourceRoot: runtimePaths.resourceRoot, env });
  const headless = resolveDesktopHeadless(env);
  logRuntime(runtimePaths.runtimeRoot, "renderer_resolved", {
    ...rendererEntry,
    headless,
  });
  logRuntime(runtimePaths.runtimeRoot, "renderer_loaded", {
    headless,
    source: rendererEntry.source,
    url: rendererEntry.value,
  });
  return {
    kind: "headless-window",
    close() {},
  };
}

async function main() {
  const devProjectRoot = resolveDevProjectRoot({ dirname: __dirname });
  const env = process.env;
  const result = await bootDesktopApp({
    app: createHeadlessApp(devProjectRoot),
    dialog: createHeadlessDialog(),
    env,
    processResourcesPath: devProjectRoot,
    devProjectRoot,
    resolveRuntimePaths,
    ensureRuntimeRoot,
    getLogFile,
    logRuntime,
    ensurePythonApi,
    resolveApiStartupFailure,
    buildApiStartupFailureMessage,
    createWindow: (runtimePaths, options = {}) => createHeadlessWindow(runtimePaths, options.env || env),
  });

  if (!result.ok) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error("[desktop-headless] bootstrap failed", error);
  process.exitCode = 1;
});
