# 20260807 Grain Index Coverage Repair Plan

## 背景

2026-08-07 粮仓知识库 80 条 verified QA 完整评测已经跑完，`error_count=0`，但 `Recall@5=0.5325`、`MRR@5=0.5238`。失败清单显示 36 条可回答问题 Recall@5 为 0，其中 19 条期望文档为 PDF，17 条为 DOCX。

进一步抽查 KB-scoped `storage/kbs/grain-knowledge-base/docstore.json` 发现，当前索引只有约 13 个核心文件族；`storage/kb_assets/grain-knowledge-base.json` 为空。后续确认 asset registry 主要登记图片和嵌入资产，普通 PDF/DOCX 不应以 asset registry 作为导入成功条件；真正的问题是大量本地资料没有进入 docstore。

因此下一阶段优化项按优先级排列如下：先修导入覆盖和索引一致性，再处理排序、噪声和拒答阈值。

## 目标

1. 让 `data/grain-knowledge-base/docs/` 下正式资料目录中的目标文档可诊断、可导入、可追踪。
2. 对 80 条 QA 的每个期望文件输出覆盖状态：本地存在、asset registry 存在、docstore 节点存在、metadata 正确、top5 召回。
3. 修复或重建 `grain-knowledge-base` 索引，使 36 条 Recall@5=0 的用例优先恢复召回。
4. 在索引覆盖修复后复跑 80 条 eval，再决定 rerank、top-k、source 去重和拒答策略是否需要开发。

## 开发任务

### Task 1：新增粮仓 QA 覆盖诊断脚本

- 新增脚本：`scripts/diagnose_grain_qa_coverage.py`
- 输入：
  - `--cases data/grain-knowledge-base/qa/verified.jsonl`
  - `--kb-id grain-knowledge-base`
  - `--storage-dir storage`
  - `--data-root data/grain-knowledge-base`
  - `--output docs/20260807-grain-index-coverage-repair/artifacts/grain-coverage-diagnostic.json`
- 输出每个期望文件的状态：
  - `case_id`
  - `file_name`
  - `expected_path`
  - `local_exists`
  - `asset_registry_applicable`
  - `asset_registry_hit`
  - `docstore_node_count`
  - `docstore_kb_id_count`
  - `metadata_file_name_variants`
  - `top5_hit`
  - `failure_reason`
- 预期失败原因枚举：
  - `missing_local_file`
  - `missing_asset_registry`
  - `missing_docstore_nodes`
  - `missing_or_wrong_kb_id`
  - `retrieval_not_top5`
  - `ok`

### Task 2：为覆盖诊断补单元测试

- 新增测试：`tests/scripts/test_diagnose_grain_qa_coverage.py`
- 覆盖场景：
  - 本地文件存在但 docstore 缺节点。
  - docstore 有节点但 `kb_id` 缺失或错误。
  - 普通 PDF/DOCX 的 asset registry 为空时仍能按 docstore/top5 正确判定。
  - 图片类资产的 asset registry 为空时输出 `missing_asset_registry`。
  - 文件名存在 hash 后缀或全角/半角括号差异时仍能归一匹配。
  - top5 命中但 registry 缺失时同时保留多个诊断信号。

### Task 3：补齐或重建粮仓知识库导入

- 优先使用现有导入 API 和 `scripts/import_grain_kb_batches.py`。
- 对正式目录执行批量导入：
  - `docs/01-standards-regulations/`
  - `docs/02-storage-operations/`
  - `docs/03-monitoring-analysis/`
  - `docs/04-regulation-platform/`
  - `docs/07-templates-samples/`
- 对诊断出的缺失文件支持 `--file` 精确导入；本轮补入 19 个唯一文件，包含 QA 必需的 `docs/99-other/相邻粮层温差法补充说明.pdf`。
- 对 `docs/98-duplicates-to-review/` 暂不默认导入到正式索引，先用于重复/冲突样本验证。
- 导入完成后要求：
  - 普通 PDF/DOCX 不要求出现在 asset registry；图片/嵌入资产按适用性检查。
  - `storage/kbs/grain-knowledge-base/docstore.json` 中 QA 期望文件均存在节点。
  - 新节点 metadata 包含 `kb_id=grain-knowledge-base`。
  - `storage/kb_registry.json` 的 `doc_count` 与导入后实际文档数接近。

### Task 4：复跑 80 条 QA eval

- 命令：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.run_grain_qa_eval \
  --cases data/grain-knowledge-base/qa/verified.jsonl \
  --api-base http://127.0.0.1:18080 \
  --kb-id grain-knowledge-base \
  --output docs/20260722-local-multi-kb-assistant/artifacts/grain-qa/qa-eval-report.json
```

- 验收门槛：
  - `error_count=0`
  - `kb_isolation_rate=1.0`
  - `Recall@5` 明显高于当前 `0.5325`
  - 36 条当前 Recall@5=0 用例中，至少 24 条恢复召回
  - PDF/表格样例失败数下降；若仍失败，必须能用覆盖诊断报告说明是 OCR/版面问题还是检索问题

### Task 5：索引覆盖修复后再治理排序与 sources 噪声

- 若覆盖修复后仍有 `rank_miss`：
  - 评估启用 reranker。
  - 对比 `top_k=5/8/10` 和 `top_n=2/3/5`。
- 若 `source_noise` 仍高：
  - 在后端 source 返回前按 `kb_id + file_name` 合并重复 chunk。
  - 前端证据展示默认折叠同文件多 chunk。
- 若拒答失败仍存在：
  - 区分“检索应无结果”和“用例期望文档仅用于隔离说明”的评测口径。
  - 修正 unanswerable 用例的 recall 计算，避免把不应返回的资料当作正向相关文件。

### 已实施结果（2026-08-10）

- 覆盖诊断脚本、单元测试和 KB-scoped docstore 读取已完成。
- 导入脚本新增重复 `--file` 参数，19 个唯一缺失文件定向导入全部成功。
- QA 期望文档覆盖达到 `local=82/82`、`docstore=82/82`、正确 `kb_id=82/82`。
- 80 条 QA 复评达到 `answerable Recall@5=0.974`、`MRR@5=0.8961`、`error_count=0`、`citation_hit_rate=1.0`、`refusal_accuracy=1.0`、`kb_isolation_rate=1.0`。
- 后端已按 `kb_id + file` 合并重复 source，`source_noise` 从 13 条降至 4 条。
- 当前剩余问题是 2 个 answerable 漏召回和 11 个命中但首位排序不佳；它们已不再是索引覆盖问题。

## 验证命令

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diagnose_grain_qa_coverage.py -q
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_run_grain_qa_eval.py -q
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diagnose_grain_qa_coverage \
  --cases data/grain-knowledge-base/qa/verified.jsonl \
  --kb-id grain-knowledge-base \
  --storage-dir storage \
  --data-root data/grain-knowledge-base \
  --output docs/20260807-grain-index-coverage-repair/artifacts/grain-coverage-diagnostic.json
```

## 当前不优先做的事

- 不先调大 top-k 掩盖索引缺文档问题。
- 不先做 LLM 答案裁判，因为当前主要问题是检索召回。
- 不把 `98-duplicates-to-review` 全量混入正式索引，避免重复资料进一步放大 source 噪声。
- 不把 80 条 QA 结果当成最终质量达标；它现在是定位下一步开发的基线。
