# 为本地多知识库助手补齐导入-问答-评测闭环

## 基本信息
- 类型：feature
- 日期：2026-07-31
- 相关模块：导入解析链路、OCR / PDF 读取、问答契约、运行时健康检查、半真实评测、live roundtrip 诊断、Knowledge Workspace
- 相关文件：
  - `api/runtime.py`
  - `api/routers/health.py`
  - `api/services/chat_service.py`
  - `api/services/kb_service.py`
  - `server/index.py`
  - `server/ingestion.py`
  - `server/readers/pdf_ocr.py`
  - `server/readers/image_ocr.py`
  - `scripts/run_chat_eval.py`
  - `scripts/diag_utf8_import_roundtrip.py`
  - `scripts/diag_pdf_text_roundtrip.py`
  - `scripts/diag_pdf_scan_roundtrip.py`
  - `scripts/diag_image_ocr_roundtrip.py`
  - `scripts/diag_mixed_batch_roundtrip.py`
  - `tests/api/test_chat_*`
  - `tests/api/test_ingestion_pipeline.py`
  - `tests/api/test_kb_directory_storage.py`
  - `tests/api/test_image_asset_import.py`
  - `tests/readers/test_pdf_ocr.py`
  - `tests/readers/test_image_ocr.py`
  - `tests/fixtures/rag_quality/eval_v1/`
  - `tests/fixtures/rag_quality/eval_v2/`
  - `tests/fixtures/rag_quality/eval_v3/`
  - `tests/fixtures/rag_quality/eval_v4/`
  - `webapp/src/components/kb/KbReceiptSummary.jsx`
  - `webapp/src/domain/importSummary.js`
  - `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-test-report.md`

## 需求背景
用户要求先把“导入、索引、问答、证据、预览”主链路跑通，再用真实测试报告和 artifacts 证明结论，不能靠放松断言换通过。这轮工作的目标就是把“本地多知识库助手的主链路是否真的打通”从推测变成可追溯事实。

## 设计与实现方案
1. 在 runtime / health 层暴露 OCR、PDF 依赖和 query engine readiness，让本地服务可以说清自己是“活着”还是“真的可用”。
2. 在 ingestion / index / kb_service / asset_service 层统一 receipt、目录树、资产与 OCR 结果，收紧 Markdown、PDF、图片导入和 preview 定位契约。
3. 在 chat_service 与前端 importSummary / KbReceiptSummary 层统一 scope、evidence、preview 和导入摘要，避免导入成功但问答不可核验。
4. 用 run_chat_eval、chat_eval_runner、chat_qa_metrics、eval_v1~v4 数据集和 5 条 live roundtrip 脚本组成正式评测闭环。
5. 用 test-report、artifacts-manifest、submit-scope 把“正式证据”和“临时调试输出”明确分开。

## 为什么选这个方案
我没有再继续围着单个 OCR 问题打转，而是先做主链路证据闭环。这样可以一次回答“是导入坏了、依赖没起、契约不一致，还是主链路其实已经通了只是缺少证明”。

## 其他方案与为什么没选
- 只跑少量 hand smoke 就宣布“主链路全部修好”：没选，因为证据力不够。
- 现在就把图片能力扩展成完整图像理解：没选，因为当前阶段只承诺 OCR 提取 + 图片入库。
- 把 artifacts/ 整包一起提交：没选，因为需要保留“正式证据”与“中间态调试文件”的边界。

## 风险与权衡
1. 多知识库仍然是共享索引 + metadata["kb_id"] 过滤的逻辑隔离，不是物理隔离。
2. 本轮可以证明“截至 2026-07-31，当前 worktree 在已覆盖场景下没有复现新的主链路阻断 bug”，但不能夸大成“永久归零”。
3. coverage 已到 83%，但 agent、settings 和部分外围模块仍需后续补测。

## 验证与结果
- `python -X utf8 -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v4/cases.json --schema tests/fixtures/rag_quality/eval_v4/schema.json --output-dir docs/20260722-local-multi-kb-assistant/artifacts/qa-eval`
- 结果：`54/54 passed`，五项核心指标全部为 `1.0`。
- `python -X utf8 -m pytest tests/api/test_ingestion_pipeline.py tests/api/test_kb_directory_storage.py tests/api/test_kb_directory_import_tree.py tests/api/test_kb_import_receipt_store.py tests/api/test_image_asset_import.py tests/api/test_index_manager_coverage.py tests/readers/test_pdf_ocr.py tests/readers/test_image_ocr.py -q`
- 结果：`138 passed in 59.77s`。
- `python -X utf8 -m pytest tests/api/test_chat_eval_runner.py tests/api/test_chat_evidence_contract.py tests/api/test_chat_image_ocr_semireal.py tests/api/test_chat_markdown_qa_semireal.py tests/api/test_chat_mixed_batch_semireal.py tests/api/test_chat_pdf_semireal.py tests/api/test_chat_qa_metrics.py tests/api/test_chat_routes.py tests/api/test_chat_scope_contract.py tests/api/test_chat_service.py tests/api/test_chat_single_kb_qa_smoke.py tests/api/test_kb_directory_import_tree.py tests/api/test_kb_directory_storage.py tests/api/test_kb_import_receipt_store.py tests/api/test_image_asset_import.py tests/api/test_ingestion_pipeline.py tests/api/test_index_manager_coverage.py tests/api/test_health_route.py tests/api/test_app_startup.py tests/api/test_runtime_model_loading.py tests/readers/test_image_ocr.py tests/readers/test_pdf_ocr.py tests/test_run_api.py tests/test_rag_quality_eval_dataset.py tests/test_rag_quality_eval_dataset_v2.py tests/test_rag_quality_eval_dataset_v3.py tests/test_rag_quality_eval_dataset_v4.py tests/test_rag_quality_fixtures.py -q`
- 结果：`314 passed, 2 warnings in 130.52s`。
- `python -X utf8 -m pytest -q` ? `605 passed, 2 warnings`。
- `python -X utf8 -m pytest --cov=api --cov=server --cov-report=term --cov-report=xml:docs/20260722-local-multi-kb-assistant/artifacts/coverage-full-20260731-current.xml -q` ? `TOTAL Cover 83%`。
- 在独立 18082 实例上运行 5 条 live roundtrip 脚本，UTF-8 Markdown 最新回答为“知识库仍然是授权边界。”，Markdown / PDF 文本层 / 扫描 PDF OCR / 图片 OCR / mixed batch 均未复现新的主链路阻断问题。

## 面试表达版本
我这轮做的核心不是再堆功能，而是把本地多知识库助手的导入、问答和评测闭环真正打通。我先用 runtime readiness、health、receipt 和 OCR/PDF 诊断把系统可观测性立起来，再把 chat 的 scope / evidence / preview 契约和导入摘要统一到同一套结构里。然后我搭了 run_chat_eval 和 5 条 live roundtrip 脚本，覆盖 Markdown、PDF 文本层、扫描 PDF OCR、图片 OCR 和 mixed batch。最后我用 605 条 full pytest、83% coverage、54/54 正式 eval_v4 评测和 5 份 live artifacts支撑“主链路已通，但结论必须诚实写清证明边界”这个结论。
