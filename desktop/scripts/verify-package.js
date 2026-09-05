/* eslint-disable no-console */
const fs = require("node:fs");
const path = require("node:path");
const asar = require("@electron/asar");

const desktopRoot = path.resolve(__dirname, "..");
const requiredRuntimeFiles = [
  "webapp/dist/index.html",
  "run_api.py",
  "config.py",
  "requirements-runtime.txt",
  "api/app.py",
  "server/index.py",
  "utils/logging_utils.py",
];
const requiredEmbeddingFiles = [
  "localmodels/BAAI/bge-small-zh-v1.5/config.json",
  "localmodels/BAAI/bge-small-zh-v1.5/model.safetensors",
  "localmodels/BAAI/bge-small-zh-v1.5/tokenizer.json",
  "localmodels/BAAI/bge-small-zh-v1.5/vocab.txt",
  "localmodels/BAAI/bge-small-zh-v1.5/modules.json",
  "localmodels/BAAI/bge-small-zh-v1.5/1_Pooling/config.json",
];

function loadPackageJson(packagePath = path.join(desktopRoot, "package.json"), fsModule = fs) {
  return JSON.parse(fsModule.readFileSync(packagePath, "utf8"));
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function findExistingMacResourcesRoot({ arch, distDir, fsModule = fs, productName }) {
  const candidateDirs = unique([`mac-${arch}`, arch === "x64" ? "mac" : "", "mac", "mac-universal"]);
  for (const candidateDir of candidateDirs) {
    const resourcesRoot = path.join(distDir, candidateDir, `${productName}.app`, "Contents", "Resources");
    if (fsModule.existsSync(resourcesRoot)) {
      return resourcesRoot;
    }
  }
  if (!fsModule.existsSync(distDir)) {
    return "";
  }
  const entries = fsModule.readdirSync(distDir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isDirectory() || !entry.name.startsWith("mac")) {
      continue;
    }
    const resourcesRoot = path.join(distDir, entry.name, `${productName}.app`, "Contents", "Resources");
    if (fsModule.existsSync(resourcesRoot)) {
      return resourcesRoot;
    }
  }
  return "";
}

function findExistingArtifactPath({ arch, distDir, extension, fsModule = fs, productName, suffix = "", version }) {
  const expected = path.join(distDir, `${productName}-${version}-${arch}${suffix}${extension}`);
  if (fsModule.existsSync(expected)) {
    return expected;
  }
  const noArch = path.join(distDir, `${productName}-${version}${suffix}${extension}`);
  if (fsModule.existsSync(noArch)) {
    return noArch;
  }
  if (!fsModule.existsSync(distDir)) {
    return expected;
  }
  const escapedProduct = productName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const escapedVersion = version.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const escapedSuffix = suffix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`^${escapedProduct}-${escapedVersion}(?:-.+)?${escapedSuffix}${extension.replace(".", "\\.")}$`);
  const otherArchPattern = new RegExp(
    `^${escapedProduct}-${escapedVersion}-(?:arm64|x64|universal)${escapedSuffix}${extension.replace(".", "\\.")}$`
  );
  const found = fsModule
    .readdirSync(distDir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && pattern.test(entry.name) && !otherArchPattern.test(entry.name))
    .map((entry) => path.join(distDir, entry.name))
    .sort();
  return found[0] || expected;
}

function resolvePackageLayout(options = {}) {
  const fsModule = options.fs || fs;
  const root = options.desktopRoot || desktopRoot;
  const pkg = options.packageJson || loadPackageJson(path.join(root, "package.json"), fsModule);
  const productName = options.productName || pkg?.build?.productName || pkg?.name || "NorthAgent";
  const version = options.version || pkg?.version || "0.1.0";
  const arch = options.arch || process.arch;
  const distDir = options.distDir || path.join(root, "dist");
  const discoveredResourcesRoot = findExistingMacResourcesRoot({ arch, distDir, fsModule, productName });
  const resourcesRoot =
    options.resourcesRoot ||
    discoveredResourcesRoot ||
    path.join(distDir, `mac-${arch}`, `${productName}.app`, "Contents", "Resources");

  return {
    arch,
    asarPath: options.asarPath || path.join(resourcesRoot, "app.asar"),
    artifactPaths:
      options.artifactPaths || [
        findExistingArtifactPath({ arch, distDir, extension: ".dmg", fsModule, productName, version }),
        findExistingArtifactPath({ arch, distDir, extension: ".zip", fsModule, productName, suffix: "-mac", version }),
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
  const embeddingFiles = options.requiredEmbeddingFiles || requiredEmbeddingFiles;
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

  for (const relativePath of embeddingFiles) {
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

function formatReadyMessage(result) {
  const artifactNames = Array.isArray(result?.artifactPaths)
    ? result.artifactPaths.map((artifactPath) => path.basename(artifactPath)).filter(Boolean)
    : [];
  const artifactSummary = artifactNames.length > 0 ? artifactNames.join(", ") : "artifacts unresolved";
  return `packaged runtime contents look ready for ad-hoc post-build verification (${artifactSummary}); final signed/notarized distribution still requires npm run release:mac and npm run verify:mac-release`;
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
  console.log(`[verify-package] ${formatReadyMessage(result)}`);
}

if (require.main === module) {
  main();
}

module.exports = {
  findExistingArtifactPath,
  findExistingMacResourcesRoot,
  loadPackageJson,
  requiredRuntimeFiles,
  requiredEmbeddingFiles,
  formatReadyMessage,
  resolvePackageLayout,
  verifyPackage,
};
