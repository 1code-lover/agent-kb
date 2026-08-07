# 粮仓知识库 QA 扩测与失败分组

## 基本信息
- 类型：feature
- 日期：2026-08-07
- 相关模块：粮仓知识库评测、QA 数据集、项目进度文档
- 相关文件：`scripts/run_grain_qa_eval.py`、`tests/scripts/test_run_grain_qa_eval.py`、`data/grain-knowledge-base/qa/verified.jsonl`、`docs/20260722-local-multi-kb-assistant/artifacts/grain-qa/qa-eval-report.json`、`docs/project.md`、`评审建议.txt`

## 需求背景

粮仓知识库原本只有 30 条 verified QA，评测结果全绿，但样本过少，不能代表 PDF、扫描件、表格、重复资料、跨库隔离和负向拒答等真实使用场景。用户希望先做完整知识库测试，再根据评测结果决定后续开发方向，而不是在样本不足时直接调检索参数。

## 设计与实现方案

本次把 `data/grain-knowledge-base/qa/verified.jsonl` 扩展到 80 条，覆盖正向、负向、跨库隔离、PDF、扫描件、表格和重复资料等场景。`scripts/run_grain_qa_eval.py` 增加了逐条 `tags`、`relevant_doc_types`、`requested_kb_ids` 输出，并修正评测时优先使用用例内的 `search_kb_ids`，使跨库隔离用例可以真实请求 `default` 知识库。

评测脚本新增 `classify_failure_groups()` 和 `build_failure_groups()`，把失败按 `api_error`、`retrieval_miss`、`rank_miss`、`source_noise`、`ocr_text_quality`、`duplicate_or_conflict`、`kb_isolation_failure`、`refusal_miss` 聚合。报告会显式输出全部失败类型，即使某类本轮计数为 0，也保留空样例，方便后续看板和人工复核稳定读取。模型配置恢复后，重新跑完整 80 条 QA，生成 `qa-eval-report.json`，并把结论更新到 `docs/project.md`、`评审建议.txt` 和本次测试报告。

## 为什么选这个方案

评测脚本的核心职责是给后续开发排序，因此先增强可解释性比直接调参更有价值。把 tags、文档类型和请求 KB 范围写入结果，可以让同一份报告同时回答“哪类资料失败”“是不是跨库请求错了”“是不是 PDF/OCR 问题”。修正 `search_kb_ids` 也避免了跨库用例表面通过、实际没有覆盖隔离路径的问题。

## 其他方案与为什么没选

推断：可以直接把 top-k 调大或启用 reranker，但在当前索引覆盖不足时，参数优化容易掩盖“文件没进索引”的根因。

推断：也可以先做 LLM 裁判式答案评分，但当前最主要风险是检索是否命中文档，先做检索和引用指标更稳定、更省成本，也更容易自动回归。

## 风险与权衡

`failure_groups` 是规则归类，不等于最终根因诊断。例如 PDF 未召回会先归到 `ocr_text_quality`，但实际也可能是文件没有导入。为控制这个风险，报告和项目文档都明确写出下一步要做导入覆盖诊断：检查本地文件、asset registry、docstore 节点、metadata 和 top5 召回。

另一个权衡是把被 `.gitignore` 忽略的 `verified.jsonl` 纳入提交。为了让评测报告可复现，这份 QA 数据应当随评测脚本一起版本化。

## 验证与结果

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_run_grain_qa_eval.py -q`：`6 passed, 1 warning`
- 报告结构审计：`api_error`、`retrieval_miss`、`rank_miss`、`source_noise`、`ocr_text_quality`、`duplicate_or_conflict`、`kb_isolation_failure`、`refusal_miss` 全部存在，其中 `duplicate_or_conflict=0`、`kb_isolation_failure=0`
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.run_grain_qa_eval --cases data/grain-knowledge-base/qa/verified.jsonl --api-base http://127.0.0.1:18080 --kb-id grain-knowledge-base --output docs/20260722-local-multi-kb-assistant/artifacts/grain-qa/qa-eval-report.json`：80 条完整跑完，`error_count=0`
- 评测结果：`Recall@5=0.5325`、`MRR@5=0.5238`、`citation_hit_rate=1.0`、`refusal_accuracy=0.6667`、`kb_isolation_rate=1.0`
- 失败分组：`ocr_text_quality=19`、`retrieval_miss=17`、`source_noise=37`、`rank_miss=1`、`refusal_miss=1`
- `git diff --check`：通过

## 面试表达版本

我接手粮仓知识库质量评估时，原来只有 30 条 verified QA，结果全绿但覆盖面不够。我先把评测集扩到 80 条，加入 PDF、扫描件、表格、跨库隔离和拒答场景，同时增强评测脚本，让每条结果带上标签、文档类型、请求 KB 范围和失败分组。恢复可用模型后我跑完整评测，发现 Recall@5 只有 0.5325，36 条可回答问题完全没召回。继续查 docstore 后发现，很多本地资料根本没有进入当前索引，所以我把下一步开发方向从调参收敛到导入覆盖和索引重建诊断。这避免了在错误根因上优化，也让后续每次改动都可以用同一套 QA gate 回归。
