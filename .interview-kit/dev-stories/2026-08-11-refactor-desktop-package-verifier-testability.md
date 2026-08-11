# 2026-08-11 Refactor: 桌面 package verifier 测试化

## 基本信息
- 类型：refactor
- 日期：2026-08-11
- 相关模块：桌面发布、打包产物校验、release gate
- 相关文件：`desktop/scripts/verify-package.js`、`desktop/scripts/verify-package.test.js`、`docs/project.md`、`docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-test-report.md`

## 重构背景

桌面端发布链路已经有 release config、preflight、notarize hook 和 macOS build 入口测试，但 `verify-package.js` 仍然是一个顶层执行脚本。它负责检查 dmg/zip、packaged runtime resources、`app.asar` 和测试文件排除，属于发布闭环里的关键门禁，却没有单测覆盖。

这会让 package 校验逻辑只能靠真实 `desktop/dist` 产物手工跑一次确认；后续如果 artifact 命名、runtime resources 或 asar 检查逻辑回退，测试层不一定能第一时间发现。

## 重构方案

把 `desktop/scripts/verify-package.js` 改成 CLI + 可测试函数的结构：保留 `npm run verify:package` 的命令行为，同时导出 `verifyPackage()`、`resolvePackageLayout()`、`loadPackageJson()` 和 `requiredRuntimeFiles`。

`verifyPackage()` 支持注入 `desktopRoot`、`packageJson`、`arch`、`fs` 和 `asar`，返回结构化结果，不直接 `process.exit`。CLI 入口只负责把失败列表打印出来并退出。

新增 `desktop/scripts/verify-package.test.js`，用临时目录构造 packaged fixture，覆盖完整 package、缺失 dmg/zip artifact、缺失 runtime 文件，以及 `app.asar` 混入 `.test.js` 的失败路径。

后续又把 package layout 解析从“只按当前 `process.arch` 拼路径”增强为“优先发现真实存在的 mac app resources 目录和 dmg/zip 产物”。这样 `mac-arm64`、`mac`、`mac-universal` 目录，以及带 arch 或不带 arch 后缀的产物名，都能被同一个 verifier 覆盖。

## 为什么这样重构

这个改法把发布校验从“只能跑真实产物的脚本”变成“脚本行为不变，但核心逻辑可回归”。发布脚本仍然轻量，测试也不依赖真实打包耗时和已有 `dist` 状态。

注入 `fs` 和 `asar` 是为了避免测试必须创建真实 asar 包；产物存在性仍用临时文件模拟，足够覆盖当前发布门禁的判断逻辑。

布局发现逻辑是为了降低 release 产物命名变化的维护成本。当前本机是 `mac-arm64` + `NorthAgent-0.1.0-arm64.*`，但 electron-builder 在 x64 或 universal 场景下可能产出 `mac/`、`mac-universal/` 或无 arch 后缀文件。verifier 先找真实存在的产物，再回退到默认推导路径，能兼顾当前路径和未来变体。

后续复核还补了一个残留产物风险：如果 `dist/` 里同时留着旧 arm64 产物和当前 x64 无后缀产物，verifier 必须优先选择当前 x64 无后缀文件，不能按字典序误选旧架构 artifact。

## 其他方案与为什么没选

推断：可以只在 CI 里每次真实打包后跑 `npm run verify:package`，但这反馈太晚，也覆盖不到缺失资源和 asar test 文件这些可单测的分支。

推断：也可以重写成更复杂的 release manifest 校验器，但当前目标只是收紧已有 package verifier，不需要引入新格式。

## 风险控制与兼容性

CLI 行为保持不变，`npm run verify:package` 仍然调用同一个文件，成功时输出 `[verify-package] package contents look ready`。失败信息仍以 `[verify-package]` 前缀输出。

默认路径仍按当前 `NorthAgent-0.1.0-arm64` 和 `dist/mac-arm64/NorthAgent.app` 口径兜底；如果 `dist/` 里已经存在 x64 或 universal 产物，会优先采用真实发现到的 resources 目录和 artifact 文件。测试通过临时目录模拟不同布局，不影响真实发布路径。

## 验证与结果

- `node --test desktop/scripts/*.test.js`：`30 passed`。
- `node desktop/scripts/verify-release-config.js`：通过。
- `cd desktop && npm run verify:package`：通过。
- `git diff --check`：通过。

## 面试表达版本

我在收桌面发布链路时发现，`verify-package.js` 是发布闭环里的关键门禁，但它还是顶层脚本，没有单测。于是我把它重构成 CLI 加可测试函数，保留原有命令行为，同时让 package layout、runtime 文件、artifact 和 asar 检查都能被测试注入。然后我补了临时 packaged fixture，覆盖完整包、缺 dmg/zip、缺 runtime 文件、app.asar 混入测试文件，以及 x64 `mac/` 布局、mac-universal 布局、无 arch 后缀产物和旧架构 artifact 残留。最后发布脚本测试扩到 30 条全过，真实 `npm run verify:package` 也继续通过。
