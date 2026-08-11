# 跨领域评测补充 Evidence 文本级校验

## 基本信息
- 类型：feature
- 日期：2026-08-11
- 相关模块：跨知识库真实评测、证据 grounding、QA 诊断报告
- 相关文件：`scripts/diag_cross_domain_kb_eval.py`、`tests/scripts/test_diag_cross_domain_kb_eval.py`、`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v5.json`、`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v10.json`、`docs/project.md`

## 需求背景

跨领域评测已经能校验答案、来源 KB、来源文件和多轮追问，但仍有一个剩余风险：模型可能答对，source 文件也正确，可返回的 evidence 片段本身却不包含支撑答案的依据。对于 RAG 系统来说，这会影响引用可信度和可解释性。

这次工作的目标是把 evidence 正文也纳入门禁，证明答案背后的 `sources` / `evidence` 文本确实包含目标依据，而不是只依赖模型最终回答。

## 设计与实现方案

在 `scripts/diag_cross_domain_kb_eval.py` 里新增 `_source_payload_text()`，只合并 API 返回的 `sources` 和 `evidence`，不包含 `answer`。case 格式新增：

- `required_source_text_terms`：证据正文必须包含的依据片段。
- `forbidden_source_text_terms`：证据正文不得泄漏的片段。

评测结果新增 `source_text_preview`，checks 中新增 `required_source_text_hit` 和 `forbidden_source_text_clean`。旧的 `forbidden_terms` 仍用于 answer + sources + evidence 的整体泄漏检查，新字段专门用于 evidence 正文本身。

外部样本新增 `cross-domain-extra-cases-v5.json`，覆盖桌面 evidence preview、扫描 PDF OCR fallback、图片 OCR 边界和 mixed batch rollback approval。真实评测输出到 `cross-domain-kb-eval-report-v10.json`。

## 为什么选这个方案

把 answer 和 evidence 分开检查，是因为答案可以是模型改写后的自然语言，而 evidence 应该代表真实检索依据。比如图片 OCR 样本里，答案会把 `Knowledge Base` 改写成小写 `knowledge base`，但 evidence 原文保留大小写；如果混在一起检查，就无法区分是模型表述变化还是证据缺失。

沿用现有跨领域脚本，可以继续复用外部 case 文件、多轮 turns、source 文件断言和 tag summary，避免新增一套平行评测入口。

## 其他方案与为什么没选

一种方案是继续把 evidence 关键词放进 `forbidden_terms` / `expected_terms`。它实现最少，但 `expected_terms` 只看答案，`forbidden_terms` 又是泄漏检查，不适合表达“证据正文必须包含依据”。

另一种方案是用 LLM 裁判判断 evidence 是否支撑答案。它更灵活，但不稳定、成本高，而且当前门禁更需要确定性的可复跑检查。

## 风险与权衡

证据文本断言会更敏感，尤其 OCR 文本存在大小写、换行和识别差异。为降低误报，v5 样本使用真实 API 返回的 evidence 原文片段，并把这层定位为高置信 grounding gate，而不是泛化语义等价裁判。

这仍然不能替代表格结构、版面顺序或完整引用精确率评估；它只是把跨领域诊断从“答对 + 来源对”推进到“证据文本也能支撑答案”。

## 验证与结果

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`18 passed, 1 warning`
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v2.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v3.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v4.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v5.json --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v10.json`：`45/45 passed`，逐轮 `48/48 passed`，`evidence-text` 为 `4/4`
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"`：`729 passed, 1 deselected, 35 warnings`
- `git diff --check`：通过

## 面试表达版本

我给跨知识库评测补了一层 evidence 文本级校验。之前可以证明答案答对、KB 对、文件对，但还不能证明返回的证据片段本身支撑答案。我新增了 `required_source_text_terms` 和 `forbidden_source_text_terms`，只检查 sources/evidence 正文，不把模型最终答案算进去。这样能区分模型自然语言改写和真实证据缺失。最后 v10 真实评测达到 `45/45`，逐轮 `48/48`，其中 evidence-text 切片 `4/4` 通过。
