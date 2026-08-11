const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { requiredRuntimeFiles, resolvePackageLayout, verifyPackage } = require("./verify-package");

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
  for (const runtimeFile of requiredRuntimeFiles) {
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
  assert.match(result.resourcesRoot, /mac-arm64\/NorthAgent\.app\/Contents\/Resources$/);
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
  assert.match(result.failures.join("\n"), /server\/index\.py/);
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
