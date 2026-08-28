# 20260820 Layered RAG Eval Refresh Test Report

## 1. 结论摘要

截至 **2026-08-28**，本次 layered RAG eval refresh 已对齐到最新可复核产物：
- **Smoke 层：24 条，24 / 24 通过，可继续作为环境重建 / Docker / CI 冒烟集。**
- **Main 层：93 条，93 / 93 通过，可作为版本发布前主 gate。**
- **Hard 层：36 条，36 / 36 通过，最新 semireal 已收口到 `run_passed = true`，且 contract gate 全部闭环。**

因此，这一轮的真实结论不是“只改了几条文案”或“单纯把 hard 题刷绿”，而是：
1. Main 数据集已经从 90 收敛到 **93**，并维持三模态 negative-contract 与 history-grounded 对称覆盖；
2. builder / fixture / schema / dataset test 已重新对齐，避免生成器和提交结果继续漂移；
3. Hard 不再停留在“36 条 case 都过了，但 run gate 仍失败”的假绿状态，而是把 `required_negative_contract_modality_markers` 等 contract gate 真正补齐了。

## 2. 本次实际验证与可复核产物

### 2.1 2026-08-27：builder / fixture / pytest 回归
```bash
python scripts/build_eval_v8_layered.py
python scripts/validate_rag_quality_fixtures.py --eval-cases tests/fixtures/rag_quality/eval_v8_main/cases.json --eval-schema tests/fixtures/rag_quality/eval_v8_main/schema.json --print-eval-summary
python scripts/validate_rag_quality_fixtures.py --eval-cases tests/fixtures/rag_quality/eval_v8_hard/cases.json --eval-schema tests/fixtures/rag_quality/eval_v8_hard/schema.json --print-eval-summary
python -m pytest tests/test_rag_quality_eval_builders.py tests/test_rag_quality_eval_dataset_v8.py tests/api/test_chat_eval_contracts.py tests/test_rag_quality_fixtures.py -q
python -m pytest tests/api/test_chat_eval_contracts.py tests/test_rag_quality_eval_dataset_v8.py tests/api/test_chat_eval_runner.py -q
```

执行结果：
- `build_eval_v8_layered.py` 已重新生成与当前 fixture 一致的 layered suite；
- Main fixture 校验通过；
- Hard fixture 校验通过；
- `pytest` 结果分别为：`44 passed`、`54 passed`。

### 2.1.1 2026-08-28：fixture per-modality marker gate 补强
```bash
python -m pytest tests/test_rag_quality_fixtures.py tests/test_rag_quality_eval_dataset_v8.py tests/api/test_chat_eval_contracts.py -q
python -m pytest tests/api/test_chat_eval_runner.py -q
```

执行结果：
- `44 passed`：fixture / dataset / eval contract 已补上 refusal 与 negative-contract 的按模态 category marker 守卫；
- `23 passed`：chat eval runner 回归通过，说明新增 gate 没有把运行期 contract 判定打坏；
- fixture summary 现在除了全局 marker 统计，还会输出：
  - `refusal_modality_marker_category_breakdown`
  - `negative_contract_modality_marker_category_breakdown`
  - `required_refusal_markers_by_category_per_modality`
  - `required_negative_contract_markers_by_category_per_modality`

### 2.2 最新 semireal 产物快照
```bash
python -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v7/cases.json --schema tests/fixtures/rag_quality/eval_v7/schema.json --output-dir temp/eval-v7-smoke
python -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v8_main/cases.json --schema tests/fixtures/rag_quality/eval_v8_main/schema.json --output-dir temp/eval-v8-main-20260827-r8
python -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v8_hard/cases.json --schema tests/fixtures/rag_quality/eval_v8_hard/schema.json --output-dir temp/eval-v8-hard-20260827-r15
```

最新可复核产物路径：
- Smoke JSON：`temp/eval-v7-smoke/local_multi_kb_eval_v7_holdout_regression-semireal-report.json`
- Main JSON：`temp/eval-v8-main-20260827-r8/local_multi_kb_eval_v8_layered_main-semireal-report.json`
- Hard JSON：`temp/eval-v8-hard-20260827-r15/local_multi_kb_eval_v8_layered_hard-semireal-report.json`

## 3. 三层评测结果总表

| Layer | Cases | run_passed | passed / total | pass_rate | scope_pass_rate | avg_keypoint_coverage | evidence_hit_rate | preview_resolvable_rate | source_count_match_rate | forbidden_term_clean_rate |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Smoke | 24 | true | 24 / 24 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Main | 93 | true | 93 / 93 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Hard | 36 | true | 36 / 36 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

## 4. 数据集规模与覆盖度验证

### 4.1 数量达标情况
- Smoke：24 条，符合目标；
- Main：93 条，位于目标区间 80~120 内；
- Hard：36 条，位于目标区间 30~50 内。

### 4.2 Main 分布
- modality：markdown 29 / pdf 32 / image_ocr 32
- difficulty：simple 31 / medium 31 / complex 31
- answer_style：fact 24 / summary 18 / refusal 23 / comparison 13 / policy 15
- category：approval_summary 10 / cross_document 9 / evidence_operation 9 / hard_refusal 6 / long_document 7 / no_evidence 14 / process_boundary 13 / role_lookup 8 / scope_contract 9 / timeline_sla 8
- answerable：70 / no_evidence：23
- negative-contract：22（image_ocr 11 / markdown 6 / pdf 5）
- history-grounded：6（markdown / pdf / image_ocr 各 2）

Main schema 中要求的 coverage gate 全部满足，包括：
- 至少 93 条；
- 每种 modality 至少 28 条；
- 每种 difficulty 至少 24 条；
- `preview_required_cases >= 60`；
- `minimum_cases_per_category >= 5`；
- `minimum_cases_per_answer_style >= 8`；
- `minimum_negative_contract_cases_per_modality >= 5`；
- `minimum_history_grounded_cases = 6` 且每种 modality 至少 2 条。

补充说明：2026-08-28 新增的 per-modality marker gate **不是**要求“每个 refusal / negative-contract category 在每个模态都出现一遍”。它真正约束的是：**某个模态里一旦已经出现被 tracked 的 category，就要求该模态下对应的 required marker 不能缺。**

这层约束主要是为了解决过去 fixture summary 只看“全局 marker 是否出现过”时，无法发现“某个模态局部漏 marker”的问题。以 `eval_v8_main` 为例，`scope_contract` refusal 目前主要集中在 `image_ocr`，markdown / pdf 并没有被强行要求也各补一条同类 refusal；新 gate 只会约束**已经存在该类 case 的模态**不能漏 marker，而不会错误地把数据集设计改成“所有 category 覆盖所有模态”。

### 4.3 Hard 分布
- modality：markdown 12 / pdf 12 / image_ocr 12
- difficulty：medium 15 / complex 21
- answer_style：comparison 14 / policy 16 / refusal 6
- category：similar_document_confusion 6 / stale_version_conflict 6 / chunk_boundary 6 / paraphrase_rewrite 6 / evidence_insufficient 6 / scope_isolation_trap 6

Hard 当前的关键点不只是 `36 / 36`，而是 challenge 分布仍然保留、没有通过削弱题目来换绿灯。

## 5. Smoke 结果解读

Smoke 层 `24 / 24` 全部通过，所有核心指标均为 `1.0`：
- `scope_pass_rate = 1.0`
- `average_keypoint_coverage = 1.0`
- `evidence_hit_rate = 1.0`
- `preview_resolvable_rate = 1.0`
- `source_count_match_rate = 1.0`
- `forbidden_term_clean_rate = 1.0`

解释：
- 这说明基础环境、最小知识库隔离、基本 evidence/preview 链路和常见问答路径是稳定的；
- Smoke 更像“系统能不能跑通”的回归集，而不是“系统边界到底有多强”的证明集。

## 6. Main 结果解读

### 6.1 总体结果
Main 层 `93 / 93` 全部通过，`run_passed = true`，并且所有主 gate 指标都是 `1.0`。

补充统计：
- `total_keypoints = 175`
- `matched_keypoints = 175`
- `preview_required_cases = 70`
- `preview_term_total = 35`
- `blocked_term_hit_cases = 0`

### 6.2 为什么 Main 仍然全是 1.0，但这次更可信
这次 Main 的 1.0 不是“题太水”，而是因为题库 contract 已经比旧版更完整：
- 主集从 90 补到 93，不是机械加题，而是专门补了 **markdown / pdf / image_ocr 三模态 negative-contract drift case**；
- `minimum_negative_contract_cases_per_modality` 从 4 提升到 5；
- history-grounded follow-up 维持在三模态对称覆盖；
- semireal 报告里的 refusal / negative-contract contract gate 现在都是实打实跑过的，不是 schema 里写了但没触发。

### 6.3 Main 当前真正说明了什么
Main 现在更适合回答这几个问题：
1. **scope**：是否发生跨库越权或隐式扩大作用域；
2. **evidence**：答案引用的文档是否正确；
3. **preview**：来源预览能否直接定位到支撑答案的片段；
4. **grounding**：回答是否被 keypoint、evidence、preview、source-count、forbidden-term 共同约束。

也就是说，Main 现在是一个**稳定回归 gate**，而不是一个“为了面试好看专门刷分”的集合。

## 7. Hard 结果解读

### 7.1 总体结果
Hard 层当前最新可复核结果为 `36 / 36`，`run_passed = true`，核心指标全部为 `1.0`：
- `scope_pass_rate = 1.0`
- `average_keypoint_coverage = 1.0`
- `evidence_hit_rate = 1.0000`
- `preview_resolvable_rate = 1.0000`
- `source_count_match_rate = 1.0000`
- `forbidden_term_clean_rate = 1.0000`
- `blocked_term_hit_cases = 0`
- `total_keypoints = 75`，`matched_keypoints = 75`
- `preview_required_cases = 30`，`preview_term_total = 59`

### 7.2 Hard 这次“全绿”为什么不是假绿
Hard 这次最关键的变化，不是 case pass rate 从 `34 / 36` 提升到 `36 / 36` 本身，而是 **run gate 也一起收口了**：
- 之前存在“36 条 case 都过了，但 `run_passed = false`”的风险，说明 contract gate 仍然有覆盖缺口；
- 这次通过补齐 hard negative-contract / scope trap 的 modality marker 覆盖，把 `required_negative_contract_modality_markers` 从缺口状态收口到 **9 / 9**；
- 同时 refusal 相关 contract gate 也全部通过，包括 categories / modalities / markers / modality markers；
- 修复方式不是继续改 chat 主链路，而是通过专用 bridge fixture 和 hard case 设计把评测资产闭环补齐。

因此，这次 Hard 的 `1.0` 更准确的含义是：
- **hard 题还在；**
- **contract gate 也在；**
- **通过是因为评测设计和负向边界真正闭环了，而不是因为把 hard 题放水。**

### 7.3 Hard 当前更适合拿来讲什么
Hard 现在不再只是“失败画像集”，而更适合作为以下论点的证据：
- 系统能区分 Main 主发布路径和 Hard 高压边界集；
- case 通过不等于 run 通过，最终还要看 contract gate 是否闭环；
- 负向边界不仅要测“拒答了没有”，还要测 refusal / negative-contract 是否覆盖到 markdown / pdf / image_ocr 三模态的关键 marker。

## 8. 本轮新增整改点

这次除了更新报告，还真实补齐了两类治理问题：
1. **builder / fixture 漂移治理**
   - `scripts/build_eval_v8_layered.py` 曾仍保留 Main `target_case_count = 90`、`minimum_total_cases = 90`、`minimum_negative_contract_cases_per_modality = 4` 的旧口径；
   - 这会导致“脚本生成结果”和“已提交 fixture 真相”分叉；
   - 现在 builder 已与 fixture 同步，避免后续一键 build 把正确数据集回退坏掉。
2. **Hard contract gate 闭环治理**
   - 通过新增专用 bridge fixture，而不是污染旧共享 fixture，补齐 hard 所需 negative-contract marker；
   - `tests/api/chat_eval_runner.py`、`tests/fixtures/rag_quality/eval_v8_hard/cases.json`、`tests/test_rag_quality_eval_dataset_v8.py`、`tests/api/test_chat_eval_runner.py` 已同步收口；
   - 定向回归已通过：`python -m pytest tests/api/test_chat_eval_contracts.py tests/test_rag_quality_eval_dataset_v8.py tests/api/test_chat_eval_runner.py -q` -> `54 passed`。

## 9. 结论与下一步

截至 2026-08-27，当前 layered eval 的更真实状态是：
- Smoke：稳定；
- Main：93 条主 gate 已收口；
- Hard：36 条高压边界题与 contract gate 已同步收口。

下一轮最值得继续做的事：
1. 继续横向检查 `eval_v7` / `eval_v8_main` / 面试文档是否全部同步最新 hard 口径；
2. 给 layered eval 增加更自动化的“报告口径一致性”守卫，减少手工改文档导致的数字漂移；
3. 准备 commit / push 前，把这轮 builder 修正、hard contract gate 收口、测试回归和报告对齐沉淀进 dev story。
