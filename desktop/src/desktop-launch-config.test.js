const assert = require("node:assert/strict");
const test = require("node:test");

const { HEADLESS_ENV_KEYS, resolveDesktopHeadless } = require("./desktop-launch-config");

test("desktop launch config prefers KB headless flag before legacy aliases", () => {
  assert.deepEqual(HEADLESS_ENV_KEYS, [
    "KB_DESKTOP_HEADLESS",
    "NORTHAGENT_DESKTOP_HEADLESS",
    "THINKRAG_DESKTOP_HEADLESS",
    "FOXGLOVE_DESKTOP_HEADLESS",
  ]);
});

test("resolveDesktopHeadless accepts KB headless flag truthy values", () => {
  assert.equal(resolveDesktopHeadless({ KB_DESKTOP_HEADLESS: "1" }), true);
  assert.equal(resolveDesktopHeadless({ KB_DESKTOP_HEADLESS: "true" }), true);
  assert.equal(resolveDesktopHeadless({ KB_DESKTOP_HEADLESS: " yes " }), true);
});

test("resolveDesktopHeadless keeps legacy aliases for compatibility", () => {
  assert.equal(resolveDesktopHeadless({ FOXGLOVE_DESKTOP_HEADLESS: "on" }), true);
  assert.equal(resolveDesktopHeadless({ NORTHAGENT_DESKTOP_HEADLESS: "0" }), false);
  assert.equal(resolveDesktopHeadless({}), false);
});
