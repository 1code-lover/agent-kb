# 跨领域评测 Preflight

## 基本信息
- 类型：feature
- 日期：2026-08-12
- 相关模块：跨知识库真实问答评测、模型/API 故障诊断、评测入口
- 相关文件：`scripts/diag_cross_domain_kb_eval.py`、`tests/scripts/test_diag_cross_domain_kb_eval.py`、`docs/project.md`、`docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-test-report.md`

## 需求背景
跨领域评测已经扩到 v6，但真实模型额度、凭据和可用性并不总是稳定。之前如果模型/API 已经不可用，脚本仍会串行跑完整矩阵，既耗时，也会生成大量业务 case 失败，看起来像知识库泛化整体退化。上一轮已经能在 summary 中识别系统性故障，这一轮把识别前移到评测入口。

## 设计与实现方案
新增 `--preflight` 参数。开启后，脚本先用首个 case 进行一次真实 chat query 探活；如果失败检查项显示 `http_status_ok=false`，并且错误可归类为 quota、401、model_not_found、network/timeout 等模型/API 层问题，就生成带 `preflight.aborted=true` 的报告并提前返回。preflight 通过时继续执行完整 case 集；默认不开启，保持历史命令兼容。

## 为什么选这个方案
首个 case 真实走同一条 RAG API 链路，比单独 ping 模型更接近实际评测环境；同时它只在显式 `--preflight` 下生效，不会改变已有门禁行为。失败报告仍保留 `summary`、`cases` 和 `systemic_failure_summary`，所以后续自动化和人工排障都能复用同一份结构。

## 其他方案与为什么没选
推断：可以在运行过程中连续失败后 fail fast，但那会让报告停在不确定的位置，而且仍要消耗多个 case。也可以只做模型 provider 的 chat completions ping，但这不能覆盖知识库 API、索引加载和 chat query 路由，因此不如首个真实 case 有代表性。

## 风险与权衡
preflight 使用首个 case，因此如果首个 case 本身设计过严但 HTTP 正常，它不会中止，只会继续跑完整矩阵；这是刻意保守的选择。它只对模型/API 层错误提前中止，避免把业务断言失败误判成环境故障。

## 验证与结果
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`25 passed, 1 warning`。
- 新增测试覆盖 preflight 在模型/API 故障时提前中止，以及 preflight 通过后继续执行完整用例集。

## 面试表达版本
我给跨知识库评测加了一个可选 preflight。以前模型额度耗尽时，脚本还会跑完整矩阵，最后生成一堆业务失败，很容易误判。我让脚本先用首个真实 case 走一遍 chat query，如果已经是 quota、401、模型不存在或网络错误，就提前写出结构化报告并中止。默认行为不变，所以原来的 CI 和历史报告兼容；需要排查模型稳定性时才显式打开。
