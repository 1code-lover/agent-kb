# Source-backed Preview Grounding

## 基本信息
- 类型：feature
- 日期：2026-08-12
- 相关模块：知识库问答后处理、跨领域评测、evidence preview grounding
- 相关文件：`api/services/chat_service.py`、`tests/api/test_chat_service.py`、`docs/project.md`、`docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-test-report.md`

## 需求背景
v1-v6 全量跨领域评测里，`desktop-positive-preview` 和 `mixed-positive-preview` 的 source 已经命中目标文档，但模型会答到同一文档里的 passcode 或相邻事实，导致 preview 期望短语没有出现在最终答案里。这不是检索失败，而是答案生成阶段没有稳定抽取 source 原句。

## 设计与实现方案
`api/services/chat_service.py` 新增 preview 问题识别和 source-backed preview 回答兜底。当问题明确包含 `preview`、`chat returns sources` 或 `resolve this file` 等信号，且 source 文本里存在 preview 原句时，服务端优先返回该 source 原句。

同时调整 exact repair 的优先级：preview 问题已经得到 preview 原句后，不再被后续精确短语修复覆盖成同源 passcode 或其他相邻短语。

## 为什么选这个方案
这类失败已经有正确 source，继续调 prompt 或扩检索不会解决“最终答案答偏”的问题。把 preview 兜底放在服务端后处理，能用真实证据原句稳定回答，同时把影响范围限制在 preview 语义问题上。

## 风险与权衡
preview 兜底可能过度相信 source 中的 preview 句，因此只在问题明确询问 preview / source resolve 时触发，并要求候选句本身包含 `preview`。这避免普通 passcode、授权边界或表格问题被错误改写。

## 验证与结果
`/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_chat_service.py tests/scripts/test_prepare_embedding_model_cache.py tests/api/test_runtime_model_loading.py tests/test_embedding_model_diagnostics.py -q`：`77 passed, 7 warnings`。

Targeted preview 评测 `desktop-positive-preview` 和 `mixed-positive-preview`：`2/2 passed`。

v6 定向评测：`4/4 passed`、逐轮 `6/6 passed`。

当前分支 v1-v6 全量复跑：`37/49 passed`、逐轮 `42/54 passed`，比上一轮 `34/49` 又推进了一步。剩余问题集中在 image OCR boundary、UTF-16/extensionless 文本、桌面多轮 preview follow-up、一卡通适用范围和一个 3072 输入长度 API 错误。

## 面试表达版本
我在跨领域 RAG 评测里发现一个典型问题：检索已经命中正确文档，但模型最终答案答成了同一文档里的其他事实。对于 evidence preview 这类问题，我没有继续扩大检索，而是在服务端增加了 source-backed 原句兜底，只在问题明确询问 preview resolve 时触发。这样答案会优先使用证据里的 preview 原句，同时避免被后续精确短语修复改回 passcode。最后 targeted preview 样本从失败变成 2/2 通过，全量 v1-v6 也从 34/49 推进到 37/49。
