# 三层 RAG 回归评测集合扩展与重测闭环

## 基本信息
- 类型：feature
- 日期：2026-08-20
- 相关模块：RAG semireal 评测、fixture 生成脚本、数据集 schema、测试报告文档
- 相关文件：`scripts/build_eval_v7_holdout.py`、`scripts/build_eval_v8_layered.py`、`tests/fixtures/rag_quality/eval_v7/schema.json`、`tests/fixtures/rag_quality/eval_v7/cases.json`、`tests/fixtures/rag_quality/eval_v8_main/schema.json`、`tests/fixtures/rag_quality/eval_v8_main/cases.json`、`tests/fixtures/rag_quality/eval_v8_hard/schema.json`、`tests/fixtures/rag_quality/eval_v8_hard/cases.json`、`tests/fixtures/rag_quality/eval_layered_suite.json`、`tests/test_rag_quality_eval_dataset_v7.py`、`tests/test_rag_quality_eval_dataset_v8.py`、`docs/20260820-layered-rag-eval-refresh/20260820-layered-rag-eval-refresh-spec.md`、`docs/20260820-layered-rag-eval-refresh/20260820-layered-rag-eval-refresh-test-plan.md`、`docs/20260820-layered-rag-eval-refresh/20260820-layered-rag-eval-refresh-test-report.md`

## 需求背景
这轮工作要把本地多知识库 RAG 评测集从“单层一把梭”的方式拆成更适合工程落地的三层结构：一层做环境重建和 CI 冒烟，一层做发布前主 gate，一层专门抓边界 bug。核心诉求不是单纯堆题量，而是把 QA 准确率、multi-source merge、refusal、scope isolation、preview grounding 这些真正影响发布决策的能力单独拉出来，同时给相似文档混淆、chunk 边界、证据不足拒答等 hard case 留出专门的暴露空间。

## 设计与实现方案
1. 我先保留 `eval_v7` 作为 Layer 1 / Smoke，并补齐 `scripts/build_eval_v7_holdout.py`、`tests/fixtures/rag_quality/eval_v7/*` 和 `tests/test_rag_quality_eval_dataset_v7.py`，让 24 条小而全的 holdout 集可以直接作为 Docker / CI 快速回归集。
2. 新增 `scripts/build_eval_v8_layered.py`，把方案 A 的三层结构落到代码里：Main 层产出 90 条主回归 case，Hard 层产出 36 条挑战 case，并写出 `tests/fixtures/rag_quality/eval_layered_suite.json` 统一描述三层套件。
3. Main 层在 `tests/fixtures/rag_quality/eval_v8_main/` 里用 schema 强化 coverage gate，确保 modality、difficulty、answer_style、category、preview_required、no_evidence、weak signal 等维度都达标；Hard 层在 `tests/fixtures/rag_quality/eval_v8_hard/` 里按 similar_document_confusion、stale_version_conflict、chunk_boundary、paraphrase_rewrite、evidence_insufficient、scope_isolation_trap 六类 challenge 等量展开。
4. 新增 `tests/test_rag_quality_eval_dataset_v8.py` 做 fixture 级别断言，保证 layered suite 的结构、分布和 gate 约束在本地就能被快速校验，不必每次都先跑完整 semireal。
5. 在 `docs/20260820-layered-rag-eval-refresh/` 下补齐 spec、test-plan、test-report，明确 grounding / evidence / preview / scope 四个指标的定义，并把 Smoke / Main / Hard 的实测结果、Hard 失败画像和下一轮优化方向写成可交付、可面试复述的文档。

## 为什么选这个方案
我选三层结构而不是继续往单一回归集里加题，主要是因为这更符合真实发布流程：Smoke 负责“系统能不能跑起来”，Main 负责“主路径质量能不能放行”，Hard 负责“边界问题能不能被稳定复现”。这样做的好处是，Main 可以保持代表性和稳定性，不会因为把大量 adversarial 样本塞进去而变成噪声 gate；Hard 又能保留足够攻击性的 case，专门暴露 refusal、证据契约和 preview 问题。对工程团队来说，这比单看一个总体 pass_rate 更可执行，也更容易解释为什么某些指标全是 1.0、而另一些问题仍然需要继续修。

## 其他方案与为什么没选
1. 把所有新增题都合进一个大而全的主回归集：没选，因为会把发布 gate 和边界挑战混在一起，导致回归不稳定，出了问题也难定位。
2. 继续优先补 OCR 文档和 OCR 题：没选，因为当前更缺的是围绕已有事实点构造 grounding / evidence / scope / preview 变体题，而不是继续堆模态数量。
3. 只写 fixture、不补文档：没选，因为这轮工作本身就带有“面试可讲解”的目标，如果不把指标定义、设计意图和 Hard 失败解释写出来，后续很容易只剩下“Main 全是 1.0”的表面结论。

## 风险与权衡
最大的权衡在于 Main 和 Hard 的边界：如果 Main 放太多对抗性 case，发布 gate 会波动；如果 Hard 被改得太简单，又失去抓边界 bug 的价值。这轮我把稳定回归需求优先留给 Main，把难而不稳的挑战留给 Hard，因此 Main 90/90 全过、Hard 20/36 通过是一个符合设计意图的结果。另一个风险是 story 和报告容易写成“看起来全绿”，所以我在测试报告里明确保留了 Hard 的失败分布，并把 refusal、evidence contract、source_count contract 识别为当前主瓶颈，而不是掩盖掉这些问题。

## 验证与结果
实际执行并记录了以下验证：
- `python scripts/build_eval_v8_layered.py`
- `python scripts/validate_rag_quality_fixtures.py --eval-cases tests/fixtures/rag_quality/eval_v8_main/cases.json --eval-schema tests/fixtures/rag_quality/eval_v8_main/schema.json --print-eval-summary`
- `python scripts/validate_rag_quality_fixtures.py --eval-cases tests/fixtures/rag_quality/eval_v8_hard/cases.json --eval-schema tests/fixtures/rag_quality/eval_v8_hard/schema.json --print-eval-summary`
- `python -m pytest tests/test_rag_quality_eval_dataset_v8.py -q`，结果 `7 passed`
- `python -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v7/cases.json --schema tests/fixtures/rag_quality/eval_v7/schema.json --output-dir temp/eval-v7-smoke`
- `python -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v8_main/cases.json --schema tests/fixtures/rag_quality/eval_v8_main/schema.json --output-dir temp/eval-v8-main`
- `python -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v8_hard/cases.json --schema tests/fixtures/rag_quality/eval_v8_hard/schema.json --output-dir temp/eval-v8-hard`

结果是：Smoke 24/24 全过、Main 90/90 全过、Hard 20/36 通过；Hard 的 `scope_pass_rate = 1.0`，但 `evidence_hit_rate = 0.8333`、`source_count_match_rate = 0.7222`、`forbidden_term_clean_rate = 0.8333`，说明最大瓶颈已经明确集中在 refusal 和 evidence/source_count 契约，而不是 scope leakage。

## 面试表达版本
我把原来的 RAG 评测集拆成了三层：Smoke 做环境和 CI 冒烟，Main 做发布前主 gate，Hard 专门抓边界 bug。这样一来，主路径评测可以保持稳定，边界问题又不会被“平均掉”。这轮我落了 24 条 Smoke、90 条 Main、36 条 Hard，并把 schema、fixture 校验、pytest 和 semireal 重测全部跑通。结果是 Smoke 和 Main 都全过，但 Hard 明确暴露出 refusal、evidence contract 和 source_count contract 的瓶颈，所以这套评测既能做工程 gate，也能指导下一轮系统优化。
