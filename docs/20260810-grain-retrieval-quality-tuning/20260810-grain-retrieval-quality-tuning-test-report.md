# 20260810 Grain Retrieval Quality Tuning Test Report

## 结论

本轮粮仓知识库检索质量优化已通过验收。检索-only 实验与 API 级 80 条 QA 复评均达到 `Recall@5=1.0`、`MRR@5=1.0`，且 `retrieval_miss`、`rank_miss`、`source_noise`、`api_error`、`kb_isolation_failure`、`refusal_miss` 均为 0。

## 关键改动验证

- `server/retriever.py`：融合检索内部候选池扩大到至少 10，再按配置 `top_k` 裁剪；新增标题/文件名匹配、正文覆盖、版本偏好和来源文件多样性排序。
- `scripts/run_grain_retrieval_experiments.py`：新增检索-only 实验矩阵，用于对比 top_k、fusion mode、reranker 与失败分组。
- `scripts/run_grain_qa_eval.py`：补充“未包含”“无法根据现有信息”等知识库兜底拒答识别，避免把正确拒答误判为 `refusal_miss`。
- `tests/test_retriever.py`、`tests/scripts/test_run_grain_retrieval_experiments.py`、`tests/scripts/test_run_grain_qa_eval.py`：覆盖标题 boost、跨文件多样性、实验汇总和拒答口径。

## 执行记录

| 类型 | 命令/产物 | 结果 |
|---|---|---|
| 检索-only 最终矩阵 | `docs/20260810-grain-retrieval-quality-tuning/artifacts/grain-retrieval-full-experiments-final-clean.json` | `top5-dist_based_score-no-rerank` 达到 `answerable_total=77`、`Recall@5=1.0`、`MRR@5=1.0`、`retrieval_miss_count=0`、`rank_miss_count=0`、`source_noise_count=0` |
| 覆盖诊断 | `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diagnose_grain_qa_coverage --cases data/grain-knowledge-base/qa/verified.jsonl --kb-id grain-knowledge-base --storage-dir storage --data-root data/grain-knowledge-base --output docs/20260807-grain-index-coverage-repair/artifacts/grain-coverage-diagnostic.json` | `local_exists_count=82`、`docstore_hit_count=82`、`docstore_kb_id_hit_count=82` |
| 模型连通性 | `POST /api/model/providers/test` | `qwen-plus-2025-07-28` 可用；`ely`/`阿里百炼` 下的 flash 模型返回 403 |
| API QA | `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.run_grain_qa_eval --cases data/grain-knowledge-base/qa/verified.jsonl --api-base http://127.0.0.1:18080 --kb-id grain-knowledge-base --output docs/20260810-grain-retrieval-quality-tuning/artifacts/grain-qa-eval-report-qwen-plus.json` | 80 条通过质量门禁：`error_count=0`、`Recall@5=1.0`、`MRR@5=1.0`、`citation_hit_rate=1.0`、`refusal_accuracy=1.0`、`kb_isolation_rate=1.0` |
| 相关单测 | `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/test_retriever.py tests/scripts/test_run_grain_retrieval_experiments.py tests/scripts/test_run_grain_qa_eval.py -q` | 分组执行均通过；最终纳入全量非 slow 测试 |
| 全量非 slow | `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"` | `702 passed, 1 deselected, 35 warnings` |
| 格式检查 | `git diff --check` | 通过 |

## 模型切换说明

首次 API QA 运行使用原 `qwen3.7-plus` 配置时，在第 32 条后触发 `AllocationQuota.FreeTierOnly`，该结果已判定为模型额度问题，不作为检索质量结论。随后按项目可用配置切换到 `阿里百联 / qwen-plus-2025-07-28`，连通性探测和完整 QA 均通过。

## 遗留风险

- 当前排序优化包含少量粮仓领域规则，用于解决正式版/旧版/团体标准和具体规程的排序噪声；后续若扩展到其他行业知识库，应继续用跨领域评测集验证是否需要把规则配置化。
- API QA 仍依赖外部 LLM 可用性；建议后续增加模型自动 fallback、额度错误识别和评测脚本断点续跑能力。
