# 2026-08-11 Feature: 跨领域评测 tag 维度扩容

## 基本信息

- 类型：feature
- 日期：2026-08-11
- 相关模块：跨知识库评测、真实业务样本、测试报告
- 相关文件：`scripts/diag_cross_domain_kb_eval.py`、`tests/scripts/test_diag_cross_domain_kb_eval.py`、`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v2.json`、`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v7.json`、`docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-test-report.md`、`docs/project.md`

## 需求背景

前一轮把跨领域评测扩成了默认基线加外部真实样本，但汇总仍然只按 focus 和来源看总通过率。随着样本继续增长，项目真正需要的不是“总分继续为 100%”，而是能按长问题、多跳、OCR、扫描件、拒答和跨库隔离这些维度分别回归，尽早发现泛化短板。

同时，外部样本也需要继续补更接近真实提问习惯的场景，比如长问题、组合问题和带上下文噪声的问题，这样门禁才更像产品的真实使用面。

## 设计与实现方案

`scripts/diag_cross_domain_kb_eval.py` 的每条 case 新增可选 `tags` 字段，`evaluate_case()` 会把 tags 写回结果，`summarize()` 则新增 `tag_summary`，按 tag 统计总数、通过数、失败数和通过率。旧的 `focus_summary` 和 `case_source_summary` 保持不变。

同时新增 `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v2.json`，补了 6 条真实样本，覆盖粮仓长问题与多跳、mixed batch 多跳、扫描 PDF 规则、OCR 负向隔离和拒答类跨库隔离。

测试侧补充了 `tests/scripts/test_diag_cross_domain_kb_eval.py`，验证 tags 透传、tag 汇总、旧结构兼容和外部样本读取仍然正常。

## 为什么选这个方案

把维度切片放进评测脚本，比后面单独拿 JSON 再做一次离线分析更稳。这样每次跑真实评测时，报告天然就有可回归的维度视图，不会只剩一个总通过率。

`tags` 是轻量扩展，不会破坏已有 case 格式，也不要求所有历史样本补齐元数据；新增样本可以逐步标注，成本低。

## 其他方案与为什么没选

推断：可以单独做一层报表分析脚本，把 v6/v7 JSON 再聚合出 tag 维度，但那样每次看结果都要跑第二层工具，门禁链条更长。

推断：也可以把所有维度直接拆成多个独立脚本，但这会让默认门禁碎片化，反而不利于统一回归。

## 风险与权衡

新增 `tags` 字段会让 case schema 稍微变宽，但旧 case 不填也能跑，风险可控。`tag_summary` 依赖样本标注质量，所以我只给确实能代表门禁意义的样本打标签，避免把一个 case 随意挂太多无意义标签。

外部样本继续扩充后，可能出现语义相近但口径漂移的问题。当前通过真实 API 复跑和按 tag 汇总，能尽早暴露这类问题。

## 验证与结果

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`12 passed, 1 warning`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v2.json --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v7.json`：`33/33 passed`。
- 默认基线 `23/23`，外部追加样本 v1 `4/4`、v2 `6/6`；`positive_total=20`、`negative_total=12`、`contract_total=1`，三类通过率均为 `100%`。
- `tag_summary` 中 `long-question`、`multi-hop`、`ocr`、`scan`、`refusal`、`cross-kb-isolation` 也都保持 `100%`。

## 面试表达版本

我把跨领域评测从“只看总通过率”推进到“按 tag 回归”。做法很直接：给 case 增加 `tags`，在脚本汇总里新增 `tag_summary`，这样长问题、多跳、OCR、扫描件和跨库拒答都能单独盯住。然后我补了一组 v2 真实样本，把粮仓长问题、mixed batch 多跳、扫描 PDF 和拒答隔离都纳进来。最后跑真实 API 验证，默认基线加 v1/v2 追加样本一共 33 条，全部通过，而且各个 tag 切片也都稳定通过。
