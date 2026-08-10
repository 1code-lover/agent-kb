# 20260810 Grain Retrieval Quality Tuning Plan

## 实施原则

先实验，后改代码。所有实验优先走检索-only 路径，减少 LLM 生成成本；只有候选方案明确后，才复跑完整 80 条 QA。

## Task 1：实验矩阵与诊断脚本

- 新增或扩展脚本，输出检索-only 报告。
- 输入：
  - `data/grain-knowledge-base/qa/verified.jsonl`
  - `storage/kbs/grain-knowledge-base/`
  - `docs/20260722-local-multi-kb-assistant/artifacts/grain-qa/qa-eval-report.json`
- 实验变量：
  - `top_k=5/8/10`
  - fusion mode：`dist_based_score`、`relative_score`、`reciprocal_rerank`
  - reranker：关闭 / 开启且 `top_n=5`
- 输出：
  - 每条 case 的 top source files、hit rank、MRR、failure group。
  - 0034、0078 的候选 chunk、metadata、得分和原文片段。
  - 汇总指标和推荐方案。

## Task 2：定位剩余失败

- 检查 0034：
  - 期望文件 `粮油储藏技术规范-最新版.pdf` 是否被检索-only 召回。
  - 当前 Top source 是否来自重复规范 `GBT29890-2013粮油储藏技术规范.pdf`。
  - 是否属于标注等价文档、排序问题或 PDF chunk 问题。
- 检查 0078：
  - 期望文件 `17空调控温储粮技术规程20160624.docx` 是否在 docstore。
  - 查询词“空调控温储粮技术规程”是否能命中文件名或标题。
  - 是否需要对标题/文件名命中增加轻量 boost。

## Task 3：最小实现

根据实验结果选择最小改动，候选优先级：

1. 对返回 sources 做跨文件噪声抑制或同主题文件名 boost。
2. 在检索融合后对文件名/标题与 query 的强匹配增加轻量排序 boost。
3. 如本地 reranker 可用且收益稳定，再启用 reranker 或作为可配置选项；否则不强依赖。

## Task 4：验证

必须执行：

```bash
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diagnose_grain_qa_coverage \
  --cases data/grain-knowledge-base/qa/verified.jsonl \
  --kb-id grain-knowledge-base \
  --storage-dir storage \
  --data-root data/grain-knowledge-base \
  --output docs/20260807-grain-index-coverage-repair/artifacts/grain-coverage-diagnostic.json
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.run_grain_qa_eval \
  --cases data/grain-knowledge-base/qa/verified.jsonl \
  --api-base http://127.0.0.1:18080 \
  --kb-id grain-knowledge-base \
  --output docs/20260722-local-multi-kb-assistant/artifacts/grain-qa/qa-eval-report.json
```

## Task 5：文档和提交

- 更新本目录测试报告。
- 更新 `docs/project.md`。
- 覆盖更新 `评审建议.txt`。
- 提交前沉淀开发故事。
- commit 并 push。
