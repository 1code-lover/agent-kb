# 问答评测报告：local_multi_kb_eval_v1

- 运行时间：2026-07-30T03:37:11.840042+00:00
- 总用例数：54
- 通过用例：54
- 失败用例：0
- 运行结论：通过

## 1. Suite 摘要

| 指标 | 数值 |
| --- | --- |
| pass_rate | 1.000 |
| pass_rate_ci95 | [0.934, 1.000] |
| scope_pass_rate | 1.000 |
| average_keypoint_coverage | 1.000 |
| total_keypoints | 159 |
| matched_keypoints | 159 |
| keypoint_hit_rate | 1.000 |
| evidence_expected_cases | 45 |
| evidence_hit_cases | 45 |
| evidence_hit_rate | 1.000 |
| preview_required_cases | 45 |
| preview_resolved_cases | 45 |
| preview_resolvable_rate | 1.000 |
| preview_term_total | 0 |
| preview_term_hits | 0 |
| preview_term_hit_rate | 1.000 |
| source_count_match_rate | 1.000 |
| blocked_term_hit_cases | 0 |
| forbidden_term_clean_rate | 1.000 |

## 2. Run Gate

| Gate | 指标 | 实际值 | 阈值 | 结果 |
| --- | --- | --- | --- | --- |
| scope_pass_rate_min | scope_pass_rate | 1.000 | 1.000 | 通过 |
| average_keypoint_coverage_min | average_keypoint_coverage | 1.000 | 0.900 | 通过 |
| evidence_hit_rate_min | evidence_hit_rate | 1.000 | 0.950 | 通过 |
| preview_resolvable_rate_min | preview_resolvable_rate | 1.000 | 0.950 | 通过 |
| source_count_match_rate_min | source_count_match_rate | 1.000 | 0.950 | 通过 |
| forbidden_term_clean_rate_min | forbidden_term_clean_rate | 1.000 | 1.000 | 通过 |

## 3. Preview 请求摘要

| 指标 | 数值 |
| --- | --- |
| required_cases | 45 |
| requested_cases | 45 |
| skipped_cases | 0 |

## 4. 导入基线摘要

| 指标 | 数值 |
| --- | --- |
| total_kbs | 3 |
| total_files | 14 |
| total_success_count | 14 |
| total_failed_count | 0 |
| total_empty_count | 0 |
| total_indexed_chunks | 14 |
| total_document_count | 14 |
| total_node_count | 14 |
| total_input_text_chars | 3396 |
| total_ocr_success_count | 3 |
| total_asset_registered_count | 3 |
| total_import_ms | 308.05 |

| modality | kb_count | total_files | success | failed | empty | indexed_chunks | document_count | node_count | input_text_chars | ocr_success_count | asset_registered_count | import_total_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | 1 | 3 | 3 | 0 | 0 | 3 | 3 | 3 | 402 | 3 | 3 | 32.83 |
| markdown | 1 | 7 | 7 | 0 | 0 | 7 | 7 | 7 | 2111 | 0 | 0 | 194.06 |
| pdf | 1 | 4 | 4 | 0 | 0 | 4 | 4 | 4 | 883 | 0 | 0 | 81.15 |

| kb_id | modality | total_files | success | failed | empty | indexed_chunks | document_count | node_count | input_text_chars | ocr_success_count | asset_registered_count | import_total_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-kb-image | image_ocr | 3 | 3 | 0 | 0 | 3 | 3 | 3 | 402 | 3 | 3 | 32.83 |
| eval-kb-markdown | markdown | 7 | 7 | 0 | 0 | 7 | 7 | 7 | 2111 | 0 | 0 | 194.06 |
| eval-kb-pdf | pdf | 4 | 4 | 0 | 0 | 4 | 4 | 4 | 883 | 0 | 0 | 81.15 |

## 5. modality 分层统计

| modality | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| markdown | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| pdf | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 6. difficulty 分层统计

| difficulty | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| complex | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| medium | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| simple | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 7. answer_style 分层统计

| answer_style | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| comparison | 8 | 8 | 0 | 1.000 | [0.676, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| fact | 19 | 19 | 0 | 1.000 | [0.832, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| metrics | 5 | 5 | 0 | 1.000 | [0.566, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| policy | 5 | 5 | 0 | 1.000 | [0.566, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| refusal | 9 | 9 | 0 | 1.000 | [0.701, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| summary | 8 | 8 | 0 | 1.000 | [0.676, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 8. category 分层统计

| category | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| evidence_preview | 12 | 12 | 0 | 1.000 | [0.757, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| folder_model | 10 | 10 | 0 | 1.000 | [0.722, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| ingestion_priority | 2 | 2 | 0 | 1.000 | [0.342, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| no_evidence | 9 | 9 | 0 | 1.000 | [0.701, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| per_case_metrics | 2 | 2 | 0 | 1.000 | [0.342, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| refusal_policy | 2 | 2 | 0 | 1.000 | [0.342, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| scope_contract | 12 | 12 | 0 | 1.000 | [0.757, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| suite_metrics | 5 | 5 | 0 | 1.000 | [0.566, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 9. kb_id 分层统计

| kb_id | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-kb-image | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| eval-kb-markdown | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| eval-kb-pdf | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 10. 失败阶段分布

本次运行无失败阶段样本。

## 11. 失败样本

本次运行无失败样本。
