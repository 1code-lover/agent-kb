const assert = require("node:assert/strict");
const test = require("node:test");

const {
  DESKTOP_BRIDGE_KEYS,
  PICK_FILES_CHANNELS,
  exposeDesktopBridge,
  registerPickFilesHandlers,
} = require("./desktop-bridge-contract");

test("desktop bridge contract keeps KB-first aliases and ThinkRAG-before-Foxglove compatibility order", () => {
  assert.deepEqual(DESKTOP_BRIDGE_KEYS, ["kbDesktop", "northAgentDesktop", "thinkragDesktop", "foxgloveDesktop"]);
  assert.deepEqual(PICK_FILES_CHANNELS, ["kb:pick-files", "northagent:pick-files"]);
});

test("exposeDesktopBridge publishes the same bridge object under every compatibility alias", () => {
  const calls = [];
  const bridge = { runtime: "desktop" };

  exposeDesktopBridge(
    {
      exposeInMainWorld: (key, value) => {
        calls.push({ key, value });
      },
    },
    bridge,
  );

  assert.deepEqual(
    calls,
    DESKTOP_BRIDGE_KEYS.map((key) => ({ key, value: bridge })),
  );
});

test("registerPickFilesHandlers binds the same handler to KB and legacy IPC channels", () => {
  const calls = [];
  const handler = () => {};

  registerPickFilesHandlers(
    {
      handle: (channel, value) => {
        calls.push({ channel, value });
      },
    },
    handler,
  );

  assert.deepEqual(
    calls,
    PICK_FILES_CHANNELS.map((channel) => ({ channel, value: handler })),
  );
});
