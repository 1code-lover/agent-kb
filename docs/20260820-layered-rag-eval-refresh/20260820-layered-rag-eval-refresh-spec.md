# 20260820 Layered RAG Eval Refresh Spec

## 1. 背景与目标

本次采用“方案 A：最实用的扩法”扩展 semireal RAG 测评集合，目标不是把所有难题都塞进同一个回归集，而是拆成三层：

1. **Layer 1 / Smoke**：24 条，用于环境重建、Docker 验证、CI 快速回归与冒烟检查。
2. **Layer 2 / Main**：**93 条**，作为版本发布前的主 gate，重点覆盖 QA 准确率、multi-source merge、refusal、scope isolation、preview grounding、negative-contract drift。
3. **Layer 3 / Hard**：36 条，专门用于抓边界 bug，不要求 1.0，但要求稳定暴露相似文档混淆、新旧版本冲突、chunk 边界、改写、证据不足拒答、scope trap 等问题。

截至 **2026-08-27**，本次交付要求已经收敛为：
- Smoke 层固定 **24 条**；
- Main 层落在 **80~120 条**区间内，当前固定为 **93 条**；
- Hard 层落在 **30~50 条**区间内，当前固定为 **36 条**；
- 扩展完成后重新执行 fixture 校验、pytest 与 semireal 评测，并输出可复核测试报告。

## 2. 指标定义

### 2.1 scope
`scope_pass_rate` 检查请求作用域和实际生效作用域是否一致，重点关注：
- `requested_scope_type`
- `requested_kb_ids`
- `effective_scope_type`
- `effective_kb_ids`
- `is_default_deny_applied`
- `isolation_level`

它回答的问题是：**这次检索有没有串库、越权、越过知识库隔离边界。**

### 2.2 evidence
`evidence_hit_rate` 检查回答返回的 `sources / evidence` 是否命中预期文档：
- 有答案的 case：必须命中 `required_evidence_docs` 或 `expected_doc`；
- 无答案的 case：如果 `expected_source_count = 0`，则要求 `sources / evidence` 都为空。

它回答的问题是：**答案引用的证据文档是否正确。**

### 2.3 preview
`preview_resolvable_rate` 检查 evidence preview 能否定位到支持答案的片段，通常通过 `preview_terms` 命中 preview excerpt 来验证。

它回答的问题是：**用户点开引用来源时，能不能直接看到真正支撑答案的内容。**

### 2.4 grounding
当前项目里 grounding 更像上位概念，不是单独一列 summary 指标。它主要由以下指标共同体现：
- `average_keypoint_coverage`
- `evidence_hit_rate`
- `preview_resolvable_rate`
- `source_count_match_rate`
- `forbidden_term_clean_rate`

它回答的问题是：**答案是否被真实证据约束，而不是模型脑补。**

## 3. 三层数据集设计

### 3.1 Layer 1: Smoke
- 路径：`tests/fixtures/rag_quality/eval_v7/`
- 数量：24
- 作用：保留小而全的基础哨兵集合，用于环境重建、Docker/CI 冒烟和快速回归。

当前分布：
- modality：markdown 8 / pdf 8 / image_ocr 8
- difficulty：simple 6 / medium 9 / complex 9
- answer_style：fact 9 / policy 9 / comparison 3 / refusal 3

### 3.2 Layer 2: Main
- 路径：`tests/fixtures/rag_quality/eval_v8_main/`
- 数量：**93**
- 构成：在既有主干 case 基础上，继续补齐 layered main 的 refusal / negative-contract / history-grounded 覆盖；2026-08-27 又追加了 **3 条跨模态 negative-contract drift case**，分别覆盖 markdown / pdf / image_ocr。

当前分布：
- modality：markdown 29 / pdf 32 / image_ocr 32
- difficulty：simple 31 / medium 31 / complex 31
- answer_style：fact 24 / summary 18 / refusal 23 / comparison 13 / policy 15
- category：approval_summary 10 / cross_document 9 / evidence_operation 9 / hard_refusal 6 / long_document 7 / no_evidence 14 / process_boundary 13 / role_lookup 8 / scope_contract 9 / timeline_sla 8
- answerable：70 / no_evidence：23
- negative-contract：22（image_ocr 11 / markdown 6 / pdf 5）
- history-grounded：6（markdown / pdf / image_ocr 各 2）
- weak-signal：5

Main schema 当前重点 gate：
- `minimum_total_cases = 93`
- `minimum_cases_per_modality = 28`
- `minimum_cases_per_difficulty = 24`
- `minimum_no_evidence_cases = 20`
- `minimum_preview_required_cases = 60`
- `minimum_refusal_cases_per_modality = 6`
- `minimum_negative_contract_cases_per_modality = 5`
- `minimum_history_grounded_cases = 6`
- `minimum_history_grounded_cases_per_modality = 2`

### 3.3 Layer 3: Hard
- 路径：`tests/fixtures/rag_quality/eval_v8_hard/`
- 数量：36
- 构成：6 类 challenge，每类 6 条。

当前分布：
- modality：markdown 12 / pdf 12 / image_ocr 12
- difficulty：medium 15 / complex 21
- answer_style：comparison 14 / policy 16 / refusal 6
- category：similar_document_confusion 6 / stale_version_conflict 6 / chunk_boundary 6 / paraphrase_rewrite 6 / evidence_insufficient 6 / scope_isolation_trap 6

Hard 层设计原则：
- 允许不过线，核心价值是暴露系统边界；
- 有意保留“难而不稳”的 case，以便复现真实故障模式；
- 用于定位 refusal 污染、旧值污染、错误引证、preview 断裂等问题。

## 4. 题目构造策略

相比继续堆文档，本次更重视 **围绕已有文档派生更多变体题**。一个事实点应尽量扩成多种问法：

1. **fact 题**：直接抽取实体、时间、责任人；
2. **comparison / merge 题**：跨两份文档拼出完整答案；
3. **refusal 题**：问题看似合理，但知识库里没有可确认信息；
4. **scope trap 题**：题目中显式限定 KB / folder / 生效版本；
5. **preview 题**：要求 source preview 中能看到关键术语；
6. **forbidden-term 题**：把旧值、近邻值、错误角色名列入禁词。

截至 2026-08-27，Main 侧的补题重点已经从“单纯扩容”转向“题面-文档-评测 contract 联动调优”：
- markdown：补 refusal wording drift，但接受真实的多 source 输出；
- pdf：把 scope drift 收敛为更稳定的精确短语抽取；
- image_ocr：补 `authorization boundary` / `knowledge base` 双锚点负向漂移；
- history-grounded：补强 prewarm 话术与真实文档标题的一致性。

## 5. 实施产物

本次新增 / 更新的核心文件：
- `scripts/build_eval_v8_layered.py`
- `tests/fixtures/rag_quality/eval_v8_main/schema.json`
- `tests/fixtures/rag_quality/eval_v8_main/cases.json`
- `tests/fixtures/rag_quality/eval_v8_hard/schema.json`
- `tests/fixtures/rag_quality/eval_v8_hard/cases.json`
- `tests/fixtures/rag_quality/eval_layered_suite.json`
- `tests/test_rag_quality_eval_dataset_v8.py`
- `tests/api/chat_eval_runner.py`
- `tests/fixtures/rag_quality/semireal_markdown/refusal-wording-note.md`

## 6. 结论

从数据集规模和 gate 设计上看，本次扩展已经满足目标：
- Smoke = 24（达标）
- Main = 93（位于 80~120 区间内）
- Hard = 36（位于 30~50 区间内）

下一步若要继续增强“面试可讲性”和统计说服力，建议优先做两件事：
1. 继续扩 `eval_v8_hard` 的 refusal / evidence_insufficient 边界；
2. 把当前 `20260825` / `docs/interview` 口径中残留的旧数字继续同步到 93 主集版本。
