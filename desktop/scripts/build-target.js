/* eslint-disable no-console */
const { platform } = require("node:os");
const { spawnSync } = require("node:child_process");

const currentPlatform = platform();
const target = currentPlatform === "darwin" ? "--mac" : "--win";

const result = spawnSync("npx", ["electron-builder", target], {
  stdio: "inherit",
  shell: true
});

if (result.status !== 0) {
  process.exit(result.status || 1);
}
