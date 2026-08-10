const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { ensureExecutable } = require("./release-preflight");

test("ensureExecutable repairs a non-executable file", () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "release-preflight-"));
  const target = path.join(tmpDir, "binary");
  fs.writeFileSync(target, "data");
  fs.chmodSync(target, 0o644);

  const result = ensureExecutable(target, () => {});

  assert.equal(result.ok, true);
  assert.equal(result.repaired, true);
  const mode = fs.statSync(target).mode & 0o777;
  assert.equal(mode & 0o111, 0o111);
});

test("ensureExecutable reports missing files", () => {
  const result = ensureExecutable(path.join(os.tmpdir(), "missing-binary"), () => {});

  assert.deepEqual(result, { ok: false, reason: "missing" });
});
