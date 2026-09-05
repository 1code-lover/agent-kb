const HEADLESS_ENV_KEYS = [
  "KB_DESKTOP_HEADLESS",
  "NORTHAGENT_DESKTOP_HEADLESS",
  "THINKRAG_DESKTOP_HEADLESS",
  "FOXGLOVE_DESKTOP_HEADLESS",
];

function firstNonEmptyValue(values) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return "";
}

function resolveDesktopHeadless(env = process.env) {
  const rawValue = firstNonEmptyValue(HEADLESS_ENV_KEYS.map((key) => env?.[key]));
  return /^(1|true|yes|on)$/i.test(rawValue);
}

module.exports = {
  HEADLESS_ENV_KEYS,
  resolveDesktopHeadless,
};
