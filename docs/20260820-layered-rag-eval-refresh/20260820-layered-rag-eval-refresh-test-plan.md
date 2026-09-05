# 20260820 Layered RAG Eval Refresh Test Plan

## 1. 测试目标

验证“方案 A：最实用的扩法”是否已经完整落地，并确认三层评测集合能支撑发布前回归与边界问题定位。

本次测试要回答四个问题：
1. 三层数据集是否已经生成完成，且数量满足目标区间；
2. Main / Hard 的 fixture 是否满足 schema 约束与样本覆盖 gate；
3. Smoke / Main 是否能稳定作为发布前回归 gate；
4. Hard 是否仍保持高压边界属性，并且通过 / 失败都可解释，而不是因为 coverage 漂移或弱化题目导致 run gate 失真。

## 2. 测试范围

### 2.1 Fixture / Schema
- `scripts/build_eval_v8_layered.py`
- `tests/fixtures/rag_quality/eval_v8_main/`
- `tests/fixtures/rag_quality/eval_v8_hard/`
- `tests/fixtures/rag_quality/eval_layered_suite.json`
- `tests/test_rag_quality_eval_builders.py`
- `tests/test_rag_quality_eval_dataset_v8.py`
- `tests/api/test_chat_eval_contracts.py`
- `tests/test_rag_quality_fixtures.py`

### 2.2 Semireal 评测
- Smoke：`tests/fixtures/rag_quality/eval_v7/`
- Main：`tests/fixtures/rag_quality/eval_v8_main/`
- Hard：`tests/fixtures/rag_quality/eval_v8_hard/`

## 3. 执行命令

```bash
python scripts/build_eval_v8_layered.py
python scripts/validate_rag_quality_fixtures.py --eval-cases tests/fixtures/rag_quality/eval_v8_main/cases.json --eval-schema tests/fixtures/rag_quality/eval_v8_main/schema.json --print-eval-summary
python scripts/validate_rag_quality_fixtures.py --eval-cases tests/fixtures/rag_quality/eval_v8_hard/cases.json --eval-schema tests/fixtures/rag_quality/eval_v8_hard/schema.json --print-eval-summary
python -m pytest tests/test_rag_quality_eval_builders.py tests/test_rag_quality_eval_dataset_v8.py tests/api/test_chat_eval_contracts.py tests/test_rag_quality_fixtures.py -q
python -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v7/cases.json --schema tests/fixtures/rag_quality/eval_v7/schema.json --output-dir temp/eval-v7-smoke
python -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v8_main/cases.json --schema tests/fixtures/rag_quality/eval_v8_main/schema.json --output-dir temp/eval-v8-main
python -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v8_hard/cases.json --schema tests/fixtures/rag_quality/eval_v8_hard/schema.json --output-dir temp/eval-v8-hard
```

## 4. 预期结果

### 4.1 数据集与覆盖度
- `eval_layered_suite.json` 中应明确包含 smoke / main / hard 三层；
- smoke = 24，main = **93**，hard = 36；
- `pytest` 套件应通过；
- Main 必须满足 schema 中定义的覆盖 gate，例如：
  - 最少 93 条；
  - 每种 modality 至少 28 条；
  - 每种 difficulty 至少 24 条；
  - no_evidence 至少 20 条；
  - preview_required 至少 60 条；
  - negative-contract 每种 modality 至少 5 条；
  - history-grounded 总数至少 6 条，且每种 modality 至少 2 条。

### 4.2 运行 gate
#### Smoke / Main
- `run_passed = true`；
- 核心质量 gate 达标：
  - `scope_pass_rate`
  - `average_keypoint_coverage`
  - `evidence_hit_rate`
  - `preview_resolvable_rate`
  - `source_count_match_rate`
  - `forbidden_term_clean_rate`

#### Hard
- 不强制 `run_passed` 必须为 `false`；
- 若 `run_passed = true`，也必须能证明 challenge 分布与 contract gate 没有被削弱；
- 若 `run_passed = false`，则必须能输出稳定、可解释的失败分布；
- 报告中应能看出 hard 的挑战点究竟来自 evidence 缺失、source count 不匹配、preview 断裂、禁词污染，还是 refusal / negative-contract marker 覆盖缺口。

## 5. 关注风险

1. **Main 被污染成 Hard**：如果把过多 adversarial case 放入 Main，会让发布 gate 不稳定；
2. **Hard 被“修得太绿”**：如果为了追求 1.0 把 challenge case 变得太简单，就失去抓边界 bug 的意义；
3. **Refusal 题被 seed docs 带偏**：无答案但看似合理的问题，最容易错误返回 sources / evidence；
4. **Chunk / stale value 混淆**：旧值、近邻值、相邻片段内容容易被误带入答案。

## 6. 通过标准

本轮测试通过，需同时满足：
- 三层数据集数量达标；
- fixture / schema 校验通过；
- builder / dataset / contract / fixture 四组回归测试通过；
- Smoke 和 Main 的 semireal 评测均通过 run gate；
- Hard 的 semireal 评测不要求固定失败；但无论通过还是失败，都必须能解释 contract gate 与 challenge 分布是否真实有效，并据此定位下一轮系统优化重点。
