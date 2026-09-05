# 20260820 Docker RAG Eval Refresh Test Report

## 1. 测试目标与结论
本轮测试围绕“**用 Docker 重新创建 semireal RAG 评测环境、重构新的 `eval_v7` 测试集、并重新执行评测**”这个目标展开，闭环覆盖以下事项：

1. 提供可运行的 Docker 评测镜像配置；
2. 在 Docker 内重建新的 `eval_v7` holdout regression 数据集；
3. 在 Docker 内重新执行 fixture validation、pytest 与 semireal eval；
4. 对比宿主机与 Docker 结果，确认评测口径一致；
5. 产出可追溯的测试报告与结果文件。

**结论：本轮目标已完成。**
- `agent-kb-eval:latest` 镜像已存在，`docker image inspect` 显示镜像 ID 为 `sha256:64741ac2fed69b0dec2961c0a2da6368fe89053dc68bf7616a126e6370fed90e`，创建时间为 `2026-08-20T04:05:09.427432386Z`。
- Docker 内成功重建 `local_multi_kb_eval_v7_holdout_regression`，共 24 条 case。
- Docker 内 fixture validation 通过，schema / distribution / gate checks 全部满足要求。
- Docker 内 `pytest tests/test_rag_quality_eval_dataset_v7.py -q` 通过，结果为 `3 passed in 1.29s`。
- Docker 内 `run_chat_eval.py` semireal eval 通过，`24 / 24 passed`，`run_passed=true`。
- 宿主机与 Docker 的核心评测指标一致，说明当前 `eval` profile 足以稳定复现这条 semireal 评测链路。

## 2. 测试对象与范围
### 2.1 涉及文件
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\Dockerfile`
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\requirements-eval.txt`
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\scripts\build_eval_v7_holdout.py`
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\tests\fixtures\rag_quality\eval_v7\cases.json`
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\tests\fixtures\rag_quality\eval_v7\schema.json`
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\tests\test_rag_quality_eval_dataset_v7.py`
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\scripts\validate_rag_quality_fixtures.py`
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\scripts\run_chat_eval.py`

### 2.2 Docker 评测镜像设计
当前 `Dockerfile` 以 `python:3.12-slim` 为基础镜像，默认 `INSTALL_PROFILE=eval`，安装 `requirements-eval.txt` 中的轻量评测依赖，而不是完整开发依赖。镜像内保留以下关键环境变量：

- `PYTHONPATH=/app`
- `THINKRAG_EMBED_PREWARM=0`
- `THINKRAG_OCR_PREWARM=0`
- `EMBEDDING_ALLOW_REMOTE_DOWNLOAD=0`

该设计目标是：**优先支持 semireal harness、fixture 校验、pytest 和 eval 回归，而不是构建 full production OCR / embedding 镜像。**

### 2.3 本轮不覆盖内容
- GUI / Desktop 打包链路
- 完整生产级 OCR 依赖栈
- 实时外部 embedding 下载与真实远程模型调用
- full profile 的重量级开发镜像验证

## 3. 执行命令与结果
### 3.1 Docker 镜像存在性确认
```powershell
docker image inspect agent-kb-eval:latest --format "{{.Id}}|{{.Created}}"
```
结果：
```text
sha256:64741ac2fed69b0dec2961c0a2da6368fe89053dc68bf7616a126e6370fed90e|2026-08-20T04:05:09.427432386Z
```

### 3.2 Docker 内重建新的 `eval_v7` 数据集
```powershell
docker run --rm -e PYTHONPATH=/app -v "${PWD}:/app" agent-kb-eval:latest python scripts/build_eval_v7_holdout.py
```
结果：
```json
{
  "dataset_name": "local_multi_kb_eval_v7_holdout_regression",
  "total_cases": 24,
  "output_dir": "/app/tests/fixtures/rag_quality/eval_v7"
}
```

### 3.3 Docker 内 fixture validation
```powershell
docker run --rm -e PYTHONPATH=/app -v "${PWD}:/app" agent-kb-eval:latest python scripts/validate_rag_quality_fixtures.py --eval-cases tests/fixtures/rag_quality/eval_v7/cases.json --eval-schema tests/fixtures/rag_quality/eval_v7/schema.json --print-eval-summary
```
结果：`fixture 校验通过`

### 3.4 Docker 内 pytest
```powershell
docker run --rm -e PYTHONPATH=/app -v "${PWD}:/app" agent-kb-eval:latest python -m pytest tests/test_rag_quality_eval_dataset_v7.py -q
```
结果：
```text
3 passed in 1.29s
```

### 3.5 Docker 内 semireal eval
```powershell
docker run --rm -e PYTHONPATH=/app -v "${PWD}:/app" agent-kb-eval:latest python scripts/run_chat_eval.py --cases tests/fixtures/rag_quality/eval_v7/cases.json --schema tests/fixtures/rag_quality/eval_v7/schema.json --output-dir temp/eval-v7-docker-check
```
结果要点：
- `run_passed = true`
- `24 / 24 passed`
- PDF 文本层真实被 PyMuPDF 命中：`scope-manual.pdf`、`preview-guide.pdf`、`folder-boundary.pdf`、`metrics-gate.pdf`、`release-checklist-business.pdf`、`war-room-handover-business.pdf`、`long-cutover-handbook.pdf`

## 4. 新测试集 `eval_v7` 重建结果
### 4.1 数据集基本信息
- 数据集名：`local_multi_kb_eval_v7_holdout_regression`
- 总 case 数：`24`
- 输出目录：`C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\tests\fixtures\rag_quality\eval_v7`

### 4.2 分布统计
| 维度 | 结果 |
| --- | --- |
| modality | markdown 8 / pdf 8 / image_ocr 8 |
| difficulty | simple 6 / medium 9 / complex 9 |
| answer_style | fact 9 / policy 9 / comparison 3 / refusal 3 |
| category | 8 类，每类 3 条 |
| answerable | 21 |
| no_evidence | 3 |
| preview_required_cases | 21 |
| weak_signal_case_count | 0 |

### 4.3 Gate 检查
fixture validation 中的 gate checks 全部为 `true`：
- `minimum_total_cases`
- `minimum_cases_per_modality`
- `minimum_cases_per_difficulty`
- `minimum_no_evidence_cases`
- `minimum_preview_required_cases`
- `minimum_cases_per_answer_style`
- `minimum_cases_per_category`

说明新的 `eval_v7` 已满足 holdout regression 的结构约束，不是零散临时样本集。

## 5. 宿主机基线结果
宿主机已有同一套 `eval_v7` semireal 评测产物，作为对照基线：
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\temp\eval-v7-host-check\local_multi_kb_eval_v7_holdout_regression-semireal-report.json`
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\temp\eval-v7-host-check\local_multi_kb_eval_v7_holdout_regression-semireal-report.md`

宿主机核心指标如下：

| 指标 | 宿主机 |
| --- | ---: |
| total_cases | 24 |
| passed_cases | 24 |
| failed_cases | 0 |
| pass_rate | 1.0000 |
| pass_rate_ci95.low | 0.8620 |
| scope_pass_rate | 1.0000 |
| average_keypoint_coverage | 1.0000 |
| keypoint_hit_rate | 1.0000 |
| evidence_hit_rate | 1.0000 |
| preview_resolvable_rate | 1.0000 |
| preview_term_hit_rate | 1.0000 |
| source_count_match_rate | 1.0000 |
| forbidden_term_clean_rate | 1.0000 |

## 6. Docker 复测结果
### 6.1 Docker semireal suite summary
| 指标 | Docker |
| --- | ---: |
| total_cases | 24 |
| passed_cases | 24 |
| failed_cases | 0 |
| pass_rate | 1.0000 |
| pass_rate_ci95.low | 0.8620 |
| scope_pass_rate | 1.0000 |
| average_keypoint_coverage | 1.0000 |
| total_keypoints | 40 |
| matched_keypoints | 40 |
| missing_keypoints | 0 |
| keypoint_hit_rate | 1.0000 |
| evidence_expected_cases | 21 |
| evidence_hit_cases | 21 |
| evidence_hit_rate | 1.0000 |
| preview_required_cases | 21 |
| preview_resolved_cases | 21 |
| preview_resolvable_rate | 1.0000 |
| preview_term_total | 34 |
| preview_term_hits | 34 |
| preview_term_hit_rate | 1.0000 |
| source_count_match_rate | 1.0000 |
| blocked_term_hit_cases | 0 |
| forbidden_term_clean_rate | 1.0000 |

### 6.2 Docker run gates
| Gate | Actual | Minimum | Passed |
| --- | ---: | ---: | --- |
| scope_pass_rate_min | 1.0000 | 1.0000 | true |
| average_keypoint_coverage_min | 1.0000 | 0.8500 | true |
| evidence_hit_rate_min | 1.0000 | 0.9500 | true |
| preview_resolvable_rate_min | 1.0000 | 0.9500 | true |
| source_count_match_rate_min | 1.0000 | 0.9500 | true |
| forbidden_term_clean_rate_min | 1.0000 | 1.0000 | true |

### 6.3 Docker import / preview 摘要
| 指标 | Docker |
| --- | ---: |
| total_kbs | 3 |
| total_files | 24 |
| total_success_count | 24 |
| total_failed_count | 0 |
| total_empty_count | 0 |
| total_indexed_chunks | 24 |
| total_document_count | 24 |
| total_node_count | 24 |
| total_input_text_chars | 6394 |
| total_ocr_success_count | 6 |
| total_asset_registered_count | 6 |
| requested preview cases | 21 |
| required preview cases | 21 |
| skipped preview cases | 0 |
| failure_stage_breakdown | {} |

## 7. 宿主机 vs Docker 对比
| 指标 | 宿主机 | Docker | 是否一致 |
| --- | ---: | ---: | --- |
| total_cases | 24 | 24 | 是 |
| passed_cases | 24 | 24 | 是 |
| failed_cases | 0 | 0 | 是 |
| pass_rate | 1.0000 | 1.0000 | 是 |
| scope_pass_rate | 1.0000 | 1.0000 | 是 |
| average_keypoint_coverage | 1.0000 | 1.0000 | 是 |
| keypoint_hit_rate | 1.0000 | 1.0000 | 是 |
| evidence_hit_rate | 1.0000 | 1.0000 | 是 |
| preview_resolvable_rate | 1.0000 | 1.0000 | 是 |
| preview_term_hit_rate | 1.0000 | 1.0000 | 是 |
| source_count_match_rate | 1.0000 | 1.0000 | 是 |
| forbidden_term_clean_rate | 1.0000 | 1.0000 | 是 |
| run_gates | 全通过 | 全通过 | 是 |

结论：**宿主机与 Docker 的核心指标完全对齐**，说明 `eval_v7` 的 semireal 回归链路可以在 Docker `eval` profile 中稳定重放。

## 8. 指标解读与边界说明
### 8.1 为什么本轮能做到 1.0
本轮 1.0 代表的是：
- 在当前固定的 `eval_v7` 闭集评测中；
- 在当前冻结的 fixture / schema / semireal harness 下；
- 系统对 scope、keypoint、evidence、preview、source-count、forbidden term 等约束没有出现回归。

这说明**评测链路稳定**，不等于“真实世界所有开放问题都 100% 正确”。

### 8.2 95% CI 的含义
虽然 `24 / 24` 都通过，但 `pass_rate_ci95.low = 0.8620`。这说明：
- 当前样本规模仍然较小；
- 本轮更适合证明“当前回归集内没有失手”；
- 不能把这 24 条 case 直接外推出真实线上场景也必然 100% 通过。

### 8.3 为什么当前 `eval` profile 依然是有价值的
当前 Docker 默认 profile 是 **semireal eval profile**，不是 full production OCR / embedding image。它的价值在于：
- 可独立重放 fixture 结构校验；
- 可验证 query contract、scope contract、no-evidence refusal；
- 可验证 evidence grounding、preview resolvability、source count 等关键指标；
- 可用于 CI / 回归环境快速重跑；
- 能避免为了 semireal harness 强行引入重型 OCR/embedding 依赖，降低构建复杂度。

换句话说，本轮交付的是“**可复现评测环境**”，不是“**完整生产部署镜像**”。

## 9. 产物位置
### 9.1 Docker 产物
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\temp\eval-v7-docker-check\local_multi_kb_eval_v7_holdout_regression-semireal-report.json`
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\temp\eval-v7-docker-check\local_multi_kb_eval_v7_holdout_regression-semireal-report.md`

### 9.2 宿主机产物
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\temp\eval-v7-host-check\local_multi_kb_eval_v7_holdout_regression-semireal-report.json`
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\temp\eval-v7-host-check\local_multi_kb_eval_v7_holdout_regression-semireal-report.md`

### 9.3 fixture 目录
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\tests\fixtures\rag_quality\eval_v7\cases.json`
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\tests\fixtures\rag_quality\eval_v7\schema.json`

## 10. 最终结论
围绕用户提出的“**Docker 重新创造一个环境，然后重新构造一份新的测试集，然后重新测试**”这一目标，本轮已经形成完整闭环：

1. Docker 评测镜像已配置并存在；
2. 新测试集 `eval_v7` 已在 Docker 内重建；
3. Docker 内 fixture validation 已通过；
4. Docker 内 pytest 已通过；
5. Docker 内 semireal eval 已通过；
6. 宿主机与 Docker 结果一致；
7. 报告与产物已落盘，可继续用于面试说明、回归检查或后续提交。
