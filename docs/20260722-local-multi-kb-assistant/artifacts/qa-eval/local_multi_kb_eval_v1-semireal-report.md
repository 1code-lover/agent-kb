# 问答评测报告：local_multi_kb_eval_v1

- 运行时间：2026-08-21T12:00:22.408385+00:00
- 评测模式：healthy
- 总用例数：54
- 通过用例：52
- 失败用例：2
- 运行结论：失败

## 1. Suite 摘要

| 指标 | 数值 |
| --- | --- |
| pass_rate | 0.963 |
| pass_rate_ci95 | [0.875, 0.990] |
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
| source_count_match_rate | 0.963 |
| blocked_term_hit_cases | 0 |
| forbidden_term_clean_rate | 1.000 |

## 2. Run Gate

| Gate | 指标 | 实际值 | 阈值 | 结果 |
| --- | --- | --- | --- | --- |
| scope_pass_rate_min | scope_pass_rate | 1.000 | 1.000 | 通过 |
| average_keypoint_coverage_min | average_keypoint_coverage | 1.000 | 0.900 | 通过 |
| evidence_hit_rate_min | evidence_hit_rate | 1.000 | 0.950 | 通过 |
| preview_resolvable_rate_min | preview_resolvable_rate | 1.000 | 0.950 | 通过 |
| source_count_match_rate_min | source_count_match_rate | 0.963 | 0.950 | 通过 |
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
| total_input_text_chars | 3528 |
| total_ocr_success_count | 3 |
| total_asset_registered_count | 3 |
| total_import_ms | 263.58 |

| modality | kb_count | total_files | success | failed | empty | indexed_chunks | document_count | node_count | input_text_chars | ocr_success_count | asset_registered_count | import_total_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | 1 | 3 | 3 | 0 | 0 | 3 | 3 | 3 | 536 | 3 | 3 | 47.14 |
| markdown | 1 | 7 | 7 | 0 | 0 | 7 | 7 | 7 | 2111 | 0 | 0 | 117.45 |
| pdf | 1 | 4 | 4 | 0 | 0 | 4 | 4 | 4 | 881 | 0 | 0 | 99.00 |

| kb_id | modality | total_files | success | failed | empty | indexed_chunks | document_count | node_count | input_text_chars | ocr_success_count | asset_registered_count | import_total_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-kb-image | image_ocr | 3 | 3 | 0 | 0 | 3 | 3 | 3 | 536 | 3 | 3 | 47.14 |
| eval-kb-markdown | markdown | 7 | 7 | 0 | 0 | 7 | 7 | 7 | 2111 | 0 | 0 | 117.45 |
| eval-kb-pdf | pdf | 4 | 4 | 0 | 0 | 4 | 4 | 4 | 881 | 0 | 0 | 99.00 |

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
| eval-kb-image | image_ocr | - | 18 | 1 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| eval-kb-markdown | markdown | - | 18 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| eval-kb-pdf | pdf | - | 18 | 1 | 0 | 0 | 0.000 | 0 | 0 | 0 |

| modality | quality_signal_tags | qa_total_cases | qa_failed_cases | evidence_miss_cases | preview_failure_cases | import_nodes_without_embedding_rate | import_total_ocr_failed_count | import_total_ocr_no_text_count | import_asset_registered_without_index_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | - | 18 | 1 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| markdown | - | 18 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| pdf | - | 18 | 1 | 0 | 0 | 0.000 | 0 | 0 | 0 |

## 6. modality 分层统计

| modality | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | 18 | 17 | 1 | 0.944 | [0.742, 0.990] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.944 | 1.000 |
| markdown | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| pdf | 18 | 17 | 1 | 0.944 | [0.742, 0.990] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.944 | 1.000 |

## 7. difficulty 分层统计

| difficulty | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| complex | 18 | 16 | 2 | 0.889 | [0.672, 0.969] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.889 | 1.000 |
| medium | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| simple | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 8. answer_style 分层统计

| answer_style | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| comparison | 8 | 6 | 2 | 0.750 | [0.409, 0.929] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.750 | 1.000 |
| fact | 19 | 19 | 0 | 1.000 | [0.832, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| metrics | 5 | 5 | 0 | 1.000 | [0.566, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| policy | 5 | 5 | 0 | 1.000 | [0.566, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| refusal | 9 | 9 | 0 | 1.000 | [0.701, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| summary | 8 | 8 | 0 | 1.000 | [0.676, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 9. category 分层统计

| category | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| evidence_preview | 12 | 12 | 0 | 1.000 | [0.757, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| folder_model | 10 | 9 | 1 | 0.900 | [0.596, 0.982] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.900 | 1.000 |
| ingestion_priority | 2 | 2 | 0 | 1.000 | [0.342, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| no_evidence | 9 | 9 | 0 | 1.000 | [0.701, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| per_case_metrics | 2 | 2 | 0 | 1.000 | [0.342, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| refusal_policy | 2 | 2 | 0 | 1.000 | [0.342, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| scope_contract | 12 | 11 | 1 | 0.917 | [0.646, 0.985] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.917 | 1.000 |
| suite_metrics | 5 | 5 | 0 | 1.000 | [0.566, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 10. kb_id 分层统计

| kb_id | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-kb-image | 18 | 17 | 1 | 0.944 | [0.742, 0.990] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.944 | 1.000 |
| eval-kb-markdown | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| eval-kb-pdf | 18 | 17 | 1 | 0.944 | [0.742, 0.990] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.944 | 1.000 |

## 11. 失败阶段分布

| failure_stage | count |
| --- | --- |
| quality_gate | 2 |

## 12. 失败样本

| case_id | kb_id | modality | category | difficulty | failure_stage | failure_message | keypoint_missed | returned_titles | source_count_match | evidence_hit | preview_resolvable | answer_excerpt | response_status_code | preview_status_code |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-pdf-011 | eval-kb-pdf | pdf | folder_model | complex | quality_gate | contract or metric mismatch | - | folder-boundary.pdf<br>metrics-gate.pdf | False | True | True | Folder boundary note for the PDF suite.
Folder is an organization object and not an authorization boundary.
Knowledge Base remains the range and authorization b | 200 | 200 |
| eval-img-005 | eval-kb-image | image_ocr | scope_contract | complex | quality_gate | contract or metric mismatch | - | folder-board.png<br>scope-board.png | False | True | True | requested_scope_type must remain single_kb and effective_kb_ids should echo the declared image knowledge base.
Knowledge Base remains the authorization boundary | 200 | 200 |
