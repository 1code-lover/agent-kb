# 2026-08-11 Bug: 桌面打包依赖安全与预检兼容收口

## 基本信息

- 类型：bug
- 日期：2026-08-11
- 相关模块：Electron 桌面发布、macOS release preflight、依赖安全
- 相关文件：`desktop/package.json`、`desktop/package-lock.json`、`desktop/scripts/release-preflight.js`、`desktop/scripts/release-preflight.test.js`、`docs/project.md`

## 问题现象

桌面端已经能打出 macOS dmg/zip，但 `desktop npm audit` 仍报告 8 个漏洞，其中 7 个 high、1 个 critical，主要来自旧 `electron-builder` 依赖链里的 `app-builder-lib`、`builder-util-runtime` 和 `tar`。audit 推荐升级到 `electron-builder@26.15.3`。

升级后又暴露出一个兼容问题：旧预检脚本固定检查 `node_modules/app-builder-bin/mac/app-builder_arm64` 并尝试修复执行位，但新版 `electron-builder` 不再安装 `app-builder-bin`，如果沿用旧检查会让 release preflight 把正常的新依赖布局误判为缺失。

## 根因分析

依赖安全问题的根因是桌面构建链停留在 `electron-builder@24.13.3`，其间接依赖版本落在 npm advisory 的影响范围内。兼容问题的根因是 `release-preflight.js` 把旧版 builder 的内部二进制路径当成稳定契约，而这类内部依赖在大版本升级后会变化。

## 解决方案

先将 `electron-builder` 升级到 `^26.15.3` 并刷新 `desktop/package-lock.json`，让 audit 风险归零。

然后调整 `release-preflight.js`：把旧 `app-builder-bin` 路径改成候选列表，只在旧二进制真实存在时执行 execute-bit 修复；如果新版 builder 不再安装该包，则记录为已跳过的兼容分支，不再让严格预检因为这个 legacy 路径失败。Apple 发布环境变量、Developer ID Application 证书和 `notarytool` 仍然保留严格 gate。

最后补充 `release-preflight.test.js`，覆盖新版不安装 `app-builder-bin` 的场景，避免以后依赖升级时重新引入误报。

## 为什么选这个方案

这个方案把“安全升级”和“发布门禁”分开处理：构建依赖使用官方建议版本消除漏洞，发布预检只放宽已经不属于新版依赖契约的 legacy 二进制检查，不降低 Apple 签名、公证和证书要求。这样既能继续推进本地打包验证，也不会把缺证书的正式发布误判为完成。

## 其他方案与为什么没选

推断：可以直接删除 `app-builder-bin` 检查，但这样会失去对旧依赖树执行位问题的保护。当前方案保留旧路径修复能力，同时兼容新版布局，风险更小。

推断：也可以用 `npm audit --force` 自动升级后不改预检脚本，但这样会把兼容问题留到发布阶段才暴露；本轮选择把预检脚本和单测一起收口。

## 验证与结果

- `npm install --save-dev electron-builder@^26.15.3`：完成，`desktop npm audit` 后续为 0 vulnerabilities。
- `node --test desktop/scripts/*.test.js desktop/src/*.test.js`：`26 passed`。
- `cd desktop && npm run build:preflight`：通过；新版不安装 legacy `app-builder-bin` 时只提示跳过 execute-bit repair，Apple 环境变量和 Developer ID 证书缺失仍正常提示。
- `cd desktop && node scripts/release-preflight.js --strict`：按预期失败在缺少 `APPLE_ID`、`APPLE_APP_SPECIFIC_PASSWORD`、`APPLE_TEAM_ID`，没有再被 legacy `app-builder-bin` 卡住。
- `cd desktop && npm run build`：通过，产出 `NorthAgent-0.1.0-arm64.dmg` 和 `NorthAgent-0.1.0-arm64-mac.zip`。
- `cd desktop && npm run verify:package`：通过，packaged resources 与 `app.asar` 过滤仍符合预期。
- `cd desktop && npm audit --json`：`0 vulnerabilities`。
- `git diff --check`：通过。

## 面试表达版本

我在桌面发布收口时发现 Electron 打包链路虽然能产包，但 `electron-builder` 旧版本带来了 high 和 critical 级别的 audit 风险。我把 builder 升到 26.15.3 后，没有只看 audit 变绿，而是继续跑 release preflight 和实际 macOS 打包，发现旧预检脚本依赖了新版已经移除的 `app-builder-bin` 内部路径。我的处理是把这个检查改成 legacy 兼容：旧二进制存在就修执行位，新版本没有就跳过，但 Apple 签名、公证和证书 gate 继续严格保留。最后我用桌面单测、build preflight、实际 dmg/zip 打包、package 校验和 npm audit 一起验证，确认安全风险清零且发布准备链路没有退化。
