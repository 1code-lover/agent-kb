# 粮仓知识库索引覆盖修复与 QA Gate 收口

## 基本信息
- 类型：feature
- 日期：2026-08-10
- 相关模块：粮仓知识库导入、覆盖诊断、QA 评测、聊天来源去重
- 相关文件：`scripts/diagnose_grain_qa_coverage.py`、`scripts/import_grain_kb_batches.py`、`scripts/run_grain_qa_eval.py`、`api/services/chat_service.py`、`docs/20260807-grain-index-coverage-repair/`、`docs/project.md`

## 需求背景

80 条粮仓 verified QA 的旧基线显示 `Recall@5=0.5325`，36 条可回答用例完全没有召回。表面上看 failure_groups 里有大量 `ocr_text_quality` 和 `source_noise`，但继续抽查发现，很多本地存在的 PDF/DOCX 根本没有进入 `grain-knowledge-base` 的 KB-scoped docstore。用户要求按计划把四项优化全部做完并合格，所以本次目标不是单纯调参，而是先把“文件存在、索引存在、kb_id 正确、QA 可召回”做成可验证闭环。

## 设计与实现方案

我新增了 `scripts/diagnose_grain_qa_coverage.py`，逐条读取 `verified.jsonl` 的期望文档，检查本地文件、asset registry 适用性、KB-scoped docstore 节点、metadata `kb_id` 和 eval Top5 命中。过程中修正了一个关键口径：`storage/kb_assets/{kb_id}.json` 主要服务图片和嵌入资产，普通 PDF/DOCX 不应因为 asset registry 为空而被判为导入失败。

导入侧，我给 `scripts/import_grain_kb_batches.py` 增加重复 `--file` 参数，支持从诊断结果精确导入缺失文件。这样可以避开全量批次导入里大 PDF 拖慢或卡住的问题。本轮根据诊断清单定向导入 19 个唯一缺失文件，最终 QA 期望文档达到 `local=82/82`、`docstore=82/82`、正确 `kb_id=82/82`。

评测侧，我修正了 `scripts/run_grain_qa_eval.py` 的拒答判断，把跨库隔离回答里的“不应返回”和 LlamaIndex 的 `Empty Response` 都识别为正确边界回答。后端还在 `api/services/chat_service.py` 增加按 `kb_id + file` 的 sources 去重，减少同一个文件多个 chunk 重复出现在证据列表里的噪声。

## 为什么选这个方案

先做覆盖诊断，是因为旧评测的最大风险不是模型不会答，而是资料没有进入检索索引。如果直接调大 top-k 或启用 reranker，可能会掩盖索引缺文档的根因。精确 `--file` 导入则让补洞动作更可控：每个缺失文件都能在导入报告里定位成功或失败，避免全量导入失败后不知道卡在哪个文件。

## 其他方案与为什么没选

推断：可以重建整个粮仓 KB，但当前已有一部分索引可用，完全重建会带来更长耗时和更大运行时风险。本次选择先按 QA gate 补齐缺口，能更快证明质量是否恢复。

推断：可以立即做 reranker/top-k 实验，但覆盖修复后 answerable `Recall@5` 已提升到 `0.974`，剩余问题更适合作为下一轮小范围排序实验，而不是和索引修复混在同一个风险窗口里。

## 风险与权衡

覆盖诊断里的 Top5 是基于当前 eval 报告的来源列表，因此会随拒答口径和 source 去重变化。例如无答案隔离用例现在正确返回空 sources，会让期望 `readme.md` 的 Top5 命中变成 false；这不代表索引覆盖失败，所以最终验收同时看 `docstore=82/82` 和 answerable `Recall@5=0.974`。

source 去重保留同一 `kb_id + file` 的首个 chunk，减少证据噪声，但不会改变底层检索排序。后续如果要提升 11 条 rank_miss，需要单独评估 reranker、查询改写或 top_k/top_n 组合。

## 验证与结果

- 定向导入报告：19 个唯一缺失文件，`passed=19`、`failed=0`
- 覆盖诊断：`local=82/82`、`docstore=82/82`、`kb_id=82/82`、`top5=78/82`
- 80 条 QA 复评：`error_count=0`、`Recall@5=0.974`、`MRR@5=0.8961`、`citation_hit_rate=1.0`、`refusal_accuracy=1.0`、`kb_isolation_rate=1.0`
- failure_groups：`retrieval_miss=1`、`rank_miss=11`、`source_noise=4`、`ocr_text_quality=1`、`refusal_miss=0`
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diagnose_grain_qa_coverage.py tests/scripts/test_import_grain_kb_batches.py tests/scripts/test_run_grain_qa_eval.py tests/api/test_chat_service.py -q`：`50 passed, 7 warnings`
- `git diff --check`：通过

## 面试表达版本

我接手粮仓知识库质量问题时，80 条 QA 的 Recall@5 只有 0.5325。第一反应不能是调 top-k，因为失败可能是资料没进索引。我先做了一个覆盖诊断脚本，把每个期望文件拆成本地存在、docstore 节点、kb_id metadata 和 Top5 召回几个维度。诊断发现真正缺的是索引覆盖，于是我给导入脚本加了精确文件导入能力，按缺口补入 19 个唯一文件。补完后，82 个期望文档全部进入正确 KB 的 docstore，80 条 QA 的 Recall@5 提升到 0.974，拒答和 KB 隔离都是 1.0。最后我再做 source 去重，把重复 chunk 噪声降下来。这个过程的关键是先证明根因，再做最小可验证修复，而不是用参数调优掩盖数据问题。
