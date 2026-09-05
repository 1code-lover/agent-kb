const assert = require("node:assert/strict");
const test = require("node:test");

const {
  REQUIRED_MODULES,
  LOCKED_PACKAGES,
  PYTHON_OVERRIDE_KEYS,
  defaultPythonCandidates,
  runVerifier,
} = require("./verify-python-runtime");

function probe(overrides = {}) {
  return {
    implementation: "CPython",
    version: "3.12.13",
    missingModules: [],
    packageVersions: {
      "llama-index-core": "0.11.19",
      "httpx": "0.27.2",
    },
    ...overrides,
  };
}

function fakeSpawn({ probeResult = probe(), probeStatus = 0, probeStderr = "", pipStatus = 0, pipStderr = "" } = {}) {
  const calls = [];
  const spawn = (command, args) => {
    calls.push({ command, args });
    if (args.includes("pip") && args.includes("check")) {
      return { status: pipStatus, stdout: "", stderr: pipStderr };
    }
    return {
      status: probeStatus,
      stdout: JSON.stringify(probeResult),
      stderr: probeStderr,
    };
  };
  return { calls, spawn };
}

test("runVerifier accepts an explicit CPython 3.12 with required modules and clean pip check", () => {
  const { calls, spawn } = fakeSpawn();

  const result = runVerifier({
    env: { KB_PYTHON: "/custom/python" },
    platform: "darwin",
    spawn,
  });

  assert.equal(result.ok, true);
  assert.equal(result.pythonCommand, "/custom/python");
  assert.equal(result.explicit, true);
  assert.equal(result.implementation, "CPython");
  assert.equal(result.version, "3.12.13");
  assert.deepEqual(result.missingModules, []);
  assert.deepEqual(result.packageVersions, {
    "llama-index-core": "0.11.19",
    "httpx": "0.27.2",
  });
  assert.equal(result.pipCheck, "passed");
  assert.equal(calls.length, 2);
  assert.deepEqual(calls[0].args.slice(0, 2), ["-c", calls[0].args[1]]);
  assert.deepEqual(calls[1].args, ["-m", "pip", "check"]);
  assert.deepEqual(result.failures, []);
});

test("defaultPythonCandidates prefer active conda and virtualenv interpreters before project fallbacks", () => {
  const candidates = defaultPythonCandidates("darwin", "/workspace/project", {
    CONDA_PREFIX: "/opt/conda/envs/agent-kb",
    VIRTUAL_ENV: "/tmp/venv",
  });

  assert.deepEqual(candidates, [
    "/opt/conda/envs/agent-kb/bin/python",
    "/tmp/venv/bin/python",
    "/workspace/project/.venv/bin/python",
    "/workspace/project/venv/bin/python",
    "python3",
    "python",
  ]);
});

test("runVerifier follows the KB-first desktop Python override precedence", () => {
  const { spawn } = fakeSpawn();

  const result = runVerifier({
    env: {
      FOXGLOVE_PYTHON: "/foxglove/python",
      THINKRAG_PYTHON: "/thinkrag/python",
      NORTHAGENT_PYTHON: "/northagent/python",
      KB_PYTHON: "/kb/python",
    },
    spawn,
  });

  assert.equal(result.ok, true);
  assert.equal(result.pythonCommand, "/kb/python");
  assert.equal(result.attempts.length, 1);
  assert.deepEqual(PYTHON_OVERRIDE_KEYS, ["KB_PYTHON", "NORTHAGENT_PYTHON", "THINKRAG_PYTHON", "FOXGLOVE_PYTHON"]);
});

test("runVerifier rejects a non-3.12 interpreter before the pip gate", () => {
  const { calls, spawn } = fakeSpawn({ probeResult: probe({ version: "3.11.9" }) });

  const result = runVerifier({
    env: { KB_PYTHON: "/custom/python" },
    spawn,
  });

  assert.equal(result.ok, false);
  assert.equal(result.version, "3.11.9");
  assert.equal(result.pipCheck, "not_run");
  assert.equal(calls.length, 1);
  assert.match(result.failures.join("\n"), /3\.12/);
});

test("runVerifier reports missing core modules", () => {
  const missingModules = ["fastapi", "llama_index", "sentence_transformers"];
  const { spawn } = fakeSpawn({ probeResult: probe({ missingModules }) });

  const result = runVerifier({ env: { KB_PYTHON: "/custom/python" }, spawn });

  assert.equal(result.ok, false);
  assert.deepEqual(result.missingModules, missingModules);
  assert.match(result.failures.join("\n"), /fastapi/);
  assert.match(result.failures.join("\n"), /sentence_transformers/);
});

test("runVerifier rejects llama-index-core lock version drift", () => {
  const { spawn } = fakeSpawn({
    probeResult: probe({
      packageVersions: {
        "llama-index-core": "0.11.20",
        "httpx": "0.27.2",
      },
    }),
  });

  const result = runVerifier({ env: { KB_PYTHON: "/custom/python" }, spawn });

  assert.equal(result.ok, false);
  assert.equal(result.packageVersions["llama-index-core"], "0.11.20");
  assert.match(result.failures.join("\n"), /llama-index/);
  assert.match(result.failures.join("\n"), /0\.11\.19/);
});

test("runVerifier reports pip check failures", () => {
  const { spawn } = fakeSpawn({
    pipStatus: 1,
    pipStderr: "fastapi 0.115.0 has requirement starlette<0.39.0, but you have starlette 0.40.0",
  });

  const result = runVerifier({ env: { KB_PYTHON: "/custom/python" }, spawn });

  assert.equal(result.ok, false);
  assert.match(result.pipCheck, /starlette/);
  assert.match(result.failures.join("\n"), /pip check/);
});

test("runVerifier falls back across default candidates", () => {
  const calls = [];
  const spawn = (command, args) => {
    calls.push({ command, args });
    const python = command;
    if (args.includes("pip") && args.includes("check")) {
      return { status: 0, stdout: "", stderr: "" };
    }
    if (python === "/first/python") {
      return { status: 0, stdout: JSON.stringify(probe({ version: "3.11.9" })), stderr: "" };
    }
    return { status: 0, stdout: JSON.stringify(probe()), stderr: "" };
  };

  const result = runVerifier({
    env: {},
    candidates: ["/first/python", "/second/python"],
    spawn,
  });

  assert.equal(result.ok, true);
  assert.equal(result.pythonCommand, "/second/python");
  assert.equal(result.explicit, false);
  assert.equal(result.attempts.length, 2);
  assert.equal(result.attempts[0].ok, false);
  assert.equal(result.attempts[1].ok, true);
});

test("runVerifier fails closed for an explicit interpreter and does not fall back", () => {
  const { calls, spawn } = fakeSpawn({ probeStatus: 1, probeStderr: "No such file or directory" });

  const result = runVerifier({
    env: { KB_PYTHON: "/missing/python" },
    candidates: ["/other/python"],
    spawn,
  });

  assert.equal(result.ok, false);
  assert.equal(result.pythonCommand, "/missing/python");
  assert.equal(result.explicit, true);
  assert.equal(result.attempts.length, 1);
  assert.equal(calls.length, 1);
  assert.match(result.failures.join("\n"), /No such file/);
});

test("runVerifier reports a missing command as a structured failure", () => {
  const result = runVerifier({
    env: { KB_PYTHON: "/missing/python" },
    spawn: () => ({ status: null, error: new Error("spawn ENOENT") }),
  });

  assert.equal(result.ok, false);
  assert.equal(result.pipCheck, "not_run");
  assert.match(result.failures.join("\n"), /ENOENT/);
});

test("runVerifier rejects invalid JSON probe output", () => {
  const result = runVerifier({
    env: { KB_PYTHON: "/custom/python" },
    spawn: () => ({ status: 0, stdout: "not-json", stderr: "" }),
  });

  assert.equal(result.ok, false);
  assert.match(result.failures.join("\n"), /JSON/);
});

test("diagnostics collapse newlines and truncate at 500 characters", () => {
  const longMessage = `${"x".repeat(300)}\n${"y".repeat(300)}`;
  const { spawn } = fakeSpawn({ pipStatus: 1, pipStderr: longMessage });

  const result = runVerifier({ env: { KB_PYTHON: "/custom/python" }, spawn });
  const diagnostic = result.failures.find((failure) => failure.includes("pip check"));

  assert.ok(diagnostic);
  assert.ok(diagnostic.length <= 500);
  assert.equal(diagnostic.includes("\n"), false);
});

test("external diagnostics redact secret-like environment values", () => {
  const secret = "super-secret-runtime-token";
  const { spawn } = fakeSpawn({
    pipStatus: 1,
    pipStderr: `private index rejected token ${secret}`,
  });

  const result = runVerifier({
    env: {
      KB_PYTHON: "/custom/python",
      PRIVATE_API_TOKEN: secret,
    },
    spawn,
  });
  const serialized = JSON.stringify(result);

  assert.equal(serialized.includes(secret), false);
  assert.equal(serialized.includes("[REDACTED]"), true);
});

test("runtime verifier constants cover the required module and package contracts", () => {
  assert.deepEqual(REQUIRED_MODULES, [
    "fastapi",
    "uvicorn",
    "llama_index",
    "sentence_transformers",
    "httpx",
  ]);
  assert.deepEqual(LOCKED_PACKAGES, {
    "llama-index-core": "0.11.19",
    "httpx": "0.27.2",
  });
});
