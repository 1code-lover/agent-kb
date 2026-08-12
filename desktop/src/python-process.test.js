const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");

const { ensurePythonApi, resolvePythonCommand } = require("./python-process");

test("resolvePythonCommand respects explicit desktop python override", () => {
  const previous = process.env.NORTHAGENT_PYTHON;
  process.env.NORTHAGENT_PYTHON = "/custom/python";

  try {
    assert.equal(resolvePythonCommand(process.cwd()), "/custom/python");
  } finally {
    if (previous === undefined) {
      delete process.env.NORTHAGENT_PYTHON;
    } else {
      process.env.NORTHAGENT_PYTHON = previous;
    }
  }
});

test("resolvePythonCommand prefers macOS agent-kb conda runtime when available", () => {
  const previous = process.env.NORTHAGENT_PYTHON;
  delete process.env.NORTHAGENT_PYTHON;

  try {
    const condaPython = "/opt/miniconda3/envs/agent-kb/bin/python";
    if (process.platform !== "win32" && fs.existsSync(condaPython)) {
      assert.equal(resolvePythonCommand(process.cwd()), condaPython);
    }
  } finally {
    if (previous !== undefined) {
      process.env.NORTHAGENT_PYTHON = previous;
    }
  }
});

test("ensurePythonApi reuses an already running API without spawning", async () => {
  const spawnCalls = [];
  const ready = await ensurePythonApi("/tmp/project", {
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

test("ensurePythonApi starts Python API when health check is not ready", async () => {
  const spawnCalls = [];
  const fakeProcess = {
    pid: 1234,
    stdout: { on: () => {} },
    stderr: { on: () => {} },
    on: () => {},
    kill: () => {},
  };
  let healthCalls = 0;

  const ready = await ensurePythonApi("/tmp/project", {
    fetchImpl: async () => {
      healthCalls += 1;
      if (healthCalls === 1) {
        throw new Error("not ready");
      }
      return { ok: true, status: 200 };
    },
    spawnImpl: (cmd, args) => {
      spawnCalls.push({ cmd, args });
      return fakeProcess;
    },
    sleep: async () => {},
  });

  assert.equal(ready, true);
  assert.equal(spawnCalls.length, 1);
  assert.deepEqual(spawnCalls[0].args, ["/tmp/project/run_api.py"]);
});
