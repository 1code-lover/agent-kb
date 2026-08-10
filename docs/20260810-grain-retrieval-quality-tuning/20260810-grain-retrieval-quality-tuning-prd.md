# 20260810 Grain Retrieval Quality Tuning PRD

## 背景

2026-08-10 粮仓知识库索引覆盖修复后，80 条 verified QA 已达到 `error_count=0`、`Recall@5=0.974`、`MRR@5=0.8961`、`refusal_accuracy=1.0`、`kb_isolation_rate=1.0`。当前问题不再是导入覆盖，而是检索质量微调。

剩余问题集中在：

- 2 条 answerable 漏召回：
  - `grain-verified-0034`：粮堆结露处理
  - `grain-verified-0078`：空调控温储粮技术规程适用条件
- 11 条 `rank_miss`：相关文档进入 Top5，但不是第一位。
- 4 条 `source_noise`：同文件去重已生效，但跨文件相似资料仍干扰证据排序。

## 目标

1. 建立可复跑的检索质量实验矩阵，比较 `top_k=5/8/10`、fusion mode、reranker 开关与 `top_n` 组合。
2. 检查 0034、0078 的原文 chunk 是否存在、是否切分合理、是否能被 BM25/向量任一路召回。
3. 在不降低当前 Recall、拒答和 KB 隔离指标的前提下，提高首位命中与 MRR，降低 source_noise。
4. 复跑 80 条 QA，确认：
   - `error_count=0`
   - `kb_isolation_rate=1.0`
   - `refusal_accuracy=1.0`
   - `Recall@5 >= 0.974`
   - `MRR@5 > 0.8961`
   - `retrieval_miss=0`
   - `source_noise <= 4` 且不反弹

## 范围

包含：

- 检索-only 实验脚本和报告。
- 针对 0034、0078 的 chunk/来源诊断。
- 必要的最小检索排序或查询增强改动。
- 对应单元测试、测试报告、项目进度文档更新。

不包含：

- 重建整个粮仓知识库。
- 继续补导入正式资料以外的新文档。
- LLM 主观答案评分。
- 大规模前端证据展示重构。

## 验收标准

- 实验矩阵有 JSON/Markdown 产物，能说明为什么选择最终方案。
- 最终 80 条 QA 报告满足目标指标。
- 2 条 answerable 漏召回全部恢复 Top5。
- rank_miss 数量下降，MRR@5 提升。
- source_noise 不高于当前 4 条。
- 所有改动有自动化测试覆盖，并使用 `/opt/miniconda3/envs/agent-kb/bin/python` 验证。
