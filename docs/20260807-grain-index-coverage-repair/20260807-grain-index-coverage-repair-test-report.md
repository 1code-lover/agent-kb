# 20260807 Grain Index Coverage Repair Test Report

## 测试范围

本报告覆盖粮仓知识库索引覆盖修复、定向导入、80 条 verified QA 复评、source 去重和拒答评测口径修正。

## 验证环境

- 日期：2026-08-10
- Python：`/opt/miniconda3/envs/agent-kb/bin/python`
- API：`http://127.0.0.1:18080`
- KB：`grain-knowledge-base`

## 执行结果

- 诊断脚本回归：`8 passed, 1 warning`
- 导入脚本、QA eval、聊天 source 去重相关回归：`50 passed, 7 warnings`
- 定向导入：19 个唯一缺失文件，`passed=19`、`failed=0`
- 覆盖诊断：`local=82/82`、`docstore=82/82`、`kb_id=82/82`、`top5=78/82`
- 80 条 QA 复评：`error_count=0`、`Recall@5=0.974`、`MRR@5=0.8961`、`citation_hit_rate=1.0`、`refusal_accuracy=1.0`、`kb_isolation_rate=1.0`

## 主要产物

- `docs/20260807-grain-index-coverage-repair/artifacts/grain-coverage-diagnostic.json`
- `docs/20260807-grain-index-coverage-repair/artifacts/grain-missing-docstore-files.txt`
- `docs/20260807-grain-index-coverage-repair/artifacts/grain-kb-import-report-20260809T020033Z.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/grain-qa/qa-eval-report.json`

## 结论

计划门槛已满足：索引覆盖缺口清零，80 条 QA 无 API 错误、KB 隔离和拒答评测通过，answerable Recall@5 从旧基线 `0.5325` 提升到 `0.974`。source 噪声已通过后端按 `kb_id + file` 去重明显下降。

剩余 2 个 answerable 漏召回属于后续检索排序/语义相似度优化候选，不阻塞本轮索引覆盖修复验收。
