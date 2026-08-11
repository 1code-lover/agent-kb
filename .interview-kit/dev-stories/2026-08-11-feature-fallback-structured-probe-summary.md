# 2026-08-11 Feature: fallback 结构化探测摘要

## 基本信息

- 类型：feature
- 日期：2026-08-11
- 相关模块：模型 fallback、模型健康状态、前端健康提示
- 相关文件：`api/services/model_service.py`、`tests/api/test_model_service.py`、`webapp/src/domain/modelHealth.js`、`webapp/src/domain/modelHealth.test.js`、`docs/project.md`、`docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-test-report.md`

## 需求背景

前一轮模型 fallback 已经能记录逐个候选的 `fallback_attempts`，前端也能把最近探测结果展示出来。但真实桌面端配置恢复后，用户最需要快速判断的是：这次总共探测了几个候选、几个可用、几个失败、是否涉及本地 Ollama，以及 Ollama 不可用时该检查什么。

如果只让前端临时遍历原始 attempts 拼文案，后续 API、桌面端和更多页面会重复实现同一套统计逻辑，也容易在字段缺失或候选类型增加时产生不一致提示。

## 设计与实现方案

后端在 `api/services/model_service.py` 新增 `_summarize_fallback_attempts()`，把每次 fallback 探测结果聚合为 `fallback_attempt_summary`。摘要包含候选总数、可用数、失败数、Ollama 候选数、Ollama 可用数，以及最近一次候选的 provider、model 和 detail。

`attempt_model_fallback()` 在成功切换和全部不可用两条路径都会写入并返回这个摘要；默认模型健康状态也补上空的 `fallback_attempt_summary`，让前端可以稳定读取字段。

前端 `webapp/src/domain/modelHealth.js` 的 `formatFallbackAttempts()` 优先使用结构化摘要生成 `probeSummary`，旧的 `fallback_attempts` 逐条展示仍作为兼容兜底。不可用状态下，如果存在 Ollama 候选但没有任何 Ollama 可用，`actionHint` 会明确提示检查 Ollama 是否启动、目标模型是否已拉取，并提醒也可以补齐云端可用供应商。

## 为什么选这个方案

把聚合逻辑放在后端，可以让 API 返回的健康状态更接近“诊断结论”，前端只负责展示，不需要在多个页面重复理解候选探测细节。这样也保留了原始 `fallback_attempts`，调试时仍能看完整明细。

摘要字段保持扁平结构，避免引入复杂嵌套对象；对当前 UI 来说已经足够表达关键判断，对后续桌面事件流或诊断报告也更容易复用。

## 其他方案与为什么没选

推断：可以只在前端基于 `fallback_attempts` 做统计，但 Agent 页、模型页和未来桌面诊断视图都会重复这段逻辑，字段口径也容易漂移。

推断：可以把每次 fallback 探测做成完整时间线事件，但本轮目标是补清楚不可用边角提示，不需要先引入新的事件模型。

## 风险与权衡

新增摘要字段会扩展模型健康状态结构。控制方式是保留 `fallback_attempts` 旧字段不变，前端也继续支持旧格式，因此已有调用方不会因为缺少摘要字段而失效。

Ollama 提示只在“存在 Ollama 候选且 Ollama 可用数为 0”时触发，避免云端候选失败时误导用户去检查本地服务。后续如果引入更多本地模型 provider，可以按同样模式扩展 provider 维度摘要。

## 验证与结果

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py -q`：`18 passed, 2 warnings`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py tests/api/test_settings_routes.py tests/api/test_chat_service.py -q`：`56 passed, 8 warnings`。
- `node --test webapp/src/domain/modelHealth.test.js`：`8 passed`。
- `node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js`：`83 passed`。
- `git diff --check`：通过。

## 面试表达版本

我在做模型 fallback 收口时发现，逐条 attempts 虽然能调试，但用户更需要一个清楚的诊断结论。于是我在后端把 fallback 探测结果聚合成 `fallback_attempt_summary`，包含总数、可用数、失败数、Ollama 候选和最近一次失败细节。前端优先展示这个结构化摘要，同时保留旧 attempts 兜底，兼容已有健康状态。对 Ollama 候选全部不可用的场景，我把提示改成检查本地服务是否启动、目标模型是否已拉取。最后我补了后端和前端测试，确认 fallback 成功、无候选、Ollama 可用和 Ollama/云端全失败这些路径都能正确展示。
