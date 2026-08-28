# 问答评测报告：local_multi_kb_eval_v3

- 运行时间：2026-08-21T11:50:22.406986+00:00
- 评测模式：diagnostic
- 总用例数：6
- 通过用例：0
- 失败用例：6
- 运行结论：失败

## 1. Suite 摘要

| 指标 | 数值 |
| --- | --- |
| pass_rate | 0.000 |
| pass_rate_ci95 | [0.000, 0.390] |
| scope_pass_rate | 0.000 |
| average_keypoint_coverage | 0.000 |
| total_keypoints | 10 |
| matched_keypoints | 0 |
| keypoint_hit_rate | 0.000 |
| evidence_expected_cases | 4 |
| evidence_hit_cases | 0 |
| evidence_hit_rate | 0.000 |
| preview_required_cases | 4 |
| preview_resolved_cases | 0 |
| preview_resolvable_rate | 0.000 |
| preview_term_total | 0 |
| preview_term_hits | 0 |
| preview_term_hit_rate | 1.000 |
| source_count_match_rate | 0.333 |
| blocked_term_hit_cases | 0 |
| forbidden_term_clean_rate | 1.000 |

## 2. Run Gate

| Gate | 指标 | 实际值 | 阈值 | 结果 |
| --- | --- | --- | --- | --- |
| scope_pass_rate_min | scope_pass_rate | 0.000 | 1.000 | 失败 |
| average_keypoint_coverage_min | average_keypoint_coverage | 0.000 | 0.000 | 通过 |
| evidence_hit_rate_min | evidence_hit_rate | 0.000 | 0.000 | 通过 |
| preview_resolvable_rate_min | preview_resolvable_rate | 0.000 | 0.000 | 通过 |
| source_count_match_rate_min | source_count_match_rate | 0.333 | 0.000 | 通过 |
| forbidden_term_clean_rate_min | forbidden_term_clean_rate | 1.000 | 1.000 | 通过 |

## 3. Preview 请求摘要

| 指标 | 数值 |
| --- | --- |
| required_cases | 4 |
| requested_cases | 0 |
| skipped_cases | 4 |

## 4. 导入基线摘要

| 指标 | 数值 |
| --- | --- |
| total_kbs | 4 |
| total_files | 19 |
| total_success_count | 16 |
| total_failed_count | 0 |
| total_empty_count | 3 |
| total_indexed_chunks | 16 |
| total_document_count | 16 |
| total_node_count | 16 |
| total_input_text_chars | 3725 |
| total_ocr_success_count | 3 |
| total_asset_registered_count | 6 |
| total_import_ms | 292.07 |

| modality | kb_count | total_files | success | failed | empty | indexed_chunks | document_count | node_count | input_text_chars | ocr_success_count | asset_registered_count | import_total_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | 1 | 6 | 3 | 0 | 3 | 3 | 3 | 3 | 536 | 3 | 6 | 71.90 |
| markdown | 1 | 7 | 7 | 0 | 0 | 7 | 7 | 7 | 2111 | 0 | 0 | 107.82 |
| pdf | 2 | 6 | 6 | 0 | 0 | 6 | 6 | 6 | 1078 | 0 | 0 | 112.36 |

| kb_id | modality | total_files | success | failed | empty | indexed_chunks | document_count | node_count | input_text_chars | ocr_success_count | asset_registered_count | import_total_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-kb-image | image_ocr | 6 | 3 | 0 | 3 | 3 | 3 | 3 | 536 | 3 | 6 | 71.90 |
| eval-kb-markdown | markdown | 7 | 7 | 0 | 0 | 7 | 7 | 7 | 2111 | 0 | 0 | 107.82 |
| eval-kb-pdf | pdf | 5 | 5 | 0 | 0 | 5 | 5 | 5 | 1078 | 0 | 0 | 85.24 |
| eval-kb-pdf-zero | pdf | 1 | 1 | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 27.11 |

## 5. 导入质量与问答关联

| 指标 | 数值 |
| --- | --- |
| weak_signal_kb_count | 3 |
| weak_signal_kb_ids | eval-kb-image, eval-kb-pdf, eval-kb-pdf-zero |
| weak_signal_modality_count | 2 |
| weak_signal_modalities | image_ocr, pdf |

| signal | kb_count | kb_ids | qa_case_count | qa_failed_cases | evidence_miss_cases | preview_failure_cases | source_count_mismatch_cases | qa_pass_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| asset_registered_without_index | 1 | eval-kb-image | 3 | 3 | 3 | 3 | 3 | 0.000 |
| dependency_missing | 1 | eval-kb-image | 3 | 3 | 3 | 3 | 3 | 0.000 |
| empty_imports | 1 | eval-kb-image | 3 | 3 | 3 | 3 | 3 | 0.000 |
| nodes_without_embedding | 1 | eval-kb-pdf | 2 | 2 | 1 | 1 | 1 | 0.000 |
| ocr_failed | 1 | eval-kb-image | 3 | 3 | 3 | 3 | 3 | 0.000 |
| ocr_no_text | 1 | eval-kb-image | 3 | 3 | 3 | 3 | 3 | 0.000 |
| zero_text_content | 1 | eval-kb-pdf-zero | 1 | 1 | 0 | 0 | 0 | 0.000 |

| kb_id | modality | quality_signal_tags | qa_total_cases | qa_failed_cases | evidence_miss_cases | preview_failure_cases | import_nodes_without_embedding_rate | import_total_ocr_failed_count | import_total_ocr_no_text_count | import_asset_registered_without_index_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-kb-image | image_ocr | empty_imports, dependency_missing, ocr_failed, ocr_no_text, asset_registered_without_index | 3 | 3 | 3 | 3 | 0.000 | 2 | 1 | 3 |
| eval-kb-markdown | markdown | - | 0 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| eval-kb-pdf | pdf | nodes_without_embedding | 2 | 2 | 1 | 1 | 0.200 | 0 | 0 | 0 |
| eval-kb-pdf-zero | pdf | zero_text_content | 1 | 1 | 0 | 0 | 0.000 | 0 | 0 | 0 |

| modality | quality_signal_tags | qa_total_cases | qa_failed_cases | evidence_miss_cases | preview_failure_cases | import_nodes_without_embedding_rate | import_total_ocr_failed_count | import_total_ocr_no_text_count | import_asset_registered_without_index_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | empty_imports, dependency_missing, ocr_failed, ocr_no_text, asset_registered_without_index | 3 | 3 | 3 | 3 | 0.000 | 2 | 1 | 3 |
| markdown | - | 0 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| pdf | nodes_without_embedding | 3 | 3 | 1 | 1 | 0.167 | 0 | 0 | 0 |

## 6. 诊断摘要

| 指标 | 数值 |
| --- | --- |
| total_cases | 6 |
| expected_failed_cases | 3 |
| actual_failed_cases | 6 |
| case_expectation_match_rate | 0.000 |
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

| case_id | expected_case_passed | actual_case_passed | expected_failure_stage | actual_failure_stage | weak_signal_tags | failure_message |
| --- | --- | --- | --- | --- | --- | --- |
| eval-v3-img-001 | False | False | quality_gate | chat_query | ocr_no_text, asset_registered_without_index | name '_tokenize_text' is not defined |
| eval-v3-img-002 | False | False | quality_gate | chat_query | ocr_failed, asset_registered_without_index | name '_tokenize_text' is not defined |
| eval-v3-img-003 | False | False | quality_gate | chat_query | dependency_missing, ocr_failed, asset_registered_without_index | name '_tokenize_text' is not defined |
| eval-v3-pdf-001 | True | False | - | chat_query | nodes_without_embedding | name '_tokenize_text' is not defined |
| eval-v3-pdf-002 | True | False | - | chat_query | zero_text_content | name '_tokenize_text' is not defined |
| eval-v3-pdf-003 | True | False | - | chat_query | - | name '_tokenize_text' is not defined |

## 7. Diagnostic Gate

| Gate | 指标 | 实际值 | 阈值/要求 | 结果 |
| --- | --- | --- | --- | --- |
| case_expectation_match_rate_min | case_expectation_match_rate | 0.000 | 1.000 | 失败 |
| minimum_weak_signal_kb_count | weak_signal_kb_count | 3.000 | 2.000 | 通过 |
| minimum_weak_signal_modality_count | weak_signal_modality_count | 2.000 | 2.000 | 通过 |
| required_signal_tags | signal_breakdown | asset_registered_without_index, dependency_missing, empty_imports, nodes_without_embedding, ocr_failed, ocr_no_text, zero_text_content | ocr_no_text, ocr_failed, dependency_missing, nodes_without_embedding, zero_text_content, asset_registered_without_index | 通过 |

## 8. modality 分层统计

| modality | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | 3 | 0 | 3 | 0.000 | [0.000, 0.562] | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 |
| pdf | 3 | 0 | 3 | 0.000 | [0.000, 0.562] | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.667 | 1.000 |

## 9. difficulty 分层统计

| difficulty | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| simple | 6 | 0 | 6 | 0.000 | [0.000, 0.390] | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.333 | 1.000 |

## 10. answer_style 分层统计

| answer_style | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| policy | 4 | 0 | 4 | 0.000 | [0.000, 0.490] | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 |
| refusal | 2 | 0 | 2 | 0.000 | [0.000, 0.658] | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 11. category 分层统计

| category | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| no_evidence | 2 | 0 | 2 | 0.000 | [0.000, 0.658] | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| scope_contract | 4 | 0 | 4 | 0.000 | [0.000, 0.490] | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 |

## 12. kb_id 分层统计

| kb_id | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-kb-image | 3 | 0 | 3 | 0.000 | [0.000, 0.562] | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 |
| eval-kb-pdf | 2 | 0 | 2 | 0.000 | [0.000, 0.658] | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.500 | 1.000 |
| eval-kb-pdf-zero | 1 | 0 | 1 | 0.000 | [0.000, 0.793] | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 13. 失败阶段分布

| failure_stage | count |
| --- | --- |
| chat_query | 6 |

## 14. 失败样本

| case_id | kb_id | modality | category | difficulty | failure_stage | failure_message | keypoint_missed | returned_titles | source_count_match | evidence_hit | preview_resolvable | answer_excerpt | response_status_code | preview_status_code |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-v3-img-001 | eval-kb-image | image_ocr | scope_contract | simple | chat_query | name '_tokenize_text' is not defined | doc_id<br>preview_locator | - | False | False | False | - | 400 | - |
| eval-v3-img-002 | eval-kb-image | image_ocr | scope_contract | simple | chat_query | name '_tokenize_text' is not defined | active knowledge base only<br>no fabricated memory | - | False | False | False | - | 400 | - |
| eval-v3-img-003 | eval-kb-image | image_ocr | scope_contract | simple | chat_query | name '_tokenize_text' is not defined | paddleocr<br>dependency | - | False | False | False | - | 400 | - |
| eval-v3-pdf-001 | eval-kb-pdf | pdf | scope_contract | simple | chat_query | name '_tokenize_text' is not defined | knowledge base<br>declared knowledge scope | - | False | False | False | - | 400 | - |
| eval-v3-pdf-002 | eval-kb-pdf-zero | pdf | no_evidence | simple | chat_query | name '_tokenize_text' is not defined | No confirmable information | - | True | True | True | - | 400 | - |
| eval-v3-pdf-003 | eval-kb-pdf | pdf | no_evidence | simple | chat_query | name '_tokenize_text' is not defined | No confirmable information | - | True | True | True | - | 400 | - |
