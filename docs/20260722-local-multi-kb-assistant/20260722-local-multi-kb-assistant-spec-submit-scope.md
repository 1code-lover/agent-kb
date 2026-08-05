# 20260722-本地多知识库助手提交范围清单

## 1. 目的
本清单基于当前 `git status` 与已确认的正式 artifacts 生成，用于在 commit 前将本需求的“必须提交”、“可选提交”与“不建议提交”内容进一步细化到文件级。

## 2. 文件级“建议纳入本轮提交”清单
以下清单为“非 artifacts 的当前变更主体”，应作为本轮 commit 的默认候选集合。

### 根目录
- `.gitignore`
- `run_api.py`
- `评审建议.txt`

### 开发故事沉淀
- `.interview-kit/dev-stories/2026-07-31-feature-local-multi-kb-ingestion-qa-closure.md`
- `.interview-kit/dev-stories/.capture-state.json`

### api
- `api/app.py`
- `api/routers/chat.py`
- `api/routers/health.py`
- `api/runtime.py`
- `api/services/asset_service.py`
- `api/services/chat_service.py`
- `api/services/kb_service.py`

### server
- `server/index.py`
- `server/ingestion.py`
- `server/readers/image_ocr.py`
- `server/readers/pdf_ocr.py`
- `server/splitters/chinese_recursive_text_splitter.py`
- `server/splitters/chinese_text_splitter.py`
- `server/stores/storage_context.py`
- `server/stores/strage_context.py`
- `server/utils/file.py`

### scripts
- `scripts/validate_rag_quality_fixtures.py`
- `scripts/diag_image_ocr_roundtrip.py`
- `scripts/diag_mixed_batch_roundtrip.py`
- `scripts/diag_pdf_scan_roundtrip.py`
- `scripts/diag_pdf_text_roundtrip.py`
- `scripts/diag_roundtrip_support.py`
- `scripts/diag_utf8_import_roundtrip.py`
- `scripts/run_chat_eval.py`
- `scripts/verify_stage3_artifacts.py`

### tests
- `tests/api/test_app_startup.py`
- `tests/api/test_chat_evidence_contract.py`
- `tests/api/test_health_route.py`
- `tests/api/test_image_asset_import.py`
- `tests/api/test_index_manager_coverage.py`
- `tests/api/test_kb_directory_import_tree.py`
- `tests/api/test_kb_directory_storage.py`
- `tests/api/test_m2_multi_kb.py`
- `tests/api/test_runtime_model_loading.py`
- `tests/readers/test_image_ocr.py`
- `tests/readers/test_pdf_ocr.py`
- `tests/test_rag_quality_fixtures.py`
- `tests/api/_semireal_chat_support.py`
- `tests/api/chat_eval_runner.py`
- `tests/api/chat_qa_metrics.py`
- `tests/api/test_chat_eval_runner.py`
- `tests/api/test_chat_image_ocr_semireal.py`
- `tests/api/test_chat_markdown_qa_semireal.py`
- `tests/api/test_chat_mixed_batch_semireal.py`
- `tests/api/test_chat_pdf_semireal.py`
- `tests/api/test_chat_qa_metrics.py`
- `tests/api/test_chat_routes.py`
- `tests/api/test_chat_service.py`
- `tests/api/test_chat_single_kb_qa_smoke.py`
- `tests/api/test_folder_registry_branches.py`
- `tests/api/test_ingestion_pipeline.py`
- `tests/api/test_kb_import_receipt_store.py`
- `tests/api/test_kb_routes_contract.py`
- `tests/api/test_model_service.py`
- `tests/api/test_semireal_chat_support.py`
- `tests/api/test_settings_routes.py`
- `tests/api/test_storage_context_branches.py`
- `tests/api/test_storage_context_lazy.py`
- `tests/fixtures/rag_quality/eval_v1/cases.json`
- `tests/fixtures/rag_quality/eval_v1/schema.json`
- `tests/fixtures/rag_quality/eval_v2/cases.json`
- `tests/fixtures/rag_quality/eval_v2/schema.json`
- `tests/fixtures/rag_quality/eval_v3/cases.json`
- `tests/fixtures/rag_quality/eval_v3/schema.json`
- `tests/fixtures/rag_quality/eval_v4/cases.json`
- `tests/fixtures/rag_quality/eval_v4/schema.json`
- `tests/fixtures/rag_quality/semireal_markdown/cases.json`
- `tests/fixtures/rag_quality/semireal_markdown/cutover-approval.md`
- `tests/fixtures/rag_quality/semireal_markdown/evaluation-metrics.md`
- `tests/fixtures/rag_quality/semireal_markdown/evidence-preview.md`
- `tests/fixtures/rag_quality/semireal_markdown/folder-boundary.md`
- `tests/fixtures/rag_quality/semireal_markdown/handover-sla.md`
- `tests/fixtures/rag_quality/semireal_markdown/ingestion-priority.md`
- `tests/fixtures/rag_quality/semireal_markdown/refusal-guideline.md`
- `tests/fixtures/rag_quality/semireal_markdown/scope-contract.md`
- `tests/fixtures/rag_quality/semireal_markdown/suite-metrics-gate.md`
- `tests/fixtures/rag_quality/semireal_markdown/utf8-boundary.md`
- `tests/fixtures/rag_quality/semireal_markdown/workflow-boundary.md`
- `tests/fixtures/rag_quality/single_kb_smoke_cases.json`
- `tests/splitters/test_chinese_splitter_branches.py`
- `tests/splitters/test_chinese_splitters.py`
- `tests/test_diag_roundtrip_support.py`
- `tests/test_diag_utf8_import_roundtrip.py`
- `tests/test_rag_quality_eval_dataset.py`
- `tests/test_rag_quality_eval_dataset_v2.py`
- `tests/test_rag_quality_eval_dataset_v3.py`
- `tests/test_rag_quality_eval_dataset_v4.py`
- `tests/test_retriever.py`
- `tests/test_run_api.py`
- `tests/scripts/test_verify_stage3_artifacts.py`

### webapp
- `webapp/src/components/kb/KbReceiptSummary.jsx`
- `webapp/src/domain/importSummary.js`
- `webapp/src/domain/importSummary.test.js`
- `webapp/src/styles.css`

### 需求相关 docs
- `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-plan-ingestion-hardening.md`
- `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-plan.md`
- `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-test-plan.md`
- `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-artifacts-manifest.md`
- `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec-submit-scope.md`
- `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec-qa-evaluation.md`
- `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-test-report.md`

## 3. 文件级“建议按最小集合选择性提交”的 artifacts
以下文件是当前测试报告与 manifest 明确指向的最小追溯产物。

- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v4_business-semireal-report.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v4_business-semireal-report.md`
- `docs/20260722-local-multi-kb-assistant/artifacts/coverage-full-20260731-current.xml`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/diag-utf8-after-answer-expand.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-utf8.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-pdf-text.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-pdf-scan.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-image-ocr.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-mixed-batch.json`

## 4. 文件级“可选提交”的历史/对比 artifacts
以下文件可用于保留演进过程证据，但不是当前阶段的最小交付集合。

- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v1-semireal-report.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v1-semireal-report.md`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v2-semireal-report.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v2-semireal-report.md`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v3-semireal-report.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v3-semireal-report.md`

## 5. “不建议提交”清单
- docs/20260714-kb-directory-storage/20260714-kb-directory-storage-test-report.md
- `tmp_* / .tmp* / temp_*` （仓库根目录调试输出模式）
- docs/20260722-local-multi-kb-assistant/artifacts/temp/
- docs/20260722-local-multi-kb-assistant/artifacts/tmp*/

## 6. 报告与产物一致性检查
- 已核对 `20260722-local-multi-kb-assistant-test-report.md` 中引用的关键正式 artifacts；本清单第 3 节所列 9 个关键追溯文件在当前 worktree 中全部存在。
- 报告所需的关键文件存在性已通过 `python -X utf8 -m scripts.verify_stage3_artifacts --json` 脚本复核，当前输出 `ok = true`，不依赖“相信之前跑过”这种弱证据。
- 测试报告中出现的 `20260731-live-18082-*.json` 为多文件简写模式，其对应的 5 个具体 JSON 文件已在第 3 节逐一列出。
- 测试报告中提到的 `artifacts/temp/` 与 `artifacts/tmp*/` 属于“不应提交的临时输出模式”，并非当前必须存在的交付文件。

## 7. 结论
如果后续要进入 stage / commit，建议优先以第 2 节 + 第 3 节作为提交主体，第 4 节只在需要保留演进历史时再选择性纳入；第 5 节内容则应继续排除在提交面之外。

