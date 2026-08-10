/* eslint-disable no-console */
const path = require("node:path");
const { notarize } = require("@electron/notarize");

const requiredEnv = ["APPLE_ID", "APPLE_APP_SPECIFIC_PASSWORD", "APPLE_TEAM_ID"];

function getMissingNotarizeEnv(env = process.env) {
  return requiredEnv.filter((name) => !env[name]);
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

async function notarizeMac(context, options = {}) {
  const env = options.env || process.env;
  const platform = options.platform || process.platform;
  const notarizeFn = options.notarizeFn || notarize;
  const logger = options.logger || console;

  if (platform !== "darwin" || context?.electronPlatformName !== "darwin") {
    logger.log("[notarize] skipped: not a macOS build");
    return { skipped: true, reason: "not_macos" };
  }

  const missing = getMissingNotarizeEnv(env);
  if (missing.length > 0) {
    const message = `missing notarization env: ${missing.join(", ")}`;
    if (shouldRequireNotarize(env)) {
      throw new Error(message);
    }
    logger.log(`[notarize] skipped: ${message}`);
    return { skipped: true, reason: "missing_env", missing };
  }

  const appPath = resolveAppPath(context);
  if (!appPath) {
    throw new Error("unable to resolve .app path for notarization");
  }

  const appBundleId = context.packager.appInfo.appId;
  logger.log(`[notarize] submitting ${appPath}`);
  await notarizeFn({
    appBundleId,
    appPath,
    appleId: env.APPLE_ID,
    appleIdPassword: env.APPLE_APP_SPECIFIC_PASSWORD,
    teamId: env.APPLE_TEAM_ID,
  });
  logger.log("[notarize] completed");
  return { skipped: false, appPath, appBundleId };
}

module.exports = notarizeMac;
module.exports.getMissingNotarizeEnv = getMissingNotarizeEnv;
module.exports.resolveAppPath = resolveAppPath;
module.exports.shouldRequireNotarize = shouldRequireNotarize;
