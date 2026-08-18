const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  requiredEmbeddingFiles,
  requiredRuntimeFiles,
  resolvePackageLayout,
  verifyPackage,
} = require("./verify-package");

function normalizePath(value) {
  return String(value).replaceAll("\\", "/");
}

function createPackagedFixture(options = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "verify-package-"));
  const packageJson = {
    name: "northagent-desktop",
    version: "0.1.0",
    build: { productName: "NorthAgent" },
  };
  fs.writeFileSync(path.join(root, "package.json"), JSON.stringify(packageJson), "utf8");
  const layout = resolvePackageLayout({ desktopRoot: root, packageJson, arch: "arm64" });
  fs.mkdirSync(path.dirname(layout.asarPath), { recursive: true });
  fs.writeFileSync(layout.asarPath, "asar");

  for (const artifactPath of layout.artifactPaths) {
    fs.mkdirSync(path.dirname(artifactPath), { recursive: true });
    fs.writeFileSync(artifactPath, "artifact");
  }
  for (const runtimeFile of [...requiredRuntimeFiles, ...requiredEmbeddingFiles]) {
    const target = path.join(layout.resourcesRoot, runtimeFile);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, "runtime");
  }

  if (options.removeArtifact) {
    fs.unlinkSync(layout.artifactPaths[0]);
  }
  if (options.removeRuntimeFile) {
    fs.unlinkSync(path.join(layout.resourcesRoot, options.removeRuntimeFile));
  }

  return { layout, packageJson, root };
}

test("verifyPackage accepts expected macOS package contents", () => {
  const { packageJson, root } = createPackagedFixture();

  const result = verifyPackage({
    arch: "arm64",
    asar: { listPackage: () => ["/src/main.js", "/resources/icon.png"] },
    desktopRoot: root,
    packageJson,
  });

  assert.equal(result.ok, true);
  assert.deepEqual(result.failures, []);
  assert.match(normalizePath(result.resourcesRoot), /mac-arm64\/NorthAgent\.app\/Contents\/Resources$/);
});

test("verifyPackage discovers x64 mac app layout and artifacts without arch suffix", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "verify-package-x64-"));
  const packageJson = {
    name: "northagent-desktop",
    version: "0.1.0",
    build: { productName: "NorthAgent" },
  };
  fs.writeFileSync(path.join(root, "package.json"), JSON.stringify(packageJson), "utf8");
  const resourcesRoot = path.join(root, "dist", "mac", "NorthAgent.app", "Contents", "Resources");
  fs.mkdirSync(resourcesRoot, { recursive: true });
  fs.writeFileSync(path.join(resourcesRoot, "app.asar"), "asar");
  fs.writeFileSync(path.join(root, "dist", "NorthAgent-0.1.0.dmg"), "artifact");
  fs.writeFileSync(path.join(root, "dist", "NorthAgent-0.1.0-mac.zip"), "artifact");
  for (const runtimeFile of [...requiredRuntimeFiles, ...requiredEmbeddingFiles]) {
    const target = path.join(resourcesRoot, runtimeFile);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, "runtime");
  }

  const result = verifyPackage({
    arch: "x64",
    asar: { listPackage: () => ["/src/main.js"] },
    desktopRoot: root,
    packageJson,
  });

  assert.equal(result.ok, true);
  assert.match(normalizePath(result.resourcesRoot), /dist\/mac\/NorthAgent\.app\/Contents\/Resources$/);
  assert.match(result.artifactPaths[0], /NorthAgent-0\.1\.0\.dmg$/);
  assert.match(result.artifactPaths[1], /NorthAgent-0\.1\.0-mac\.zip$/);
});

test("verifyPackage prefers no-arch x64 artifacts over stale arm64 artifacts", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "verify-package-x64-stale-"));
  const packageJson = {
    name: "northagent-desktop",
    version: "0.1.0",
    build: { productName: "NorthAgent" },
  };
  fs.writeFileSync(path.join(root, "package.json"), JSON.stringify(packageJson), "utf8");
  const resourcesRoot = path.join(root, "dist", "mac", "NorthAgent.app", "Contents", "Resources");
  fs.mkdirSync(resourcesRoot, { recursive: true });
  fs.writeFileSync(path.join(resourcesRoot, "app.asar"), "asar");
  fs.writeFileSync(path.join(root, "dist", "NorthAgent-0.1.0-arm64.dmg"), "stale artifact");
  fs.writeFileSync(path.join(root, "dist", "NorthAgent-0.1.0-arm64-mac.zip"), "stale artifact");
  fs.writeFileSync(path.join(root, "dist", "NorthAgent-0.1.0.dmg"), "artifact");
  fs.writeFileSync(path.join(root, "dist", "NorthAgent-0.1.0-mac.zip"), "artifact");
  for (const runtimeFile of [...requiredRuntimeFiles, ...requiredEmbeddingFiles]) {
    const target = path.join(resourcesRoot, runtimeFile);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, "runtime");
  }

  const result = verifyPackage({
    arch: "x64",
    asar: { listPackage: () => ["/src/main.js"] },
    desktopRoot: root,
    packageJson,
  });

  assert.equal(result.ok, true);
  assert.match(result.artifactPaths[0], /NorthAgent-0\.1\.0\.dmg$/);
  assert.match(result.artifactPaths[1], /NorthAgent-0\.1\.0-mac\.zip$/);
});

test("verifyPackage discovers mac-universal layout and universal artifacts", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "verify-package-universal-"));
  const packageJson = {
    name: "northagent-desktop",
    version: "0.1.0",
    build: { productName: "NorthAgent" },
  };
  fs.writeFileSync(path.join(root, "package.json"), JSON.stringify(packageJson), "utf8");
  const resourcesRoot = path.join(root, "dist", "mac-universal", "NorthAgent.app", "Contents", "Resources");
  fs.mkdirSync(resourcesRoot, { recursive: true });
  fs.writeFileSync(path.join(resourcesRoot, "app.asar"), "asar");
  fs.writeFileSync(path.join(root, "dist", "NorthAgent-0.1.0-universal.dmg"), "artifact");
  fs.writeFileSync(path.join(root, "dist", "NorthAgent-0.1.0-universal-mac.zip"), "artifact");
  for (const runtimeFile of [...requiredRuntimeFiles, ...requiredEmbeddingFiles]) {
    const target = path.join(resourcesRoot, runtimeFile);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, "runtime");
  }

  const result = verifyPackage({
    arch: "universal",
    asar: { listPackage: () => ["/src/main.js"] },
    desktopRoot: root,
    packageJson,
  });

  assert.equal(result.ok, true);
  assert.match(normalizePath(result.resourcesRoot), /dist\/mac-universal\/NorthAgent\.app\/Contents\/Resources$/);
  assert.match(result.artifactPaths[0], /NorthAgent-0\.1\.0-universal\.dmg$/);
  assert.match(result.artifactPaths[1], /NorthAgent-0\.1\.0-universal-mac\.zip$/);
});

test("verifyPackage reports missing release artifacts", () => {
  const { packageJson, root } = createPackagedFixture({ removeArtifact: true });

  const result = verifyPackage({
    arch: "arm64",
    asar: { listPackage: () => [] },
    desktopRoot: root,
    packageJson,
  });

  assert.equal(result.ok, false);
  assert.match(result.failures.join("\n"), /missing artifact/);
  assert.match(result.failures.join("\n"), /NorthAgent-0\.1\.0-arm64\.dmg/);
});

test("verifyPackage reports missing runtime files", () => {
  const { packageJson, root } = createPackagedFixture({ removeRuntimeFile: "server/index.py" });

  const result = verifyPackage({
    arch: "arm64",
    asar: { listPackage: () => [] },
    desktopRoot: root,
    packageJson,
  });

  assert.equal(result.ok, false);
  assert.match(result.failures.join("\n"), /missing runtime file/);
  assert.match(normalizePath(result.failures.join("\n")), /server\/index\.py/);
});

test("verifyPackage requires a loadable default SentenceTransformer embedding", () => {
  assert.deepEqual(requiredEmbeddingFiles, [
    "localmodels/BAAI/bge-small-zh-v1.5/config.json",
    "localmodels/BAAI/bge-small-zh-v1.5/model.safetensors",
    "localmodels/BAAI/bge-small-zh-v1.5/tokenizer.json",
    "localmodels/BAAI/bge-small-zh-v1.5/vocab.txt",
    "localmodels/BAAI/bge-small-zh-v1.5/modules.json",
    "localmodels/BAAI/bge-small-zh-v1.5/1_Pooling/config.json",
  ]);

  const missingModelFile = requiredEmbeddingFiles[1];
  const { packageJson, root } = createPackagedFixture({ removeRuntimeFile: missingModelFile });
  const result = verifyPackage({
    arch: "arm64",
    asar: { listPackage: () => [] },
    desktopRoot: root,
    packageJson,
  });

  assert.equal(result.ok, false);
  assert.match(result.failures.join("\n"), /missing runtime file/);
  assert.match(result.failures.join("\n"), /model\.safetensors/);
});

test("verifyPackage rejects packaged test files inside app.asar", () => {
  const { packageJson, root } = createPackagedFixture();

  const result = verifyPackage({
    arch: "arm64",
    asar: { listPackage: () => ["/src/main.js", "/src/main.test.js"] },
    desktopRoot: root,
    packageJson,
  });

  assert.equal(result.ok, false);
  assert.match(result.failures.join("\n"), /test files should not be packaged/);
  assert.match(result.failures.join("\n"), /main\.test\.js/);
});
