# 跨领域评测系统性故障归因

## 基本信息
- 类型：feature
- 日期：2026-08-12
- 相关模块：跨知识库真实问答评测、报告汇总、模型故障诊断
- 相关文件：`scripts/diag_cross_domain_kb_eval.py`、`tests/scripts/test_diag_cross_domain_kb_eval.py`、`docs/project.md`、`docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-test-report.md`

## 需求背景
跨领域 v11 全量试跑时，当前模型 `qwen-plus-2025-07-28` 已经返回免费额度耗尽，导致 49 个 case 里只有 contract 用例通过。原报告能看到大量 `http_status_ok` 失败，但不够直接说明这是模型/API 层系统性故障，容易被误读为多知识库、跨领域泛化整体退化。

## 设计与实现方案
在 `summarize` 中新增 `systemic_failure_summary`。它会展开 multi-turn 的每个 turn，统计 `http_status_ok` 失败比例，并从 `error`、`response_message`、`answer_preview` 中识别 quota、401、model_not_found、timeout/network 等模型/API 层错误。只有当 turn 总量、HTTP 失败数量和失败比例同时达到阈值时，才标记 `suspected=true` 和 `reason=model_or_api_unavailable`。

## 为什么选这个方案
这次选择只增强报告解释层，不改变用例执行、exit code 或 pass/fail 判定。这样既能保持既有 v10/v6 报告兼容，也能让 v11 这类模型额度故障有明确归因。按 turn 粒度展开 multi-turn，可以避免一个多轮 case 被粗略算成单点失败。

## 其他方案与为什么没选
推断：可以在评测开始前做一次模型预检，失败就直接中止全量评测，但这会减少报告中对实际失败面的可见性。也可以在遇到连续失败时 fail fast，不过当前脚本的价值之一是留下完整矩阵报告，所以本轮先做非侵入式归因。

## 风险与权衡
系统性故障识别是启发式判断，不替代具体错误日志。为降低误判，只有大面积 `http_status_ok` 失败且错误类型明确时才标记 `suspected=true`；少量 timeout 或单点 HTTP 失败仍会保留为普通 case 失败。

## 验证与结果
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`23 passed, 1 warning`。
- 对既有 `cross-domain-kb-eval-report-v11.json` 重新汇总，得到 `suspected=true`、`dominant_error_kind=quota_exhausted`、`http_failure_total=53`、`http_failure_rate=0.9815`。

## 面试表达版本
我在跨知识库真实评测里补了一个系统性故障归因层。之前模型额度耗尽会让几十个业务 case 全部失败，看起来像知识库泛化突然崩了，但其实是模型/API 不可用。我没有改变评测的通过标准，而是在 summary 里按 turn 粒度统计 HTTP 失败，并识别 quota、401、模型不存在和网络超时等错误。这样报告既保留完整矩阵，又能一眼判断是环境问题还是业务质量问题。
