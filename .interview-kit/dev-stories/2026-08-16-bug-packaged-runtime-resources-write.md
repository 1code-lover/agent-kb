# 修复 packaged Electron 将运行数据写入签名 Resources 的问题

## 基本信息
- 类型：bug
- 日期：2026-08-16
- 相关模块：Electron 主进程、Python API 启动、模型加载、macOS 打包校验
- 相关文件：`desktop/src/main.js`、`desktop/src/python-process.js`、`desktop/src/runtime-paths.js`、`desktop/src/runtime-log.js`、`config.py`、`server/utils/model_paths.py`、`desktop/package.json`、`desktop/scripts/verify-package.js`

## 问题现象
packaged app 原来把 `process.resourcesPath` 同时当成资源目录、Python `cwd` 和日志根目录。正式签名后，运行期间写入 `Contents/Resources` 可能因权限失败，也会改变签名 bundle。另一个问题是 embedding 默认禁止远程下载，但 `localmodels` 没有进入安装包，离线 packaged app 无法保证 embedding ready。

## 根因分析
Electron 主进程只有一个 `projectRoot` 概念，没有区分只读 app resources 和可写用户数据。Python 进程继承这个目录作为工作目录，源码中部分持久化路径依赖 cwd，session/fallback store 又直接基于源码目录计算路径。Python 导入模块时还会默认创建 `__pycache__`，因此即使业务日志改到用户目录，Resources 仍可能被修改。

## 解决方案
新增可测试的 `resourceRoot`/`runtimeRoot` 路径解析：packaged 模式从 Resources 读取脚本、静态资源和模型，把 `userData/runtime` 作为 Python cwd 与所有运行数据目录；runtime root 不可创建或不可写时 fail-closed。Python 子进程显式接收 `NORTHAGENT_DATA_ROOT`、`NORTHAGENT_MODEL_ROOT`、`PYTHONDONTWRITEBYTECODE=1` 和 UTF-8 环境。Python 配置、store、embedding、reranker 和通用 model loader 改为正确处理绝对路径。最后把 `localmodels` 放进 `extraResources`，并让 package verifier 检查默认 SentenceTransformer 的关键文件。

## 为什么选这个方案
该方案保持 app bundle 只读，符合 macOS 签名和公证后的运行约束，同时保留开发模式仓库根目录行为，改动范围集中在路径边界。通过显式环境变量把资源、数据和模型依赖传给子进程，能够测试和审计，不依赖当前工作目录的偶然性。模型资源随包发布是远程下载关闭时的必要条件；本轮继续复用已有外部 conda Python 运行时，没有把解释器和原生依赖一并塞进安装包，因为自包含 Python runtime 的体积、依赖和嵌套签名需要单独的发布需求。

## 其他方案与为什么没选
1. 继续让 Python 写 Resources，只依赖签名后目录权限：没有解决签名内容被修改和不同安装位置权限不一致的问题。
2. 只把 Electron 日志移到 userData：无法覆盖 Python cwd、session、KB、receipt、配置和导入模块生成的 `__pycache__`，真实验证也会遗漏污染来源。

## 验证与结果
- TDD 初始失败测试验证了缺少 runtime path 模块、spawn cwd/env 和 embedding package 门禁。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"`：`791 passed, 1 deselected, 35 warnings`。
- `node --test desktop/src/*.test.js desktop/scripts/*.test.js`：`69 passed`。
- `node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js`：`89 passed`；Vite build 通过。
- `cd desktop && npm run build:mac`、`npm run verify:package`：通过，DMG/ZIP 包含默认 embedding。
- 真实 packaged E2E：embedding 从 Resources 本地加载并 ready；Resources 启动前后 114 项文件 SHA-256 一致，没有生成 `__pycache__`；runtime 数据写入独立 userData/runtime，退出后 Python 已停止。
- packaged Agent API 直连返回 `PACKAGED_OLLAMA_OK`；坏云端模型自动发现 Ollama 候选并返回 `PACKAGED_FALLBACK_OK`，step 明确为“已自动切换到 Ollama / qwen2.5:0.5b”。
- 证据：`docs/20260810-model-fallback-desktop-e2e/artifacts/packaged-runtime-release-e2e-report-20260816.json`。

## 面试表达版本
我在做 macOS Electron 发布收口时发现，packaged app 会把 Python 的运行数据和导入缓存写进签名包的 Resources 目录，这会导致权限和签名完整性问题。我的处理是把只读资源根目录和 userData 下的可写 runtime 根目录彻底拆开，并通过环境变量把数据根、模型根和禁止 bytecode 写入的策略传给 Python。随后我把默认 embedding 模型随包发布，并用 verifier 和真实 packaged E2E 做门禁。第一次 E2E 还发现了 `__pycache__` 这个遗漏，修复后最终证明 Resources 哈希不变、embedding ready、Agent Ollama fallback 正常且 Python 能正常退出。
