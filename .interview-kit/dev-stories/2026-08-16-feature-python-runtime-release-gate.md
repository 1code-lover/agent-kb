# 为 Electron 发布链路增加外部 Python runtime 门禁

## 基本信息
- 类型：feature
- 日期：2026-08-16
- 相关模块：Electron 构建脚本、macOS release preflight、外部 Python 运行时
- 相关文件：`desktop/scripts/verify-python-runtime.js`、`desktop/scripts/build-target.js`、`desktop/scripts/verify-release-config.js`、`desktop/package.json`

## 需求背景
NorthAgent 的 packaged app 已把只读 Resources 和可写 runtime 数据分开，但当前安装包仍依赖机器上的外部 Python。原发布报告只记录了测试时使用的解释器和 `pip check`，构建脚本不会阻止 Python 版本错误、核心模块缺失、LlamaIndex 锁版本漂移或依赖冲突，因此可能生成一个内容完整但 API 无法启动的安装包。

## 设计与实现方案
新增独立的 `verify-python-runtime.js`，复用桌面启动的三个 override 优先级；显式解释器失败时 fail-closed，默认模式才继续探测 conda、项目虚拟环境和系统 Python 候选。探针要求 CPython 3.12，检查 FastAPI、Uvicorn、LlamaIndex、SentenceTransformers 和 HTTPX，并强制 `llama-index`、`llama-index-core` 都是 `0.11.19`，最后单独执行 `<python> -m pip check`。结果使用稳定结构，外部诊断折叠为单行、限制 500 字符，并把 secret-like 环境变量值替换为 `[REDACTED]`。npm build/release preflight、macOS build target 和 release config verifier 都接入该门禁，验证失败后不会继续 electron-builder。

## 为什么选这个方案
项目依赖 LlamaIndex 私有 API，单纯检查 `python --version` 或 `import` 无法发现兼容但错误的包版本；`pip check` 也不能代替项目自己的锁版本契约。因此采用“解释器与模块探针、项目锁版本、pip 依赖一致性”三层门禁。把 verifier 做成可注入 spawn 的独立脚本，可以在不创建真实坏环境的情况下覆盖异常路径，也便于 build target 和 npm scripts 统一调用。

## 其他方案与为什么没选
1. 只在安装后启动时检查 Python：发现问题太晚，签名、公证和分发成本已经发生，不能保护发布链路。
2. 只执行 `pip check`：无法发现 Python 3.11/3.13、模块未安装和 `llama-index=0.11.20` 这类项目不兼容但依赖图仍合法的情况。
3. 本轮直接把 Python 解释器和全部依赖内置进 app：能消除外部前提，但会引入体积、原生依赖、嵌套签名和跨架构发布问题，需要独立设计与验证，不能用一个 preflight 改动替代。

## 风险与权衡
门禁验证的是构建/发布机器当前可解析的外部 runtime，不能证明任意清洁安装机器都具备同一环境，因此文档继续明确安装包不是自包含 runtime。默认候选允许回退以兼容现有开发机，但显式 override 必须失败关闭，避免用户选择被悄悄覆盖。诊断需要可操作信息又不能泄露凭证，所以只记录必要版本和短摘要，并按 secret-like 环境变量值做精确脱敏。

## 验证与结果
- TDD 初始执行：`5 failed, 6 passed`，证实 verifier 缺失、build target 未接线和 release config 存在旁路。
- 代码评审增加 secret stderr 测试，初次为 `1 failed, 12 passed`；统一脱敏后通过。
- `node --test desktop/scripts/verify-python-runtime.test.js desktop/scripts/build-target.test.js desktop/scripts/verify-release-config.test.js`：`24 passed`。
- `node --test desktop/src/*.test.js desktop/scripts/*.test.js`：`86 passed`。
- 真实 verifier：`/opt/miniconda3/envs/agent-kb/bin/python`、CPython `3.12.13`、两个 LlamaIndex 包均为 `0.11.19`，`pip check` 返回 `No broken requirements found.`。
- `cd desktop && npm run build:preflight`、`npm run build:mac`、`npm run verify:package`：通过。
- Python 非 slow 全量：`791 passed, 1 deselected, 35 warnings`；Web：`89 passed` 且 Vite build 通过。
- 严格 `release:preflight` 先通过 Python 门禁，再因 Developer ID 和 Apple 公证凭证缺失按预期退出 `1`，没有误报正式 release 完成。

## 面试表达版本
我在收口 Electron 打包时发现，安装包依赖外部 Python，但发布链路只在报告里披露这个事实，错误解释器或依赖漂移仍能生成不可启动的包。我新增了一个分层 runtime verifier，检查 CPython 3.12、核心模块、LlamaIndex 精确锁版本和 pip 依赖一致性，并把它接入 build 与 release preflight。显式 Python 失败会直接阻断，默认候选才允许回退。评审时我又发现外部 stderr 可能夹带环境秘密，所以补了统一脱敏和失败测试。最终桌面 86 个测试、真实打包和包校验都通过，Apple 签名公证仍按外部凭证状态明确阻断。
