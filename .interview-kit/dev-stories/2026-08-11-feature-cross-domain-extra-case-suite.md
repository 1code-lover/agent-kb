# 2026-08-11 Feature: 跨领域评测外部样本追加能力

## 基本信息

- 类型：feature
- 日期：2026-08-11
- 相关模块：跨知识库评测、真实业务样本、测试报告
- 相关文件：`scripts/diag_cross_domain_kb_eval.py`、`tests/scripts/test_diag_cross_domain_kb_eval.py`、`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json`、`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6.json`

## 需求背景

跨领域诊断已经从 6 条扩到 23 条，但这些用例都写在 Python 的 `DEFAULT_CASES` 里。继续扩大真实业务验证面时，如果每次新增样本都要改脚本代码，会让评测数据和评测逻辑耦合在一起，也不利于后续按业务资料集沉淀独立样本包。

这次目标是让默认基线保持稳定，同时允许追加外部真实样本文件，并在报告里看清楚每条结果来自默认集还是外部样本。

## 设计与实现方案

`scripts/diag_cross_domain_kb_eval.py` 新增外部用例读取能力：用例文件可以是 JSON list，也可以是 `{ "cases": [...] }` 对象格式。CLI 增加可重复的 `--extra-cases`，用于把外部样本追加到当前用例集；`--cases` 仍保留替换完整用例集的语义。

每条用例会补充 `case_source` 字段，默认基线标记为 `default`，外部样本标记为文件路径。报告汇总新增 `case_source_summary`，用于同时看默认基线和外部样本的通过率。脚本还加入重复 case id 检查，避免追加多个文件时相同 id 让报告难以追踪。

本轮新增 `cross-domain-extra-cases-v1.json`，追加 4 条真实业务样本：粮仓适用对象、一卡通收储库点，以及两条跨库负向隔离问题。运行后生成 `cross-domain-kb-eval-report-v6.json`，默认 23 条和外部 4 条合计 27 条全部通过。

同时修正了一个评测误报口径：默认负向用例的 `forbidden_terms` 不再包含题目自身已经出现的标题词，避免模型拒答时复述题目被误判为跨库泄漏。

## 为什么选这个方案

这个方案把“评测框架”和“业务样本集”拆开。默认基线继续留在脚本里，保证当前门禁开箱可跑；新增业务样本则可以独立成 JSON 文件，后续按行业、资料集或客户场景逐步追加，不需要每次都改 Python 代码。

`case_source` 和重复 id 检查是为了让扩样本后仍然可审计：失败时能定位到具体样本文件，多个样本文件也不会因为 id 冲突把报告搞混。

## 其他方案与为什么没选

推断：可以把所有默认用例都迁移到 JSON 文件，但这会扩大本轮改动范围，也会改变既有 CLI 的开箱行为。当前阶段先保留内置基线，只给新增样本提供外部入口。

推断：也可以只支持 `--cases` 替换整套用例，但这样每次想跑“默认门禁 + 新样本”都需要手工复制 23 条默认用例，维护成本高且容易漂移。

## 风险与权衡

外部样本文件让评测扩展更灵活，但也会带来样本质量不一致的风险。当前通过重复 id 检查、单测覆盖和报告中的 `case_source_summary` 降低风险；后续如果外部样本继续变多，还应该补更严格的 schema 校验。

负向用例的 forbidden term 不能只是题目复述，这是这次真实运行暴露出来的口径问题。后续新增负向样本时，需要优先禁止“答案短语或证据短语”，而不是禁止题目里已经出现的对象名。

## 验证与结果

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`12 passed, 1 warning`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6.json`：`27/27 passed`。
- v6 报告中默认基线 `23/23`，外部追加样本 `4/4`；`positive_total=16`、`negative_total=10`、`contract_total=1`，三类通过率均为 `100%`。
- `git diff --check`：通过。

## 面试表达版本

我在扩跨领域评测时发现，继续把真实样本写死在 Python 默认列表里会让数据和逻辑越绑越紧。于是我给诊断脚本加了外部样本追加能力，支持 JSON list 和 `{cases: [...]}` 两种格式，也支持多次传 `--extra-cases`。为了让结果可审计，我给每条用例加了 `case_source`，报告里按来源汇总，并且重复 case id 会直接失败。最后我用 4 条新的真实业务样本把默认 23 条扩到 27 条，真实 API 评测跑到 `27/27 passed`，同时修掉了一个负向用例把题目复述误判成泄漏的口径问题。
