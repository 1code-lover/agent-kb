const fs = require("node:fs");
const path = require("node:path");

const RUNTIME_ROOT_ENV_KEYS = ["KB_RUNTIME_ROOT", "NORTHAGENT_RUNTIME_ROOT", "THINKRAG_RUNTIME_ROOT", "FOXGLOVE_RUNTIME_ROOT"];

function firstNonEmptyValue(values) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return "";
}

function resolveRuntimeRoot({
  devProjectRoot,
  isPackaged,
  userDataPath,
  env = process.env,
}) {
  const explicitRuntimeRoot = firstNonEmptyValue(RUNTIME_ROOT_ENV_KEYS.map((key) => env?.[key]));
  if (explicitRuntimeRoot) {
    return explicitRuntimeRoot;
  }
  return isPackaged ? path.join(userDataPath, "runtime") : devProjectRoot;
}

function resolveRuntimePaths({
  devProjectRoot,
  isPackaged,
  resourcesPath,
  userDataPath,
  env = process.env,
}) {
  const resourceRoot = isPackaged ? resourcesPath : devProjectRoot;
  const runtimeRoot = resolveRuntimeRoot({ devProjectRoot, isPackaged, userDataPath, env });

  if (!resourceRoot || !runtimeRoot) {
    throw new Error("resourceRoot and runtimeRoot are required");
  }

  return {
    modelRoot: path.join(resourceRoot, "localmodels"),
    resourceRoot,
    runtimeRoot,
  };
}

function ensureRuntimeRoot(runtimeRoot, options = {}) {
  const fsModule = options.fs || fs;
  try {
    fsModule.mkdirSync(runtimeRoot, { recursive: true });
    fsModule.accessSync(runtimeRoot, fsModule.constants.W_OK);
  } catch (error) {
    throw new Error(`runtime directory is not writable: ${runtimeRoot}: ${error.message}`, {
      cause: error,
    });
  }
  return runtimeRoot;
}

module.exports = {
  RUNTIME_ROOT_ENV_KEYS,
  ensureRuntimeRoot,
  resolveRuntimePaths,
  resolveRuntimeRoot,
};
