# 真实 Ollama fallback 暴露并修复切换来源丢失

## 基本信息
- 类型：bug
- 日期：2026-08-15
- 相关模块：模型健康状态、Agent fallback、Ollama 真实 E2E
- 相关文件：`api/services/model_service.py`、`tests/api/test_model_service.py`、`docs/20260810-model-fallback-desktop-e2e/artifacts/agent-ollama-fallback-e2e-report-20260815.json`

## 问题现象
在真实执行“不可达云端模型 -> 动态发现 Ollama -> 本地模型回答”时，切换成功、最终模型和 `fallback_to` 都正确，但 API 与报告中的 `fallback_from` 是 `null`。这会让前端只能提示切换目标，无法明确说明从哪个失败模型切换而来。

## 根因分析
`attempt_model_fallback` 在开始时把原模型写入健康状态，但候选探活成功后会调用 `select_model`。`select_model` 为手工选择场景重置了 `fallback_from=None` 和 `fallback_to=None`；随后写入 `fallback_applied` 时只恢复了 `fallback_to`，没有把之前的原模型快照写回，导致来源丢失。

## 解决方案
在最终 `fallback_applied` 健康状态更新中显式写入 `fallback_from=base_status["fallback_from"]`。同时在已有 fallback 选择测试中增加完整 provider/model/api_base 断言，保证以后修改 `select_model` 或健康状态合并逻辑时不能再次丢失来源。

此外安装并启动了官方 Ollama 0.32.13，拉取 `qwen2.5:0.5b`，生成包含直接 Agent 推理和动态 fallback 两例的真实 JSON 报告。修复后的报告同时包含完整 `fallback_from`、`fallback_to`、候选摘要和明确 step 文案。

## 为什么选这个方案
`base_status` 是 fallback 开始时捕获的权威原模型快照，最终状态写入时恢复它只改变一处合并字段，不需要改变 `select_model` 对手工切换的重置语义。相比让 `select_model` 判断调用上下文，这个修复更局部，也不会让普通手工选择错误继承旧 fallback 状态。

## 其他方案与为什么没选
1. **取消 `select_model` 对 fallback 字段的重置（推断）**：会让手工切换后仍显示上一次自动切换，产生陈旧提示。
2. **从当前 session 反推原模型（推断）**：fallback 已经更新 session，反推容易得到新模型；`base_status` 已有精确快照，无需增加状态读取。

## 验证与结果
- 新增 `fallback_from` 断言后初次执行：`1 failed`，实际值为 `None`。
- 修复后定向测试：`1 passed`。
- Python 非 slow 全量：`790 passed, 1 deselected, 35 warnings`。
- Electron：`64 passed`；Web Vite build 通过。
- 最新 `build:mac` 和 `verify:package` 通过，packaged `model_service.py` 包含修复。
- 真实 Ollama 报告：`run_passed=true`、`2/2 cases passed`。
  - 直接 Agent 推理：`OLLAMA_AGENT_DIRECT_OK`。
  - 坏云端模型自动切换：`OLLAMA_AGENT_FALLBACK_OK`，最终 `Ollama / qwen2.5:0.5b`，`candidate_count=1`，来源 `BadCloud / offline-model`、目标 Ollama 均完整。
- 正式 Apple 签名、公证和安装后回归仍因外部凭证缺失未执行。

## 面试表达版本
我在做真实 Ollama fallback E2E 时发现，模型已经成功切换并回答，但界面需要的切换来源却是空的。根因是候选成功后复用了手工选模型函数，它会清空 fallback 字段，而最终状态只写回了目标模型。我没有改变手工切换语义，而是在自动 fallback 的最终写入中恢复开始时捕获的原模型快照。随后我用先失败后通过的回归测试、真实 Ollama 两条链路、全量测试和重新打包验证了修复。
