# 跨领域评测补充耗时诊断

## 基本信息
- 类型：feature
- 日期：2026-08-11
- 相关模块：跨知识库真实评测、QA 诊断报告、泛化优化
- 相关文件：`scripts/diag_cross_domain_kb_eval.py`、`tests/scripts/test_diag_cross_domain_kb_eval.py`、`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v10.json`、`docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-test-report.md`、`docs/project.md`

## 需求背景

跨领域评测已经能覆盖多知识库、长问题、多跳、多轮追问、来源文件 grounding、evidence 文本 grounding 和失败归因。但当报告全部通过时，我们仍然缺少一个关键视角：哪些 case 虽然通过了，但已经明显偏慢。

如果继续扩大真实业务样本，只看 `45/45 passed` 这类结果会掩盖性能风险。后续需要判断慢点来自某个 KB、某类负向隔离、某轮追问，还是单个边界样本，因此评测报告需要把耗时数据和 slow item 直接沉淀下来。

## 设计与实现方案

在 `scripts/diag_cross_domain_kb_eval.py` 中补充耗时采集与汇总：

- 单轮 case 记录 `duration_ms`。
- 多轮 case 记录整体 `duration_ms`，并汇总每一轮的 `turn_duration_total_ms`。
- summary 新增 `duration_summary`，包含 case/turn 总耗时、平均耗时、最慢 case/turn、慢 case 列表和慢 turn 列表。
- CLI 新增 `--slow-threshold-ms`，默认阈值为 `5000ms`，便于不同机器或 CI 环境调整慢用例判定口径。

测试侧新增 `test_summarize_includes_duration_diagnostics`，验证慢 case、慢 turn、最大耗时和平均耗时都会被正确汇总。

## 为什么选这个方案

耗时诊断放在评测脚本本身，而不是另写外部日志分析脚本，是因为它能和已有 `case_source_summary`、`tag_summary`、`failure_check_summary` 放在同一份 JSON 报告里。这样后续无论是人工查看、CI 门禁还是质量看板，都可以直接消费结构化字段。

同时保留 `--slow-threshold-ms`，避免把当前本机的性能口径写死。默认 `5000ms` 足够突出明显异常，同时不会因为模型偶发波动让报告噪声过高。

## 其他方案与为什么没选

一种方案是只在命令行输出总耗时。这能快速看趋势，但无法定位慢 case，也无法复盘历史报告。

另一种方案是把超过阈值直接判失败。当前没有这么做，因为本轮目标是诊断增强，不是引入新的阻断门禁。先观察慢项分布，再决定是否把性能阈值升级成 CI 失败条件，会更稳。

## 风险与权衡

这次改动不改变问答判定逻辑，也不影响已有通过率计算，主要风险是报告字段增多。为降低阅读成本，耗时信息集中在 `duration_summary`，case 明细中只增加必要的 `duration_ms`。

真实 v10 报告显示唯一超过 `5000ms` 的 slow item 是 `grain-negative-utf8-exact-boundary`。这说明下一步性能优化可以先聚焦负向隔离边界样本，而不是盲目改动整个检索链路。

## 验证与结果

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`20 passed, 1 warning`
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v2.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v3.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v4.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v5.json --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v10.json`：`45/45 passed`，逐轮 `48/48 passed`
- v10 `duration_summary`：`case_total_ms=73247.147`、`case_avg_ms=1627.714`、`turn_avg_ms=1525.958`，最慢 case/turn 和唯一 slow item 均为 `grain-negative-utf8-exact-boundary`
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"`：`731 passed, 1 deselected, 35 warnings`
- `/opt/miniconda3/envs/agent-kb/bin/python -m json.tool docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v10.json >/dev/null`：通过
- `git diff --check`：通过

## 面试表达版本

我给跨领域真实评测补了一层耗时诊断。之前报告能说明哪些 case 通过、哪些失败、失败在哪个检查项，但全绿时看不出性能风险。现在每个 case 和 turn 都会记录耗时，summary 里会直接给出平均值、最大值和 slow item。真实 v10 评测仍是 `45/45`、逐轮 `48/48` 全通过，同时发现唯一慢项是 `grain-negative-utf8-exact-boundary`，这让下一步优化可以从具体边界样本入手，而不是泛泛调整整个问答链路。
