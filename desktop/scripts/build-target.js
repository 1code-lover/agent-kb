/* eslint-disable no-console */
const { platform } = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const currentPlatform = platform();
const target = currentPlatform === "darwin" ? "--mac" : "--win";

if (currentPlatform === "darwin") {
  const preflight = spawnSync("node", [path.join(__dirname, "release-preflight.js")], {
    stdio: "inherit"
  });
  if (preflight.status !== 0) {
    process.exit(preflight.status || 1);
  }
}

const result = spawnSync("node", [path.join(__dirname, "..", "node_modules", "electron-builder", "cli.js"), target], {
  stdio: "inherit"
});

if (result.status !== 0) {
  process.exit(result.status || 1);
}
