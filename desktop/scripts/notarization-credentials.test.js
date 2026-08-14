const assert = require("node:assert/strict");
const test = require("node:test");

const {
  formatNotarizationCredentialDiagnostics,
  resolveNotarizationCredentials,
} = require("./notarization-credentials");

test("resolveNotarizationCredentials selects a complete Keychain profile", () => {
  const result = resolveNotarizationCredentials({
    APPLE_KEYCHAIN_PROFILE: "northagent-notary",
  });

  assert.equal(result.strategy, "keychain_profile");
  assert.deepEqual(result.credentials, { keychainProfile: "northagent-notary" });
  assert.deepEqual(result.partial, []);
  assert.deepEqual(result.missing, []);
});

test("resolveNotarizationCredentials passes the optional Keychain path", () => {
  const result = resolveNotarizationCredentials({
    APPLE_KEYCHAIN_PROFILE: "northagent-notary",
    APPLE_KEYCHAIN: "/Users/release/Library/Keychains/release.keychain-db",
  });

  assert.deepEqual(result.credentials, {
    keychainProfile: "northagent-notary",
    keychain: "/Users/release/Library/Keychains/release.keychain-db",
  });
});

test("resolveNotarizationCredentials selects complete App Store Connect API credentials", () => {
  const result = resolveNotarizationCredentials({
    APPLE_API_KEY: "/secure/AuthKey_TEST123.p8",
    APPLE_API_KEY_ID: "TEST123",
    APPLE_API_ISSUER: "issuer-uuid",
  });

  assert.equal(result.strategy, "api_key");
  assert.deepEqual(result.credentials, {
    appleApiKey: "/secure/AuthKey_TEST123.p8",
    appleApiKeyId: "TEST123",
    appleApiIssuer: "issuer-uuid",
  });
  assert.deepEqual(result.partial, []);
  assert.deepEqual(result.missing, []);
});

test("resolveNotarizationCredentials selects complete Apple ID credentials", () => {
  const result = resolveNotarizationCredentials({
    APPLE_ID: "release@example.com",
    APPLE_APP_SPECIFIC_PASSWORD: "app-password",
    APPLE_TEAM_ID: "TEAM123456",
  });

  assert.equal(result.strategy, "apple_id");
  assert.deepEqual(result.credentials, {
    appleId: "release@example.com",
    appleIdPassword: "app-password",
    teamId: "TEAM123456",
  });
  assert.deepEqual(result.partial, []);
  assert.deepEqual(result.missing, []);
});

test("resolveNotarizationCredentials reports every strategy when none is configured", () => {
  const result = resolveNotarizationCredentials({});

  assert.equal(result.strategy, null);
  assert.equal(result.credentials, null);
  assert.deepEqual(result.partial, []);
  assert.deepEqual(result.missing, [
    { strategy: "keychain_profile", missing: ["APPLE_KEYCHAIN_PROFILE"] },
    {
      strategy: "api_key",
      missing: ["APPLE_API_KEY", "APPLE_API_KEY_ID", "APPLE_API_ISSUER"],
    },
    {
      strategy: "apple_id",
      missing: ["APPLE_ID", "APPLE_APP_SPECIFIC_PASSWORD", "APPLE_TEAM_ID"],
    },
  ]);
});

test("resolveNotarizationCredentials records partial strategies and missing fields", () => {
  const result = resolveNotarizationCredentials({
    APPLE_API_KEY: "/secure/AuthKey_TEST123.p8",
    APPLE_API_KEY_ID: "TEST123",
    APPLE_ID: "release@example.com",
  });

  assert.equal(result.strategy, null);
  assert.deepEqual(result.partial, [
    { strategy: "api_key", missing: ["APPLE_API_ISSUER"] },
    {
      strategy: "apple_id",
      missing: ["APPLE_APP_SPECIFIC_PASSWORD", "APPLE_TEAM_ID"],
    },
  ]);
  assert.deepEqual(result.missing[1], { strategy: "api_key", missing: ["APPLE_API_ISSUER"] });
  assert.deepEqual(result.missing[2], {
    strategy: "apple_id",
    missing: ["APPLE_APP_SPECIFIC_PASSWORD", "APPLE_TEAM_ID"],
  });
});

test("resolveNotarizationCredentials follows Keychain then API key then Apple ID priority", () => {
  const env = {
    APPLE_KEYCHAIN_PROFILE: "northagent-notary",
    APPLE_API_KEY: "/secure/AuthKey_TEST123.p8",
    APPLE_API_KEY_ID: "TEST123",
    APPLE_API_ISSUER: "issuer-uuid",
    APPLE_ID: "release@example.com",
    APPLE_APP_SPECIFIC_PASSWORD: "app-password",
    APPLE_TEAM_ID: "TEAM123456",
  };

  assert.equal(resolveNotarizationCredentials(env).strategy, "keychain_profile");
  delete env.APPLE_KEYCHAIN_PROFILE;
  assert.equal(resolveNotarizationCredentials(env).strategy, "api_key");
  delete env.APPLE_API_ISSUER;
  assert.equal(resolveNotarizationCredentials(env).strategy, "apple_id");
});

test("a partial higher-priority strategy does not block a complete lower-priority strategy", () => {
  const result = resolveNotarizationCredentials({
    APPLE_API_KEY: "/secure/AuthKey_TEST123.p8",
    APPLE_ID: "release@example.com",
    APPLE_APP_SPECIFIC_PASSWORD: "app-password",
    APPLE_TEAM_ID: "TEAM123456",
  });

  assert.equal(result.strategy, "apple_id");
  assert.deepEqual(result.partial, [
    { strategy: "api_key", missing: ["APPLE_API_KEY_ID", "APPLE_API_ISSUER"] },
  ]);
  assert.deepEqual(result.missing, []);
});

test("credential diagnostics contain strategy names and missing fields but not secret values", () => {
  const env = {
    APPLE_API_KEY: "/secure/SECRET-PRIVATE-KEY.p8",
    APPLE_ID: "secret-release@example.com",
  };
  const result = resolveNotarizationCredentials(env);
  const diagnostics = formatNotarizationCredentialDiagnostics(result).join("\n");

  assert.match(diagnostics, /api_key/);
  assert.match(diagnostics, /APPLE_API_KEY_ID/);
  assert.match(diagnostics, /apple_id/);
  assert.match(diagnostics, /APPLE_APP_SPECIFIC_PASSWORD/);
  assert.doesNotMatch(diagnostics, /SECRET-PRIVATE-KEY/);
  assert.doesNotMatch(diagnostics, /secret-release@example\.com/);
});

test("a partial Keychain configuration does not block complete API credentials", () => {
  const result = resolveNotarizationCredentials({
    APPLE_KEYCHAIN: "/Users/release/Library/Keychains/release.keychain-db",
    APPLE_API_KEY: "/secure/AuthKey_TEST123.p8",
    APPLE_API_KEY_ID: "TEST123",
    APPLE_API_ISSUER: "issuer-uuid",
  });

  assert.equal(result.strategy, "api_key");
  assert.deepEqual(result.partial, [
    { strategy: "keychain_profile", missing: ["APPLE_KEYCHAIN_PROFILE"] },
  ]);
  assert.deepEqual(result.missing, []);
});
