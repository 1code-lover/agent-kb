# 防止 macOS Release 重复公证

## 基本信息
- 类型：bug
- 日期：2026-08-14
- 相关模块：Electron macOS 打包、签名预检、公证 hook、发布配置校验
- 相关文件：`desktop/package.json`、`desktop/scripts/notarization-credentials.js`、`desktop/scripts/notarize-mac.js`、`desktop/scripts/release-preflight.js`、`desktop/scripts/verify-release-config.js`

## 问题现象
桌面发布链路同时配置了 electron-builder 26.15.3 和自定义 `afterSign` 公证 hook。审计本地依赖后发现，electron-builder 会在 macOS 签名阶段调用内建 `notarizeIfProvided(appPath)`，之后才触发项目的 `afterSign=scripts/notarize-mac.js`。当前机器没有 Apple 凭证，所以问题尚未在外部服务上发生；但凭证一旦到位，同一个 app 存在被提交两次公证的风险，而且原有 hook 和 preflight 只识别 Apple ID 一种凭证。

## 根因分析
根因不是 notarize API 本身，而是发布流程存在两个潜在 submission owner：electron-builder 内建自动公证和项目自定义 `afterSign`。项目又需要自定义 hook 提供严格模式、明确缺项诊断和可测试的提交行为，因此不能让两条路径同时根据环境变量自行决定是否公证。与此同时，hook 与 preflight 各自维护 Apple ID 环境变量列表，后续增加 Keychain 或 API Key 时容易产生策略选择漂移。

## 解决方案
我把自定义 `afterSign` 定义为唯一公证提交点，并在 `desktop/package.json` 显式设置 `build.mac.notarize=false`，关闭 electron-builder 内建自动公证。`verify-release-config.js` 对该字段缺失或为 `true` 都直接失败，避免配置回归重新引入第二个提交点。

同时新增纯函数模块 `notarization-credentials.js`，统一支持三种 `@electron/notarize` payload：Keychain profile、App Store Connect API Key 和 Apple ID，优先级为 `keychain_profile > api_key > apple_id`。部分高优先级配置只产生策略名和缺失字段警告，不会阻止后续完整策略，也不会把密码、账号、私钥路径或 Team ID 写入诊断日志。`notarize-mac.js` 与 `release-preflight.js` 复用同一解析器，严格 preflight 还会一次汇总凭证、Developer ID Application 和 notarytool 三类独立门禁。

## 为什么选这个方案
保留自定义 hook 可以继续提供 `NORTHAGENT_REQUIRE_NOTARIZE` 的严格发布约束、可控日志和依赖注入单测；显式关闭 builder 内建公证则从配置层消除重复 submission，而不是依赖“当前环境刚好没触发”。共享纯函数让 hook 和 preflight 使用同一优先级与完整性判断，降低发布前检查通过但实际 hook 选择另一组凭证的风险。

## 其他方案与为什么没选
1. 只使用 electron-builder 内建公证、删除自定义 hook：会失去项目已有的严格跳过控制、无秘密诊断和单次调用测试接口，也难以保持 release checklist 的现有门禁口径。
2. 继续只支持 Apple ID：实现最简单，但不适合本地安全存储推荐的 Keychain profile，也无法覆盖 CI 常用的 App Store Connect API Key，会让预检和正式发布能力不完整。

## 验证与结果
- TDD 红灯：新增测试后，相关 29 个测试中 12 个按预期失败，暴露共享模块缺失、Keychain/API Key 不支持和 `mac.notarize=false` 未校验。
- Electron 全量：`node --test desktop/src/*.test.js desktop/scripts/*.test.js`，结果 `64 passed`。
- Python 非 slow 全量：`783 passed, 1 deselected, 35 warnings`。
- Web：`89 passed`，Vite build 通过。
- `npm run build:preflight`：通过，确认 `afterSign`、`mac.notarize=false`、hardened runtime、entitlements 和 dmg/zip target。
- `npm run build:mac`：真实 arm64 dmg/zip 打包通过；electron-builder 接受新配置，自定义 hook 执行一次并因无凭证安全跳过。
- `npm run verify:package`：通过。
- `npm run release:preflight`：按预期退出 `1`，一次列出三类凭证缺失和 Developer ID Application 缺失；notarytool 可用。
- 由于本机没有 Developer ID Application 证书和完整 Apple 公证凭证，真实 submission、accepted 状态、stapling 和安装后 Gatekeeper 回归尚未执行，不能宣称正式 macOS release 完成。

## 面试表达版本
我在收口 Electron macOS 发布时发现，electron-builder 26.15.3 的内建公证和项目 `afterSign` hook 都可能提交同一个 app。这个问题在没有 Apple 凭证时不会显现，但正式发布会有重复 submission 风险。我保留了可测试、带严格门禁的自定义 hook，并显式设置 `mac.notarize=false` 关闭内建公证；同时抽出共享凭证解析器，支持 Keychain、API Key 和 Apple ID 三种策略。最终 64 条桌面测试、Python 和 Web 全量回归都通过，真实非正式 dmg/zip 也打包成功；正式签名和公证只剩外部证书与凭证条件。
