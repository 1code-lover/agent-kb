# 跨领域评测补充失败归因汇总

## 基本信息
- 类型：feature
- 日期：2026-08-11
- 相关模块：跨知识库真实评测、失败诊断、QA 诊断报告
- 相关文件：`scripts/diag_cross_domain_kb_eval.py`、`tests/scripts/test_diag_cross_domain_kb_eval.py`、`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v10.json`、`docs/project.md`

## 需求背景

跨领域评测已经覆盖答案、KB、文件、evidence 文本和多轮追问，但报告失败时主要依赖 `failed_case_ids`。这对后续泛化优化还不够，因为同样是失败，可能是答案词没命中、来源 KB 越界、来源文件偏移、evidence 文本不支撑，或者多轮中的某一轮失败。

这次工作的目标是让失败报告直接告诉我们“坏在哪个检查项、哪个 case、哪个 turn”，减少后续定位成本。

## 设计与实现方案

在 `scripts/diag_cross_domain_kb_eval.py` 中新增失败归因汇总：

- `failure_check_summary`：按失败检查项聚合，列出影响的 case ids 和 turn ids。
- `failure_case_summary`：按失败 case 聚合，列出该 case 的失败检查项和失败 turn。

实现上新增 `_failed_check_names()`、`_iter_check_results()` 和 `_summarize_failures()`。单轮 case 直接读取自身 `checks`；多轮 case 会进入每个 turn 的 `checks`，并忽略父级 `turns_passed` 这种包装性失败，避免归因被“多轮整体失败”遮住具体原因。

## 为什么选这个方案

失败归因放在 summary 层，能保持 case 明细结构不变，也不会影响现有通过率、tag summary 和 case source summary。对全绿报告来说，这两个字段就是空对象 / 空列表；一旦失败，就能直接用于 CI 日志、人工排查或后续质量看板。

多轮 case 优先展开 turn，是为了符合真实排查方式：用户关心的是第一轮铺垫失败，还是第二轮追问没接住，而不是只看到一个笼统的 `turns_passed=false`。

## 其他方案与为什么没选

一种方案是在每个 failed case 里手动读 `checks`。这不需要开发，但每次失败都要人工翻 JSON，无法按失败类型聚合。

另一种方案是把失败归入固定大类，例如 retrieval / generation / isolation。这个方向未来可以做，但当前已有 checks 粒度更精确，先基于 checks 汇总更稳。

## 风险与权衡

这次没有改变评测判定逻辑，只增加汇总字段，因此对现有门禁风险较低。主要权衡是报告字段更多，但这些字段只在 summary 里，且失败时信息密度更高。

如果后续 checks 名称调整，失败归因会跟随名称变化；这反而能保持和真实判定逻辑一致。

## 验证与结果

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`19 passed, 1 warning`
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v2.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v3.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v4.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v5.json --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v10.json`：`45/45 passed`，逐轮 `48/48 passed`，`failure_check_summary={}`，`failure_case_summary=[]`
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"`：`730 passed, 1 deselected, 35 warnings`
- `git diff --check`：通过

## 面试表达版本

我给跨领域评测报告补了失败归因汇总。之前失败时只能看到 failed case id，还要手动翻每个 case 的 checks。现在 summary 里会按失败检查项聚合，也会按 case 和 turn 聚合，尤其适合多轮追问场景。实现上我没有改判定逻辑，只把已有 checks 汇总成 `failure_check_summary` 和 `failure_case_summary`。真实 v10 评测仍是 `45/45`、逐轮 `48/48` 全通过，失败归因字段为空，说明它是纯诊断增强。
