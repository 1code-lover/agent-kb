const path = require("node:path");

const PYTHON_OVERRIDE_KEYS = ["KB_PYTHON", "NORTHAGENT_PYTHON", "THINKRAG_PYTHON", "FOXGLOVE_PYTHON"];

function normalizeCandidate(value) {
  if (typeof value !== "string") {
    return "";
  }
  return value.trim();
}

function pushCandidate(candidates, value) {
  const candidate = normalizeCandidate(value);
  if (candidate && !candidates.includes(candidate)) {
    candidates.push(candidate);
  }
}

function pathForPlatform(platform = process.platform) {
  return platform === "win32" ? path.win32 : path.posix;
}

function resolveExplicitPythonCommand(env = process.env) {
  for (const key of PYTHON_OVERRIDE_KEYS) {
    const command = normalizeCandidate(env?.[key]);
    if (command) {
      return {
        command,
        overrideKey: key,
      };
    }
  }
  return {
    command: "",
    overrideKey: null,
  };
}

function defaultPythonCandidates(root, options = {}) {
  const env = options.env || process.env;
  const platform = options.platform || process.platform;
  const pathImpl = pathForPlatform(platform);
  const candidates = [];
  const condaPrefix = normalizeCandidate(env?.CONDA_PREFIX);
  const virtualEnv = normalizeCandidate(env?.VIRTUAL_ENV);
  const projectRoot = normalizeCandidate(root);

  if (platform === "win32") {
    pushCandidate(candidates, condaPrefix && pathImpl.join(condaPrefix, "python.exe"));
    pushCandidate(candidates, virtualEnv && pathImpl.join(virtualEnv, "Scripts", "python.exe"));
    pushCandidate(candidates, projectRoot && pathImpl.join(projectRoot, ".venv", "Scripts", "python.exe"));
    pushCandidate(candidates, projectRoot && pathImpl.join(projectRoot, "venv", "Scripts", "python.exe"));
    pushCandidate(candidates, "python");
    pushCandidate(candidates, "py");
    return candidates;
  }

  pushCandidate(candidates, condaPrefix && pathImpl.join(condaPrefix, "bin", "python"));
  pushCandidate(candidates, virtualEnv && pathImpl.join(virtualEnv, "bin", "python"));
  pushCandidate(candidates, projectRoot && pathImpl.join(projectRoot, ".venv", "bin", "python"));
  pushCandidate(candidates, projectRoot && pathImpl.join(projectRoot, "venv", "bin", "python"));
  pushCandidate(candidates, "python3");
  pushCandidate(candidates, "python");
  return candidates;
}

module.exports = {
  PYTHON_OVERRIDE_KEYS,
  defaultPythonCandidates,
  resolveExplicitPythonCommand,
};
