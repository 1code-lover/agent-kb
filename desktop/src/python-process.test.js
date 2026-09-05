const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  PYTHON_OVERRIDE_KEYS,
  buildDefaultPythonCandidates,
  ensurePythonApi,
  resolvePythonCommand,
  stopPythonApi,
} = require("./python-process");

function normalizePath(value) {
  return String(value).replaceAll("\\", "/");
}

const runtimePaths = {
  modelRoot: "/tmp/resources/localmodels",
  resourceRoot: "/tmp/resources",
  runtimeRoot: "/tmp/user-data/runtime",
};

test("resolvePythonCommand prefers KB_PYTHON over legacy desktop overrides", () => {
  const env = {
    KB_PYTHON: "/custom/kb-python",
    NORTHAGENT_PYTHON: "/custom/northagent-python",
    THINKRAG_PYTHON: "/custom/thinkrag-python",
  };

  assert.equal(resolvePythonCommand(process.cwd(), env), "/custom/kb-python");
  assert.deepEqual(PYTHON_OVERRIDE_KEYS, ["KB_PYTHON", "NORTHAGENT_PYTHON", "THINKRAG_PYTHON", "FOXGLOVE_PYTHON"]);
});

test("buildDefaultPythonCandidates prefers active env interpreters before project-local fallbacks", () => {
  const candidates = buildDefaultPythonCandidates(
    "/workspace/project",
    {
      CONDA_PREFIX: "/opt/conda/envs/agent-kb",
      VIRTUAL_ENV: "/tmp/venv",
    },
    "darwin",
  );

  assert.deepEqual(candidates, [
    "/opt/conda/envs/agent-kb/bin/python",
    "/tmp/venv/bin/python",
    "/workspace/project/.venv/bin/python",
    "/workspace/project/venv/bin/python",
    "python3",
    "python",
  ]);
});

test("resolvePythonCommand reuses a project-local virtualenv before bare python fallbacks", () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "agent-kb-python-"));
  const localPython =
    process.platform === "win32"
      ? path.join(tempRoot, ".venv", "Scripts", "python.exe")
      : path.join(tempRoot, ".venv", "bin", "python");

  fs.mkdirSync(path.dirname(localPython), { recursive: true });
  fs.writeFileSync(localPython, "", { encoding: "utf8" });

  assert.equal(normalizePath(resolvePythonCommand(tempRoot, {})), normalizePath(localPython));
});

test("ensurePythonApi reuses an already running API without spawning", async () => {
  const spawnCalls = [];
  const ready = await ensurePythonApi(runtimePaths, {
    apiHealthUrl: "http://127.0.0.1:18095/api/health",
    fetchImpl: async () => ({ ok: true, status: 200 }),
    spawnImpl: () => {
      spawnCalls.push("spawned");
      throw new Error("spawn should not be called");
    },
    sleep: async () => {},
  });

  assert.equal(ready, true);
  assert.deepEqual(spawnCalls, []);
});

test("ensurePythonApi does not auto-spawn when explicit external API base is unavailable", async () => {
  const spawnCalls = [];

  const ready = await ensurePythonApi(runtimePaths, {
    env: { KB_API_BASE_URL: "https://api.example.com:18443" },
    fetchImpl: async () => {
      throw new Error("remote api unavailable");
    },
    spawnImpl: () => {
      spawnCalls.push("spawned");
      throw new Error("spawn should not be called");
    },
    sleep: async () => {},
  });

  assert.equal(ready, false);
  assert.deepEqual(spawnCalls, []);
});

test("ensurePythonApi rejects an invalid explicit API base before probing or spawning local runtime", async () => {
  const fetchCalls = [];
  const spawnCalls = [];

  const ready = await ensurePythonApi(runtimePaths, {
    env: { KB_API_BASE_URL: "not-a-valid-url", KB_API_PORT: "19090" },
    fetchImpl: async (url) => {
      fetchCalls.push(url);
      return { ok: true, status: 200 };
    },
    spawnImpl: () => {
      spawnCalls.push("spawned");
      throw new Error("spawn should not be called");
    },
    sleep: async () => {},
  });

  assert.equal(ready, false);
  assert.deepEqual(fetchCalls, []);
  assert.deepEqual(spawnCalls, []);
});

test("ensurePythonApi starts Python from resources with writable cwd and unified KB runtime roots", async () => {
  const spawnCalls = [];
  const fakeProcess = {
    pid: 1234,
    stdout: { on: () => {} },
    stderr: { on: () => {} },
    on: () => {},
    kill: () => {},
  };
  let healthCalls = 0;

  const ready = await ensurePythonApi(runtimePaths, {
    env: { KB_API_PORT: "18095", KB_PYTHON: "/custom/kb-python" },
    fetchImpl: async (url) => {
      healthCalls += 1;
      if (healthCalls === 1) {
        throw new Error(`not ready: ${url}`);
      }
      return { ok: true, status: 200 };
    },
    spawnImpl: (cmd, args, options) => {
      spawnCalls.push({ cmd, args, options });
      return fakeProcess;
    },
    sleep: async () => {},
  });

  assert.equal(ready, true);
  assert.equal(spawnCalls.length, 1);
  assert.equal(spawnCalls[0].cmd, "/custom/kb-python");
  assert.deepEqual(spawnCalls[0].args.map(normalizePath), ["/tmp/resources/run_api.py"]);
  assert.equal(normalizePath(spawnCalls[0].options.cwd), "/tmp/user-data/runtime");
  assert.equal(normalizePath(spawnCalls[0].options.env.KB_DATA_ROOT), "/tmp/user-data/runtime");
  assert.equal(normalizePath(spawnCalls[0].options.env.KB_MODEL_ROOT), "/tmp/resources/localmodels");
  assert.equal(normalizePath(spawnCalls[0].options.env.NORTHAGENT_DATA_ROOT), "/tmp/user-data/runtime");
  assert.equal(normalizePath(spawnCalls[0].options.env.NORTHAGENT_MODEL_ROOT), "/tmp/resources/localmodels");
  assert.equal(normalizePath(spawnCalls[0].options.env.THINKRAG_DATA_ROOT), "/tmp/user-data/runtime");
  assert.equal(normalizePath(spawnCalls[0].options.env.THINKRAG_MODEL_ROOT), "/tmp/resources/localmodels");
  assert.equal(normalizePath(spawnCalls[0].options.env.FOXGLOVE_DATA_ROOT), "/tmp/user-data/runtime");
  assert.equal(normalizePath(spawnCalls[0].options.env.FOXGLOVE_MODEL_ROOT), "/tmp/resources/localmodels");
  assert.equal(spawnCalls[0].options.env.KB_API_PORT, "18095");
  assert.equal(spawnCalls[0].options.env.PYTHONDONTWRITEBYTECODE, "1");
  assert.equal(spawnCalls[0].options.env.PYTHONIOENCODING, "utf-8");
  stopPythonApi(runtimePaths);
});
