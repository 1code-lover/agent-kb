# 20260810 Model Fallback Desktop E2E PRD

## 背景

粮仓知识库检索质量已收口，当前真实风险转向模型配置韧性和桌面端真实工作流。此前完整 QA 评估曾因 `AllocationQuota.FreeTierOnly` 中途失败，说明只依赖人工切换模型会让长评估和桌面问答不稳定。

## 目标

1. 自动识别模型额度耗尽、HTTP 403、HTTP 401、模型不可用等错误。
2. 当前模型失败时，自动切换到已配置且可用的候选模型。
3. API 返回当前模型健康状态，前端可展示健康状态和最近 fallback 信息。
4. 粮仓 QA 评测脚本支持断点续跑，避免长评估中途失败后全部重跑。
5. 完成桌面端真实工作流 E2E 验证：启动、模型配置、问答、引用、preview、跨 KB 隔离。
6. 收口 macOS 正式发布入口：签名、公证、stapling、CSP 和安装后校验；公证支持 Apple ID、App Store Connect API Key、Keychain profile 三种凭证策略，并保证每个 app 只提交一次公证。

## 范围

### 本轮包含

- 后端模型错误分类、候选模型枚举、fallback 选择和状态持久化。
- Agent 高级模式直连聊天支持 Ollama，并在当前模型不可用时复用同一套自动 fallback。
- `/api/model/options` 或新增 API 输出模型健康状态。
- 前端模型页/Agent 页显示当前模型健康状态。
- `scripts.run_grain_qa_eval` 支持恢复已有报告并跳过已完成用例。
- 桌面端启动和真实链路验证脚本/报告。
- Electron CSP、hardened runtime、entitlements、Developer ID 签名检查、notarytool 公证和 Gatekeeper/stapler 后置校验。
- Apple ID、App Store Connect API Key、Keychain profile 三种 notarization 凭证策略；本地发布优先推荐 Keychain profile。
- 显式关闭 electron-builder 内建自动公证，由严格 afterSign hook 单次提交，避免重复公证。
- 更新 `docs/project.md` 最近提交和下一阶段目标。

### 本轮不包含

- 新增第三方模型供应商注册 UI 大改。
- 改造 LLM SDK 底层调用协议。
- 重做检索排序或粮仓 QA 题集。

## 验收标准

- 单元测试覆盖 401、403、额度耗尽、模型不可用的分类与 fallback 选择。
- 模型 fallback 后 `current_llm_info` 更新为可用模型，健康状态记录最近错误和切换结果。
- 基础问答、知识库问答和 Agent 直连聊天均能在可恢复模型错误后自动切换并重试一次；Agent 直连 Ollama 不要求 API Key。
- API 能返回模型健康状态，前端能显示健康状态文本。
- QA eval 支持 `--resume`，已有报告中成功用例不会重复请求 API。
- 桌面端 E2E 报告覆盖模型配置、KB 问答、引用来源、preview、跨 KB 隔离。
- `release:preflight` 接受三种完整公证凭证策略中的任意一种，对部分配置输出缺失字段，并始终要求有效 Developer ID Application 身份和 notarytool。
- macOS 构建只执行一次公证提交；release config verifier 必须确认自定义 afterSign hook 已启用且 electron-builder 内建 notarization 已关闭。
- 正式 `release:mac` 产物通过 codesign、Gatekeeper、stapler、包内容和安装后工作流验证。
- 全量非 slow 测试通过，前端 Node 测试和构建通过。

## 2026-08-15 packaged runtime 数据隔离补充

### 问题

当前 packaged Electron 将 `process.resourcesPath` 同时作为程序资源目录、Python 工作目录和日志目录。正式签名后，运行数据写入 `.app/Contents/Resources` 可能因权限失败，也可能改变签名覆盖内容。与此同时，默认禁止 embedding 远程下载，但 `localmodels/` 尚未进入安装包，干净运行目录无法加载默认 embedding。

### 范围补充

- 将只读程序资源根目录与可写运行根目录分离：程序代码、Web 静态文件和模型从 app resources 读取，日志、配置、会话、知识库和索引只写入 Electron `userData/runtime`。
- Electron 启动 Python 时，脚本仍来自 resources，`cwd` 改为 runtime 根目录，并显式传入数据根目录和模型根目录环境变量。
- Python 所有显式配置、会话、fallback 配置和模型路径支持绝对根目录，不再强制回落到源码目录。
- 将默认 `bge-small-zh-v1.5` 本地模型作为 packaged runtime 必需资源，并由 `verify:package` 阻断缺失模型文件的产物。

### 验收标准补充

- packaged 模式的桌面日志和 Python `cwd` 位于 `app.getPath("userData")/runtime`，不得位于 `process.resourcesPath`。
- Python 子进程接收 `NORTHAGENT_DATA_ROOT=<runtimeRoot>` 与 `NORTHAGENT_MODEL_ROOT=<resourceRoot>/localmodels`，`run_api.py` 路径仍为 `<resourceRoot>/run_api.py`。
- 默认开发模式路径行为保持兼容；设置环境变量后，storage/data/model 均解析为对应绝对目录。
- app 启动、API ready、embedding ready、知识库链路和 Ollama fallback 执行后，Resources 文件树和内容哈希保持不变，运行数据只出现在 userData/runtime。
- `verify:package` 至少检查默认 embedding 的 `config.json`、`model.safetensors`、`tokenizer.json`、`vocab.txt`、`modules.json` 和 `1_Pooling/config.json`。
- 本轮复用显式配置或本机兼容 Python 环境，不宣称安装包已内置完整 Python 解释器及原生依赖；真实 packaged E2E 必须记录实际 Python 路径、版本和依赖检查结果。

## 2026-08-16 外部 Python runtime 发布门禁补充

### 问题

当前安装包明确依赖外部 Python，但 `build:preflight`、`release:preflight` 和通用 build target 只验证 Electron、Apple 和包配置。错误的系统 Python、非 3.12 版本、缺少核心模块或依赖冲突仍可能在签名、公证之后才暴露，产生“发布成功但首次启动失败”的产物。

### 范围补充

- 新增可独立执行和单元测试的 Python runtime verifier，复用桌面端解释器候选优先级。
- 验证 Python 3.12、核心运行模块可发现、`pip check` 通过，并输出不含秘密的解释器路径和诊断。
- 显式 `NORTHAGENT_PYTHON` 配置失败时不得静默切换到其他解释器，避免验证环境与实际启动环境不一致。
- 将 verifier 接入 `build:preflight`、严格 `release:preflight` 和 macOS 通用 build target；发布配置校验器必须阻断丢失该门禁的脚本配置。

### 验收标准补充

- 正确的 `/opt/miniconda3/envs/agent-kb/bin/python` 3.12 runtime 通过并报告 `llama-index=0.11.19`、`llama-index-core=0.11.19` 和 `pip check` 无冲突。
- Python 版本不符、锁定包版本漂移、核心模块缺失、`pip check` 失败、解释器不可执行均返回非零并给出可操作原因。
- 显式解释器失败时结果记录该解释器，不回退到系统 Python；未显式配置时可按候选顺序选择首个完整 runtime。
- `build:preflight`、`release:preflight` 和 `npm run build` 的 macOS 路径都必须先通过 runtime verifier，才允许进入 Electron 构建或 Apple 门禁。
