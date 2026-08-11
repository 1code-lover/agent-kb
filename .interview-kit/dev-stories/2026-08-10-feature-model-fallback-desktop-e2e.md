# 2026-08-10 Feature: 模型 fallback 与桌面端 E2E 收口

## 背景

粮仓知识库检索质量已经达到 `Recall@5=1.0` 和 `MRR@5=1.0`，下一阶段的真实痛点转向模型额度和桌面端体验。此前真实 QA 运行曾遇到模型额度耗尽，导致长评测需要人工切换模型后重跑；桌面端启动也在 macOS 上出现 Electron 被系统判定为危险应用并移除的问题。

## 目标

- 自动识别额度耗尽、403、401、模型不可用和网络异常。
- 模型调用失败时自动切换到已配置可用模型，并重试一次 chat query。
- API 和 UI 展示当前模型健康状态。
- QA eval 支持断点续跑和遇 API 错误提前写出部分报告。
- 桌面端能启动、配置模型、导入文件、定向 KB 问答、展示来源和 preview，并验证跨 KB 隔离。

## 实现

后端在 `api/services/model_service.py` 中新增模型健康状态存储、错误分类、候选模型枚举和 fallback 探活。`api/services/chat_service.py` 捕获可恢复模型异常后调用 fallback，清理 LLM 缓存并重建 query engine，最多重试一次。`api/routers/settings.py` 新增 `GET /api/model/health`，`get_model_options()` 同步返回 `model_health`。

评测脚本 `scripts/run_grain_qa_eval.py` 增加 `--resume` 和 `--stop-on-api-error`。已有报告中无错误的 case 会被复用，旧 API error case 会重新执行；遇 API 错误提前停止时会写出部分报告并返回非 0。

前端新增 `webapp/src/domain/modelHealth.js`，统一把 `healthy`、`fallback_applied`、`degraded`、`unavailable` 和未知状态映射为页面摘要。模型页和 Agent 页接入同一套健康状态文案。

2026-08-11 又补了一层诊断可见性：后端在 fallback health 里记录 `fallback_attempts`，每个候选都带 `service_provider`、`model`、`api_base`、`reachable` 和 `detail`；前端在 ModelsPage 和 AgentPage 同步展示 `probeSummary`，让用户能看见这次探测了几个候选、最近一次结果是什么。

桌面端修复了两个运行时问题。第一，`desktop/src/python-process.js` 优先使用 `NORTHAGENT_PYTHON` 或 macOS conda `agent-kb` 解释器，避免回落到系统 Python。第二，`electron@31.7.7` 在本机 macOS 上被系统报告 `notarization indicates this code has been revoked`，启动后 `Electron.app` 会被移除；升级到 `electron@43.3.0` 后桌面端可正常进入主进程和渲染进程。

新增 `scripts/diag_desktop_model_workflow.py` 作为桌面真实工作流诊断脚本，覆盖模型 options/health、模型选择与探活、文件导入、定向知识库问答、来源/evidence、preview 和 `default` 跨 KB 隔离。

## 验证

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py tests/api/test_settings_routes.py tests/api/test_chat_service.py tests/scripts/test_run_grain_qa_eval.py -q`：`65 passed, 8 warnings`。
- `node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js`：`80 passed`。
- `node --test desktop/src/python-process.test.js`：`2 passed`。
- `cd webapp && npm run build`：通过。
- `ELECTRON_ENABLE_LOGGING=1 NORTHAGENT_PYTHON=/opt/miniconda3/envs/agent-kb/bin/python npm run dev`：桌面端独立启动成功，runtime log 记录使用 conda Python、API ready、加载 `webapp/dist/index.html`。
- `scripts.diag_desktop_model_workflow` 在桌面拉起的 API 上生成 `desktop-model-workflow-report-after-electron-fix.json`，`run_passed=true`。
- `cd webapp && npm run build`：通过，ModelsPage 和 AgentPage 都能显示 fallback 探测摘要。

## 取舍

- fallback 当前只探活 OpenAI-compatible 且具备 API Key 的候选模型，暂不自动切换到 Ollama，避免本地模型接口差异扩大本轮风险。
- chat query 只重试一次，防止模型错误造成循环切换或重复写历史。
- 桌面端本轮优先解决开发态启动和真实工作流验证；正式打包签名、公证、CSP 和 `electron-builder` 依赖安全升级留给后续发布收口。
- fallback 探测摘要先以文本形式落到页面，后续如果还要继续增强，可再做展开式明细或时间线事件。

## 后续

- 补全桌面依赖安全升级，处理 `npm audit` 中的高危/严重项。
- 将 fallback 事件展示为 Agent 时间线通知。
- 扩展桌面工作流诊断到多领域知识库和更多文件类型。
