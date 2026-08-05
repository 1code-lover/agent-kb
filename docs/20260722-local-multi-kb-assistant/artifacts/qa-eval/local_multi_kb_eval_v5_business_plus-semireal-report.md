# 问答评测报告：local_multi_kb_eval_v5_business_plus

- 运行时间：2026-07-31T13:43:00.946376+00:00
- 评测模式：healthy
- 总用例数：72
- 通过用例：72
- 失败用例：0
- 运行结论：通过

## 1. Suite 摘要

| 指标 | 数值 |
| --- | --- |
| pass_rate | 1.000 |
| pass_rate_ci95 | [0.949, 1.000] |
| scope_pass_rate | 1.000 |
| average_keypoint_coverage | 1.000 |
| total_keypoints | 132 |
| matched_keypoints | 132 |
| keypoint_hit_rate | 1.000 |
| evidence_expected_cases | 57 |
| evidence_hit_cases | 57 |
| evidence_hit_rate | 1.000 |
| preview_required_cases | 57 |
| preview_resolved_cases | 57 |
| preview_resolvable_rate | 1.000 |
| preview_term_total | 11 |
| preview_term_hits | 11 |
| preview_term_hit_rate | 1.000 |
| source_count_match_rate | 1.000 |
| blocked_term_hit_cases | 0 |
| forbidden_term_clean_rate | 1.000 |

## 2. Run Gate

| Gate | 指标 | 实际值 | 阈值 | 结果 |
| --- | --- | --- | --- | --- |
| scope_pass_rate_min | scope_pass_rate | 1.000 | 1.000 | 通过 |
| average_keypoint_coverage_min | average_keypoint_coverage | 1.000 | 0.850 | 通过 |
| evidence_hit_rate_min | evidence_hit_rate | 1.000 | 0.950 | 通过 |
| preview_resolvable_rate_min | preview_resolvable_rate | 1.000 | 0.950 | 通过 |
| source_count_match_rate_min | source_count_match_rate | 1.000 | 0.950 | 通过 |
| forbidden_term_clean_rate_min | forbidden_term_clean_rate | 1.000 | 1.000 | 通过 |

## 3. Preview 请求摘要

| 指标 | 数值 |
| --- | --- |
| required_cases | 57 |
| requested_cases | 57 |
| skipped_cases | 0 |

## 4. 导入基线摘要

| 指标 | 数值 |
| --- | --- |
| total_kbs | 3 |
| total_files | 27 |
| total_success_count | 27 |
| total_failed_count | 0 |
| total_empty_count | 0 |
| total_indexed_chunks | 27 |
| total_document_count | 27 |
| total_node_count | 27 |
| total_input_text_chars | 6990 |
| total_ocr_success_count | 6 |
| total_asset_registered_count | 6 |
| total_import_ms | 264.09 |

| modality | kb_count | total_files | success | failed | empty | indexed_chunks | document_count | node_count | input_text_chars | ocr_success_count | asset_registered_count | import_total_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | 1 | 6 | 6 | 0 | 0 | 6 | 6 | 6 | 1173 | 6 | 6 | 77.90 |
| markdown | 1 | 12 | 12 | 0 | 0 | 12 | 12 | 12 | 3470 | 0 | 0 | 87.43 |
| pdf | 1 | 9 | 9 | 0 | 0 | 9 | 9 | 9 | 2347 | 0 | 0 | 98.75 |

| kb_id | modality | total_files | success | failed | empty | indexed_chunks | document_count | node_count | input_text_chars | ocr_success_count | asset_registered_count | import_total_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-kb-image | image_ocr | 6 | 6 | 0 | 0 | 6 | 6 | 6 | 1173 | 6 | 6 | 77.90 |
| eval-kb-markdown | markdown | 12 | 12 | 0 | 0 | 12 | 12 | 12 | 3470 | 0 | 0 | 87.43 |
| eval-kb-pdf | pdf | 9 | 9 | 0 | 0 | 9 | 9 | 9 | 2347 | 0 | 0 | 98.75 |

## 5. 导入质量与问答关联

| 指标 | 数值 |
| --- | --- |
| weak_signal_kb_count | 0 |
| weak_signal_kb_ids | - |
| weak_signal_modality_count | 0 |
| weak_signal_modalities | - |

本次运行未发现导入弱信号知识库。

| kb_id | modality | quality_signal_tags | qa_total_cases | qa_failed_cases | evidence_miss_cases | preview_failure_cases | import_nodes_without_embedding_rate | import_total_ocr_failed_count | import_total_ocr_no_text_count | import_asset_registered_without_index_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-kb-image | image_ocr | - | 24 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| eval-kb-markdown | markdown | - | 24 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| eval-kb-pdf | pdf | - | 24 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |

| modality | quality_signal_tags | qa_total_cases | qa_failed_cases | evidence_miss_cases | preview_failure_cases | import_nodes_without_embedding_rate | import_total_ocr_failed_count | import_total_ocr_no_text_count | import_asset_registered_without_index_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | - | 24 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| markdown | - | 24 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| pdf | - | 24 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |

## 6. modality 分层统计

| modality | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | 24 | 24 | 0 | 1.000 | [0.862, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| markdown | 24 | 24 | 0 | 1.000 | [0.862, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| pdf | 24 | 24 | 0 | 1.000 | [0.862, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 7. difficulty 分层统计

| difficulty | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| complex | 24 | 24 | 0 | 1.000 | [0.862, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| medium | 24 | 24 | 0 | 1.000 | [0.862, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| simple | 24 | 24 | 0 | 1.000 | [0.862, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 8. answer_style 分层统计

| answer_style | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| comparison | 7 | 7 | 0 | 1.000 | [0.646, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| fact | 24 | 24 | 0 | 1.000 | [0.862, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| policy | 9 | 9 | 0 | 1.000 | [0.701, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| refusal | 15 | 15 | 0 | 1.000 | [0.796, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| summary | 17 | 17 | 0 | 1.000 | [0.816, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 9. category 分层统计

| category | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| approval_summary | 10 | 10 | 0 | 1.000 | [0.722, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| cross_document | 6 | 6 | 0 | 1.000 | [0.610, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| evidence_operation | 9 | 9 | 0 | 1.000 | [0.701, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| hard_refusal | 3 | 3 | 0 | 1.000 | [0.438, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| long_document | 4 | 4 | 0 | 1.000 | [0.510, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| no_evidence | 12 | 12 | 0 | 1.000 | [0.757, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| process_boundary | 12 | 12 | 0 | 1.000 | [0.757, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| role_lookup | 8 | 8 | 0 | 1.000 | [0.676, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| timeline_sla | 8 | 8 | 0 | 1.000 | [0.676, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 10. kb_id 分层统计

| kb_id | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-kb-image | 24 | 24 | 0 | 1.000 | [0.862, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| eval-kb-markdown | 24 | 24 | 0 | 1.000 | [0.862, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| eval-kb-pdf | 24 | 24 | 0 | 1.000 | [0.862, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 11. 失败阶段分布

本次运行无失败阶段样本。

## 12. 失败样本

本次运行无失败样本。
