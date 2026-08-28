import test from "node:test";
import assert from "node:assert/strict";

import { DESKTOP_BRIDGE_KEYS, getDesktopBridge } from "./desktopBridge.js";

test("getDesktopBridge prefers kbDesktop before legacy aliases", () => {
  const bridge = { apiBaseUrl: "http://127.0.0.1:18080" };
  const legacyBridge = { apiBaseUrl: "http://127.0.0.1:18081" };
  const target = {
    kbDesktop: bridge,
    northAgentDesktop: legacyBridge,
  };

  assert.equal(getDesktopBridge(target), bridge);
  assert.deepEqual(DESKTOP_BRIDGE_KEYS, [
    "kbDesktop",
    "northAgentDesktop",
    "thinkragDesktop",
    "foxgloveDesktop",
  ]);
});

test("getDesktopBridge prefers ThinkRAG alias over Foxglove to match runtime contract order", () => {
  const thinkragBridge = { runtime: "thinkrag" };
  const foxgloveBridge = { runtime: "foxglove" };

  assert.equal(
    getDesktopBridge({ thinkragDesktop: thinkragBridge, foxgloveDesktop: foxgloveBridge }),
    thinkragBridge,
  );
});

test("getDesktopBridge falls back to legacy aliases when KB bridge is absent", () => {
  const bridge = { pickFiles: () => null };
  assert.equal(getDesktopBridge({ thinkragDesktop: bridge }), bridge);
  assert.equal(getDesktopBridge(null), null);
});
