# 模型选择即时探活

## 基本信息
- 类型：feature
- 日期：2026-08-12
- 相关模块：模型配置、模型健康状态、fallback 探活摘要
- 相关文件：`api/services/model_service.py`、`tests/api/test_model_service.py`、`docs/project.md`、`docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-test-report.md`

## 需求背景
在跨领域 v6 试跑时，真实模型链路暴露出一个体验问题：用户切换模型后，配置保存成功就会把 `model_health` 写成 `healthy`，但真实问答可能立刻因为 401、额度耗尽或模型不存在失败。这样前端看到的是“模型健康”，实际下一次问答才暴露问题，恢复路径不够可信。

## 设计与实现方案
在 `select_model` 中新增选择后的轻量探活：云端兼容模型复用 `_check_openai_compatible`，Ollama 复用 `_check_ollama_model`。探活成功时写入 `healthy`，失败时写入 `unavailable`，并保留 `last_error_kind`、`last_error`、`fallback_attempts` 和 `fallback_attempt_summary`，让现有前端健康摘要可以直接展示原因。自动 fallback 路径已经探活过候选时，通过 `probe_result` 参数把结果传入 `select_model`，避免成功切换时重复请求。

## 为什么选这个方案
项目已经有成熟的候选探活、错误分类和前端摘要展示结构，所以最小风险的做法是复用现有机制，而不是新增一套选择模型专用状态。这样 `/api/model/select` 的语义仍然是“保存当前配置”，但保存后立刻给出真实可用性，不会把坏配置伪装成健康状态。

## 其他方案与为什么没选
推断：可以让前端在选择后额外调用一个 test endpoint，但这会让桌面端和 Agent 页都要补流程，并且容易出现保存成功但探活请求丢失的分裂状态。也可以只在下一次 chat query 失败时更新状态，但这正是本次要修掉的延迟暴露问题。

## 风险与权衡
选择模型现在会多一次轻量网络请求，坏供应商可能让选择操作等待到探活超时。为控制成本，fallback 自动切换会复用已完成的候选探活结果；普通手动选择则用已有短探活逻辑，换来更准确的健康状态。

## 验证与结果
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py -q`：`20 passed, 2 warnings`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py tests/api/test_settings_routes.py tests/api/test_chat_service.py -q`：`58 passed, 8 warnings`。
- `node --test webapp/src/domain/modelHealth.test.js`：`10 passed`。

## 面试表达版本
我修了一个模型配置恢复路径里的可信度问题：过去用户选择模型后，只要配置保存成功就显示 healthy，但真实调用可能因为凭据或额度失败。我在选择模型后接入轻量探活，把失败直接写进 `model_health`，并复用现有的 fallback 探测摘要给前端展示。自动 fallback 已经探活过候选时，我把结果传给选择逻辑复用，避免重复网络请求。这个改动让“模型切换成功”和“模型真实可用”不再混在一起，排障时用户能马上看到是 401、额度还是模型不可用。
