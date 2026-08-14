/* eslint-disable no-console */
const path = require("node:path");
const { notarize } = require("@electron/notarize");
const {
  formatNotarizationCredentialDiagnostics,
  resolveNotarizationCredentials,
} = require("./notarization-credentials");

function getMissingNotarizeEnv(env = process.env) {
  return resolveNotarizationCredentials(env).missing;
}

function shouldRequireNotarize(env = process.env) {
  return env.NORTHAGENT_REQUIRE_NOTARIZE === "1" || env.NORTHAGENT_REQUIRE_NOTARIZE === "true";
}

function resolveAppPath(context) {
  const appOutDir = context?.appOutDir;
  const productFilename = context?.packager?.appInfo?.productFilename;
  if (!appOutDir || !productFilename) {
    return "";
  }
  return path.join(appOutDir, `${productFilename}.app`);
}

/** 使用共享策略选择器提交一次 macOS 公证。 */
async function notarizeMac(context, options = {}) {
  const env = options.env || process.env;
  const platform = options.platform || process.platform;
  const notarizeFn = options.notarizeFn || notarize;
  const logger = options.logger || console;

  if (platform !== "darwin" || context?.electronPlatformName !== "darwin") {
    logger.log("[notarize] skipped: not a macOS build");
    return { skipped: true, reason: "not_macos" };
  }

  const resolution = resolveNotarizationCredentials(env);
  const diagnostics = formatNotarizationCredentialDiagnostics(resolution);
  for (const diagnostic of diagnostics) {
    logger.log(`[notarize] ${diagnostic}`);
  }
  if (!resolution.strategy) {
    const message = `missing notarization env: ${diagnostics.join("; ")}`;
    if (shouldRequireNotarize(env)) {
      throw new Error(message);
    }
    logger.log(`[notarize] skipped: ${message}`);
    return { skipped: true, reason: "missing_env", missing: resolution.missing, partial: resolution.partial };
  }

  const appPath = resolveAppPath(context);
  if (!appPath) {
    throw new Error("unable to resolve .app path for notarization");
  }

  const appBundleId = context.packager.appInfo.appId;
  logger.log(`[notarize] submitting ${appPath} with strategy ${resolution.strategy}`);
  await notarizeFn({
    appBundleId,
    appPath,
    ...resolution.credentials,
  });
  logger.log(`[notarize] completed with strategy ${resolution.strategy}`);
  return { skipped: false, appPath, appBundleId, strategy: resolution.strategy };
}

module.exports = notarizeMac;
module.exports.getMissingNotarizeEnv = getMissingNotarizeEnv;
module.exports.resolveAppPath = resolveAppPath;
module.exports.shouldRequireNotarize = shouldRequireNotarize;
