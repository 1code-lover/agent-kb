/*
 * macOS 公证凭证解析器。
 * 只把凭证值放入提交 payload；诊断信息仅包含策略名和环境变量名。
 */

const credentialStrategies = [
  {
    strategy: "keychain_profile",
    required: ["APPLE_KEYCHAIN_PROFILE"],
    optional: ["APPLE_KEYCHAIN"],
    buildCredentials(env) {
      const credentials = { keychainProfile: env.APPLE_KEYCHAIN_PROFILE };
      if (isConfigured(env.APPLE_KEYCHAIN)) {
        credentials.keychain = env.APPLE_KEYCHAIN;
      }
      return credentials;
    },
  },
  {
    strategy: "api_key",
    required: ["APPLE_API_KEY", "APPLE_API_KEY_ID", "APPLE_API_ISSUER"],
    optional: [],
    buildCredentials(env) {
      return {
        appleApiKey: env.APPLE_API_KEY,
        appleApiKeyId: env.APPLE_API_KEY_ID,
        appleApiIssuer: env.APPLE_API_ISSUER,
      };
    },
  },
  {
    strategy: "apple_id",
    required: ["APPLE_ID", "APPLE_APP_SPECIFIC_PASSWORD", "APPLE_TEAM_ID"],
    optional: [],
    buildCredentials(env) {
      return {
        appleId: env.APPLE_ID,
        appleIdPassword: env.APPLE_APP_SPECIFIC_PASSWORD,
        teamId: env.APPLE_TEAM_ID,
      };
    },
  },
];

/** 判断环境变量是否包含可用值。 */
function isConfigured(value) {
  return typeof value === "string" ? value.trim().length > 0 : Boolean(value);
}

/**
 * 按 Keychain、API Key、Apple ID 的顺序选择第一组完整凭证。
 * 部分配置会被保留为无秘密诊断，但不会阻止后续完整策略。
 */
function resolveNotarizationCredentials(env = process.env) {
  const states = credentialStrategies.map((definition) => {
    const missing = definition.required.filter((name) => !isConfigured(env[name]));
    const configuredNames = [...definition.required, ...definition.optional].filter((name) => isConfigured(env[name]));
    return {
      definition,
      complete: missing.length === 0,
      partial: configuredNames.length > 0 && missing.length > 0,
      missing,
    };
  });
  const selected = states.find((state) => state.complete) || null;
  const partial = states
    .filter((state) => state.partial)
    .map((state) => ({ strategy: state.definition.strategy, missing: state.missing }));

  return {
    strategy: selected ? selected.definition.strategy : null,
    credentials: selected ? selected.definition.buildCredentials(env) : null,
    partial,
    missing: selected
      ? []
      : states.map((state) => ({ strategy: state.definition.strategy, missing: state.missing })),
  };
}

/** 生成可安全写入日志的凭证诊断，不包含任何凭证值。 */
function formatNotarizationCredentialDiagnostics(resolution) {
  const messages = [];
  for (const item of resolution.partial || []) {
    messages.push(`partial notarization strategy ${item.strategy}; missing: ${item.missing.join(", ")}`);
  }
  if (resolution.strategy) {
    messages.push(`notarization credential strategy ready: ${resolution.strategy}`);
    return messages;
  }
  for (const item of resolution.missing || []) {
    if ((resolution.partial || []).some((partial) => partial.strategy === item.strategy)) {
      continue;
    }
    messages.push(`notarization strategy ${item.strategy} missing: ${item.missing.join(", ")}`);
  }
  return messages;
}

module.exports = {
  credentialStrategies,
  formatNotarizationCredentialDiagnostics,
  resolveNotarizationCredentials,
};
