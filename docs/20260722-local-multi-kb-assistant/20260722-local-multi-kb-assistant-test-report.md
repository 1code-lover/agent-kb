# 20260722-local-multi-kb-assistant-test-report

## 1. Scope
- Report date: 2026-07-31
- Requirement folder: `docs/20260722-local-multi-kb-assistant/`
- Related documents:
  - `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-plan.md`
  - `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-test-plan.md`
  - `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec-qa-evaluation.md`
- This report only states two kinds of evidence:
  1. **Re-run evidence in the current worktree**: ingestion regression, formal QA evaluations (`eval_v4` / `eval_v5` / `eval_v6`), focused semireal regression, frontend receipt-summary regression, broad ingestion+QA regression, full pytest, coverage, and the Stage 3 artifact consistency verifier.
  2. **Review evidence from existing formal artifacts**: live roundtrip diagnostic JSON files.
- This report does not present historically executed commands that were not re-run in this round as if they were current results.

## 2. Executive summary
1. **The ingestion-to-QA main path is working in the current worktree, and a real empty-markdown import failure was found, fixed, and revalidated in this continuation.**
2. **The formal `eval_v4` QA evaluation was re-run in the current worktree and passed with `54/54 passed`.**
3. **The formal `eval_v5` QA evaluation was expanded and re-run in the current worktree, and it now passes with `72/72 passed`, adding stronger evidence-operation, process-boundary, approval-summary, and long-document coverage on top of the earlier long-document, cross-document, and hard-refusal cases.**
4. **The unified formal `eval_v6` business-plus-diagnostic evaluation has now been stabilized and re-run in the current worktree: it passes with `78/78 passed`, all business run gates pass, and all diagnostic gates also pass while still preserving honest weak-signal coverage.**
5. **Focused supporting regressions around the formal QA layer and adjacent receipt-summary contract were re-run again in the current worktree. The latest focused QA slice passed with `81 passed`, the targeted cross-document + mixed-batch receipt-consistency rerun passed with `15 passed`, the semireal Markdown/PDF/image/mixed-batch/smoke slice remains green at `47 passed`, and the receipt-summary frontend contract passed with `10 passed`.**
6. **A focused follow-up/session/runtime-stability regression was re-run in the current worktree and passed with `33 passed`, confirming minimal history-grounded follow-up support plus the Windows session-path and log-handle fixes required by the formal eval flow.**
7. **The full automated regression suite was re-run in the current worktree and passed with `667 passed, 2 warnings`.**
8. **A refreshed broad ingestion + QA regression slice was re-run again in the current worktree and now passes with `354 passed, 2 warnings`, covering ingestion, OCR, evidence contract, chat routes/services, runtime loading, and fixture governance together.**
9. **`api + server` coverage was re-run and reached `TOTAL 6661 / Miss 1189 / Cover 82%`, which is above the repository threshold `>= 80%`.**
10. **The Stage 3 report-artifact-submit-scope consistency verifier is now implemented and passes with `ok = true`.**
11. **The five-path live smoke was not only available from the earlier `http://127.0.0.1:18084` run; it was also re-run again in the current worktree on `http://127.0.0.1:18090`, covering Markdown, PDF text layer, scanned PDF OCR, image OCR, and mixed batch.**
12. **The new `18090` outputs keep all core checks green, so the report now has two separate live service runs plus the retained artifact set as traceable evidence for those five core paths.**
13. **A fresh runtime reproduction plus a fresh live HTTP validation on `http://127.0.0.1:18086` both confirm that whitespace-only Markdown now returns `empty` instead of `failed`.**
14. **A fresh targeted regression confirms that extensionless uploads with empty MIME now recognize supported PDF/image signatures correctly: PDF stays `file_kind = pdf` even on dependency failure, and PNG enters the OCR/image path as `file_kind = image`.**
15. **A fresh live HTTP import on `http://127.0.0.1:18088` confirms that an extensionless PNG with empty MIME no longer stops at `ocr_skipped`: it now enters OCR, reports `ocr_attempted = true`, and honestly returns `no_text` for a blank sample image.**
16. **A fresh regression and live import on `http://127.0.0.1:18089` confirm that extensionless files with generic `application/octet-stream` now fall back to content sniffing: UTF-8 text imports as `text`, supported PNG enters OCR as `image`, and obvious binary bytes are still rejected.**
17. **A fresh storage-boundary addendum was re-run in the current worktree: `tests/api/test_index_manager_coverage.py` + `tests/utils/test_file_kb_paths.py` now pass with `71 passed`, `server/index.py` reaches `95%`, `server/utils/file.py` reaches `96%`, and the focused import-path hardening evidence is now both functional and measurable.**

## 3. Re-run records in the current worktree

### 3.1 Ingestion-focused regression
Command 1:
```bash
python -X utf8 -m pytest tests/api/test_ingestion_pipeline.py tests/api/test_kb_directory_storage.py tests/api/test_kb_directory_import_tree.py tests/api/test_kb_import_receipt_store.py tests/api/test_image_asset_import.py tests/api/test_index_manager_coverage.py tests/readers/test_pdf_ocr.py tests/readers/test_image_ocr.py -q
```

Result 1:
- `161 passed in 10.19s`

Command 1a:
```bash
python -X utf8 -m pytest tests/api/test_ingestion_pipeline.py tests/api/test_kb_import_receipt_store.py tests/api/test_image_asset_import.py tests/api/test_kb_directory_import_tree.py tests/api/test_kb_directory_storage.py -q
```

Result 1a:
- `92 passed in 11.56s`

Command 2:
```bash
node --test webapp/src/domain/importSummary.test.js
```

Result 2:
- `10 passed`

Interpretation:
- Command 1 directly covers ingestion, directory-tree handling, receipt persistence, image asset registration, index-manager behavior, PDF OCR, and image OCR.
- Command 1a is a narrower backend-only ingestion rerun that cross-checks the import pipeline, receipt store, image asset path, directory import tree, and storage/display-summary contract together.
- Command 2 validates the import receipt summary frontend contract, including batch stage metrics, batch index stage metrics, the corrected middle-dot summary separator instead of a corrupted question-mark separator, and the mixed-batch empty-result mapping path.
- Together they provide both backend receipt-generation evidence and frontend receipt-rendering evidence for the current ingestion feedback path.

### 3.2 Formal QA evaluation `eval_v4`
Command:
```bash
python -X utf8 -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v4/cases.json --schema tests/fixtures/rag_quality/eval_v4/schema.json --output-dir docs/20260722-local-multi-kb-assistant/artifacts/qa-eval
```

Result:
- `54/54 passed`
- `scope_pass_rate = 1.0`
- `average_keypoint_coverage = 1.0`
- `evidence_hit_rate = 1.0`
- `preview_resolvable_rate = 1.0`
- `source_count_match_rate = 1.0`
- `forbidden_term_clean_rate = 1.0`

Formal outputs:
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v4_business-semireal-report.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v4_business-semireal-report.md`

Interpretation:
- The current evaluation set is no longer a one-off smoke check; it is a repeatable formal QA gate with saved artifacts.
- In the current sample set, scope enforcement, keypoint coverage, evidence hit rate, preview resolvability, and forbidden-term cleanliness all remain stable.

### 3.2.1 Formal QA evaluation `eval_v5`
Command:
```bash
python -X utf8 -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v5/cases.json --schema tests/fixtures/rag_quality/eval_v5/schema.json --output-dir docs/20260722-local-multi-kb-assistant/artifacts/qa-eval
```

Result:
- `72/72 passed`
- `scope_pass_rate = 1.0`
- `average_keypoint_coverage = 1.0`
- `evidence_hit_rate = 1.0`
- `preview_required_cases = 57`
- `preview_resolved_cases = 57`
- `preview_resolvable_rate = 1.0`
- `source_count_match_rate = 1.0`
- `forbidden_term_clean_rate = 1.0`
- `total_keypoints = 132`
- `matched_keypoints = 132`

Formal outputs:
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v5_business_plus-semireal-report.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v5_business_plus-semireal-report.md`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v6_business_plus_diagnostic-semireal-report.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v6_business_plus_diagnostic-semireal-report.md`

Interpretation:
- This second formal dataset now extends the QA gate from the original business-path set into harder long-document, cross-document, evidence-operation, approval-summary, and process-boundary scenarios.
- The current run shows that those added scenarios still pass with the same top-line stability as `eval_v4`, while also pushing the business-path dataset to a larger and more balanced shape: `72` total cases, `24` per modality, `24` per difficulty, and `57` evidence-backed preview-required cases under the same honest product boundary: logical-only KB isolation and OCR-first image support.

### 3.2.2 Formal QA evaluation `eval_v6`
Command:
```bash
python -X utf8 -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v6/cases.json --schema tests/fixtures/rag_quality/eval_v6/schema.json --output-dir docs/20260722-local-multi-kb-assistant/artifacts/qa-eval
```

Result:
- `78 total / 78 passed / 0 failed`
- `run_passed = true`
- `scope_pass_rate = 1.0`
- `average_keypoint_coverage = 1.0`
- `evidence_hit_rate = 1.0 (58 / 58)`
- `preview_required_cases = 58`
- `preview_resolved_cases = 58`
- `preview_resolvable_rate = 1.0`
- `source_count_match_rate = 1.0`
- `forbidden_term_clean_rate = 1.0`
- `diagnostic_summary.case_expectation_match_rate = 1.0`
- `diagnostic_summary.weak_signal_case_count = 5`
- `diagnostic_summary.weak_signal_kb_count = 3`
- `diagnostic_summary.weak_signal_modality_count = 2`
- `diagnostic_gates`: all passed
- `run_gates`: all passed

Formal outputs:
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v6_business_plus_diagnostic-semireal-report.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v6_business_plus_diagnostic-semireal-report.md`

Interpretation:
- `eval_v6` remains the formal artifact that combines stable business QA coverage with weak-signal/OCR diagnostic samples in one report set.
- After the semireal retrieval stabilization around short alnum anchors such as `P1`, the business-path cases and the inherited weak-signal diagnostic cases now coexist in one fully passing run instead of forcing a tradeoff between retrieval accuracy and honest refusal behavior.
- The weak-signal coverage is still visible in `diagnostic_summary` and `diagnostic_gates`; the difference is that those cases are now modeled and answered in a way that satisfies both the diagnostic contract and the top-line business gates.

### 3.2.3 Focused support regression for the formal QA layer
Command 1:
```bash
python -X utf8 -m pytest tests/test_rag_quality_eval_dataset_v4.py tests/test_rag_quality_eval_dataset_v5.py tests/api/test_chat_eval_runner.py tests/api/test_chat_qa_metrics.py tests/api/test_semireal_chat_support.py -q
```

Result 1:
- Historical current-worktree rerun: `26 passed in 9.14s`
- Fresh rerun after the multi-source preview aggregation enhancement: `27 passed in 8.29s`
- Fresh rerun after the short alnum anchor retrieval fix: `23 passed in 9.26s` for `tests/api/test_semireal_chat_support.py tests/test_rag_quality_eval_dataset_v6.py tests/api/test_chat_eval_runner.py -q`

Command 2:
```bash
python -X utf8 -m pytest tests/api/test_chat_eval_runner.py tests/api/test_chat_mixed_batch_semireal.py -q
```

Result 2:
- `15 passed in 11.41s`

Command 3:
```bash
python -X utf8 -m pytest tests/api/test_chat_markdown_qa_semireal.py tests/api/test_chat_pdf_semireal.py tests/api/test_chat_image_ocr_semireal.py tests/api/test_chat_mixed_batch_semireal.py tests/api/test_chat_single_kb_qa_smoke.py -q
```

Result 3:
- `47 passed in 13.85s`

Interpretation:
- Command 1 validates the `eval_v4`/`eval_v5` dataset schema and fixture layer, the semireal chat support helpers, the QA metrics helpers, and the eval runner support needed by the formal evaluation flow. The fresh `27 passed` rerun reflects the newly added cross-document preview aggregation support.
- Command 2 is a tighter regression focused on the newly expanded multi-source evidence path: it verifies that cross-document cases in both `test_chat_eval_runner.py` and `test_chat_mixed_batch_semireal.py` now request previews for every evidence item and merge them into a single evaluable preview payload, and it now also asserts that the mixed-batch import receipt keeps `display_summary` consistent with the persisted latest receipt.
- Command 3 confirms that the broader semireal Markdown/PDF/image/mixed-batch/smoke regression slice remains green after the latest ingestion hardening, fixture-governance updates, the new cross-document QA additions, and the extra mixed-batch receipt-consistency assertion.

Command 4:
```bash
python -X utf8 -m pytest tests/api/test_chat_eval_runner.py tests/api/test_chat_qa_metrics.py tests/api/test_semireal_chat_support.py tests/api/test_chat_markdown_qa_semireal.py tests/api/test_chat_pdf_semireal.py tests/api/test_chat_image_ocr_semireal.py tests/api/test_chat_mixed_batch_semireal.py tests/api/test_chat_single_kb_qa_smoke.py tests/test_rag_quality_eval_dataset_v4.py tests/test_rag_quality_eval_dataset_v5.py tests/test_rag_quality_eval_dataset_v6.py -q
```

Result 4:
- `81 passed in 18.54s`

Interpretation addendum:
- Command 4 is the latest focused QA master slice for this continuation. It proves that the formal runner, semireal retrieval helpers, markdown/PDF/image OCR QA paths, mixed-batch path, single-KB smoke, and dataset-governance checks all stay green together after the latest import/retrieval fixes.

### 3.2.4 Broad ingestion + QA regression
Command:
```bash
python -X utf8 -m pytest tests/api/test_chat_eval_runner.py tests/api/test_chat_evidence_contract.py tests/api/test_chat_image_ocr_semireal.py tests/api/test_chat_markdown_qa_semireal.py tests/api/test_chat_mixed_batch_semireal.py tests/api/test_chat_pdf_semireal.py tests/api/test_chat_qa_metrics.py tests/api/test_chat_routes.py tests/api/test_chat_scope_contract.py tests/api/test_chat_service.py tests/api/test_chat_single_kb_qa_smoke.py tests/api/test_kb_directory_import_tree.py tests/api/test_kb_directory_storage.py tests/api/test_kb_import_receipt_store.py tests/api/test_image_asset_import.py tests/api/test_ingestion_pipeline.py tests/api/test_index_manager_coverage.py tests/api/test_health_route.py tests/api/test_app_startup.py tests/api/test_runtime_model_loading.py tests/readers/test_image_ocr.py tests/readers/test_pdf_ocr.py tests/test_run_api.py tests/test_rag_quality_eval_dataset.py tests/test_rag_quality_eval_dataset_v2.py tests/test_rag_quality_eval_dataset_v3.py tests/test_rag_quality_eval_dataset_v4.py tests/test_rag_quality_eval_dataset_v5.py tests/test_rag_quality_fixtures.py -q
```

Result:
- `354 passed, 2 warnings in 30.09s`

Notes:
- This current value supersedes older historical text that still mentioned `318 passed, 2 warnings`, the earlier intermediate rerun `329 passed, 2 warnings`, and the prior broader rerun `339 passed, 2 warnings`.
- The warning profile remains unchanged: the 2 warnings come from third-party `jieba/pkg_resources`, and this run did not introduce any new project-owned warning.

Interpretation:
- This suite is the best middle-layer evidence between single-topic regressions and full-suite pytest because it exercises the ingestion path, OCR path, evidence contract, chat service/router surface, runtime model loading, dataset fixtures, and now the `eval_v5` formal dataset checks together.
- The result strengthens the claim that the end-to-end ingestion-to-QA pipeline is stable not only in isolated unit tests but also in a broad business-facing regression slice.

### 3.2.5 Minimal follow-up history grounding and runtime stability
Command:
```bash
python -X utf8 -m pytest tests/test_logging_utils.py tests/api/test_session_store.py tests/api/test_chat_service.py tests/api/test_chat_eval_runner.py -q
```

Result:
- `33 passed in 9.57s`

Interpretation:
- The chat path no longer treats `session_id` history as persistence only: likely follow-up questions can now ground retrieval on recent turns from the same session while keeping the existing single-KB scope/default-deny contract unchanged.
- This focused rerun also revalidates two real runtime fixes introduced while enabling that path: Windows-unsafe session IDs such as `eval::...` are sanitized before becoming filenames, and `session.log` no longer keeps a long-lived file handle that blocks temporary-directory cleanup on Windows.
- This is still only a **minimal** follow-up capability. It should not be overstated as complete multi-turn dialogue reasoning.

### 3.3 Full pytest regression
Command:
```bash
python -X utf8 -m pytest -q
```

Result:
- `667 passed, 2 warnings in 35.80s`

Notes:
- This current value supersedes earlier stale text that still mentioned `610 passed, 2 warnings` and the previous intermediate rerun `626 passed, 2 warnings`.
- The 2 warnings still come from third-party `jieba/pkg_resources`; no new project-owned warning was found in this round.

Interpretation:
- The full automated suite passes in the current worktree.
- This is the strongest overall evidence that there is no new automated blocking failure across the repository surface covered by tests.

### 3.4 Full coverage regression
Command:
```bash
python -X utf8 -m pytest tests/api tests/readers tests/utils tests/test_rag_quality_eval_dataset.py tests/test_rag_quality_eval_dataset_v2.py tests/test_rag_quality_eval_dataset_v3.py tests/test_rag_quality_eval_dataset_v4.py tests/test_rag_quality_eval_dataset_v5.py tests/test_rag_quality_eval_dataset_v6.py tests/test_diag_roundtrip_support.py tests/test_diag_utf8_import_roundtrip.py tests/test_logging_utils.py tests/test_retriever.py tests/test_run_api.py --cov=api --cov=server --cov-report=term --cov-report=xml:docs/20260722-local-multi-kb-assistant/artifacts/coverage-full-20260731-current.xml
```

Result:
- `629 passed, 2 warnings in 115.53s (0:01:55)`
- `TOTAL 6661 / Miss 1189 / Cover 82%`

Formal output:
- `docs/20260722-local-multi-kb-assistant/artifacts/coverage-full-20260731-current.xml`

Notes:
- This current coverage summary supersedes earlier stale text that still mentioned `Miss 1122`, `TOTAL 6565 / Miss 1117 / Cover 83%`, and older total-statement counts.
- `82%` is above the repository requirement `>= 80%`.

### 3.4.1 Focused storage-boundary addendum
Command 1:
```bash
python -X utf8 -m pytest tests/api/test_index_manager_coverage.py tests/utils/test_file_kb_paths.py --cov=server.index --cov=server.utils.file --cov-report=term-missing
```

Result 1:
- `71 passed in 13.10s`
- `server/index.py: 530 statements / 24 missed / 95% cover`
- `server/utils/file.py: 81 statements / 3 missed / 96% cover`
- `TOTAL: 611 statements / 27 missed / 96% cover`

Command 2:
```bash
python -X utf8 -m pytest tests/api/test_ingestion_pipeline.py tests/api/test_kb_import_receipt_store.py tests/api/test_image_asset_import.py tests/api/test_kb_directory_storage.py tests/api/test_kb_directory_import_tree.py tests/readers/test_image_ocr.py tests/readers/test_pdf_ocr.py tests/api/test_chat_service.py tests/api/test_session_store.py tests/test_logging_utils.py tests/api/test_chat_eval_runner.py tests/api/test_index_manager_coverage.py tests/utils/test_file_kb_paths.py -q
```

Result 2:
- `227 passed in 19.90s`

Command 3:
```bash
python -X utf8 -m pytest tests/api/test_ingestion_pipeline.py tests/api/test_kb_import_receipt_store.py tests/api/test_image_asset_import.py tests/api/test_kb_directory_storage.py tests/api/test_kb_directory_import_tree.py tests/readers/test_image_ocr.py tests/readers/test_pdf_ocr.py tests/api/test_index_manager_coverage.py tests/utils/test_file_kb_paths.py --cov=api.services.kb_service --cov=server.ingestion --cov=server.readers.image_ocr --cov=server.readers.pdf_ocr --cov=server.index --cov=server.utils.file --cov-report=term-missing
```

Result 3:
- `194 passed in 21.82s`
- `api/services/kb_service.py: 83%`
- `server/ingestion.py: 93%`
- `server/readers/image_ocr.py: 89%`
- `server/readers/pdf_ocr.py: 92%`
- `server/index.py: 97%`
- `server/utils/file.py: 96%`
- `TOTAL: 2639 statements / 326 missed / 88% cover`

Interpretation:
- The previously weakest import-boundary utilities are now covered much more directly.
- `save_uploaded_file()` is no longer only tested against a legacy in-memory object shape; it is also validated against a FastAPI-style upload object carrying `filename` and `file.read()`.
- `IndexManager` now has focused regression coverage for path-resolution failures, ingestion-diagnostic merging, document/file metadata backfilling, and `persist=False` insertion paths.
- This addendum supersedes the earlier smaller boundary rerun (`221 passed`) because the new command includes the expanded index/file tests added in this continuation.

### 3.5 Stage 3 artifact consistency verifier
Command 1:
```bash
python -X utf8 -m pytest tests/scripts/test_verify_stage3_artifacts.py -q
```

Result 1:
- `5 passed in 0.60s`

Command 2:
```bash
python -X utf8 -m scripts.verify_stage3_artifacts --json
```

Result 2:
- `ok = true`
- `manifest_count = 9`
- `submit_scope_count = 9`
- `missing_files = []`
- `missing_report_refs = []`
- `missing_report_tokens = []`
- `manifest_only = []`
- `submit_scope_only = []`

Files involved:
- `scripts/verify_stage3_artifacts.py`
- `tests/scripts/test_verify_stage3_artifacts.py`

Interpretation:
- The report, artifact manifest, and submit scope are aligned again.
- This step turns file existence, report references, and minimal submit-scope alignment into a machine-checkable contract instead of a manual assumption.

### 3.6 Fresh live smoke on the current worktree service
Execution setup:
- A fresh backend process was started from the current worktree with `KB_API_PORT=18083` and `python -X utf8 run_api.py`.
- Runtime readiness was then confirmed via `/api/health` until both embedding warmup and OCR warmup reported `is_ready = true`.

Commands:
```bash
python -X utf8 scripts/diag_utf8_import_roundtrip.py --base-url http://127.0.0.1:18084 --output-path docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18084-utf8.json
python -X utf8 scripts/diag_pdf_text_roundtrip.py --base-url http://127.0.0.1:18084 --output-path docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18084-pdf-text.json
python -X utf8 scripts/diag_pdf_scan_roundtrip.py --base-url http://127.0.0.1:18084 --output-path docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18084-pdf-scan.json
python -X utf8 scripts/diag_image_ocr_roundtrip.py --base-url http://127.0.0.1:18084 --output-path docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18084-image-ocr.json
python -X utf8 scripts/diag_mixed_batch_roundtrip.py --base-url http://127.0.0.1:18084 --output-path docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18084-mixed-batch.json
```

Fresh outputs:
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18084-utf8.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18084-pdf-text.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18084-pdf-scan.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18084-image-ocr.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18084-mixed-batch.json`

Observed results:
- `20260731-live-18084-utf8.json`: all checks are `true`; the answer is `知识库仍然是授权边界。`; import diagnostics report `total_ms = 39901.119`, and the saved Markdown bytes still match the source hash.
- `20260731-live-18084-pdf-text.json`: all checks are `true`; the answer is `Knowledge Base remains the authorization boundary.`; preview resolution is present; end-to-end import diagnostics report `total_ms = 196.128`.
- `20260731-live-18084-pdf-scan.json`: all checks are `true`, including `source_text_layer_empty = true` and `saved_text_layer_empty = true`; the scanned-PDF OCR import completed with `total_ms = 40124.786`.
- `20260731-live-18084-image-ocr.json`: all checks are `true`, including `ocr_attempted = true` and `indexed_from_ocr = true`; standalone OCR time is `14619.347 ms`, and end-to-end import diagnostics report `total_ms = 14713.464`.
- `20260731-live-18084-mixed-batch.json`: `run_gates.core_ingestion_passed = true`, `run_gates.core_positive_qa_passed = true`, `run_gates.strict_no_evidence_contract_passed = true`, `run_gates.no_evidence_answer_refusal_like = true`, and `run_gates.run_passed = true`. The batch display summary shows 4 imported items with 3 indexed and 1 expected empty result caused by `shadowed_by_embedded_asset`, which matches the script's import checks.

Interpretation:
- This fresh smoke validates the current worktree under a real backend process, not just via isolated pytest execution.
- It strengthens confidence that the current implementation can actually start, warm embedding/OCR dependencies, accept imports, persist files, build/reuse indexes, answer questions within explicit KB scope, and return evidence/preview payloads that remain structurally usable.

#### 3.6.1 Fresh re-run on a second live service port
Execution setup:
- A second fresh backend process was started from the current worktree with `KB_API_PORT=18090` and `python -X utf8 run_api.py`.
- Runtime readiness was re-checked via `/api/health` until both embedding warmup and OCR warmup again reported `is_ready = true`.

Commands:
```bash
python -X utf8 scripts/diag_utf8_import_roundtrip.py --base-url http://127.0.0.1:18090 --output-path docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18090-utf8.json
python -X utf8 scripts/diag_pdf_text_roundtrip.py --base-url http://127.0.0.1:18090 --output-path docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18090-pdf-text.json
python -X utf8 scripts/diag_pdf_scan_roundtrip.py --base-url http://127.0.0.1:18090 --output-path docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18090-pdf-scan.json
python -X utf8 scripts/diag_image_ocr_roundtrip.py --base-url http://127.0.0.1:18090 --output-path docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18090-image-ocr.json
python -X utf8 scripts/diag_mixed_batch_roundtrip.py --base-url http://127.0.0.1:18090 --output-path docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18090-mixed-batch.json
```

Fresh outputs:
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18090-utf8.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18090-pdf-text.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18090-pdf-scan.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18090-image-ocr.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18090-mixed-batch.json`

Observed results:
- `20260731-live-18090-utf8.json`: all checks are `true`; the answer again states that the Knowledge Base remains the authorization boundary; import diagnostics report `total_ms = 1711.109`, and the saved Markdown bytes still match the source hash.
- `20260731-live-18090-pdf-text.json`: all checks are `true`; the answer is `Knowledge Base remains the authorization boundary.`; preview resolution is present; end-to-end import diagnostics report `total_ms = 149.945`.
- `20260731-live-18090-pdf-scan.json`: all checks are `true`, including `source_text_layer_empty = true` and `saved_text_layer_empty = true`; the scanned-PDF OCR import still answers correctly, and the imported file-result diagnostics report `total_ms = 24360.152`.
- `20260731-live-18090-image-ocr.json`: all checks are `true`, including `ocr_attempted = true` and `indexed_from_ocr = true`; standalone OCR time is `11905.315 ms`, and the imported file-result diagnostics report `total_ms = 11952.342`.
- `20260731-live-18090-mixed-batch.json`: `run_gates.core_ingestion_passed = true`, `run_gates.core_positive_qa_passed = true`, `run_gates.strict_no_evidence_contract_passed = true`, `run_gates.no_evidence_answer_refusal_like = true`, and `run_gates.run_passed = true`. The asset summary again reports exactly 2 registered image assets (`1 embedded + 1 standalone`), which matches the mixed-batch import checks.

Interpretation:
- This second live run did not reveal a new import/embedding break in the current worktree; instead, it independently re-confirmed the same five-path chain on a different fresh service process.
- That matters because the user concern is specifically "real import and embedding issues": this rerun adds current-round HTTP evidence that the chain is not only green in pytest/semireal evaluation, but also repeatedly green in live startup -> warmup -> import -> retrieve -> answer -> evidence preview flow.

### 3.7 Empty-markdown import bugfix revalidation
Background:
- During the follow-up sweep after the main smoke passed, a real bug was reproduced on the live service: importing a whitespace-only Markdown file returned `status = failed` with the error `'NoneType' object is not iterable`.
- Root cause tracing pointed to `server/ingestion.py`, where the custom `AdvancedIngestionPipeline.run()` path could pass `None` directly into cache persistence when a transform produced no nodes.

Code and regression updates:
- `server/ingestion.py`
  - added `_normalize_transformed_nodes()` and now normalizes `None` to `[]` before cache writes and later stages consume the transform output.
- `tests/api/test_ingestion_pipeline.py`
  - added a direct regression that reproduces the transform-returns-`None` case and asserts cache writes `[]` instead of crashing.
- `tests/api/test_index_manager_coverage.py`
  - the previously added manager-level guards for empty pipeline outputs remained green after the pipeline fix.

Targeted regression command:
```bash
python -X utf8 -m pytest tests/api/test_ingestion_pipeline.py tests/api/test_index_manager_coverage.py tests/api/test_kb_directory_storage.py -q
```

Result:
- `82 passed in 10.63s`

Fresh runtime artifact:
- `docs/20260722-local-multi-kb-assistant/artifacts/runtime/20260731-empty-markdown-runtime.json`

Fresh live artifact:
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18086-empty-file.json`

Observed results:
- `20260731-empty-markdown-runtime.json`: `node_count = 0`, `empty_document_count = 1`, `nodes_with_embedding_count = 0`, and the pipeline no longer throws while processing a whitespace-only Markdown file.
- `20260731-live-18086-empty-file.json`: the file result reports `status = empty`, `empty_count = 1`, `failed_count = 0`, `empty_reason = no_nodes_generated`, and `/api/kb/list` returns an empty doc list for that KB.

Interpretation:
- The previously reproduced empty-Markdown crash is now fixed on the current worktree.
- This closes an important ingestion edge case without overstating the broader conclusion: the main path is working, and one real bug discovered during validation has been turned into a regression-tested behavior.


### 3.8 Binary-upload rejection hardening
Background:
- During the next ingestion sweep, a real runtime probe showed that uploading `payload.bin` with `content_type = application/octet-stream` was previously treated as a successful import.
- That behavior was incorrect for the current product scope: instead of being rejected early, the binary payload went through the generic loader path and produced an indexed node.

Code and regression updates:
- `api/services/kb_service.py`
  - added an explicit import-entry rejection for `file_kind = binary`, so unsupported binary uploads now fail before file persistence and before any runtime/model/index-manager call.
  - added a user-facing error message builder for unsupported file types, and surfaced the stable failure category `unsupported_file_type` in per-file diagnostics and batch aggregation.
- `tests/api/test_kb_directory_storage.py`
  - added one regression that asserts binary uploads are rejected with `status = failed`, `path = None`, `file_retained_on_disk = false`, `failure_category = unsupported_file_type`, and that runtime/index-manager methods are never called.
  - added a second mixed-batch regression that proves one binary reject does not block a later supported text file in the same batch.

Targeted regression command:
```bash
python -X utf8 -m pytest tests/api/test_kb_directory_storage.py tests/api/test_image_asset_import.py tests/api/test_ingestion_pipeline.py tests/api/test_index_manager_coverage.py -q
```

Result:
- `97 passed in 9.40s`

Fresh runtime artifact:
- `docs/20260722-local-multi-kb-assistant/artifacts/runtime/20260731-binary-upload-rejected-runtime.json`

Observed results:
- `success_count = 0`, `failed_count = 1`, `indexed_chunks = 0`
- the file result now reports `status = failed`, `file_kind = binary`, `failure_category = unsupported_file_type`, and `path = null`
- the runtime artifact also shows `file_save_ms = 0`, `primary_index_ms = 0`, and `files_on_disk = []`, which is consistent with an early reject rather than a partial ingest

Interpretation:
- This closes another real ingestion boundary bug: unsupported binary uploads are no longer misreported as successful knowledge import.
- The fix keeps the current scope honest: the system currently promises Markdown / PDF / text / image ingestion, not arbitrary binary understanding.


### 3.9 Binary-suffix rejection when MIME is missing
Background:
- After the earlier binary-upload hardening landed, a smaller follow-up runtime probe found that `payload.bin` could still slip through when `content_type` was empty.
- In that case, the file was previously classified as `unknown` instead of `binary`, so it still reached the generic import path and was misreported as a successful import.

Code and regression updates:
- `api/services/kb_service.py`
  - tightened `_detect_file_kind(...)` so that an unrecognized file that still has a concrete suffix is treated as `binary` even when MIME is absent.
  - kept extensionless uploads as `unknown`, which avoids overcorrecting into a blanket rejection of suffix-less text files.
  - updated the early-reject branch to preserve the detected suffix in diagnostics, so the failed result now reports `file_kind = binary` instead of a misleading `unknown`.
- `tests/api/test_kb_directory_storage.py`
  - added `test_import_files_rejects_binary_suffix_without_content_type_before_runtime`.

Targeted regression command:
```bash
python -X utf8 -m pytest tests/api/test_kb_directory_storage.py tests/api/test_image_asset_import.py tests/api/test_ingestion_pipeline.py tests/api/test_index_manager_coverage.py -q
```

Result:
- `98 passed in 10.63s`

Fresh runtime artifact:
- `docs/20260722-local-multi-kb-assistant/artifacts/runtime/20260731-binary-suffix-no-content-type-rejected-runtime.json`

Observed results:
- the runtime artifact shows `success_count = 0`, `failed_count = 1`, `indexed_chunks = 0`
- the file result reports `file_kind = binary`, `failure_category = unsupported_file_type`, and the user-visible message `暂不支持该文件类型导入（.bin），请上传 Markdown、PDF、文本或图片文件`
- `files_on_disk = []`, which means the suffix-only binary case is also rejected before persistence and indexing

Additional QA smoke after the import hardening:
```bash
python -X utf8 -m pytest tests/api/test_chat_single_kb_qa_smoke.py tests/test_rag_quality_eval_dataset_v5.py -q
```
- Result: `13 passed in 3.30s`

Interpretation:
- This closes the remaining easy bypass for the binary false-positive import class.
- The import boundary is now more consistent with the product statement, and the quick QA smoke indicates these import hardening changes did not regress the current single-KB chat evaluation baseline.

### 3.10 Extensionless binary rejection when both suffix and MIME are missing
Background:
- A follow-up runtime probe showed one more real bypass after Sections 3.8 and 3.9: an upload like `README` with `content_type = ""` and raw binary bytes such as `b"\x00\x01\x02\x03"` was still being reported as a successful import.
- The root cause was that the file-kind inference had no suffix and no MIME to work with, so the payload stayed `unknown` and still reached the generic import path.

Code and regression updates:
- `api/services/kb_service.py`
  - added a narrow content-sniffing fallback that only activates when both suffix and MIME are missing;
  - recognizes UTF-8 / UTF-16-like extensionless text as `text`, so README-like text files are not over-rejected;
  - recognizes clearly binary extensionless payloads as `binary`, so they are rejected before persistence and indexing;
  - preserves the inferred `file_kind` through the final diagnostics via `file_kind_override`, avoiding a later fallback to `unknown` in the result payload.
- `tests/api/test_kb_directory_storage.py`
  - added `test_import_files_rejects_extensionless_binary_without_content_type_before_runtime`;
  - added `test_import_files_allows_extensionless_utf8_text_without_content_type` to prove the hardening does not accidentally break suffix-less UTF-8 text import.

Targeted regression command:
```bash
python -X utf8 -m pytest tests/api/test_kb_directory_storage.py tests/api/test_image_asset_import.py tests/api/test_ingestion_pipeline.py tests/api/test_index_manager_coverage.py -q
```

Result:
- `100 passed in 8.84s`

Fresh runtime artifact:
- `docs/20260722-local-multi-kb-assistant/artifacts/runtime/20260731-extensionless-binary-no-content-type-rejected-runtime.json`

Observed results:
- the runtime artifact shows `success_count = 0`, `failed_count = 1`, `indexed_chunks = 0`
- the file result reports `name = README`, `file_kind = binary`, `failure_category = unsupported_file_type`, and `path = null`
- `files_on_disk = []`, and the artifact also records `ensure_models_ready_called = false`, `get_index_manager_called = false`, and `load_files_called = false`
- the new positive regression proves that extensionless UTF-8 text still imports successfully and is now classified as `file_kind = text`

Additional QA smoke after the hardening:
```bash
python -X utf8 -m pytest tests/api/test_chat_single_kb_qa_smoke.py tests/test_rag_quality_eval_dataset_v5.py -q
```
- Result: `13 passed in 2.97s`

Interpretation:
- This closes the next real binary false-positive import bypass: unsupported extensionless binary payloads are no longer misreported as successful knowledge import.
- The hardening is intentionally narrow: it closes the binary leak while preserving the import path for legitimate suffix-less UTF-8 text documents.

### 3.11 Extensionless supported PDF/image recognition when suffix and MIME are both missing
Background:
- After the extensionless-binary hardening in Section 3.10, a fresh probe still exposed one more real gap: supported files like `manual` (`%PDF-...`) and `diagram` (PNG signature) with `content_type = ""` could still be misclassified.
- The concrete risk was different from the binary false-positive case: these files were already inside product scope, but they were not reliably entering the intended PDF/image pipeline when both suffix and MIME were absent.

Code and regression updates:
- `api/services/kb_service.py`
  - added `_detect_file_kind_from_content_signature()` and checks for supported PDF/image signatures before the generic text/binary fallback;
  - currently recognizes `%PDF-`, PNG, JPEG, GIF, BMP, and WEBP signatures when suffix and MIME are both missing;
  - preserves the inferred `file_kind` through failed-result branches as well, so dependency-missing PDF failures no longer degrade to `file_kind = unknown`.
- `tests/api/test_kb_directory_storage.py`
  - added `test_import_files_detects_extensionless_pdf_without_content_type_as_pdf`;
  - added `test_import_files_detects_extensionless_png_without_content_type_as_image`;
  - repaired the affected Chinese docstrings/assertions so the tests validate the real contract instead of matching placeholder question marks.

Targeted regression command:
```bash
python -X utf8 -m pytest tests/api/test_kb_directory_storage.py -k "extensionless_pdf_without_content_type or extensionless_png_without_content_type or extensionless_binary_without_content_type or extensionless_utf8_text_without_content_type" -q
```

Result:
- `4 passed in 3.11s`

Broader ingestion regression after the fix:
```bash
python -X utf8 -m pytest tests/api/test_kb_directory_storage.py tests/api/test_image_asset_import.py tests/api/test_ingestion_pipeline.py tests/api/test_index_manager_coverage.py -q
```

Result:
- `102 passed in 11.90s`

Additional QA smoke after the fix:
```bash
python -X utf8 -m pytest tests/api/test_chat_single_kb_qa_smoke.py tests/test_rag_quality_eval_dataset_v5.py -q
```
- Result: `13 passed in 2.68s`

Artifact verifier:
```bash
python -X utf8 scripts/verify_stage3_artifacts.py
```
- Result: `ok=True`, `manifest_count=9`, `submit_scope_count=9`

Interpretation:
- Extensionless files no longer have to rely on suffix/MIME luck to enter the supported PDF/image pipeline.
- The fix stays narrow: supported PDF/image signatures are promoted into the right path, while the earlier Section 3.10 guards still keep unsupported extensionless binary payloads out.
- The single-KB QA smoke still passes after the file-kind recognition update, so the hardening did not regress the current answer-quality baseline.

### 3.11.1 Extensionless image OCR eligibility when suffix and MIME are both missing
Background:
- A fresh live probe after Section 3.11 revealed one more chain-level inconsistency: extensionless PNG uploads were already classified as `file_kind = image`, but the standalone OCR reader could still return `status = skipped` when both suffix and MIME were empty.
- That meant the import classifier and the OCR executor were using different eligibility rules. In the live service this showed up as `ocr_skipped` instead of a real OCR attempt.

Code and regression updates:
- `server/readers/image_ocr.py`
  - added `_has_supported_image_signature()` and `_is_supported_image_input()` so OCR eligibility can fall back to PNG/JPEG/BMP/WEBP signature detection when suffix and MIME are both missing;
  - keeps the previous narrow contract: unsupported text/binary inputs still return `skipped`, while supported extensionless image payloads now proceed into the actual OCR path.
- `tests/readers/test_image_ocr.py`
  - added `test_extract_image_ocr_result_supports_extensionless_png_without_content_type`;
- `tests/api/test_kb_directory_storage.py`
  - added `test_import_files_runs_ocr_for_extensionless_png_without_content_type` to prove the full import path no longer degrades to `ocr_skipped`.

Targeted regression command:
```bash
python -X utf8 -m pytest tests/readers/test_image_ocr.py tests/api/test_kb_directory_storage.py tests/api/test_image_asset_import.py tests/api/test_ingestion_pipeline.py tests/api/test_index_manager_coverage.py -q
```

Result:
- `119 passed in 10.26s`

Fresh live artifact:
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18088-extensionless-image-empty-mime.json`

Observed live result:
- the uploaded file is extensionless (`name = diagram`, `type = ""`) but still lands in `file_kind = image`;
- the live import now reports `ocr_attempted = true`, `ocr_status = no_text`, `ocr_skipped_count = 0`, and `asset_registered = true`;
- this is the expected honest result for a blank white PNG sample: OCR was executed, but there was no text to index.

Interpretation:
- This closes the mismatch between file-kind recognition and standalone image OCR eligibility for extensionless supported images.
- The chain is now more honest and easier to debug: blank images become `no_text`, not `ocr_skipped`, so the product no longer hides a classifier/executor inconsistency behind an empty import result.

### 3.11.2 Extensionless supported files with generic `application/octet-stream` MIME
Background:
- After closing the empty-MIME extensionless gap in Sections 3.11 and 3.11.1, one more realistic client behavior still remained: some upload clients send extensionless files as `application/octet-stream` instead of leaving MIME empty.
- In the prior implementation, that generic MIME blocked content sniffing. As a result, extensionless supported text/image/PDF payloads could still be misclassified as `binary`, and the image OCR executor could still skip a real supported image.

Code and regression updates:
- `api/services/kb_service.py`
  - added `_CONTENT_SNIFF_FALLBACK_MIME_TYPES` and now allows the existing content-signature/text/binary sniffing path to run when the filename has no suffix and MIME is a generic binary fallback such as `application/octet-stream`;
  - this preserves the narrow contract: suffix-based `.bin` files and clearly binary extensionless payloads still stay rejected.
- `server/readers/image_ocr.py`
  - added `_SIGNATURE_SNIFF_FALLBACK_IMAGE_MIME_TYPES` so extensionless supported images with generic MIME can still enter OCR by signature;
  - keeps non-image generic payloads out of OCR because the signature gate still has to pass.
- `tests/readers/test_image_ocr.py`
  - added `test_extract_image_ocr_result_supports_extensionless_png_with_octet_stream_content_type`;
- `tests/api/test_kb_directory_storage.py`
  - added `test_import_files_rejects_extensionless_binary_with_octet_stream_before_runtime`;
  - added `test_import_files_allows_extensionless_utf8_text_with_octet_stream`;
  - added `test_import_files_detects_extensionless_pdf_with_octet_stream_as_pdf`;
  - added `test_import_files_runs_ocr_for_extensionless_png_with_octet_stream`.

Targeted regression commands:
```bash
python -X utf8 -m pytest tests/readers/test_image_ocr.py -k "extensionless_png_without_content_type or extensionless_png_with_octet_stream_content_type" -q
python -X utf8 -m pytest tests/api/test_kb_directory_storage.py -k "extensionless_binary_with_octet_stream or extensionless_utf8_text_with_octet_stream or extensionless_pdf_with_octet_stream or extensionless_png_with_octet_stream" -q
python -X utf8 -m pytest tests/readers/test_image_ocr.py tests/api/test_kb_directory_storage.py tests/api/test_image_asset_import.py tests/api/test_ingestion_pipeline.py tests/api/test_index_manager_coverage.py -q
```

Results:
- `2 passed`
- `4 passed`
- `124 passed in 10.23s`

Focused QA regression after the hardening:
```bash
python -X utf8 -m pytest tests/api/test_chat_image_ocr_semireal.py tests/api/test_chat_mixed_batch_semireal.py tests/api/test_chat_single_kb_qa_smoke.py -q
```
- Result: `22 passed in 6.41s`

Fresh live artifact:
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18089-extensionless-octet-fallback-import.json`

Observed live result:
- the extensionless `README` uploaded as `application/octet-stream` now imports as `status = indexed`, `file_kind = text`;
- the extensionless `diagram` uploaded as `application/octet-stream` now imports as `file_kind = image`, `ocr_status = no_text`, `empty_reason = no_extractable_text`;
- the extensionless `BLOB` uploaded as `application/octet-stream` is still rejected with `status = failed`, `file_kind = binary`, `failure_category = unsupported_file_type`.

Interpretation:
- This closes another realistic ingest mismatch between product scope and client behavior: a generic binary MIME no longer forces supported extensionless content into the unsupported bucket.
- The hardening remains honest and bounded: supported payloads recover into the correct import path, while unsupported binary bytes are still blocked before indexing.

## 4. Review of existing formal live roundtrip artifacts
The following evidence is based on formal JSON artifacts that already exist in the repository. They are included because they add chain-level evidence beyond pure unit/integration test output.

### 4.1 Reviewed files
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/diag-utf8-after-answer-expand.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-utf8.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-pdf-text.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-pdf-scan.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-image-ocr.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-mixed-batch.json`

### 4.2 Reviewed findings
- `diag-utf8-after-answer-expand.json` and `20260731-live-18082-utf8.json` both show a short Markdown diagnostic answer whose meaning is 'the knowledge base remains the authorization boundary', and their checks such as `source_saved_hash_match`, `chat_answer_meets_minimum_contract`, and `chat_evidence_contains_expected_snippet` are all `true`.
- `20260731-live-18082-pdf-text.json` shows the PDF text-layer answer `Knowledge Base remains the authorization boundary.`, with source, evidence, and preview checks all `true`.
- `20260731-live-18082-pdf-scan.json` shows the scanned-PDF OCR fallback path with `source_text_layer_empty = true` and `saved_text_layer_empty = true`, while answer, evidence, and preview checks remain `true`.
- `20260731-live-18082-image-ocr.json` shows the image OCR answer `In the OCR diagnostic image, the authorization boundary is the Knowledge Base.`, with `ocr_attempted = true` and `indexed_from_ocr = true`.
- `20260731-live-18082-mixed-batch.json` shows `core_ingestion_passed`, `core_positive_qa_passed`, `strict_no_evidence_contract_passed`, `no_evidence_answer_refusal_like`, and `run_passed` all equal to `true`.
- The JSON also echoes `requested_scope_type`, `effective_scope_type`, and `isolation_level`, which is consistent with the current product statement: explicit single-KB scope is provided, and the current isolation level is still `logical_filter_only`.

### 4.3 What this evidence proves and what it does not prove
- It proves that there is traceable chain-level evidence for Markdown, PDF text layer, scanned PDF OCR, image OCR, and mixed batch.
- It proves that the current image path covers **OCR extraction + image asset indexing + evidence/preview resolution**.
- It does not prove advanced image understanding, flowchart semantic understanding, or general VQA. This report does not claim those capabilities.

## 5. Current quality judgment and remaining boundaries

### 5.1 What can be stated with confidence
- The base ingestion path is working, because the wide ingestion slice (`161 passed in 10.19s`), the narrower backend-only ingestion slice (`92 passed in 11.56s`), and the frontend receipt-summary contract (`10 passed`) together cover the critical ingestion/OCR/directory/receipt/asset surface.
- The base QA path is working, because all three formal evaluation layers were re-run successfully: `eval_v4` reached `54/54 passed`, `eval_v5` reached `72/72 passed`, and `eval_v6` reached `78/78 passed` with both business and diagnostic gates green.
- The strengthened QA gate now has explicit evidence for long-document, cross-document, hard-refusal, mixed-batch receipt-consistency, minimal follow-up/session-stability, and `eval_v6` dataset-validation scenarios in addition to the earlier business-path coverage, and the refreshed broad QA slice reached `354 passed, 2 warnings`.
- The focused follow-up/session/runtime-stability rerun also passed with `33 passed in 9.57s`, so the formal eval support path is now covered not only at dataset level but also at session persistence and Windows runtime-behavior level.
- The full repository regression also remains green at `667 passed, 2 warnings`, and the current coverage re-run still stays above threshold at `82%`.

### 5.2 What must not be overstated
- Do not state that multi-KB storage isolation is already physical. The current state remains shared storage plus `metadata["kb_id"]` filtering.
- Do not state that image understanding is already complete. The committed scope is OCR extraction plus image ingestion/indexing.
- Do not state that QA quality has already been comprehensively proven for production reality. The more accurate statement is that the base pipeline is working and the evaluation framework is now credible and reusable.
- Do not state that full multi-turn dialogue reasoning is already complete. The current state is only minimal history-grounded follow-up support for likely same-session follow-up questions.

### 5.3 Recommended next strengthening steps
- Continue expanding semi-real and business-like QA datasets and run them as formal regressions.
- Extend the current dataset beyond the newly landed **minimal** follow-up/session grounding into richer multi-turn context chains, larger mixed-modality batches, and more difficult cross-document competition cases.
- Keep the security discussion explicit around default-deny and logical-only isolation, and clarify acceptable P0/P1 risk versus the future P2 physical-isolation path.

## 6. Formal artifacts explicitly referenced by this report
The following 15 files are the formal outputs explicitly referenced by this report's retained artifact set. The first 9 are aligned with the Stage 3 manifest/submit-scope verifier, the 10th and 11th are the fresh runtime artifacts referenced in Sections 3.8 and 3.9, the next 2 are the re-run `eval_v5` QA artifacts, and the last 2 are the new unified `eval_v6` diagnostic-report artifacts referenced in this update. The fresh `20260731-live-18084-*.json` and `20260731-live-18090-*.json` smoke outputs from Section 3.6, plus the current-run `18088`/`18089` live artifacts from Sections 3.11.1 and 3.11.2, are valid supplementary evidence, but they are not yet part of that minimal retained artifact set:
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v4_business-semireal-report.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v4_business-semireal-report.md`
- `docs/20260722-local-multi-kb-assistant/artifacts/coverage-full-20260731-current.xml`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/diag-utf8-after-answer-expand.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-utf8.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-pdf-text.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-pdf-scan.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-image-ocr.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-mixed-batch.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/runtime/20260731-binary-upload-rejected-runtime.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/runtime/20260731-binary-suffix-no-content-type-rejected-runtime.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v5_business_plus-semireal-report.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v5_business_plus-semireal-report.md`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v6_business_plus_diagnostic-semireal-report.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v6_business_plus_diagnostic-semireal-report.md`

## 7. Final conclusion
> The most accurate current conclusion is: **the base ingestion and QA path is working, and this is supported by the current-round re-run results `161 passed`, `92 passed`, `10 passed`, `54/54 passed`, `72/72 passed`, `78/78 passed`, `81 passed`, `15 passed`, `33 passed`, `47 passed`, `354 passed, 2 warnings`, `667 passed, 2 warnings`, `629 passed, 2 warnings`, `TOTAL 6661 / Miss 1189 / Cover 82%`, `5 passed`, plus the reviewed and freshly generated live roundtrip artifacts.**

> The new `eval_v6` artifact remains especially important because it unifies business QA and weak-signal diagnostics in one formal report, and it now passes end-to-end while still keeping those weak-signal cases explicit in `diagnostic_summary`. That means the next meaningful step is no longer "make the formal eval green," but **continue strengthening real import/live-roundtrip coverage and harder competition cases**, while continuing to keep product claims honest around logical-only isolation, default-deny scope control, and the current image scope of OCR plus asset ingestion.

