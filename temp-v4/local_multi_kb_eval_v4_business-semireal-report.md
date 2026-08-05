# 问答评测报告：local_multi_kb_eval_v4_business

- 运行时间：2026-07-31T13:30:35.019660+00:00
- 评测模式：healthy
- 总用例数：54
- 通过用例：53
- 失败用例：1
- 运行结论：失败

## 1. Suite 摘要

| 指标 | 数值 |
| --- | --- |
| pass_rate | 0.981 |
| pass_rate_ci95 | [0.902, 0.997] |
| scope_pass_rate | 1.000 |
| average_keypoint_coverage | 0.981 |
| total_keypoints | 100 |
| matched_keypoints | 98 |
| keypoint_hit_rate | 0.980 |
| evidence_expected_cases | 42 |
| evidence_hit_cases | 41 |
| evidence_hit_rate | 0.976 |
| preview_required_cases | 42 |
| preview_resolved_cases | 42 |
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
| average_keypoint_coverage_min | average_keypoint_coverage | 0.981 | 0.850 | 通过 |
| evidence_hit_rate_min | evidence_hit_rate | 0.976 | 0.950 | 通过 |
| preview_resolvable_rate_min | preview_resolvable_rate | 1.000 | 0.950 | 通过 |
| source_count_match_rate_min | source_count_match_rate | 1.000 | 0.950 | 通过 |
| forbidden_term_clean_rate_min | forbidden_term_clean_rate | 1.000 | 1.000 | 通过 |

## 3. Preview 请求摘要

| 指标 | 数值 |
| --- | --- |
| required_cases | 42 |
| requested_cases | 42 |
| skipped_cases | 0 |

## 4. 导入基线摘要

| 指标 | 数值 |
| --- | --- |
| total_kbs | 3 |
| total_files | 24 |
| total_success_count | 24 |
| total_failed_count | 0 |
| total_empty_count | 0 |
| total_indexed_chunks | 24 |
| total_document_count | 24 |
| total_node_count | 24 |
| total_input_text_chars | 5900 |
| total_ocr_success_count | 5 |
| total_asset_registered_count | 5 |
| total_import_ms | 224.77 |

| modality | kb_count | total_files | success | failed | empty | indexed_chunks | document_count | node_count | input_text_chars | ocr_success_count | asset_registered_count | import_total_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | 1 | 5 | 5 | 0 | 0 | 5 | 5 | 5 | 911 | 5 | 5 | 45.10 |
| markdown | 1 | 11 | 11 | 0 | 0 | 11 | 11 | 11 | 3058 | 0 | 0 | 84.53 |
| pdf | 1 | 8 | 8 | 0 | 0 | 8 | 8 | 8 | 1931 | 0 | 0 | 95.14 |

| kb_id | modality | total_files | success | failed | empty | indexed_chunks | document_count | node_count | input_text_chars | ocr_success_count | asset_registered_count | import_total_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-kb-image | image_ocr | 5 | 5 | 0 | 0 | 5 | 5 | 5 | 911 | 5 | 5 | 45.10 |
| eval-kb-markdown | markdown | 11 | 11 | 0 | 0 | 11 | 11 | 11 | 3058 | 0 | 0 | 84.53 |
| eval-kb-pdf | pdf | 8 | 8 | 0 | 0 | 8 | 8 | 8 | 1931 | 0 | 0 | 95.14 |

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
| eval-kb-image | image_ocr | - | 18 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| eval-kb-markdown | markdown | - | 18 | 1 | 1 | 0 | 0.000 | 0 | 0 | 0 |
| eval-kb-pdf | pdf | - | 18 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |

| modality | quality_signal_tags | qa_total_cases | qa_failed_cases | evidence_miss_cases | preview_failure_cases | import_nodes_without_embedding_rate | import_total_ocr_failed_count | import_total_ocr_no_text_count | import_asset_registered_without_index_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | - | 18 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |
| markdown | - | 18 | 1 | 1 | 0 | 0.000 | 0 | 0 | 0 |
| pdf | - | 18 | 0 | 0 | 0 | 0.000 | 0 | 0 | 0 |

## 6. modality 分层统计

| modality | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image_ocr | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| markdown | 18 | 17 | 1 | 0.944 | [0.742, 0.990] | 1.000 | 0.944 | 0.935 | 0.929 | 1.000 | 1.000 | 1.000 | 1.000 |
| pdf | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 7. difficulty 分层统计

| difficulty | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| complex | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| medium | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| simple | 18 | 17 | 1 | 0.944 | [0.742, 0.990] | 1.000 | 0.944 | 0.929 | 0.917 | 1.000 | 1.000 | 1.000 | 1.000 |

## 8. answer_style 分层统计

| answer_style | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| comparison | 4 | 4 | 0 | 1.000 | [0.510, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| fact | 18 | 17 | 1 | 0.944 | [0.742, 0.990] | 1.000 | 0.944 | 0.909 | 0.944 | 1.000 | 1.000 | 1.000 | 1.000 |
| policy | 9 | 9 | 0 | 1.000 | [0.701, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| refusal | 12 | 12 | 0 | 1.000 | [0.757, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| summary | 11 | 11 | 0 | 1.000 | [0.741, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 9. category 分层统计

| category | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| approval_summary | 9 | 9 | 0 | 1.000 | [0.701, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| evidence_operation | 6 | 6 | 0 | 1.000 | [0.610, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| no_evidence | 12 | 12 | 0 | 1.000 | [0.757, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| process_boundary | 11 | 11 | 0 | 1.000 | [0.741, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| role_lookup | 8 | 8 | 0 | 1.000 | [0.676, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| timeline_sla | 8 | 7 | 1 | 0.875 | [0.529, 0.978] | 1.000 | 0.875 | 0.818 | 0.875 | 1.000 | 1.000 | 1.000 | 1.000 |

## 10. kb_id 分层统计

| kb_id | count | passed | failed | pass_rate | pass_rate_ci95 | scope_pass_rate | average_keypoint_coverage | keypoint_hit_rate | evidence_hit_rate | preview_resolvable_rate | preview_term_hit_rate | source_count_match_rate | forbidden_term_clean_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-kb-image | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| eval-kb-markdown | 18 | 17 | 1 | 0.944 | [0.742, 0.990] | 1.000 | 0.944 | 0.935 | 0.929 | 1.000 | 1.000 | 1.000 | 1.000 |
| eval-kb-pdf | 18 | 18 | 0 | 1.000 | [0.824, 1.000] | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 11. 失败阶段分布

| failure_stage | count |
| --- | --- |
| quality_gate | 1 |

## 12. 失败样本

| case_id | kb_id | modality | category | difficulty | failure_stage | failure_message | keypoint_missed | returned_titles | response_status_code | preview_status_code |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eval-v4-md-005 | eval-kb-markdown | markdown | timeline_sla | simple | quality_gate | contract or metric mismatch | 15<br>Zhao Lin | cutover-approval.md | 200 | 200 |
