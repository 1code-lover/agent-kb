# macOS 发布补充后置签名公证校验

## 基本信息
- 类型：feature
- 日期：2026-08-11
- 相关模块：桌面端发布、Electron 打包、签名/公证校验、发布门禁
- 相关文件：`desktop/package.json`、`desktop/scripts/verify-mac-release.js`、`desktop/scripts/verify-mac-release.test.js`、`desktop/scripts/verify-release-config.js`、`desktop/scripts/verify-release-config.test.js`、`docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-test-report.md`、`docs/project.md`

## 需求背景

桌面端发布链路已经有 CSP、release config verifier、严格 release preflight、notarize hook 和 packaged resources 校验。但 `release:mac` 在 `electron-builder --mac` 完成后，还缺少一个后置 gate 来证明最终 `.app` 真的满足 macOS 发布信任链：代码签名有效、Gatekeeper 可接受、notarization ticket 已 stapled。

这意味着 Apple 凭证到位后，即使打包和公证提交命令执行了，也还需要人工再跑 `codesign`、`spctl`、`stapler` 才能确认产物闭环。为了减少正式发布的人为遗漏，本轮把这些校验纳入脚本和 release 配置门禁。

## 设计与实现方案

新增 `desktop/scripts/verify-mac-release.js`：

- 根据 packaged resources root 解析 `NorthAgent.app` 路径。
- 在 macOS 上执行 `codesign --verify --deep --strict --verbose=2`。
- 执行 `spctl --assess --type execute --verbose=4`，校验 Gatekeeper 接受度。
- 执行 `xcrun stapler validate`，校验 notarization ticket 是否已 stapled。
- 非 macOS 平台跳过 shell 校验，避免跨平台测试受本机工具影响。
- `--strict` 模式下失败退出；非严格模式用于本机诊断当前签名/公证缺口。

同时更新 `desktop/package.json`：

- 新增 `verify:mac-release`。
- `release:mac` 在 `electron-builder --mac` 后继续执行 `verify:package` 和 `verify:mac-release`。

更新 `desktop/scripts/verify-release-config.js`，要求 `release:mac` 必须包含打包内容校验和 mac release 后置校验，防止后续配置调整绕过这些 gate。

## 为什么选这个方案

把 `codesign`、`spctl`、`stapler` 做成独立 verifier，而不是塞进 `release-preflight`，是因为两者验证的时间点不同：

- `release-preflight` 验证打包前条件是否具备，例如 Apple 环境变量、Developer ID 证书、`notarytool`。
- `verify-mac-release` 验证打包后产物是否真的可信，例如签名、Gatekeeper、公证票据。

这样发布链路从“能开始打包”延伸到“打包结果可信”，边界更清楚，测试也更容易写。

## 其他方案与为什么没选

一种方案是只依赖 electron-builder 的 afterSign/notarize hook。这个方案能提交公证，但不能直接证明最终 `.app` 通过本机信任链检查。

另一种方案是把后置校验写在 release checklist 文档里。文档有价值，但容易被跳过；放进 `release:mac` 之后，正式发布时会自动阻断不合格产物。

## 风险与权衡

正式 `release:mac` 现在更严格：Apple 凭证、Developer ID 证书或公证票据缺失时会失败。这是符合发布目标的，因为不能把未签名或未 stapled 的产物误当成正式发布。

当前本机没有 Apple 凭证和 Developer ID Application 证书，所以不能宣称已经完成正式签名/公证。非严格 `verify-mac-release` 已明确暴露当前产物的状态：codesign/Gatekeeper 失败，且没有 stapled notarization ticket。

## 验证与结果

- `node --test desktop/src/*.test.js desktop/scripts/*.test.js`：`42 passed`
- `node --test desktop/scripts/verify-mac-release.test.js desktop/scripts/verify-release-config.test.js desktop/scripts/verify-package.test.js desktop/scripts/release-preflight.test.js desktop/scripts/notarize-mac.test.js desktop/scripts/build-target.test.js`：`36 passed`
- `node desktop/scripts/verify-release-config.js`：通过，release config ready
- `cd desktop && npm run build:preflight`：通过；非严格预检提示缺少 `APPLE_ID`、`APPLE_APP_SPECIFIC_PASSWORD`、`APPLE_TEAM_ID` 和 Developer ID Application 证书，`notarytool` 可用
- `cd desktop && npm run verify:package`：通过，当前 `desktop/dist` 包内容可解析
- `cd desktop && node scripts/verify-mac-release.js`：非严格诊断按预期指出当前 `.app` 尚未完成正式签名/公证，codesign/Gatekeeper 校验失败且没有 stapled notarization ticket
- `git diff --check`：通过

## 面试表达版本

我把 macOS 桌面发布链路从“打包前条件检查”推进到了“打包后产物信任链检查”。以前 `release:mac` 能跑严格 preflight 和 notarize hook，但打包完成后没有强制证明 `.app` 真的通过 codesign、Gatekeeper 和 stapler。现在新增了 `verify-mac-release`，并把它和 `verify:package` 串到正式 `release:mac` 末尾，还用 release config verifier 防止后续绕过。当前机器因为缺 Apple 凭证和 Developer ID 证书，正式签名/公证仍未完成，但链路已经会在凭证到位后自动阻断未签名、未通过 Gatekeeper 或未 stapled 的产物。
