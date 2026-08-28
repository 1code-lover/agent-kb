# 20260821 Project Audit Remediation Test Report

## 1. 报告目标

本报告对应 2026-08-21 ~ 2026-08-25 这轮“继续检查并迭代整个项目”的复查结果。重点不是宣称项目已经全部完成，而是：

1. 用真实命令说明当前主能力是否仍然成立；
2. 明确当前最新、可信的评测结果；
3. 说明为什么现在可以把项目讲成“能力闭环已成型”，但仍不能讲成“工程已经完全收尾”。

## 2. 本轮证据来源

### 2.1 最新评测产物

- `temp/eval-layered-suite-20260821-targeted-fact-fix-r5/local_multi_kb_eval_v8_layered_suite-suite-report.json`
- `temp/eval-layered-suite-20260821-targeted-fact-fix-r5/local_multi_kb_eval_v8_layered_suite-suite-report.md`
- `temp/eval-layered-suite-20260821-targeted-fact-fix-r5/hard/local_multi_kb_eval_v8_layered_hard-semireal-report.json`

### 2.2 本轮实际执行的验证

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| targeted fact / preview / metrics 回归 | `python -m pytest tests/api/test_chat_qa_metrics.py tests/api/test_chat_service.py tests/api/test_chat_evidence_contract.py tests/api/test_kb_preview_route.py -q` | `114 passed` |
| 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约 | `python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_docs_entry_contracts.py tests/test_requirements_profiles.py tests/scripts/test_cleanup_local_artifacts.py tests/scripts/test_repo_hygiene_contracts.py -q` | `83 passed` |
| runtime 依赖 dry-run | `python -m pip install --dry-run --ignore-installed --report temp/runtime-report-after-langchain-pin.json -r requirements-runtime.txt` | 报告中不再出现 `llama-parse / llama-cloud-services / llama-cloud / llama-index` |
| Docker runtime partial smoke | `docker build --progress plain -t agent-kb-runtime-smoke --build-arg INSTALL_PROFILE=runtime .` | 已进入正常依赖下载阶段，未再观察到 `llama-parse` 依赖链或 `langchain-core` 多版本回溯；本轮为避免长时间下载重依赖，手动中断，暂不记为完整 build 通过 |
| Docker smoke helper 契约 | `python -m pytest tests/scripts/test_docker_smoke.py -q` | `20 passed` |
| cleanup 单测 | `python -m pytest tests/scripts/test_cleanup_local_artifacts.py -q` | `13 passed` |
| layered eval fixture / builder 契约（v7 refresh） | `python -m pytest tests/test_rag_quality_eval_dataset_v7.py tests/test_rag_quality_eval_builders.py tests/test_rag_quality_fixtures.py -q` | `16 passed` |
| layered eval fixture 契约（v8） | `python -m pytest tests/test_rag_quality_eval_dataset_v8.py -q` | `12 passed` |
| Desktop 关键单测 | `node --test desktop/src/csp.test.js desktop/src/python-process.test.js desktop/src/renderer-entry.test.js desktop/scripts/verify-release-config.test.js` | `19 passed` |
| Web domain / API 关键单测 | `node --test webapp/src/domain/agentExperience.test.js webapp/src/domain/chatWorkflow.test.js webapp/src/api/client.test.js` | `16 passed` |
| API host / runtime path / startup contract 增量回归 | `python -m pytest tests/test_run_api.py tests/test_runtime_paths.py tests/scripts/test_dev_startup_contracts.py -q` | `17 passed` |
| Desktop runtime / renderer alias 增量回归 | `node --test desktop/src/runtime-config.test.js desktop/src/python-process.test.js desktop/src/renderer-entry.test.js` | `15 passed` |
| `start_dev.ps1` 真实执行型 smoke | `python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_start_dev_smoke.py -q` | `11 passed` |
| Desktop bridge contract 收口回归 | `node --test desktop/src/desktop-bridge-contract.test.js desktop/src/runtime-config.test.js desktop/src/python-process.test.js desktop/src/renderer-entry.test.js` | `18 passed` |
| Desktop 全量 Node 单测 | `npm --prefix desktop test` | `136 passed` |
| startup + desktop 双 smoke | `python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_start_dev_smoke.py tests/scripts/test_dev_all_smoke.py -q` | `20 passed` |
| startup / docker helper / repo hygiene 回归 bundle | `python -m pytest tests/scripts/test_docker_smoke.py tests/scripts/test_repo_hygiene_contracts.py tests/scripts/test_dev_startup_contracts.py tests/scripts/test_webapp_contracts.py tests/scripts/test_start_dev_smoke.py tests/scripts/test_dev_all_smoke.py tests/scripts/test_docs_entry_contracts.py tests/test_legacy_streamlit_entry.py tests/test_run_api.py tests/test_requirements_profiles.py -q` | `108 passed` |
| QueryRequest route / scope 闭环 | `python -m pytest tests/api/test_chat_routes.py tests/api/test_chat_scope_contract.py -q` | `19 passed, 2 warnings` |
| QueryRequest semireal smoke 非默认参数 | `python -m pytest tests/api/test_chat_single_kb_qa_smoke.py -q` | `11 passed, 2 warnings` |
| OpenAPI answer / search 参数边界回归 | `python -m pytest tests/api/test_open_api.py tests/api/test_open_api_service.py tests/api/test_open_api_integration.py -q` | `12 passed, 2 warnings` |
| runtime effective config + chat_service 模块化复核 | `python -m pytest tests/api/test_runtime_model_loading.py tests/api/test_chat_hook_builders.py tests/api/test_chat_source_answers.py tests/api/test_chat_answer_repair.py tests/api/test_chat_composite_answers.py tests/api/test_chat_targeted_fact.py -q` | `62 passed, 2 warnings` |
| Web bridge / chat workflow 增量回归 | `node --test webapp/src/api/client.test.js webapp/src/domain/chatWorkflow.test.js webapp/src/domain/agentExperience.test.js webapp/src/domain/desktopBridge.test.js` | `19 passed` |
| Web 全量 Node 单测 | `npm --prefix webapp test` | `139 passed` |
| Web AgentPage 静态契约 | `python -m pytest tests/scripts/test_webapp_contracts.py -q` | `4 passed` |
| Web 生产构建 | `npm --prefix webapp run build` | `built in 6.51s` |
| chat 主链路局部回归 | `python -m pytest tests/api/test_chat_service.py tests/api/test_kb_preview_route.py tests/api/test_chat_scope_contract.py tests/api/test_chat_evidence_contract.py -q` | `100 passed, 2 warnings` |
| 全量非慢测回归 | `python -m pytest tests/ -q -m "not slow"` | `1299 passed, 4 deselected` |
| Prompt bundle 1（composite answers / postprocessors / chat_service） | `python -m pytest tests/api/test_chat_composite_answers.py tests/api/test_chat_postprocessors.py tests/api/test_chat_service.py -q` | `98 passed` |
| Prompt bundle 2（question intents / targeted fact / source answers / answer repair） | `python -m pytest tests/api/test_chat_question_intents.py tests/api/test_chat_targeted_fact.py tests/api/test_chat_source_answers.py tests/api/test_chat_answer_repair.py -q` | `49 passed` |
| Prompt bundle 3（eval runner / layered dataset） | `python -m pytest tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py -q` | `41 passed` |
| 当前 layered suite | `python scripts/run_chat_eval.py --suite tests/fixtures/rag_quality/eval_layered_suite.json --output-dir temp/eval-layered-suite-20260821-targeted-fact-fix-r5` | `153 / 153` |
| 根目录治理第一批 | `python scripts/cleanup_local_artifacts.py --apply --recommended-action archive_or_delete` | 归档 `63` 个日志类对象，manifest：`temp/root-artifacts/20260821-235858/manifest.json` |
| 根目录治理第二批 | `python scripts/cleanup_local_artifacts.py --apply --category scratch_ocr_script` | 归档 `18` 个 OCR 草稿脚本，manifest：`temp/root-artifacts/20260822-000325/manifest.json` |
| 根目录治理第三批 | `python scripts/cleanup_local_artifacts.py --apply --category temp_probe` | 归档 `19` 个临时探针 / 一次性产物，manifest：`temp/root-artifacts/20260822-000326/manifest.json` |
| 根目录治理现状复核 | `python scripts/cleanup_local_artifacts.py --dry-run` + `python scripts/cleanup_local_artifacts.py --dry-run --include-directories` | file-mode `managed_count = 0`；directory-mode `managed_count = 0` |

### 2.2.1 Desktop build/package/release 四层边界补充

1. `scripts/build-desktop.ps1/.sh`：本地 helper，只负责准备 `webapp/dist` 与 Electron bundle。
2. `npm run build:mac` + `npm run verify:package`：ad-hoc package verification，只验证 packaged runtime contents。
3. `npm run release:preflight`：strict Apple preflight，只验证凭证、Developer ID、`notarytool` 等前置条件。
4. `npm run release:mac` + `npm run verify:mac-release`：formal signed/notarized distribution lane，才是当前 mac release source of truth。

> 这轮顺手修正了另一个真实漂移：此前 `npm --prefix desktop test` 只跑到 `desktop/package.json` 里手写列出的部分测试，导致 `verify-package` / `release-preflight` / `verify-mac-release` 等脚本单测没有进入“Desktop 全量 Node 单测”；当前已把 `test` 脚本收口到全部 `desktop/src/*.test.js` + `desktop/scripts/*.test.js`，所以最新结果更新为 `136 passed`。

### 2.3 本轮新增真实整改

1. `tests/api/test_chat_routes.py`、`tests/api/test_chat_scope_contract.py` 与 `tests/api/test_chat_single_kb_qa_smoke.py` 现在已经把 `top_k / response_mode / use_reranker / top_n / reranker_model` 从 HTTP payload 一路补到 semireal smoke 主链路：不仅 route 会断言参数已进入 `runtime_state.build_query_engine(...)`，单库 smoke 也会在真实 `/api/chat/query` 主链路下验证非默认参数不会破坏 scope / evidence 基线；`webapp/src/api/chat.test.js` 也已补上前端 API 透传断言，因此 `QueryRequest` 已从 route + frontend API 推进到 semireal 证据闭环。
2. `/api/open/v1` 只读协议已经从“边界待定”推进到“按场景分层承诺”：`/search` 继续只支持 `top_k`，`/answer` 额外支持 `response_mode / use_reranker / top_n / reranker_model`；对应 `tests/api/test_open_api.py`、`tests/api/test_open_api_service.py` 与 `tests/api/test_open_api_integration.py` 已回归 `12 passed, 2 warnings`。
3. `webapp/src/pages/AgentPage.jsx` 已把问答 `query / history / preview / model refresh` 工作流提取到新的 `webapp/src/pages/useAgentChatWorkspace.js`，页面主体职责收口到 route intent、KB 选择和 agent/runtime 切换；在此基础上，这轮又把 `QaWorkbench` 继续拆成 `QaWorkbench.jsx` + `QaConversation.jsx` + `SourceList.jsx` + `KnowledgeScopeSelector.jsx` 四层结构，`AgentPage.jsx` 当前约 `792` 行，`QaWorkbench.jsx` 约 `281` 行；`useAgentChatWorkspace.js` 已收口到 `251` 行。
4. `tests/scripts/test_webapp_contracts.py` 已从 2 条补到 4 条静态契约：除 `chatNotice` 透传与 evidence preview scope 外，还新增了“KB 选择器 + 发送禁用保护”与“notice / error 独立横幅”保护，避免前端拆分后把 UI 组合关系回退坏掉。
5. 以上前端静态契约与 OpenAPI 边界补强已通过 `python -m pytest tests/scripts/test_webapp_contracts.py -q`（`4 passed`）与 `python -m pytest tests/api/test_open_api.py tests/api/test_open_api_service.py tests/api/test_open_api_integration.py -q`（`12 passed, 2 warnings`）回归。
6. 2026-08-25 新增的 runtime 复核已经把 `QueryRequest` 生效证据从 route / smoke 推进到 `create_query_engine(...)` 调用实参：`tests/api/test_runtime_model_loading.py` 现在明确验证默认配置透传与请求级覆盖透传两种路径。
7. 同一轮 `tests/api/test_chat_hook_builders.py` + source answers / answer repair / composite / targeted-fact bundle（合计 `62 passed, 2 warnings`）也说明：当前更值得继续投入的是复杂度治理，而不是重复补 P1-4 / P1-5 的同质边界测试。

- `webapp/src/api/client.js` 与 `webapp/src/pages/AgentPage.jsx` 把 `desktopBridge` 的相对导入改成显式 `.js` 后缀，修复 Node ESM 直跑 `client.test.js` 时的模块解析失败。
- `desktop/src/renderer-entry.js` 补上 `FOXGLOVE_WEB_PORT` 兼容读取，并通过 `desktop/src/renderer-entry.test.js` 增量用例锁住这条契约。
- `start_dev.ps1` 现在按端口分桶生成 backend/frontend PID 与日志文件，自定义端口不再覆盖默认 `backend.pid` / `frontend.pid` 和默认 log；`scripts/dev-all.ps1` 也同步补了 desktop 侧的双端口分桶命名。
- `tests/scripts/test_start_dev_smoke.py` 新增 Windows 真实执行型 smoke，验证 `start_dev.ps1` 能在自定义端口下真实启动、通过 health check、产出端口隔离 PID/log，并在 `-Stop` 后清理端口与 PID 文件。
- `tests/scripts/test_start_dev_smoke.py` 与 `tests/scripts/test_dev_all_smoke.py` 现已从 `bind(127.0.0.1:0)` 的瞬时空闲端口策略切换到稳定 loopback range 扫描：backend `20000-29999`、frontend `30000-39999`；这轮复核已把 Windows 下偶发 `WinError 10061` 的端口复用竞争收口掉。
- backend / frontend / desktop PID 文件写入统一改成 `-Encoding ascii`，修复 UTF-8 BOM 导致 smoke 读取 PID 时出现 `\ufeff1732` 这类解析失败的问题。
- `desktop/src/desktop-bridge-contract.js` 新增 preload / main 共用的契约 helper，把桌面桥接暴露名和 pick-files IPC 通道从分散硬编码收口到一处，并通过 `desktop/src/desktop-bridge-contract.test.js` 锁住兼容别名行为。
- `desktop/src/runtime-paths.js` 现在支持 `KB_RUNTIME_ROOT / NORTHAGENT_RUNTIME_ROOT / THINKRAG_RUNTIME_ROOT / FOXGLOVE_RUNTIME_ROOT` 覆盖 runtime root，`desktop/src/runtime-paths.test.js` 已验证 desktop 运行态目录不再只能写死到仓库根目录。
- `desktop/src/desktop-launch-config.js` 与 `desktop/src/main.js` 新增 headless 启动开关和 `renderer_loaded / renderer_load_failed` 运行日志事件，为 desktop smoke 提供稳定观测点。
- `tests/scripts/test_dev_all_smoke.py` 新增 Windows 真实执行型 desktop smoke，已验证 `scripts/dev-all.ps1` 能在自定义 backend/frontend 端口下拉起 headless Electron、写入隔离 runtime log，并在 `-Stop` 后清理 desktop PID 与 API/web 端口。
- `scripts/docker_smoke.py` 默认不再先抢宿主机瞬时空闲端口，而是改成让 Docker 用 `-p 127.0.0.1::{container_port}` 自动分配 loopback host port，再通过 `docker port` 反查映射；`tests/scripts/test_docker_smoke.py` 也已补到 `6` 条契约，避免 Docker smoke helper 自身引入端口竞争型假红。
- 这意味着当前 KB 主名优先、legacy alias 兼容的收口，不再只停留在 `runtime-config.js` / `python-process.js`，renderer、preload、main 与 web bridge 都开始被测试覆盖到；同时启动链路也从“字符串契约”推进到了 `start_dev.ps1` + `scripts/dev-all.ps1` 的真实执行型 smoke。

## 3. 当前结果总览

### 3.1 Layered suite

| 层级 | 结果 | 通过率 |
| --- | --- | --- |
| Smoke | `24 / 24` | `1.0` |
| Main | `90 / 90` | `1.0` |
| Hard | `36 / 36` | `1.0` |
| Total | `153 / 153` | `1.0` |

`suite_passed = true`。

### 3.1.1 评测指标样本覆盖（新增检查）

为避免“指标全是 1.0，但每个指标实际只测了极少题”的误解，本轮把 `judge_focus` 的样本覆盖也显式纳入 fixture schema gate：`minimum_cases_per_judge_dimension`。

| 数据集 | factual_accuracy | completeness | citation_accuracy | groundedness | refusal_correctness | gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `eval_v7` | 21 | 21 | 21 | 24 | 3 | `>= 3` |
| `eval_v8_main` | 66 | 66 | 66 | 88 | 23 | `>= 20` |
| `eval_v8_hard` | 30 | 30 | 30 | 36 | 6 | `>= 6` |

### 3.1.2 follow-up 覆盖摘要（便于面试口径统一）

为避免面试时还要手工拼接 `history_grounded_case_count`、模态分布与 semireal refusal follow-up 证据，这里把当前 follow-up 覆盖单独汇总：

| 维度 | 当前结果 |
| --- | --- |
| main 集 answerable follow-up gate | `history_grounded_case_count = 6` |
| main 集 history-grounded 模态分布 | `markdown = 2`、`pdf = 2`、`image_ocr = 2` |
| main 集 contract 相关负向覆盖 | refusal `23`、negative contract `19` |
| semireal refusal follow-up 回归 | `126 passed, 2 warnings` |
| semireal refusal follow-up 模态 | Markdown / PDF / Image OCR |
| 当前解释 | 现在不是只有 hard refusal follow-up；正式 gate 已同时覆盖 answerable follow-up 与 refusal follow-up |

对应证据命令固定为：

- `python scripts/validate_rag_quality_fixtures.py --eval-cases tests/fixtures/rag_quality/eval_v8_main/cases.json --eval-schema tests/fixtures/rag_quality/eval_v8_main/schema.json --print-eval-summary`
- `python -m pytest tests/api/test_chat_service.py tests/api/test_chat_markdown_qa_semireal.py tests/api/test_chat_pdf_semireal.py tests/api/test_chat_image_ocr_semireal.py -q`

### 3.2 根目录治理

| 视角 | 结果 |
| --- | --- |
| 文件级三批 apply 合计 | 归档 `100` 个根目录文件对象 |
| file-mode dry-run | `managed_count = 0` |
| directory-mode dry-run | `managed_count = 0` |
| directory 分类 | `scratch_eval_dir = 12`、`scratch_debug_dir = 2` |

### 3.3 这说明了什么

1. 当前 semireal layered suite 的主能力路径已经全绿；
2. 上一轮卡住 hard 的 targeted fact / preview hygiene / forbidden term 误判，已经在本轮被修掉；
3. 根目录治理已经从“只有方案”推进到了“文件模式清干净 + 目录模式能力补上”；
4. Docker runtime baseline 的依赖根因也已经从“猜测为什么慢”推进到“拿 dry-run 和 partial smoke 证明顶层 `llama_index` metapackage 确实是一个关键诱因”；
5. 启动 / desktop / Docker smoke helper 这几条脚本级验证现在已经把端口竞争型假红进一步收口，剩余重心更集中在真实依赖体重与完整 build/run 证据，而不是 smoke 工具本身；
6. 现在项目的主要风险，不再是“这套能力还经常答不出来”，而是“工程治理和长期维护体验还没完全跟上”。

## 4. 当前仍需诚实保留的风险

### 4.1 评测全绿 ≠ 工程完成度也满分

尽管当前 layered suite 是 `153 / 153`，但以下问题依然成立：

- `app.py`、`frontend/`、`.streamlit/` 等 legacy 入口仍在仓库中存在；不过 `app.py` 现在已经是默认禁用、需 `KB_ALLOW_LEGACY_STREAMLIT=1` 显式 opt-in 的 compatibility shim，不再默认充当现行主入口；
- README 与主 runbook 已统一到当前入口，但 `docs/project.md` 这类长文档仍保留大量历史阶段纪要，后续还要继续做分层与收敛；
- `chat_service.py` 的回答修复依然明显依赖 `_maybe_*` 规则链。

### 4.2 refusal / negative contract 不应因此被视为“完全没问题”

当前 refusal / negative contract 覆盖相比之前已经明显增强：

- `eval_v7`：3 条 `no_evidence` refusal + 6 条 negative contract（`process_boundary = 3`、`scope_contract = 3`），并且 smoke 层 schema 现在也显式要求 `minimum_negative_contract_cases_per_modality = 2`
- `eval_v8_main`：23 条 refusal（`no_evidence = 14`、`hard_refusal = 6`、`scope_contract = 3`）+ 19 条 negative contract（`process_boundary = 12`、`scope_contract = 7`）
- `eval_v8_hard`：6 条 `evidence_insufficient` refusal + 6 条 negative contract（`scope_isolation_trap = 6`）

这意味着现在不只是“有几条拒答题”，而是 smoke / main / hard 三层都已经把 refusal 与范围边界约束分开做 gate；同时 builder 与 checked-in fixture 的 schema 也重新对齐，减少了后续重建数据集时把 negative contract gate 覆盖回旧版本的风险。更进一步，`chat_eval_runner` 现在已把 contract gate 直接联动到最终 `run_passed`：逐题 case 即便全部通过，只要 required refusal marker 或 negative contract coverage 仍有缺口，整次运行结果也会失败。

### 4.3 根目录治理能力已补齐，当前 file-mode / directory-mode 均已回到 `managed_count = 0`，重点转为后续重点转为防回脏、定期巡检与受控 apply 预案固化

当前 `scripts/cleanup_local_artifacts.py` 不再只是列文件，而是支持：

- `summary.by_category`
- `summary.by_recommended_action`
- `--category` / `--recommended-action` / `--include-directories`

本轮人工评审后的处理结论：

1. `_test_ocr*.py` 18 个脚本均为历史 scratch/probe，已被 semireal 测试与 `scripts/diag_*` 正式脚本覆盖，因此统一归档；
2. `tmp_diag_*.json`、`tmp_eval_v4_probe.json`、`tmp_run_api_18081.py`、`tmp_recovered_test_chat_eval_runner.py`、`tmp_manual_diag.pdf`、`tmp_ocr_bench.png`、`temp_test_view.txt` 等一次性诊断输出也已归档；
3. 当前 file-mode dry-run 已经是 `managed_count = 0`，但 directory-mode 已清零（`managed_count = 0`）待进一步评审。

### 4.4 Docker runtime baseline 根因已定位，但完整 smoke 仍待补

当前 Docker / requirements 的分层相比之前已经清楚很多，新的真实结论应当这样讲：

- Docker 默认已经统一到 `INSTALL_PROFILE=runtime` + API 模式，`eval` / `prod` 退到显式模式；
- `requirements-minimal.txt` 现在只是本地兼容 alias，不再作为 Docker install profile 的主叙事；
- runtime build 变慢的关键根因之一，是 `requirements-runtime.txt` 曾引入顶层 `llama_index` metapackage，额外拉起 `llama-parse / llama-cloud-services / llama-cloud`；
- 当前 runtime baseline 已改成 `llama-index-core==0.11.19` + 显式 integrations，并把 `langchain-core==0.3.63` / `langchain-text-splitters==0.3.8` 显式 pin 住；
- 最新 dry-run 报告已确认不再出现 `llama-parse / llama-cloud-services / llama-cloud / llama-index`；
- 但 `llama-index-embeddings-huggingface / sentence-transformers / torch` 仍让默认 runtime baseline 偏重，完整 `docker build + docker run` smoke 还没补完；
- 不过 `scripts/docker_smoke.py` 这条 smoke helper 本身已经切到 Docker 自分配 host port + `docker port` 反查映射，后续需要继续攻克的重点，已经更偏向依赖体重与镜像构建时长，而不是 helper 自身的端口竞争。

## 5. 当前可以怎么讲

### 5.1 对外简版

> 项目当前已经把多知识库 scope、evidence / preview、layered eval 这些核心能力做成闭环，当前 semireal layered suite 是 `153 / 153`；同时根目录文件级临时产物已经完成多轮治理并清到 file-mode `0`。但我会明确补一句：directory-mode 已清零（`managed_count = 0`），Docker runtime baseline 虽然已经从顶层 `llama_index` metapackage 回退到更干净的 runtime 依赖链，但完整 smoke 证据还要继续补，这两件事说明工程尾巴还在。

### 5.2 如果被问“为什么现在是 1.0？”

推荐回答：

> 这里的 1.0 指的是当前这套 semireal layered suite 全绿，不代表生产环境对所有真实问题都已经完美。它说明主能力和当前评测闭环已经打通；而且现在单题 case 全过也不再自动等于最终通过，因为 refusal / negative contract 的 contract gate 会直接阻断 `run_passed`。但工程完成度不是只看分数，还要看启动链路、legacy 入口、文档闭环、Docker runtime baseline、仓库治理和代码可维护性，这些部分我会明确说还在继续收口。

## 6. 下一步建议

1. 补 Docker runtime / eval 的真实 build + run smoke
2. 把目录治理从‘清 backlog’切到‘防回脏 + 定期巡检 + 受控 apply 预案’；当前 file-mode / directory-mode 均已回到 `managed_count = 0`
3. 统一主入口与 legacy 入口说明
4. 持续降低 `chat_service.py` 的规则后处理权重
5. 对 refusal / OCR / preview hygiene 补更多负向评测

## 7. 结论

本轮最重要的结论不是“又多过了几题”，而是：

> **项目现在已经具备‘能力可讲、评测可讲、问题也能讲清楚’的条件。接下来应该把重点从‘单次提分’切到‘工程收口与长期可维护性’，并把 cleanup 侧已经做到 file-mode / directory-mode 均已回到 `managed_count = 0`、runtime baseline 根因已定位但完整 Docker smoke 仍待补齐这些事实讲清楚。**
## 补充更新（2026-08-22 directory backlog sizing + docker eval smoke）

### 1. 新增测试与命令

#### 1.1 cleanup backlog sizing
```powershell
python -m pytest tests/scripts/test_cleanup_local_artifacts.py -q
python scripts/cleanup_local_artifacts.py --dry-run --include-directories
```
结果：
- `16 passed`
- dry-run 输出 `managed_count = 0`
- `summary.total_size_bytes = 1159774`
- `summary.size_bytes_by_category = { scratch_debug_dir: 26998, scratch_eval_dir: 1132776 }`
- `summary.largest_records` 已能直接给出 top 5 最大目录

#### 1.2 repo hygiene / docs entry contracts
```powershell
python -m pytest tests/scripts/test_repo_hygiene_contracts.py tests/scripts/test_docs_entry_contracts.py -q
```
结果：`11 passed`

#### 1.3 docker smoke helper regression
```powershell
python -m pytest tests/scripts/test_docker_smoke.py -q
```
结果：`9 passed`

### 2. cleanup backlog 新增解读

这段 backlog sizing 记录对应的是历史快照；截至最新 dry-run，file-mode / directory-mode 均已回到 `managed_count = 0`。后续保留 sizing / top offenders 视角，是为了下次回脏时仍能快速确定受控 apply 顺序。

- 最大类别现在是 `scratch_eval_dir`，共 `12` 个目录、约 `1132776` bytes；
- `scratch_debug_dir` 当前只有 `2` 个，约 `26998` bytes；
- top 5 offender 已经明确：
  1. `tmp_eval_out` → `112417` bytes
  2. `tmp_eval_out5` → `107567` bytes
  3. `tmp_eval_debug_codex3` → `106632` bytes
  4. `tmp_eval_debug_codex5` → `106632` bytes
  5. `tmp_eval_out8` → `100760` bytes

这也说明 cleanup 不该只停留在‘把 backlog 清零’：既然当前 file-mode / directory-mode 均已回到 `managed_count = 0`，下一轮更应该把 sizing、top offenders 与受控 apply 预案沉淀为长期巡检机制。

### 3. Docker eval smoke 当前真实状态

这轮 helper 逻辑已经补正：

- `APP_RUNTIME_MODE=eval` 时，`scripts/docker_smoke.py` 会等待容器退出码；
- 不再错误探测 `/api/health`；
- 相关单测已从之前的 `6 passed` 增加到 `9 passed`。

但是 live smoke 也暴露了更关键的新事实：当前 Docker build 的主要瓶颈，已经不是 helper 自身，而是默认 embedding 依赖链太重。构建日志中已经观察到以下超大下载：

- `torch-2.13.0` → `526.6 MB`
- `nvidia_cudnn_cu13` → `366.2 MB`
- `nvidia_cusparselt_cu13` → `170.1 MB`
- `nvidia_nccl_cu13` → `206.0 MB`
- `triton-3.7.1` → `197.7 MB`
- `nvidia_cublas` → `423.1 MB`
- `nvidia_cufft` → `214.1 MB`

因此本轮对 Docker 的测试结论应更新为：

> helper 契约问题已经修正，但 requirements runtime/eval profile 仍被 `llama-index-embeddings-huggingface -> sentence-transformers -> torch` 这条链拖得过重；下一步瓶颈已经明确落在依赖口径，而不是端口探测逻辑。

### 4. 对项目判断的影响

1. 根目录治理能力已不仅是“能分类”，还开始具备 backlog 优先级排序能力；
2. Docker baseline 的问题也从“metapackage 误拉依赖”进一步推进到了“torch GPU transitive chain 过重”；
3. 所以下一轮 P0 更值得继续做：
   - `scratch_eval_dir` 第一批受控归档计划；
   - Docker runtime/eval 的 lighter install profile 设计或 CPU-only 依赖评估；
   - 完整 smoke 的最终收口。

## 补充更新（2026-08-22 docker smoke lighter profile + startup retry fix）

### 1. 新增测试与命令

#### 1.1 Docker smoke / profile contract
```powershell
python -m pytest tests/scripts/test_docker_smoke.py -q
python -m pytest tests/test_requirements_profiles.py -q
```
结果：
- `16 passed`
- `9 passed`

#### 1.2 smoke profile dry-run
```powershell
python -m pip install --dry-run --ignore-installed --report temp/smoke-profile-report.json -r requirements-smoke.txt
python -c "import json, pathlib; data=json.loads(pathlib.Path('temp/smoke-profile-report.json').read_text(encoding='utf-8')); names=sorted({item['metadata']['name'] for item in data.get('install', []) if item.get('metadata')}); flagged=[name for name in names if any(token in name.lower() for token in ('torch','sentence-transformers','nvidia','triton'))]; print('flagged=', flagged); print('install_count=', len(names))"
```
结果：
- `flagged=[]`
- `install_count=84`

#### 1.3 Docker smoke 实跑
```powershell
python scripts/docker_smoke.py --tag agent-kb-smoke:local --install-profile smoke --app-runtime-mode api
```
结果：
- Docker build 成功
- Docker run 成功
- `/api/health` 返回 `{"code":0,"message":"ok"...}`

### 2. 这轮新增的真实修复

#### 2.1 lighter Docker smoke profile
- 新增 `requirements-smoke.txt`；
- Dockerfile 现在支持 `INSTALL_PROFILE=smoke`；
- smoke profile 保留 FastAPI / healthcheck / import smoke 所需依赖，但刻意去掉 `llama-index-embeddings-huggingface`。

#### 2.2 Windows checkout -> Linux entrypoint 兼容修复
第一次实跑时，容器报错：
- `exec /app/scripts/docker-entrypoint.sh: no such file or directory`

根因不是文件真的不存在，而是 Windows checkout 的 CRLF 让 Linux shebang/entrypoint 解析失败。当前 Dockerfile 已改为在镜像内执行：
- `sed -i 's/\r$//' /app/scripts/docker-entrypoint.sh`

#### 2.3 health startup race 重试修复
第二次实跑时，容器已经起来，但 helper 首次 probe 遇到：
- `http.client.RemoteDisconnected: Remote end closed connection without response`

这说明容器启动初期会存在短暂 HTTP 断连窗口。`wait_for_http_json(...)` 现在会把 `RemoteDisconnected` 视为可重试瞬时错误，因此不会再因为第一次断连就提前判失败。

### 3. 更新后的测试结论

1. 之前“建议做 lighter profile”的路线，现在已经变成真实、可重复执行的 smoke 口径。
2. smoke profile dry-run 已经证明：至少在 dependency resolution 层面，不再引入 `torch / sentence-transformers / nvidia / triton`。
3. 完整的 `docker_smoke.py --install-profile smoke` 也已经成功跑通，因此 Docker health smoke 可以从“理论建议”升级为“已有实跑证据”。
4. 但这轮不能夸大成“runtime / eval 全部解决”：`requirements-runtime.txt` 的正式契约没改，真正的推理 / 检索链路依旧比 smoke profile 重。

### 4. 对项目判断的影响

- Docker 项从“helper 契约已改正、但真实 build 仍被重依赖拖住”进一步推进为：
  - **health smoke 已有轻量 profile + build/run 实证**；
  - **runtime/eval baseline 仍需单独优化**。
- 这轮属于真实工程收口，而不是只补面试话术：因为它同时解决了 requirements profile、Windows/Linux line ending 兼容和 startup retry 三个运行层问题。

## 补充更新（2026-08-22 API entry env alias symmetry）

### 1. 新增测试与命令

```powershell
python -m pytest tests/test_run_api.py tests/scripts/test_dev_startup_contracts.py -q
```

结果：
- `18 passed`

### 2. 这轮新增的真实修复

#### 2.1 run_api host / port 环境变量契约对齐
- 新增 `_API_PORT_ENV_KEYS = (KB_API_PORT, NORTHAGENT_API_PORT, THINKRAG_API_PORT, FOXGLOVE_API_PORT)`；
- `run_api.py` 现在和 host 一样，会按 `KB_* -> legacy aliases` 的顺序读取端口；
- `_get_port()` 的异常信息现在会直接指出实际出错的环境变量名，而不是统一写成 `KB_API_PORT`。

#### 2.2 API-only 入口与桌面运行时配置对齐
- `desktop/src/runtime-config.js` 本来就会兼容四套端口别名；
- 这轮之后，`run_api.py` 也采用相同的优先级策略；
- 因此桌面脚本、手动 API 启动和联调环境变量的契约更一致，减少“脚本明明注入了端口，但 API-only 入口没吃到”的隐性差异。

### 3. 更新后的测试结论

1. 这轮不是新增大功能，而是修掉了一个真实的启动契约缝隙：host 已兼容别名，port 现在也同步兼容。
2. 对外更准确的话术应更新为：**`KB_API_PORT` 仍是推荐/规范口径，但 API-only 入口在兼容阶段也会继续读取 `NORTHAGENT_API_PORT` / `THINKRAG_API_PORT` / `FOXGLOVE_API_PORT`。**
3. 这个改动能降低桌面联调、旧脚本迁移和手动排障时的配置踩坑概率，但它仍是启动链路收口的一小步，不等于整个命名债务已经清完。

## Desktop build/package/release four-layer boundary


