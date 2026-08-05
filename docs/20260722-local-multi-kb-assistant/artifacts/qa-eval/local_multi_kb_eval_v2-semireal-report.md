# 问答评测报告：local_multi_kb_eval_v2

- 运行时间：2026-07-30T19:22:24.606353+00:00
- 评测模式：healthy
- 总用例数：117
- 通过用例：117
- 失败用例：0
- 运行结论：通过

## 1. Suite 摘要

| 指标 | 数值 |
| --- | --- |
| pass_rate | 1.000 |
| pass_rate_ci95 | [0.968, 1.000] |
| scope_pass_rate | 1.000 |
| average_keypoint_coverage | 1.000 |
| total_keypoints | 352 |
| matched_keypoints | 352 |
| keypoint_hit_rate | 1.000 |
| evidence_expected_cases | 96 |
| evidence_hit_cases | 96 |
| evidence_hit_rate | 1.000 |
| preview_required_cases | 96 |
| preview_resolved_cases | 96 |
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
| required_cases | 96 |
| requested_cases | 96 |
| skipped_cases | 0 |

## 4. 导入基线摘要

| 指标 | 数值 |
| --- | --- |
| total_kbs | 3 |
| total_files | 19 |
| total_success_count | 19 |
| total_failed_count | 0 |
| total_empty_count | 0 |
| total_indexed_chunks | 19 |
| total_document_count | 19 |
| total_node_count | 19 |
| total_input_text_chars | 4287 |
| total_ocr_success_count | 5 |
| total_asset_registered_count | 5 |
| total_import_ms | 856.40 |

| modality | kb_count | total_files | success | failed | empty | indexed_chunks | document_count | node_count | input_text_chars | ocr_success_count | asset_registered_count | import_total_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | 1 | 5 | 5 | 0 | 0 | 5 | 5 | 5 | 621 | 5 | 5 | 165.90 |
| markdown | 1 | 7 | 7 | 0 | 0 | 7 | 7 | 7 | 2111 | 0 | 0 | 267.18 |
| pdf | 1 | 7 | 7 | 0 | 0 | 7 | 7 | 7 | 1555 | 0 | 0 | 423.32 |

| kb_id | modality | total_files | success | failed | empty | indexed_chunks | document_count | node_count | input_text_chars | ocr_success_count | asset_registered_count | import_total_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-kb-image | image_ocr | 5 | 5 | 0 | 0 | 5 | 5 | 5 | 621 | 5 | 5 | 165.90 |
| eval-kb-markdown | markdown | 7 | 7 | 0 | 0 | 7 | 7 | 7 | 2111 | 0 | 0 | 267.18 |
| eval-kb-pdf | pdf | 7 | 7 | 0 | 0 | 7 | 7 | 7 | 1555 | 0 | 0 | 423.32 |

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
| eval-kb-image | image_ocr | - | 39 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| eval-kb-markdown | markdown | - | 39 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| eval-kb-pdf | pdf | - | 39 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |

| modality | quality_signal_tags | qa_total_cases | qa_failed_cases | evidence_miss_cases | preview_failure_cases | import_nodes_without_embedding_rate | import_total_ocr_failed_count | import_total_ocr_no_text_count | import_asset_registered_without_index_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | - | 39 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| markdown | - | 39 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| pdf | - | 39 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |

## 6. modality 分层统计

| modality | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | 39 | 39 | 0 | 1.000 | [0.910, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| markdown | 39 | 39 | 0 | 1.000 | [0.910, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| pdf | 39 | 39 | 0 | 1.000 | [0.910, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 7. difficulty 分层统计

| difficulty | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| complex | 39 | 39 | 0 | 1.000 | [0.910, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| medium | 39 | 39 | 0 | 1.000 | [0.910, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| simple | 39 | 39 | 0 | 1.000 | [0.910, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 8. answer_style 分层统计

| answer_style | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| comparison | 15 | 15 | 0 | 1.000 | [0.796, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| fact | 31 | 31 | 0 | 1.000 | [0.890, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| metrics | 14 | 14 | 0 | 1.000 | [0.785, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| policy | 15 | 15 | 0 | 1.000 | [0.796, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| refusal | 21 | 21 | 0 | 1.000 | [0.845, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| summary | 21 | 21 | 0 | 1.000 | [0.845, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 9. category 分层统计

| category | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| evidence_preview | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| folder_model | 20 | 20 | 0 | 1.000 | [0.839, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| ingestion_priority | 9 | 9 | 0 | 1.000 | [0.701, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| no_evidence | 21 | 21 | 0 | 1.000 | [0.845, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| per_case_metrics | 5 | 5 | 0 | 1.000 | [0.566, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| refusal_policy | 11 | 11 | 0 | 1.000 | [0.741, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| scope_contract | 20 | 20 | 0 | 1.000 | [0.839, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| suite_metrics | 13 | 13 | 0 | 1.000 | [0.772, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 10. kb_id 分层统计

| kb_id | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-kb-image | 39 | 39 | 0 | 1.000 | [0.910, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| eval-kb-markdown | 39 | 39 | 0 | 1.000 | [0.910, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| eval-kb-pdf | 39 | 39 | 0 | 1.000 | [0.910, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 11. 失败阶段分布

本次运行无失败阶段样本。

## 12. 失败样本

本次运行无失败样本。
