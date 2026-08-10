const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  checkNotaryTool,
  ensureExecutable,
  findDeveloperIdApplicationIdentities,
  getMissingReleaseEnv,
} = require("./release-preflight");

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

test("getMissingReleaseEnv reports only absent notarization variables", () => {
  const result = getMissingReleaseEnv({
    APPLE_ID: "dev@example.com",
    APPLE_TEAM_ID: "TEAM12345",
  });

  assert.deepEqual(result, ["APPLE_APP_SPECIFIC_PASSWORD"]);
});

test("findDeveloperIdApplicationIdentities parses valid security output", () => {
  const fakeSpawn = () => ({
    status: 0,
    stdout: Buffer.from(
      [
        '  1) ABCDEF1234567890 "Developer ID Application: NorthAgent Inc. (TEAM12345)"',
        '  2) 1234567890ABCDEF "Apple Development: Dev User (TEAM12345)"',
        "     2 valid identities found",
      ].join("\n"),
    ),
    stderr: Buffer.from(""),
  });

  const result = findDeveloperIdApplicationIdentities(fakeSpawn);

  assert.equal(result.ok, true);
  assert.deepEqual(result.identities, ["Developer ID Application: NorthAgent Inc. (TEAM12345)"]);
});

test("findDeveloperIdApplicationIdentities reports missing Developer ID identity", () => {
  const fakeSpawn = () => ({
    status: 0,
    stdout: Buffer.from('  1) 1234567890ABCDEF "Apple Development: Dev User (TEAM12345)"\n'),
    stderr: Buffer.from(""),
  });

  const result = findDeveloperIdApplicationIdentities(fakeSpawn);

  assert.equal(result.ok, false);
  assert.deepEqual(result.identities, []);
});

test("checkNotaryTool accepts xcrun lookup output", () => {
  const fakeSpawn = () => ({
    status: 0,
    stdout: Buffer.from("/Applications/Xcode.app/Contents/Developer/usr/bin/notarytool\n"),
    stderr: Buffer.from(""),
  });

  const result = checkNotaryTool(fakeSpawn);

  assert.equal(result.ok, true);
  assert.match(result.path, /notarytool$/);
});

test("checkNotaryTool reports xcrun lookup failure", () => {
  const fakeSpawn = () => ({
    status: 1,
    stdout: Buffer.from(""),
    stderr: Buffer.from("xcrun: error: unable to find utility \"notarytool\""),
  });

  const result = checkNotaryTool(fakeSpawn);

  assert.equal(result.ok, false);
  assert.match(result.detail, /unable to find utility/);
});
