const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const { buildApiStartupFailureMessage, buildRendererStartupFailureMessage, resolveApiStartupFailure } = require("./bootstrap-messages");
const { bootDesktopApp, resolveDevProjectRoot } = require("./desktop-bootstrap");

function normalizePath(value) {
  return String(value).replaceAll("\\", "/");
}

test("resolveDevProjectRoot resolves repo root relative to desktop/src", () => {
  const dirname = path.join("/repo", "desktop", "src");
  assert.ok(normalizePath(resolveDevProjectRoot({ dirname })).endsWith("/repo"));
});

test("bootDesktopApp surfaces explicit remote API failures without creating a window", async () => {
  const dialogCalls = [];
  const quitCalls = [];
  const logCalls = [];
  const runtimePathsSeen = [];
  const createWindowCalls = [];
  const ensurePythonApiCalls = [];

  const result = await bootDesktopApp({
    app: {
      isPackaged: false,
      getPath: (name) => {
        assert.equal(name, "userData");
        return "/tmp/user-data";
      },
      quit: () => {
        quitCalls.push("quit");
      },
    },
    dialog: {
      showErrorBox: (title, message) => {
        dialogCalls.push({ title, message });
      },
    },
    env: { KB_API_BASE_URL: "https://api.example.com:18443" },
    processResourcesPath: "/tmp/resources",
    devProjectRoot: "/repo",
    onRuntimePaths: (runtimePaths) => {
      runtimePathsSeen.push(runtimePaths);
    },
    resolveRuntimePaths: ({ devProjectRoot, isPackaged, resourcesPath, userDataPath, env }) => {
      assert.equal(devProjectRoot, "/repo");
      assert.equal(isPackaged, false);
      assert.equal(resourcesPath, "/tmp/resources");
      assert.equal(userDataPath, "/tmp/user-data");
      assert.deepEqual(env, { KB_API_BASE_URL: "https://api.example.com:18443" });
      return {
        runtimeRoot: "/repo/.runtime",
        resourceRoot: "/repo",
        modelRoot: "/repo/localmodels",
      };
    },
    ensureRuntimeRoot: (runtimeRoot) => {
      assert.equal(runtimeRoot, "/repo/.runtime");
    },
    getLogFile: (runtimeRoot) => `${runtimeRoot}/storage/logs/desktop_runtime.log`,
    logRuntime: (runtimeRoot, event, payload) => {
      logCalls.push({ runtimeRoot, event, payload });
    },
    ensurePythonApi: async (runtimePaths, options) => {
      ensurePythonApiCalls.push({ runtimePaths, options });
      return false;
    },
    resolveApiStartupFailure,
    buildApiStartupFailureMessage,
    createWindow: (...args) => {
      createWindowCalls.push(args);
      return { kind: "window" };
    },
  });

  assert.deepEqual(runtimePathsSeen, [{
    runtimeRoot: "/repo/.runtime",
    resourceRoot: "/repo",
    modelRoot: "/repo/localmodels",
  }]);
  assert.equal(result.ok, false);
  assert.equal(result.reason, "explicit_remote_api_unavailable");
  assert.equal(result.apiBaseUrl, "https://api.example.com:18443");
  assert.equal(result.autoStartLocalApi, false);
  assert.equal(result.logFile, "/repo/.runtime/storage/logs/desktop_runtime.log");
  assert.deepEqual(ensurePythonApiCalls, [{
    runtimePaths: {
      runtimeRoot: "/repo/.runtime",
      resourceRoot: "/repo",
      modelRoot: "/repo/localmodels",
    },
    options: { env: { KB_API_BASE_URL: "https://api.example.com:18443" } },
  }]);
  assert.deepEqual(createWindowCalls, []);
  assert.deepEqual(quitCalls, ["quit"]);
  assert.equal(dialogCalls.length, 1);
  assert.equal(dialogCalls[0].title, "NorthAgent");
  assert.match(dialogCalls[0].message, /https:\/\/api\.example\.com:18443/);
  assert.match(dialogCalls[0].message, /不会自动回退到本地 run_api\.py/);
  assert.deepEqual(logCalls, [
    {
      runtimeRoot: "/repo/.runtime",
      event: "desktop_app_ready",
      payload: { log_file: "/repo/.runtime/storage/logs/desktop_runtime.log" },
    },
    {
      runtimeRoot: "/repo/.runtime",
      event: "desktop_app_boot_failed",
      payload: {
        reason: "explicit_remote_api_unavailable",
        apiBaseUrl: "https://api.example.com:18443",
        autoStartLocalApi: false,
        log_file: "/repo/.runtime/storage/logs/desktop_runtime.log",
      },
    },
  ]);
});


test("bootDesktopApp aborts before API startup when runtime root is unavailable", async () => {
  const dialogCalls = [];
  const quitCalls = [];
  const logCalls = [];
  const consoleErrors = [];
  const ensurePythonApiCalls = [];
  const createWindowCalls = [];

  const result = await bootDesktopApp({
    app: {
      isPackaged: false,
      getPath: () => "/tmp/user-data",
      quit: () => {
        quitCalls.push("quit");
      },
    },
    dialog: {
      showErrorBox: (title, message) => {
        dialogCalls.push({ title, message });
      },
    },
    env: {},
    processResourcesPath: "/tmp/resources",
    devProjectRoot: "/repo",
    resolveRuntimePaths: () => ({
      runtimeRoot: "/repo/.runtime",
      resourceRoot: "/repo",
      modelRoot: "/repo/localmodels",
    }),
    ensureRuntimeRoot: () => {
      throw new Error("runtime directory is not writable");
    },
    getLogFile: (runtimeRoot) => `${runtimeRoot}/storage/logs/desktop_runtime.log`,
    logRuntime: (runtimeRoot, event, payload) => {
      logCalls.push({ runtimeRoot, event, payload });
    },
    ensurePythonApi: async (...args) => {
      ensurePythonApiCalls.push(args);
      return true;
    },
    resolveApiStartupFailure,
    buildApiStartupFailureMessage,
    createWindow: (...args) => {
      createWindowCalls.push(args);
      return { kind: "window" };
    },
    consoleImpl: {
      error: (...args) => {
        consoleErrors.push(args);
      },
    },
  });

  assert.equal(result.ok, false);
  assert.equal(result.reason, "runtime_root_unavailable");
  assert.equal(result.logFile, "/repo/.runtime/storage/logs/desktop_runtime.log");
  assert.deepEqual(logCalls, []);
  assert.deepEqual(ensurePythonApiCalls, []);
  assert.deepEqual(createWindowCalls, []);
  assert.deepEqual(quitCalls, ["quit"]);
  assert.equal(dialogCalls.length, 1);
  assert.equal(dialogCalls[0].title, "NorthAgent");
  assert.match(dialogCalls[0].message, /运行目录不可写，无法启动：\/repo\/.runtime/);
  assert.match(dialogCalls[0].message, /runtime directory is not writable/);
  assert.equal(consoleErrors.length, 1);
  assert.equal(consoleErrors[0][0], "[desktop-runtime] runtime root unavailable");
  assert.match(String(consoleErrors[0][1]?.message || ""), /runtime directory is not writable/);
});

test("bootDesktopApp surfaces renderer entry failures after API bootstrap", async () => {
  const dialogCalls = [];
  const quitCalls = [];
  const logCalls = [];
  const result = await bootDesktopApp({
    app: {
      isPackaged: true,
      getPath: () => "/tmp/user-data",
      quit: () => {
        quitCalls.push("quit");
      },
    },
    dialog: {
      showErrorBox: (title, message) => {
        dialogCalls.push({ title, message });
      },
    },
    env: {},
    processResourcesPath: "/packaged/resources",
    devProjectRoot: "/repo",
    resolveRuntimePaths: () => ({
      runtimeRoot: "/tmp/user-data/runtime",
      resourceRoot: "/packaged/resources",
      modelRoot: "/packaged/resources/localmodels",
    }),
    ensureRuntimeRoot: () => {},
    getLogFile: (runtimeRoot) => `${runtimeRoot}/storage/logs/desktop_runtime.log`,
    logRuntime: (runtimeRoot, event, payload) => {
      logCalls.push({ runtimeRoot, event, payload });
    },
    ensurePythonApi: async () => true,
    resolveApiStartupFailure,
    buildApiStartupFailureMessage,
    buildRendererStartupFailureMessage,
    createWindow: () => {
      throw new Error("packaged renderer entry is missing: /packaged/resources/webapp/dist/index.html");
    },
  });

  assert.equal(result.ok, false);
  assert.equal(result.reason, "renderer_entry_unavailable");
  assert.equal(result.errorMessage, "packaged renderer entry is missing: /packaged/resources/webapp/dist/index.html");
  assert.equal(result.logFile, "/tmp/user-data/runtime/storage/logs/desktop_runtime.log");
  assert.deepEqual(quitCalls, ["quit"]);
  assert.equal(dialogCalls.length, 1);
  assert.equal(dialogCalls[0].title, "NorthAgent");
  assert.match(dialogCalls[0].message, /桌面前端入口不可用/);
  assert.match(dialogCalls[0].message, /KB_WEB_URL/);
  assert.deepEqual(logCalls, [
    {
      runtimeRoot: "/tmp/user-data/runtime",
      event: "desktop_app_ready",
      payload: { log_file: "/tmp/user-data/runtime/storage/logs/desktop_runtime.log" },
    },
    {
      runtimeRoot: "/tmp/user-data/runtime",
      event: "desktop_app_boot_failed",
      payload: {
        reason: "renderer_entry_unavailable",
        message: "packaged renderer entry is missing: /packaged/resources/webapp/dist/index.html",
        log_file: "/tmp/user-data/runtime/storage/logs/desktop_runtime.log",
      },
    },
  ]);
});

test("bootDesktopApp creates a window after the API is ready", async () => {
  const dialogCalls = [];
  const quitCalls = [];
  const logCalls = [];
  const createWindowCalls = [];
  const expectedWindow = { kind: "window" };

  const result = await bootDesktopApp({
    app: {
      isPackaged: true,
      getPath: (name) => {
        assert.equal(name, "userData");
        return "/tmp/user-data";
      },
      quit: () => {
        quitCalls.push("quit");
      },
    },
    dialog: {
      showErrorBox: (title, message) => {
        dialogCalls.push({ title, message });
      },
    },
    env: { KB_API_PORT: "18095" },
    processResourcesPath: "/packaged/resources",
    devProjectRoot: "/repo",
    resolveRuntimePaths: ({ isPackaged, resourcesPath, userDataPath, env }) => {
      assert.equal(isPackaged, true);
      assert.equal(resourcesPath, "/packaged/resources");
      assert.equal(userDataPath, "/tmp/user-data");
      assert.deepEqual(env, { KB_API_PORT: "18095" });
      return {
        runtimeRoot: "/tmp/user-data/runtime",
        resourceRoot: "/packaged/resources",
        modelRoot: "/packaged/resources/localmodels",
      };
    },
    ensureRuntimeRoot: (runtimeRoot) => {
      assert.equal(runtimeRoot, "/tmp/user-data/runtime");
    },
    getLogFile: (runtimeRoot) => `${runtimeRoot}/storage/logs/desktop_runtime.log`,
    logRuntime: (runtimeRoot, event, payload) => {
      logCalls.push({ runtimeRoot, event, payload });
    },
    ensurePythonApi: async (runtimePaths, options) => {
      assert.deepEqual(runtimePaths, {
        runtimeRoot: "/tmp/user-data/runtime",
        resourceRoot: "/packaged/resources",
        modelRoot: "/packaged/resources/localmodels",
      });
      assert.deepEqual(options, { env: { KB_API_PORT: "18095" } });
      return true;
    },
    resolveApiStartupFailure,
    buildApiStartupFailureMessage,
    createWindow: (runtimePaths, options) => {
      createWindowCalls.push({ runtimePaths, options });
      return expectedWindow;
    },
  });

  assert.equal(result.ok, true);
  assert.deepEqual(result.runtimePaths, {
    runtimeRoot: "/tmp/user-data/runtime",
    resourceRoot: "/packaged/resources",
    modelRoot: "/packaged/resources/localmodels",
  });
  assert.equal(result.logFile, "/tmp/user-data/runtime/storage/logs/desktop_runtime.log");
  assert.equal(result.window, expectedWindow);
  assert.deepEqual(createWindowCalls, [{
    runtimePaths: {
      runtimeRoot: "/tmp/user-data/runtime",
      resourceRoot: "/packaged/resources",
      modelRoot: "/packaged/resources/localmodels",
    },
    options: { env: { KB_API_PORT: "18095" } },
  }]);
  assert.deepEqual(logCalls, [{
    runtimeRoot: "/tmp/user-data/runtime",
    event: "desktop_app_ready",
    payload: { log_file: "/tmp/user-data/runtime/storage/logs/desktop_runtime.log" },
  }]);
  assert.deepEqual(dialogCalls, []);
  assert.deepEqual(quitCalls, []);
});
