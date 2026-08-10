const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");

const { resolvePythonCommand } = require("./python-process");

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
