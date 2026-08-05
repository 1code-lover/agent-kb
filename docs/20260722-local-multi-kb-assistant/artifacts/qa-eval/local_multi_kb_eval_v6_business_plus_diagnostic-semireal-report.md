# 问答评测报告：local_multi_kb_eval_v6_business_plus_diagnostic

- 运行时间：2026-07-31T13:37:23.984609+00:00
- 评测模式：diagnostic
- 总用例数：78
- 通过用例：78
- 失败用例：0
- 运行结论：通过

## 1. Suite 摘要

| 指标 | 数值 |
| --- | --- |
| pass_rate | 1.000 |
| pass_rate_ci95 | [0.953, 1.000] |
| scope_pass_rate | 1.000 |
| average_keypoint_coverage | 1.000 |
| total_keypoints | 142 |
| matched_keypoints | 142 |
| keypoint_hit_rate | 1.000 |
| evidence_expected_cases | 58 |
| evidence_hit_cases | 58 |
| evidence_hit_rate | 1.000 |
| preview_required_cases | 58 |
| preview_resolved_cases | 58 |
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
| required_cases | 58 |
| requested_cases | 58 |
| skipped_cases | 0 |

## 4. 导入基线摘要

| 指标 | 数值 |
| --- | --- |
| total_kbs | 4 |
| total_files | 32 |
| total_success_count | 29 |
| total_failed_count | 0 |
| total_empty_count | 3 |
| total_indexed_chunks | 29 |
| total_document_count | 29 |
| total_node_count | 29 |
| total_input_text_chars | 7187 |
| total_ocr_success_count | 6 |
| total_asset_registered_count | 9 |
| total_import_ms | 281.14 |

| modality | kb_count | total_files | success | failed | empty | indexed_chunks | document_count | node_count | input_text_chars | ocr_success_count | asset_registered_count | import_total_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | 1 | 9 | 6 | 0 | 3 | 6 | 6 | 6 | 1173 | 6 | 9 | 52.60 |
| markdown | 1 | 12 | 12 | 0 | 0 | 12 | 12 | 12 | 3470 | 0 | 0 | 108.53 |
| pdf | 2 | 11 | 11 | 0 | 0 | 11 | 11 | 11 | 2544 | 0 | 0 | 120.00 |

| kb_id | modality | total_files | success | failed | empty | indexed_chunks | document_count | node_count | input_text_chars | ocr_success_count | asset_registered_count | import_total_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-kb-image | image_ocr | 9 | 6 | 0 | 3 | 6 | 6 | 6 | 1173 | 6 | 9 | 52.60 |
| eval-kb-markdown | markdown | 12 | 12 | 0 | 0 | 12 | 12 | 12 | 3470 | 0 | 0 | 108.53 |
| eval-kb-pdf | pdf | 10 | 10 | 0 | 0 | 10 | 10 | 10 | 2544 | 0 | 0 | 106.17 |
| eval-kb-pdf-zero | pdf | 1 | 1 | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 13.83 |

## 5. 导入质量与问答关联

| 指标 | 数值 |
| --- | --- |
| weak_signal_kb_count | 3 |
| weak_signal_kb_ids | eval-kb-image, eval-kb-pdf, eval-kb-pdf-zero |
| weak_signal_modality_count | 2 |
| weak_signal_modalities | image_ocr, pdf |

| signal | kb_count | kb_ids | qa_case_count | qa_failed_cases | evidence_miss_cases | preview_failure_cases | source_count_mismatch_cases | qa_pass_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| asset_registered_without_index | 1 | eval-kb-image | 27 | 0 | 0 | 0 | 0 | 1.000 |
| dependency_missing | 1 | eval-kb-image | 27 | 0 | 0 | 0 | 0 | 1.000 |
| empty_imports | 1 | eval-kb-image | 27 | 0 | 0 | 0 | 0 | 1.000 |
| nodes_without_embedding | 1 | eval-kb-pdf | 26 | 0 | 0 | 0 | 0 | 1.000 |
| ocr_failed | 1 | eval-kb-image | 27 | 0 | 0 | 0 | 0 | 1.000 |
| ocr_no_text | 1 | eval-kb-image | 27 | 0 | 0 | 0 | 0 | 1.000 |
| zero_text_content | 1 | eval-kb-pdf-zero | 1 | 0 | 0 | 0 | 0 | 1.000 |

| kb_id | modality | quality_signal_tags | qa_total_cases | qa_failed_cases | evidence_miss_cases | preview_failure_cases | import_nodes_without_embedding_rate | import_total_ocr_failed_count | import_total_ocr_no_text_count | import_asset_registered_without_index_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-kb-image | image_ocr | empty_imports, dependency_missing, ocr_failed, ocr_no_text, asset_registered_without_index | 27 | 0 | 0 | 0 | 0.000 | 2 | 1 | 3 |
| eval-kb-markdown | markdown | - | 24 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| eval-kb-pdf | pdf | nodes_without_embedding | 26 | 0 | 0 | 0 | 0.100 | 0 | 0 | 0 |
| eval-kb-pdf-zero | pdf | zero_text_content | 1 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |

| modality | quality_signal_tags | qa_total_cases | qa_failed_cases | evidence_miss_cases | preview_failure_cases | import_nodes_without_embedding_rate | import_total_ocr_failed_count | import_total_ocr_no_text_count | import_asset_registered_without_index_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | empty_imports, dependency_missing, ocr_failed, ocr_no_text, asset_registered_without_index | 27 | 0 | 0 | 0 | 0.000 | 2 | 1 | 3 |
| markdown | - | 24 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| pdf | nodes_without_embedding | 27 | 0 | 0 | 0 | 0.091 | 0 | 0 | 0 |

## 6. 诊断摘要

| 指标 | 数值 |
| --- | --- |
| total_cases | 78 |
| expected_failed_cases | 0 |
| actual_failed_cases | 0 |
| case_expectation_match_rate | 1.000 |
| weak_signal_case_count | 5 |
| weak_signal_kb_count | 3 |
| weak_signal_modality_count | 2 |

| weak_signal_tag | case_count |
| --- | --- |
| asset_registered_without_index | 3 |
| dependency_missing | 1 |
| nodes_without_embedding | 1 |
| ocr_failed | 2 |
| ocr_no_text | 1 |
| zero_text_content | 1 |

本次诊断运行无预期偏差样本。

## 7. Diagnostic Gate

| Gate | 指标 | 实际值 | 阈值/要求 | 结果 |
| --- | --- | --- | --- | --- |
| case_expectation_match_rate_min | case_expectation_match_rate | 1.000 | 1.000 | 通过 |
| minimum_weak_signal_kb_count | weak_signal_kb_count | 3.000 | 3.000 | 通过 |
| minimum_weak_signal_modality_count | weak_signal_modality_count | 2.000 | 2.000 | 通过 |
| required_signal_tags | signal_breakdown | asset_registered_without_index, dependency_missing, empty_imports, nodes_without_embedding, ocr_failed, ocr_no_text, zero_text_content | ocr_no_text, ocr_failed, dependency_missing, nodes_without_embedding, zero_text_content, asset_registered_without_index | 通过 |

## 8. modality 分层统计

| modality | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | 27 | 27 | 0 | 1.000 | [0.875, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| markdown | 24 | 24 | 0 | 1.000 | [0.862, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| pdf | 27 | 27 | 0 | 1.000 | [0.875, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 9. difficulty 分层统计

| difficulty | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| complex | 24 | 24 | 0 | 1.000 | [0.862, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| medium | 24 | 24 | 0 | 1.000 | [0.862, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| simple | 30 | 30 | 0 | 1.000 | [0.886, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 10. answer_style 分层统计

| answer_style | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| comparison | 7 | 7 | 0 | 1.000 | [0.646, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| fact | 24 | 24 | 0 | 1.000 | [0.862, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| policy | 10 | 10 | 0 | 1.000 | [0.722, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| refusal | 20 | 20 | 0 | 1.000 | [0.839, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| summary | 17 | 17 | 0 | 1.000 | [0.816, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 11. category 分层统计

| category | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| approval_summary | 10 | 10 | 0 | 1.000 | [0.722, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| cross_document | 6 | 6 | 0 | 1.000 | [0.610, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| evidence_operation | 9 | 9 | 0 | 1.000 | [0.701, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| hard_refusal | 3 | 3 | 0 | 1.000 | [0.438, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| long_document | 4 | 4 | 0 | 1.000 | [0.510, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| no_evidence | 14 | 14 | 0 | 1.000 | [0.785, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| process_boundary | 12 | 12 | 0 | 1.000 | [0.757, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| role_lookup | 8 | 8 | 0 | 1.000 | [0.676, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| scope_contract | 4 | 4 | 0 | 1.000 | [0.510, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| timeline_sla | 8 | 8 | 0 | 1.000 | [0.676, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 12. kb_id 分层统计

| kb_id | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-kb-image | 27 | 27 | 0 | 1.000 | [0.875, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| eval-kb-markdown | 24 | 24 | 0 | 1.000 | [0.862, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| eval-kb-pdf | 26 | 26 | 0 | 1.000 | [0.871, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| eval-kb-pdf-zero | 1 | 1 | 0 | 1.000 | [0.207, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 13. 失败阶段分布

本次运行无失败阶段样本。

## 14. 失败样本

本次运行无失败样本。
