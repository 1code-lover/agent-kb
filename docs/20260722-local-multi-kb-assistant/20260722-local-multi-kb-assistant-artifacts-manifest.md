# 20260722-本地多知识库助手产物清单

## 1. 目的
本清单用于区分“当前阶段应正式保留的验证产物”与“仅用于本地调试/排障的临时输出”，避免后续提交时把 `tmp_*`、`.tmp*`、端口试跑日志或中间 coverage 版本误当成正式交付物带入版本库。

## 2. 当前阶段应正式保留的产物
以下文件已被 `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-test-report.md` 明确引用，属于当前阶段最重要的追溯证据。

### 2.1 正式问答评测产物
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v4_business-semireal-report.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v4_business-semireal-report.md`

说明：对应 `python -X utf8 -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v4/cases.json --schema tests/fixtures/rag_quality/eval_v4/schema.json --output-dir docs/20260722-local-multi-kb-assistant/artifacts/qa-eval` 的正式运行结果，当前结论为 `54/54 passed`。

### 2.2 正式 coverage 产物
- `docs/20260722-local-multi-kb-assistant/artifacts/coverage-full-20260731-current.xml`

说明：这是测试报告当前引用的唯一 coverage 追溯文件，对应 `python -X utf8 -m pytest --cov=api --cov=server --cov-report=term --cov-report=xml:docs/20260722-local-multi-kb-assistant/artifacts/coverage-full-20260731-current.xml -q`。

### 2.3 关键 live roundtrip 产物
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/diag-utf8-after-answer-expand.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-utf8.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-pdf-text.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-pdf-scan.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-image-ocr.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18082-mixed-batch.json`

说明：
- `diag-utf8-after-answer-expand.json` 用于证明 UTF-8 Markdown 的短答案问题已在 live roundtrip 中得到修复；
- `20260731-live-18082-*` 是 2026-07-31 独立端口复核的 5 条主链路证据，覆盖 Markdown、PDF 文本层、扫描 PDF OCR、图片 OCR 与 mixed batch。

## 3. 可以保留但不是本轮提交硬要求的辅助产物
以下内容在分析或历史对比上有参考价值，但并非当前阶段的最小交付集合；如果提交面需要收窄，可优先不纳入版本库。

### 3.1 历史版本评测/coverage 产物
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v1-semireal-report.*`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v2-semireal-report.*`
- `docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/local_multi_kb_eval_v3-semireal-report.*`
- `docs/20260722-local-multi-kb-assistant/artifacts/coverage-import-*.xml`
- `docs/20260722-local-multi-kb-assistant/artifacts/coverage-full-20260731-v12.xml`
- `docs/20260722-local-multi-kb-assistant/artifacts/coverage-full-20260731-v13.xml`

### 3.2 历史/中间态 live 诊断产物
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/diag-utf8.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/diag-pdf-text.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/diag-pdf-scan.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/diag-image-ocr.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/diag-mixed-batch.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/runtime-smoke/`
- `docs/20260722-local-multi-kb-assistant/artifacts/runtime/20260731-empty-markdown-runtime.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/runtime/20260731-binary-upload-rejected-runtime.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/runtime/20260731-binary-suffix-no-content-type-rejected-runtime.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/runtime/20260731-extensionless-binary-no-content-type-rejected-runtime.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260729-*.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18084-*.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18086-empty-file.json`
- `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/*-roundtrip-v*.json`

说明：这些文件对回溯修复过程有帮助，也覆盖了测试报告中新补充引用的 current-run 复核产物（例如 `18084` fresh smoke、`18086` 空 Markdown live 验证以及 runtime 直连验证）；但如果只保留当前阶段的最终证明链，可不作为强制提交项。

## 4. 明确不应提交的本地临时输出
以下内容属于排障或试跑中间产物，不应作为正式交付证据：
- 仓库根目录下的 `tmp_*`、`.tmp*`、`temp_*` 文件或目录；
- `docs/20260722-local-multi-kb-assistant/artifacts/temp/`；
- `docs/20260722-local-multi-kb-assistant/artifacts/tmp*/`；
- 仅用于端口探测、chunk probe、局部 debug 的临时 JSON、图片、PDF 或 recovered 草稿文件。

这些路径已在仓库 `.gitignore` 中补充默认忽略规则，用于减少后续误提交概率。

## 5. 提交前筛选建议
1. 先以本清单第 2 节作为最小保留集；
2. 若需要保留辅助对比证据，再从第 3 节按需增补，而不是整包提交整个 `artifacts/`。
3. `git add` 前先检查根目录是否仍存在新的 `tmp_* / .tmp* / temp_*` 输出；
4. 测试报告若新增引用了其他产物，应先同步更新本清单，再决定是否纳入提交面。

## 6. 当前工作树的提交面建议
以下建议用于后续 `git add` / commit 前的人工筛选，避免把“真实交付内容”和“分析过程残留”混在一起。

### 6.1 建议纳入本轮正式提交的目录
- `api/`
- `server/`
- `tests/`
- `scripts/`
- `webapp/`
- `run_api.py`
- `.gitignore`
- `评审建议.txt`
- `docs/20260722-local-multi-kb-assistant/` 下与本需求直接相关的方案、测试方案、测试报告、评测规范与本清单文档

说明：这些目录/文件共同构成“导入链路修复 + 问答评测体系 + 报告闭环”的主体变更，缺少其中任何一块都会削弱当前阶段的可追溯性。

### 6.2 建议按最小集合选择性纳入的 artifacts
- 第 2 节列出的正式追溯产物，建议作为最小提交集合；
- 第 3 节列出的历史/中间态 artifacts，仅在需要保留调试过程证据时再按需挑选；
- 不建议直接整包 `git add docs/20260722-local-multi-kb-assistant/artifacts/`。

### 6.3 建议暂不纳入本轮提交的内容
- 仓库根目录下的 `tmp_*`、`.tmp*`、`temp_*` 调试输出；
- `docs/20260722-local-multi-kb-assistant/artifacts/temp/` 与 `artifacts/tmp*/`；
- `docs/20260714-kb-directory-storage/20260714-kb-directory-storage-test-report.md` 的当前变更，除非明确要回补旧需求测试报告；当前它不属于本需求的最小交付范围。

说明：最后这一项并不是说旧文档一定错误，而是它既不在当前需求目录下，也不是本轮“完整链路导入 + 问答测试报告”结论成立所必需的证据，提交时应单独判断是否需要保留。
