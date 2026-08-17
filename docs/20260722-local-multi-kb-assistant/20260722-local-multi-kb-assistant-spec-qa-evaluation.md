# 20260722 本地多知识库助手问答评测 Spec

## 1. 文档信息
- 文档日期：2026-07-30
- 适用范围：`docs/20260722-local-multi-kb-assistant/`
- 对应文档：
  - PRD / FRD / RTM：同需求目录内既有文档
  - 实施方案：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-plan.md`
  - 测试方案：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-test-plan.md`
  - 测试报告：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-test-report.md`

---

## 2. 背景与目标
本评测规范服务于**本地多知识库知识助手**的问答质量验证。它验证的不是通用 benchmark 分数，而是当前产品主链路是否满足以下工程目标：
1. 导入后的知识对象可以在显式知识库范围内稳定检索。
2. 回答必须带有可追溯的 `scope / evidence / preview` 结果，而不是只返回一段不可核验的文本。
3. Markdown、PDF 文字层、扫描 PDF OCR fallback 与图片 OCR 需要统一进入同一评测闭环。
4. 拒答、no-evidence、forbidden term 清洁度必须可测、可回归、可量化。
5. 评测结果需要支撑持续回归、趋势比较、后续真实业务样本接入。

---

## 3. 风险背景与评测动机
当前知识库已采用物理索引隔离，但问答评测仍必须显式覆盖错误路由、默认范围拒绝、历史数据重建遗漏和跨库证据泄漏风险：
1. 范围过滤失效导致跨知识库越界。
2. chat 查询在未声明范围时退回全局检索，而不是执行 default-deny。
3. OCR 文档与普通文本文档在 evidence / preview / answer 契约上行为不一致。
4. folder / path 语义在导入、检索与证据引用间发生漂移。
5. 评测失败时无法定位是 query、schema、evidence、preview、refusal 还是 metrics 侧的问题。

---

## 4. 数据集设计

### 4.1 eval_v1：基础 semireal 回归集
目录：`tests/fixtures/rag_quality/eval_v1/`

定位：
- 第一版 semireal 问答回归基线。
- 验证 runner、metrics、artifact 落盘与基础问答契约是否成立。
- 作为后续扩容时的基线对照。

当前规模：
- 总计 `54` 个 cases。
- `modality`：Markdown / PDF / image_ocr 各 `18`。
- `difficulty`：simple / medium / complex 各 `18`。
- `no_evidence = 9`
- `preview_required = 45`

### 4.2 eval_v2：当前主评测集
目录：`tests/fixtures/rag_quality/eval_v2/`

定位：
- 在 v1 基础上扩大覆盖面，作为当前主评测集。
- 显式加强 scope 契约、拒答策略、preview、folder 语义、OCR 与 CJK 覆盖。
- 作为测试报告、阶段验收与后续趋势对比的主数据集。

当前规模：
- 总计 `117` 个 cases。
- `modality`：Markdown / PDF / image_ocr 各 `39`。
- `difficulty`：simple / medium / complex 各 `39`。
- `answer_style`：
  - `fact = 31`
  - `summary = 21`
  - `refusal = 21`
  - `comparison = 15`
  - `policy = 15`
  - `metrics = 14`
- `category`：
  - `scope_contract = 20`
  - `folder_model = 20`
  - `no_evidence = 21`
  - `evidence_preview = 18`
  - `refusal_policy = 11`
  - `suite_metrics = 13`
  - `ingestion_priority = 9`
  - `per_case_metrics = 5`
- `answerable = 96`
- `no_evidence = 21`
- `preview_required = 96`
- `cjk_case_count = 13`
- `cjk_modality_breakdown`：Markdown `4` / PDF `5` / image_ocr `4`

v2 当前重点覆盖：
- 单库范围契约与 default-deny
- 证据预览、拒答、no-evidence 场景
- OCR / 扫描件 / 中文问题的稳定性
- folder / path / source / preview 的一致性
- 指标口径（suite metrics / per-case metrics）可回归

---

## 5. 验收门槛

### 5.1 数据集结构校验门槛
使用 `scripts/validate_rag_quality_fixtures.py` 校验。

#### eval_v1 最低门槛
- `minimum_total_cases = 50`
- `minimum_cases_per_modality = 10`
- `minimum_cases_per_difficulty = 10`
- `minimum_no_evidence_cases = 6`
- `minimum_preview_required_cases = 20`

#### eval_v2 最低门槛
- `minimum_total_cases = 117`
- `minimum_cases_per_modality = 39`
- `minimum_cases_per_difficulty = 39`
- `minimum_no_evidence_cases = 21`
- `minimum_preview_required_cases = 96`
- `minimum_cases_per_answer_style = 14`
- `minimum_cases_per_category = 5`
- `minimum_cjk_cases = 12`
- `minimum_cjk_cases_per_modality = 4`

### 5.2 运行门槛
每次正式评测至少满足以下 gate：
- `scope_pass_rate >= 1.0`
- `average_keypoint_coverage >= 0.90`
- `evidence_hit_rate >= 0.95`
- `preview_resolvable_rate >= 0.95`
- `source_count_match_rate >= 0.95`
- `forbidden_term_clean_rate >= 1.0`

说明：
- `scope_pass_rate` 是硬门槛，因为范围越界属于产品边界错误。
- `forbidden_term_clean_rate` 当前也作为硬门槛，用于约束拒答与 no-evidence 场景的清洁度。
- 其他指标既承担运行 gate，也承担趋势追踪用途。

### 5.3 统计稳定性指标（report-only）
- `pass_rate_ci95`：对 suite 和各 breakdown 的 `pass_rate` 输出 Wilson 95% 置信区间。
- 引入目的：避免把“100% 通过”误读成“零风险”。
- 当前参考值：
  - `eval_v1` suite：`[0.934, 1.000]`
  - `eval_v2` suite：`[0.968, 1.000]`
  - `eval_v2` 单个 `modality` / `difficulty` 分层（39 cases）：`[0.910, 1.000]`
- 当前阶段 `pass_rate_ci95` 仅作为报告指标，不单独作为 release gate。

---

## 6. 输出产物
每次评测运行至少输出：
1. suite 汇总指标（pass_rate、keypoint、evidence、preview、source_count、forbidden_term 等）。
2. stratified breakdown（modality / difficulty / answer_style / category / kb_id）。
3. run gates 逐项判定结果。
4. 失败用例明细（若存在）。
5. 导入摘要（知识库数、文件数、OCR 成功数、资产注册数、耗时等）。
6. markdown 与 json 两份 report artifact。

标准产物路径：
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v1-semireal-report.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v1-semireal-report.md`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v2-semireal-report.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v2-semireal-report.md`

---

## 7. 执行方式

### 7.1 运行约束
- `run_chat_eval` 必须以模块方式执行：`python -m scripts.run_chat_eval ...`
- 不推荐直接运行 `python scripts/run_chat_eval.py ...`，否则在当前仓库环境下可能出现 `ModuleNotFoundError: No module named "tests"`。

### 7.2 数据集校验
```bash
python scripts/validate_rag_quality_fixtures.py --eval-cases tests/fixtures/rag_quality/eval_v2/cases.json --eval-schema tests/fixtures/rag_quality/eval_v2/schema.json --print-eval-summary
```

### 7.3 相关测试
```bash
python -m pytest tests/test_rag_quality_eval_dataset.py tests/test_rag_quality_eval_dataset_v2.py tests/test_rag_quality_fixtures.py tests/api/test_chat_eval_runner.py tests/api/test_chat_qa_metrics.py tests/api/test_semireal_chat_support.py -q
```

### 7.4 eval_v1 执行
```bash
python -m scripts.run_chat_eval --output-dir docs/20260722-local-multi-kb-assistant/artifacts/qa-eval
```

### 7.5 eval_v2 执行
```bash
python -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v2/cases.json --schema tests/fixtures/rag_quality/eval_v2/schema.json --output-dir docs/20260722-local-multi-kb-assistant/artifacts/qa-eval
```

### 7.6 eval_v3 执行
```bash
python -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v3/cases.json --schema tests/fixtures/rag_quality/eval_v3/schema.json --output-dir docs/20260722-local-multi-kb-assistant/artifacts/qa-eval
```

### 7.7 eval_v4 执行
```bash
python -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v4/cases.json --schema tests/fixtures/rag_quality/eval_v4/schema.json --output-dir docs/20260722-local-multi-kb-assistant/artifacts/qa-eval
```

---

## 8. 最新实测结果（2026-07-30）

### 8.1 数据集校验结果
执行：
```bash
python scripts/validate_rag_quality_fixtures.py --eval-cases tests/fixtures/rag_quality/eval_v2/cases.json --eval-schema tests/fixtures/rag_quality/eval_v2/schema.json --print-eval-summary
```

结果：
- `dataset_name = local_multi_kb_eval_v2`
- `total_cases = 117`
- `modality_breakdown = {image_ocr: 39, markdown: 39, pdf: 39}`
- `difficulty_breakdown = {complex: 39, medium: 39, simple: 39}`
- `preview_required_cases = 96`
- `cjk_case_count = 13`
- 所有 `gate_checks = true`

### 8.2 支撑测试结果
执行：
```bash
python -m pytest tests/test_rag_quality_eval_dataset_v2.py tests/api/test_chat_eval_runner.py tests/test_rag_quality_fixtures.py tests/test_rag_quality_eval_dataset.py tests/api/test_chat_qa_metrics.py tests/api/test_semireal_chat_support.py -q
```

结果：
- `45 passed, 2 warnings in 14.02s`
- warning 来源：FastAPI `on_event` deprecation warning × 2

### 8.3 eval_v1 基线
来自现有产物：
- `total_cases = 54`
- `passed_cases = 54`
- `failed_cases = 0`
- `pass_rate = 1.0`
- `pass_rate_ci95 = [0.9335841332189981, 1.0]`
- `run_passed = true`

### 8.4 eval_v2 最新结果
执行：
```bash
python -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v2/cases.json --schema tests/fixtures/rag_quality/eval_v2/schema.json --output-dir docs/20260722-local-multi-kb-assistant/artifacts/qa-eval
```

结果：
- `run_passed = true`
- `total_cases = 117`
- `passed_cases = 117`
- `failed_cases = 0`
- `pass_rate = 1.0`
- `pass_rate_ci95 = [0.9682096231761248, 1.0]`
- `scope_pass_rate = 1.0`
- `average_keypoint_coverage = 1.0`
- `total_keypoints = 352`
- `matched_keypoints = 352`
- `evidence_hit_rate = 1.0`
- `preview_resolvable_rate = 1.0`
- `source_count_match_rate = 1.0`
- `forbidden_term_clean_rate = 1.0`
- `preview_required_cases = 96`
- `preview_resolved_cases = 96`
- `blocked_term_hit_cases = 0`
- run gates 全部通过

分层结果：
- `modality` 三层（Markdown / PDF / image_ocr）均为 `39 / 39`，各自 `pass_rate_ci95 = [0.9103301463997611, 1.0]`
- `difficulty` 三层（simple / medium / complex）均为 `39 / 39`，各自 `pass_rate_ci95 = [0.9103301463997611, 1.0]`
- `answer_style` 六层全部 `100%` 通过，其中 `fact = 31`、`summary = 21`、`refusal = 21`、`comparison = 15`、`policy = 15`、`metrics = 14`
- `category` 八层全部 `100%` 通过，其中 `scope_contract = 20`、`folder_model = 20`、`no_evidence = 21`、`evidence_preview = 18`

导入摘要：
- `total_kbs = 3`
- `total_files = 19`
- `total_success_count = 19`
- `total_failed_count = 0`
- `total_ocr_success_count = 5`
- `total_asset_registered_count = 5`
- `total_import_ms = 297.56`

---

## 9. 当前判断
1. `eval_v2` 已经足以作为当前阶段的主评测基线。
2. 范围控制、证据可追溯、preview 可解析、拒答清洁度等核心契约已经具备稳定自动回归能力。
3. OCR 已不再是孤立的解析能力，而是进入了与 Markdown / PDF 同口径的问答评测闭环。
4. 现阶段最重要的下一步不是重写评测框架，而是继续扩充真实业务样本与更复杂故障模式。

---

## 10. 下一步建议
1. 扩充真实业务语料样本，尤其是图文混排、长文档、多段证据命中、复杂 OCR 失真场景。
2. 将重导入、目录树、asset registry 稳定性结果与问答评测结果形成统一报告视图。
3. 在后续阶段增加趋势对比章节，对比不同数据集版本、不同导入策略、不同检索参数下的质量变化。
4. 视后续需求再补更精细的准确率标注、人工抽检与 LLM-as-judge 扩展，但当前优先级低于真实样本扩容。

## 11. 2026-07-30 eval_v3 弱信号诊断扩展

### 11.1 定位
- `eval_v2` 继续作为 healthy 主评测集，用于验证主链路稳定性。
- `eval_v3` 新增为 weak-signal diagnostic 扩展集，用于验证“导入异常是否会被 `import_summary`、`import_qa_correlation` 与 QA case 同时暴露”。
- `eval_v3` 不追求所有 case 通过；它的核心验收口径是：**预期失败的弱信号 case 必须稳定失败，预期通过的 healthy refusal case 必须稳定通过，且 diagnostic gate 全通过。**

### 11.2 数据集结构
- schema：`tests/fixtures/rag_quality/eval_v3/schema.json`
- cases：`tests/fixtures/rag_quality/eval_v3/cases.json`
- 总 case 数：`4`
- modality 分布：`image_ocr = 2`、`pdf = 2`
- answer_style 分布：`policy = 3`、`refusal = 1`
- category 分布：`scope_contract = 3`、`no_evidence = 1`
- 弱信号覆盖：`ocr_no_text = 1`、`ocr_failed = 1`、`nodes_without_embedding = 1`
- 弱信号模态分布：`image_ocr = 2`、`pdf = 1`

### 11.3 Gate 设计
- quality_gates：
  - `minimum_total_cases = 4`
  - `minimum_cases_per_modality = 2`
  - `minimum_weak_signal_cases = 3`
- diagnostic_gates：
  - `case_expectation_match_rate_min = 1.0`
  - `minimum_weak_signal_kb_count = 2`
  - `minimum_weak_signal_modality_count = 2`
  - `required_signal_tags = [ocr_no_text, ocr_failed, nodes_without_embedding]`
- run_gates 故意放宽到“只检查 scope / forbidden term / 基础结构不回归”，避免把弱信号诊断集误判成 healthy 主评测集。

### 11.4 执行命令与最新结果
数据集校验：
```bash
python -m pytest tests/test_rag_quality_eval_dataset_v3.py -q
```

runner / diagnostic 回归：
```bash
python -m pytest tests/api/test_chat_eval_runner.py tests/api/test_chat_qa_metrics.py tests/api/test_semireal_chat_support.py tests/test_rag_quality_eval_dataset_v2.py tests/test_rag_quality_eval_dataset_v3.py -q
```

正式评测：
```bash
python -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v3/cases.json --schema tests/fixtures/rag_quality/eval_v3/schema.json --output-dir docs/20260722-local-multi-kb-assistant/artifacts/qa-eval
```

最新结果（2026-07-30）：
- `36 passed in 136.98s`
- `dataset_name = local_multi_kb_eval_v3`
- `evaluation_mode = diagnostic`
- `run_passed = true`
- `passed_cases = 1`、`failed_cases = 3`
- `case_expectation_match_rate = 1.0`
- `weak_signal_case_count = 3`
- `weak_signal_breakdown = {nodes_without_embedding: 1, ocr_failed: 1, ocr_no_text: 1}`
- `diagnostic_gates` 全通过
- 产物：
  - `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v3-semireal-report.json`
  - `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v3-semireal-report.md`

## 12. 2026-07-31 eval_v4 业务化问答扩展

### 12.1 定位
- `eval_v2` 继续作为 healthy 主评测集，验证广覆盖的主链路稳定性。
- `eval_v3` 继续作为 diagnostic 弱信号集，验证导入异常能否在 QA 层被显式暴露。
- `eval_v4` 新增为 **business-style healthy 扩展集**，目标是把更接近真实业务表达方式的问题纳入自动评测。

### 12.2 数据集结构
- schema：`tests/fixtures/rag_quality/eval_v4/schema.json`
- cases：`tests/fixtures/rag_quality/eval_v4/cases.json`
- dataset_name：`local_multi_kb_eval_v4_business`
- 总 case 数：`24`
- modality 分布：Markdown `8` / PDF `8` / image_ocr `8`
- difficulty 分布：simple `8` / medium `8` / complex `8`
- answer_style 分布：fact `9` / comparison `3` / policy `2` / summary `4` / refusal `6`
- category 分布：role_lookup `5` / timeline_sla `4` / approval_summary `5` / evidence_operation `2` / process_boundary `2` / no_evidence `6`
- `answerable = 18`
- `preview_required = 18`
- `cjk_case_count = 24`

### 12.3 设计原则
1. 保持中文业务问句为主，但在问题中显式带入必要的英文锚点，如 `Payroll release checklist`、`final sign-off owner`、`rollback owner`，降低误召回。
2. comparison 类问题不再强依赖“不是”这类字面否定词，而是优先验证角色区分是否被答对。
3. no-evidence 类问题优先使用“会议密码 / 座机号码”这类当前 KB 明确不存在的字段，避免问句本身被已有实体抢召回。
4. process boundary 类问题按真实稳定召回结果建契约：`eval-v4-img-007` 当前稳定命中 `folder-board.png`，因此评测以真实证据对象为准。

### 12.4 最新执行与结果（2026-07-31）
数据集校验：
```bash
python -m pytest tests/test_rag_quality_eval_dataset_v4.py -q
```

runner 回归：
```bash
python -m pytest tests/test_rag_quality_eval_dataset_v4.py tests/api/test_chat_eval_runner.py -k v4 -q
```

正式评测：
```bash
python -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v4/cases.json --schema tests/fixtures/rag_quality/eval_v4/schema.json --output-dir docs/20260722-local-multi-kb-assistant/artifacts/qa-eval
```

最新结果：
- `dataset_name = local_multi_kb_eval_v4_business`
- `evaluation_mode = healthy`
- `run_passed = true`
- `passed_cases = 24`、`failed_cases = 0`
- `scope_pass_rate = 1.0`
- `average_keypoint_coverage = 1.0`
- `evidence_hit_rate = 1.0`
- `preview_resolvable_rate = 1.0`
- `source_count_match_rate = 1.0`
- `forbidden_term_clean_rate = 1.0`
- category breakdown 全部 `pass_rate = 1.0`
- 产物：
  - `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v4_business-semireal-report.json`
  - `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v4_business-semireal-report.md`

### 12.5 当前判断
- `eval_v4` 证明当前评测体系已不只能覆盖“平台契约型问答”，也能覆盖一批更接近真实业务沟通方式的问句。
- 本轮调整的重点是让数据集契约与真实系统行为对齐，而不是修改主链路实现。
- 后续扩充业务样本时，应继续沿用“先确认召回锚点，再设计 keypoint 与 no-evidence 断言”的方法。



## 12.6 2026-07-31 短答案完整性扩容记录

本轮在 `eval_v4` 中新增 3 条面向“答案完整表达质量”的 healthy case：
- `eval-v4-md-017`：UTF-8 Markdown 边界说明，要求回答命中“知识库仍然是授权边界”；
- `eval-v4-pdf-017`：`folder-boundary.pdf`，要求回答同时包含 `Knowledge Base` 与 `authorization boundary`；
- `eval-v4-img-017`：`folder-board.png` OCR，要求回答同时体现 `Knowledge Base` 与“知识库边界”。

扩容后的 `eval_v4` 当前规模：
- total cases：`51`
- modality：Markdown `17` / PDF `17` / image_ocr `17`
- difficulty：simple `17` / medium `17` / complex `17`
- preview_required：`39`
- answerable：`39`
- no_evidence：`12`

本轮设计结论：
1. “答案过短”不能只停留在 live 诊断脚本里观察，必须进入正式评测集；
2. 短答案完整性 case 需要显式约束完整 keypoint，避免回答只命中实体名词却漏掉谓词；
3. 新增 fixture 会改变检索噪声分布，因此扩容后必须重跑既有 `no_evidence` case，确认没有把拒答样例冲掉；
4. 当次扩容后的正式 run gate 结果为 `51/51 passed`；后续在 12.7 中继续扩容到 `54/54 passed`。


## 12.7 2026-07-31 二次扩容：覆盖 PDF / OCR / mixed batch

在 12.6 把“短答案完整性”正式纳入 `eval_v4` 之后，本轮继续把覆盖范围从 UTF-8 Markdown 扩展到 PDF / 图片 OCR / mixed batch，避免只修单一 fixture 就误判问题已经解决。

新增内容：
- `eval-v4-md-018`：`workflow-boundary.md`，要求回答同时体现 `access control` 与 `knowledge base level`；
- `eval-v4-pdf-018`：扫描 PDF `scan-fallback.pdf`，要求回答覆盖 `OCR fallback`、`merge every predict batch` 与 `same page`；
- `eval-v4-img-018`：OCR 图片 `escalation-whiteboard-business.png`，要求回答同时体现 `Knowledge base` 与 `authorization boundary`；
- `tests/api/test_chat_service.py`：新增 PDF / image OCR 的 source-backed 短答案补全单测；
- `tests/api/test_chat_mixed_batch_semireal.py`：收紧 embedded image case，避免回答只命中名词片段却缺少边界语义。

本轮 TDD 真实发现：
- 新增 PDF / OCR 短答案测试第一次运行并未通过；
- 根因不是断言过严，而是 `api/services/chat_service.py` 中 `_SENTENCE_SPLIT_RE` 之前没有按 ASCII 句号切分 source 文本；
- 这会让多句 PDF / OCR source 被当成一个过长候选句，进而导致最小完整句补全放弃扩写；
- 修复后，source-backed 最小完整句补全已经从 Markdown 扩展到了 PDF 与 OCR 来源。

验证命令：
```bash
python -X utf8 -m pytest tests/api/test_chat_service.py tests/api/test_chat_mixed_batch_semireal.py tests/test_rag_quality_eval_dataset_v4.py tests/api/test_chat_eval_runner.py -q
# 29 passed in 69.41s

python -X utf8 -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v4/cases.json --schema tests/fixtures/rag_quality/eval_v4/schema.json --output-dir docs/20260722-local-multi-kb-assistant/artifacts/qa-eval
# run_passed = true
# 54/54 passed
# total_keypoints = 100
# matched_keypoints = 100
# evidence_expected_cases = 42
# evidence_hit_cases = 42
# preview_required_cases = 42
# preview_resolved_cases = 42
```

扩容后的 `eval_v4` 当前规模：
- total cases：`54`
- modality：Markdown `18` / PDF `18` / image_ocr `18`
- difficulty：simple `18` / medium `18` / complex `18`
- answerable：`42`
- no_evidence：`12`
- preview_required：`42`

阶段判断：
1. “短答案完整性”已经不是只依赖 UTF-8 fixture 的局部问题，而是 Markdown / PDF / OCR / mixed batch 统一进入正式评测闭环；
2. 这轮扩容把真实实现缺口暴露在自动化回归里，而不是继续依赖 live 手工观察；
3. 后续如果继续优化答案质量，应优先继续扩充 PDF OCR / mixed batch 下的完整句与多 source 竞争场景，而不是盲目追加启发式规则。

## 12.8 2026-07-31 最小 follow-up / session 稳定性补充

在 `eval_v4` / `eval_v5` 已经覆盖单轮业务问答主链路之后，本轮补充一层更靠近运行时的支撑回归：确认 chat 会话历史不再只是持久化，而是能在**疑似 follow-up 问题**下参与检索问句构造，同时不破坏现有 scope 契约与 Windows 本地评测稳定性。

补充内容：
- `api/services/chat_service.py`：新增 `_question_looks_follow_up(...)`、`_load_recent_history_for_follow_up(...)` 与 `_build_history_grounded_question(...)`，仅在疑似 follow-up 场景下把最近同 session 历史拼入检索问句；
- `api/services/session_store.py`：新增 `session_id` 到文件路径的安全清洗，避免 `eval::...` 一类评测 session_id 在 Windows 上落盘失败；
- `utils/logging_utils.py`：`append_json_log(...)` 改为逐次 `open(..., "a")` 写入并立即关闭句柄，避免 `session.log` 持有句柄阻塞临时目录清理；
- `tests/api/test_chat_service.py`、`tests/api/test_session_store.py`、`tests/test_logging_utils.py`：补充对应单测与半真实 follow-up 场景。

验证命令：
```bash
python -X utf8 -m pytest tests/test_logging_utils.py tests/api/test_session_store.py tests/api/test_chat_service.py tests/api/test_chat_eval_runner.py -q
# 33 passed in 9.57s
```

本轮判断：
1. chat 历史已经进入最小 follow-up 检索闭环，但它仍然只是**history-grounded retrieval**，不是完整多轮推理系统；
2. 该能力不改变 `default-deny`、单库范围或 evidence / preview 契约；
3. 对本地 Windows 评测链路来说，`session_id` 清洗与日志句柄释放已经成为正式评测稳定性的必要支撑；
4. 下一步应把 follow-up / multi-turn 从“支撑回归”继续提升为“正式评测数据集”，而不是只停留在实现层或单测层。

## 13. 2026-07-31 eval_v6 业务问答 + 弱信号诊断统一正式评测

### 13.1 定位
`eval_v6` 用于把两类信号合并到同一份正式 report 里：
1. `eval_v5` 已经证明稳定的业务问答主链路；
2. `eval_v3` 弱信号 / OCR / 嵌入异常的诊断能力。

它不是要用 diagnostic 样本去“冒充通过”，而是要让一份正式产物同时回答两个问题：“业务问答现在稳不稳”和“弱信号样本现在还差在哪里”。

### 13.2 数据集结构
目录：`tests/fixtures/rag_quality/eval_v6/`

组成方式：
- `eval_v5 (72 cases)` + `eval_v3 (6 cases)` => `eval_v6 (78 cases)`

最新结构校验结果：
- total = `78`
- modality = Markdown `24` / PDF `27` / image_ocr `27`
- difficulty = simple `30` / medium `24` / complex `24`
- answerable = `61` / no_evidence = `17` / preview_required = `61`
- weak_signal_case_count = `5`
- weak_signal_breakdown = `asset_registered_without_index: 3`, `dependency_missing: 1`, `nodes_without_embedding: 1`, `ocr_failed: 2`, `ocr_no_text: 1`, `zero_text_content: 1`
- CJK = `54`，且 Markdown / PDF / image_ocr 各 `18`

### 13.3 Gate 设计
`eval_v6` 同时保留两层 gate：
1. **Run Gate**：继续用业务问答指标衡量健康度，包括 `scope_pass_rate`、`average_keypoint_coverage`、`evidence_hit_rate`、`preview_resolvable_rate`、`source_count_match_rate`、`forbidden_term_clean_rate`。
2. **Diagnostic Gate**：要求“预期失败样本真的被观察到”，包括 `case_expectation_match_rate = 1.0`、`minimum_weak_signal_kb_count = 3`、`minimum_weak_signal_modality_count = 2`，以及六类 required signal tags 必须全部出现。

这意味着：`run_passed = false` 不自动等于“评测体系失效”；对 `eval_v6` 来说，更重要的是 diagnostic gate 是否通过，以及失败是否与预期一致。

### 13.4 执行命令与最新结果（2026-07-31）
数据集校验：
```bash
python -X utf8 scripts/validate_rag_quality_fixtures.py --eval-cases tests/fixtures/rag_quality/eval_v6/cases.json --eval-schema tests/fixtures/rag_quality/eval_v6/schema.json --print-eval-summary
# fixture validation passed
```

支撑测试：
```bash
python -X utf8 -m pytest tests/test_rag_quality_eval_dataset_v6.py tests/api/test_chat_eval_runner.py -q
# 14 passed in 12.11s
```

正式评测：
```bash
python -X utf8 -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v6/cases.json --schema tests/fixtures/rag_quality/eval_v6/schema.json --output-dir docs/20260722-local-multi-kb-assistant/artifacts/qa-eval
```

最新正式结果：
- `total_cases = 78`
- `passed_cases = 74`
- `failed_cases = 4`
- `run_passed = false`
- `scope_pass_rate = 1.0`
- `average_keypoint_coverage = 0.955`
- `evidence_hit_rate = 0.934 (57 / 61)`
- `preview_resolvable_rate = 0.984 (60 / 61)`
- `source_count_match_rate = 0.987`
- `forbidden_term_clean_rate = 1.0`
- `diagnostic_summary.case_expectation_match_rate = 1.0`
- `diagnostic_summary.weak_signal_case_count = 5`
- `diagnostic_gates` 全部通过

正式产物：
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v6_business_plus_diagnostic-semireal-report.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v6_business_plus_diagnostic-semireal-report.md`

### 13.5 当前判断
1. `eval_v6` 已经实现“业务问答稳定性 + 弱信号诊断可见性”合一的正式 artifact。
2. 当前 `74/78` 不是随机失败，而是 4 个 `scope_contract` 弱信号样本的预期失败；diagnostic gate 全通过，说明 runner / schema / import-qa correlation 都在正确反映问题。
3. 当前真正阻断 `run_passed` 的是 `evidence_hit_rate = 0.934 < 0.95`，根因主要集中在 weak-signal 样本下的 evidence / preview 契约缺口，不是 scope leakage 或 forbidden term 污染。
4. 下一步要做的不是继续拼数据集，而是先修掉这 4 个失败样本暴露出来的契约问题，例如 `doc_id` / `preview_locator` 缺失、弱信号拒答措辞不完整、声明范围表达不稳定等。


## 2026-08-17 评测口径更新

- 当前期望 `isolation_level` 为 `physical_isolated`。
- 旧 artifacts 中的 `logical_filter_only` 是历史证据，不回写伪造；新 fixture 和新报告必须使用新口径。
- OCR 质量除关键词召回外，增加行顺序准确率与表格单元格召回。
