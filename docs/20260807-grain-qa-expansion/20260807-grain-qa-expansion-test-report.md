# 20260807 Grain QA Expansion Test Report

## 背景

本次验证目标是把粮仓知识库真实 QA 从 30 条扩展到 80 条，并用恢复后的可用模型重新运行完整评测，替换此前因 LLM 免费额度耗尽导致的中断报告。

## 环境

- 日期：2026-08-07
- 分支：`codex/desktop-agent-stage3`
- Python：`/opt/miniconda3/envs/agent-kb/bin/python`
- API：`http://127.0.0.1:18080`
- LLM：`阿里百联 / qwen3.7-plus`
- 用例文件：`data/grain-knowledge-base/qa/verified.jsonl`
- 报告产物：`docs/20260722-local-multi-kb-assistant/artifacts/grain-qa/qa-eval-report.json`

## 执行命令

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.run_grain_qa_eval \
  --cases data/grain-knowledge-base/qa/verified.jsonl \
  --api-base http://127.0.0.1:18080 \
  --kb-id grain-knowledge-base \
  --output docs/20260722-local-multi-kb-assistant/artifacts/grain-qa/qa-eval-report.json
```

## 结果摘要

- `total=80`
- `answerable_total=77`
- `unanswerable_total=3`
- `error_count=0`
- `Recall@5=0.5325`
- `MRR@5=0.5238`
- `citation_hit_rate=1.0`
- `refusal_accuracy=0.6667`
- `kb_isolation_rate=1.0`

## 失败分组

- `api_error=0`：本轮没有 API 或模型调用错误。
- `retrieval_miss=17`：相关文件没有进入 top5。
- `rank_miss=1`：`grain-verified-0003` 召回正确资料但排序靠后。
- `source_noise=37`：多来源、重复来源或无关相似资料较多。
- `ocr_text_quality=19`：主要集中在 PDF、扫描件和表格样例相关问题。
- `duplicate_or_conflict=0`：本轮没有单独归入重复或冲突资料失败的用例。
- `kb_isolation_failure=0`：本轮没有来源 KB 泄露失败。
- `refusal_miss=1`：`grain-verified-0080` 是跨库拒答口径问题。

## 主要发现

本次失败的首要原因不是 LLM 回答能力，而是当前粮仓知识库索引覆盖不足。36 条 answerable 用例 Recall@5 为 0，其中 19 条期望文档类型为 PDF，17 条为 DOCX。抽查当前 `storage/docstore.json` 后发现，`grain-knowledge-base` 只有 543 个节点，约 13 个核心文件族；大量 QA 期望文件虽然存在于 `data/grain-knowledge-base/docs/`，但没有出现在当前 docstore 文件名统计中。

典型缺失文件包括：

- `粮油储藏技术规范-最新版.pdf`
- `粮油储藏理论与技术.pdf`
- `20180307基于粮情大数据分析的储粮安全水分分析辅助软件—技术需求报告.docx`
- `粮情调研报告v3.pdf`
- `粮食流通管理条例.docx`
- `粮食安全保障法.docx`
- `03仓房和粮堆隔热技术规程T3.docx`
- `04谷物冷却机经济运行技术规程T4.docx`
- `17空调控温储粮技术规程20160624.docx`
- `18磷化氢熏蒸蒸技术规程20160819.docx`

## 结论

下一阶段应优先做粮仓知识库导入覆盖与索引重建诊断：确认正式资料目录中的文件是否完成导入、是否写入 asset registry、是否进入 docstore、是否带有正确 `kb_id` metadata。完成覆盖修复后再复跑 80 条 QA，再决定是否继续优化 rerank、top-k、source 去重和拒答阈值。
