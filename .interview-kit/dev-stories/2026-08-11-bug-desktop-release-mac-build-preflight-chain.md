# 2026-08-11 Bug: release:mac 补齐 build:preflight 门禁

## 基本信息
- 类型：bug
- 日期：2026-08-11
- 相关模块：桌面发布脚本、发布配置校验、签名/公证预检
- 相关文件：`desktop/package.json`、`desktop/scripts/build-target.js`、`desktop/scripts/build-target.test.js`、`desktop/scripts/verify-release-config.js`、`desktop/scripts/verify-release-config.test.js`、`docs/project.md`、`docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-release-checklist.md`

## 问题现象

桌面端的 `release:mac` 能直接进入 `release:preflight` 和 `electron-builder --mac`，但没有显式串起 `build:preflight`。这意味着真正的一键发布命令虽然会做签名/公证预检，却不会在同一条链路里强制执行发布配置校验。

从维护角度看，这会让 `build:preflight` 和 `release:mac` 的门禁语义分开，后续如果有人只跑 release 命令，可能会漏掉对 `afterSign`、hardened runtime、entitlements、打包资源和脚本链路的统一检查。

后续复核时又发现，常用的 `npm run build` 会走 `desktop/scripts/build-target.js`，它在 macOS 上也只跑了 `release-preflight.js`，没有显式跑 `verify-release-config.js`。这条本机打包路径同样可能绕过配置校验。

## 根因分析

问题根因不是单个校验项缺失，而是发布入口分层不一致：`build:preflight` 负责校验 release config，`release:preflight` 负责 Apple 凭证和 notarization 预检，但 `release:mac` 只串了后者，没有把前者纳入真正的发布路径。

这样就形成了“测试里能看到配置校验，release 命令本身却不保证先过配置校验”的流程断层。

`build-target.js` 也有同类问题：它作为 `npm run build` 的平台分发入口，直接调用 Electron builder，却没有把配置校验作为 macOS 打包前置条件。

## 解决方案

把 `desktop/package.json` 的 `release:mac` 改成先跑 `npm run build:preflight`，再跑严格 `npm run release:preflight`，最后进入 `electron-builder --mac`。

同步把 `desktop/scripts/verify-release-config.js` 的检查项补成：`release:mac` 必须包含 `build:preflight`、`release:preflight` 和 `electron-builder --mac`。这样配置一旦回退，校验器会直接报错。

`desktop/scripts/verify-release-config.test.js` 也补了对应断言，确保缺少 `build:preflight` 时会被捕捉。

随后把 `desktop/scripts/build-target.js` 改成可测试的 `runBuildTarget()`，在 macOS 上先执行 `verify-release-config.js`，再执行 `release-preflight.js`，最后才进入 Electron builder。新增 `build-target.test.js` 覆盖 macOS 预检顺序、预检失败提前停止，以及非 macOS 平台只进入对应 builder target。

## 为什么选这个方案

这个方案改动面最小，但能把“配置校验”真正绑进正式发布入口，避免后面再出现只跑了一半门禁的情况。

相比单独新增一个新命令，直接收紧现有 `release:mac` 更符合当前仓库的使用习惯，脚本入口也不会变多。

## 其他方案与为什么没选

推断：可以只更新文档，要求人工在发布前先跑 `build:preflight`，但那样仍然依赖执行者记忆，还是会漏。

推断：也可以新增一个 `release:full` 命令专门串起所有步骤，但这会增加一套新的入口，和现有 `release:mac` 职责重复。

## 验证与结果

- `node --test desktop/scripts/verify-release-config.test.js desktop/scripts/release-preflight.test.js desktop/scripts/notarize-mac.test.js`：`20 passed`。
- `node --test desktop/scripts/*.test.js`：`23 passed`。
- `git diff --check`：通过。
- 项目文档已同步更新 `release:mac` 和 macOS `npm run build` 的实际预检链路。

## 面试表达版本

我在收桌面发布链路时发现，`release:mac` 虽然会做签名和公证预检，但没有把发布配置校验一起绑进去。于是我把 `release:mac` 改成先跑 `build:preflight`，再跑严格 `release:preflight`，最后才进入 `electron-builder --mac`。后续我又把 `npm run build` 的 macOS 路径补齐，让 `build-target.js` 也先过发布配置校验和非严格预检。这样一键 release 和本机 build 两条入口都不会绕过门禁，发布流程不再依赖人工记步骤。
