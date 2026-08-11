/* eslint-disable no-console */
const fs = require("node:fs");
const path = require("node:path");
const asar = require("@electron/asar");

const desktopRoot = path.resolve(__dirname, "..");
const requiredRuntimeFiles = [
  "webapp/dist/index.html",
  "run_api.py",
  "config.py",
  "requirements.txt",
  "api/app.py",
  "server/index.py",
  "utils/logging_utils.py",
];

function loadPackageJson(packagePath = path.join(desktopRoot, "package.json"), fsModule = fs) {
  return JSON.parse(fsModule.readFileSync(packagePath, "utf8"));
}

function resolvePackageLayout(options = {}) {
  const root = options.desktopRoot || desktopRoot;
  const pkg = options.packageJson || loadPackageJson(path.join(root, "package.json"), options.fs || fs);
  const productName = options.productName || pkg?.build?.productName || pkg?.name || "NorthAgent";
  const version = options.version || pkg?.version || "0.1.0";
  const arch = options.arch || process.arch;
  const distDir = options.distDir || path.join(root, "dist");
  const resourcesRoot =
    options.resourcesRoot || path.join(distDir, `mac-${arch}`, `${productName}.app`, "Contents", "Resources");

  return {
    arch,
    asarPath: options.asarPath || path.join(resourcesRoot, "app.asar"),
    artifactPaths: options.artifactPaths || [
      path.join(root, "dist", `${productName}-${version}-${arch}.dmg`),
      path.join(root, "dist", `${productName}-${version}-${arch}-mac.zip`),
    ],
    productName,
    resourcesRoot,
    version,
  };
}

function verifyPackage(options = {}) {
  const fsModule = options.fs || fs;
  const asarModule = options.asar || asar;
  const runtimeFiles = options.requiredRuntimeFiles || requiredRuntimeFiles;
  const layout = resolvePackageLayout({ ...options, fs: fsModule });
  const failures = [];

  for (const artifactPath of layout.artifactPaths) {
    if (!fsModule.existsSync(artifactPath)) {
      failures.push(`missing artifact: ${artifactPath}`);
    }
  }

  for (const relativePath of runtimeFiles) {
    const target = path.join(layout.resourcesRoot, relativePath);
    if (!fsModule.existsSync(target)) {
      failures.push(`missing runtime file: ${target}`);
    }
  }

  if (!fsModule.existsSync(layout.asarPath)) {
    failures.push(`missing app.asar: ${layout.asarPath}`);
  } else {
    const asarEntries = asarModule.listPackage(layout.asarPath);
    const testEntries = asarEntries.filter((entry) => /\.test\.js$/.test(entry));
    if (testEntries.length > 0) {
      failures.push(`test files should not be packaged: ${testEntries.join(", ")}`);
    }
  }

  return {
    ...layout,
    failures,
    ok: failures.length === 0,
  };
}

function fail(message) {
  console.error(`[verify-package] ${message}`);
  process.exit(1);
}

function main() {
  const result = verifyPackage();
  if (!result.ok) {
    fail(result.failures.join("\n[verify-package] "));
  }
  console.log("[verify-package] package contents look ready");
}

if (require.main === module) {
  main();
}

module.exports = {
  loadPackageJson,
  requiredRuntimeFiles,
  resolvePackageLayout,
  verifyPackage,
};
