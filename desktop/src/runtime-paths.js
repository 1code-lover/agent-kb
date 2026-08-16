const fs = require("node:fs");
const path = require("node:path");

function resolveRuntimePaths({
  devProjectRoot,
  isPackaged,
  resourcesPath,
  userDataPath,
}) {
  const resourceRoot = isPackaged ? resourcesPath : devProjectRoot;
  const runtimeRoot = isPackaged ? path.join(userDataPath, "runtime") : devProjectRoot;

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
  ensureRuntimeRoot,
  resolveRuntimePaths,
};
