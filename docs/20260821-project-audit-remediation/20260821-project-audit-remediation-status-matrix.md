# 20260821 Project Audit Remediation Status Matrix

## 1. 文档目标

这份文档把当前线程里反复提到的 12 个核心问题重新整理成一份“**当前状态 / 证据 / 真实结论 / 下一步**”矩阵，方便：

1. 继续按 P0 / P1 / P2 做真正整改；
2. 面试或汇报时区分“已经修到什么程度”和“还没完全收口什么”；
3. 避免继续混用旧结论、旧分数和旧启动叙事。

## 2. 当前统一口径

### 2.1 最新可信评测基线

以 `temp/eval-layered-suite-20260821-targeted-fact-fix-r5/local_multi_kb_eval_v8_layered_suite-suite-report.json` 为准：

- Layered suite：`153 / 153`
- Smoke：`24 / 24`
- Main：`90 / 90`
- Hard：`36 / 36`
- `suite_passed = true`

### 2.2 本轮已核对的快速验证

- `python -m pytest tests/api/test_chat_qa_metrics.py tests/api/test_chat_service.py tests/api/test_chat_evidence_contract.py tests/api/test_kb_preview_route.py -q` → `114 passed`
- `python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_docs_entry_contracts.py tests/test_requirements_profiles.py tests/scripts/test_cleanup_local_artifacts.py tests/scripts/test_repo_hygiene_contracts.py -q` → `83 passed`
- `python -m pip install --dry-run --ignore-installed --report temp/runtime-report-after-langchain-pin.json -r requirements-runtime.txt` → 报告中不再出现 `llama-parse / llama-cloud-services / llama-cloud / llama-index`
- `docker build --progress plain -t agent-kb-runtime-smoke --build-arg INSTALL_PROFILE=runtime .` → 已进入正常依赖下载阶段，未再观察到 `llama-parse` 依赖链或 `langchain-core` 多版本回溯；本轮为避免长时间下载重依赖，手动中断，暂不记为完整 build 通过
- `python -m pytest tests/scripts/test_docker_smoke.py -q` → `20 passed`
- `python -m pytest tests/test_rag_quality_eval_dataset_v7.py tests/test_rag_quality_eval_builders.py tests/test_rag_quality_fixtures.py -q` → `16 passed`
- `python -m pytest tests/test_rag_quality_eval_dataset_v8.py -q` → `12 passed`
- `python -m pytest tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py -q` → `41 passed`
- `chat_eval_runner` 当前已把 `contract_gates` 直接纳入最终 `run_passed`；单题全过但 required refusal marker / negative contract coverage 不足时，整次运行仍会失败
- `python -m pytest tests/scripts/test_cleanup_local_artifacts.py -q` → `13 passed`
- `node --test desktop/src/csp.test.js desktop/src/python-process.test.js desktop/src/renderer-entry.test.js desktop/scripts/verify-release-config.test.js` → `19 passed`
- `node --test webapp/src/domain/agentExperience.test.js webapp/src/domain/chatWorkflow.test.js webapp/src/api/client.test.js` → `16 passed`
- `python -m pytest tests/test_run_api.py tests/test_runtime_paths.py tests/scripts/test_dev_startup_contracts.py -q` → `17 passed`
- `node --test desktop/src/runtime-config.test.js desktop/src/python-process.test.js desktop/src/renderer-entry.test.js` → `15 passed`
- `node --test webapp/src/api/client.test.js webapp/src/domain/chatWorkflow.test.js webapp/src/domain/agentExperience.test.js webapp/src/domain/desktopBridge.test.js` → `19 passed`
- `python -m pytest tests/api/test_chat_routes.py tests/api/test_chat_scope_contract.py -q` → `19 passed, 2 warnings`
- `python -m pytest tests/api/test_chat_single_kb_qa_smoke.py -q` → `11 passed, 2 warnings`
- `python -m pytest tests/api/test_open_api.py tests/api/test_open_api_service.py tests/api/test_open_api_integration.py -q` → `12 passed, 2 warnings`
- `npm --prefix webapp test` → `139 passed`
- `python -m pytest tests/scripts/test_webapp_contracts.py -q` → `4 passed`
- `npm --prefix webapp run build` → `built in 6.51s`
- `python -m pytest tests/api/test_chat_service.py tests/api/test_kb_preview_route.py tests/api/test_chat_scope_contract.py tests/api/test_chat_evidence_contract.py -q` → `100 passed, 2 warnings`
- `python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_start_dev_smoke.py -q` → `11 passed`
- `node --test desktop/src/desktop-bridge-contract.test.js desktop/src/runtime-config.test.js desktop/src/python-process.test.js desktop/src/renderer-entry.test.js` → `18 passed`
- `npm --prefix desktop test` → `136 passed`（当前已覆盖全部 `desktop/src/*.test.js` + `desktop/scripts/*.test.js`，不再遗漏 package/release 相关脚本单测）
- `python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_start_dev_smoke.py tests/scripts/test_dev_all_smoke.py -q` → `20 passed`
- startup / docker helper / repo hygiene 回归 bundle：`python -m pytest tests/scripts/test_docker_smoke.py tests/scripts/test_repo_hygiene_contracts.py tests/scripts/test_dev_startup_contracts.py tests/scripts/test_webapp_contracts.py tests/scripts/test_start_dev_smoke.py tests/scripts/test_dev_all_smoke.py tests/scripts/test_docs_entry_contracts.py tests/test_legacy_streamlit_entry.py tests/test_run_api.py tests/test_requirements_profiles.py -q` → `108 passed`
- `python -m pytest tests/ -q -m "not slow"` → `1299 passed, 4 deselected`

### 2.2.1 本轮新增真实整改

- `tests/api/test_chat_routes.py`、`tests/api/test_chat_scope_contract.py` 与 `tests/api/test_chat_single_kb_qa_smoke.py` 现在已经把 `top_k / response_mode / use_reranker / top_n / reranker_model` 从 HTTP payload 一路补到 semireal smoke 主链路：route / scope 契约断言参数进入 `runtime_state.build_query_engine(...)`，单库 smoke 还会在真实 `/api/chat/query` 主链路下验证非默认参数不破坏 scope / evidence 基线；`webapp/src/api/chat.test.js` 也补上前端 API 透传断言，因此 `QueryRequest` 已不再只是 route + frontend API 证据。
- `/api/open/v1` 这轮继续把只读协议从“边界待定”推进到“按场景分层承诺”：`/search` 只接受 `top_k`，`/answer` 额外接受 `response_mode / use_reranker / top_n / reranker_model`；`tests/api/test_open_api.py`、`tests/api/test_open_api_service.py` 与 `tests/api/test_open_api_integration.py` 已回归 `12 passed, 2 warnings`。
- `webapp/src/pages/AgentPage.jsx` 继续把 `chatNotice` 显式透传给 `QaWorkbench`，修复 query 成功但 history 同步失败时，工作台层 notice 横幅可能因为漏传 prop 而失效的风险。
- 同一处证据预览链路已改成把 `item?.kb_id || selectedKbId` 收口为 `targetKbId` 并透传给 `previewItem(...)`，避免证据项自带 `kb_id` 时仍误回退到当前 UI 选中知识库。
- `webapp/src/pages/useAgentChatWorkspace.js` 已把问答 query / history / preview / model refresh 状态从 `AgentPageContent` 中抽离出来；在此基础上，这轮又把 `QaWorkbench` 继续拆成 `QaWorkbench.jsx` + `QaConversation.jsx` + `SourceList.jsx` + `KnowledgeScopeSelector.jsx` 四层结构，当前 `AgentPage.jsx` 约 `792` 行，`QaWorkbench.jsx` 约 `281` 行；问答 workflow 已抽到 `useAgentChatWorkspace.js`（`251` 行），但展示层和 runtime panel 仍有继续收口空间。
- `tests/scripts/test_webapp_contracts.py` 已从 2 条补到 4 条静态契约：在 `chatNotice` 透传和 evidence preview scope 之外，又补了“KB 选择器 + 发送禁用保护”与“notice / error 独立横幅”保护，确保前端拆分后 UI 组合关系不回退。

- `webapp/src/api/client.js` 与 `webapp/src/pages/AgentPage.jsx` 把 `desktopBridge` 的相对导入补成显式 `.js` 后缀，修复 Node ESM 直跑测试时的模块解析失败。
- `desktop/src/renderer-entry.js` 现在把 `FOXGLOVE_WEB_PORT` 纳入 `WEB_PORT_ENV_KEYS`，并补了兼容单测，避免脚本已经注入兼容端口变量但 renderer 解析链没有真正接住。
- `start_dev.ps1` 现在按 backend / frontend 端口分桶生成 PID 与日志文件：默认端口仍保留旧文件名，自定义端口改为 `backend-<port>.pid`、`frontend-<port>.pid` 与对应 `*_out-<port>.log` / `*_err-<port>.log`，避免多套 dev 进程相互覆盖运行态文件。
- `scripts/dev-all.ps1` 同步补了 desktop 侧的 backend/frontend 双端口分桶命名，desktop PID / log 不再和默认端口实例共用同一组文件。
- `tests/scripts/test_start_dev_smoke.py` 新增 Windows 真实执行型 smoke，已验证 `start_dev.ps1` 在自定义端口下可以真实拉起 backend/frontend、响应健康检查、创建端口隔离的 PID/log 文件，并在 `-Stop` 后释放端口和删除对应 PID 文件。
- backend / frontend / desktop PID 文件写入统一改为 `-Encoding ascii`，修复 UTF-8 BOM 导致 smoke 读取 PID 时出现 `\ufeff1732` 这类解析失败的问题。
- `desktop/src/desktop-bridge-contract.js` 新增 preload / main 共用的桥接契约 helper，集中维护桌面桥接暴露名与 pick-files IPC 通道；`desktop/src/desktop-bridge-contract.test.js` 已锁住 KB 主名优先 + legacy alias 兼容的集中化收口。
- `desktop/src/runtime-paths.js` 现在支持 `KB_RUNTIME_ROOT / NORTHAGENT_RUNTIME_ROOT / THINKRAG_RUNTIME_ROOT / FOXGLOVE_RUNTIME_ROOT` 覆盖 runtime root，桌面开发态不再只能把运行态日志和数据写死到仓库根目录；对应 `desktop/src/runtime-paths.test.js` 已补充 override 契约。
- `desktop/src/desktop-launch-config.js` 与 `desktop/src/main.js` 新增 headless 启动开关和 `renderer_loaded / renderer_load_failed` 运行日志事件，为 `scripts/dev-all.ps1` 的真实执行型 smoke 提供稳定探针。
- `tests/scripts/test_dev_all_smoke.py` 新增 Windows 真实执行型 desktop smoke，已验证 `scripts/dev-all.ps1` 可以在自定义 backend/frontend 端口下拉起 headless Electron、写入隔离 runtime log，并在 `-Stop` 后清理端口与 desktop PID 文件。

### 2.2.2 Desktop build/package/release 边界补充

- `scripts/build-desktop.ps1/.sh` 仍只是本地 build helper，不是 formal release。
- `npm run build:mac` + `npm run verify:package` 当前只代表 ad-hoc packaged runtime contents verification。
- `npm run release:preflight` 是 strict Apple prerequisite gate，验证的是“能不能开始正式发版”，不是“最终产物已经签名/公证完成”。
- `npm run release:mac` + `npm run verify:mac-release` 才是 signed/notarized distribution lane；只有这条链路可被讲成当前 mac release source of truth。

### 2.3 根目录临时产物治理现状

脚本 `python scripts/cleanup_local_artifacts.py` 现在支持：

- 显式 `--dry-run` / `--apply`
- `--category` / `--recommended-action`
- `--include-directories`

本轮已完成三批文件级实际 apply：

1. `python scripts/cleanup_local_artifacts.py --apply --recommended-action archive_or_delete`
   - 结果：归档 `63` 个日志类对象
   - manifest：`temp/root-artifacts/20260821-235858/manifest.json`
2. `python scripts/cleanup_local_artifacts.py --apply --category scratch_ocr_script`
   - 结果：归档 `18` 个 OCR 草稿脚本
   - manifest：`temp/root-artifacts/20260822-000325/manifest.json`
3. `python scripts/cleanup_local_artifacts.py --apply --category temp_probe`
   - 结果：归档 `19` 个临时探针 / 一次性产物
   - manifest：`temp/root-artifacts/20260822-000326/manifest.json`

合计已归档 `100` 个根目录文件对象。

当前再次 dry-run 后：

- file-mode：`python scripts/cleanup_local_artifacts.py --dry-run` → `managed_count = 0`
- directory-mode：`python scripts/cleanup_local_artifacts.py --dry-run --include-directories` → `managed_count = 0`
- `summary.by_category = { scratch_debug_dir: 2, scratch_eval_dir: 12 }`

人工评审结论：

- 文件级治理能力已经收敛，根目录散落日志 / OCR scratch 脚本 / temp probe 已基本清掉；
- 目录级治理能力也已经补上，当前 file-mode / directory-mode 均已回到 `managed_count = 0`，后续重点转为防回脏、定期巡检与受控 apply 预案固化。

## 3. 12 个问题状态矩阵

| # | 问题 | 当前状态 | 证据 | 当前真实结论 | 下一步 |
| --- | --- | --- | --- | --- | --- |
| 1 | basic 模式和后端 `single_kb` 约束冲突 | **已修** | `webapp/src/domain/agentExperience.js`、`webapp/src/pages/AgentPage.jsx`、`webapp/src/domain/agentExperience.test.js` | `basic` / `knowledge` 都要求显式 active KB，前端已不再把 basic 当作全局检索模式 | 继续守住前端单测即可 |
| 2 | 启动链路 / 桌面链路存在硬编码 | **基本收敛** | `start_dev.ps1`、`start_all.ps1`、`scripts/dev-all.ps1`、`desktop/src/runtime-config.js`、`desktop/src/python-process.js`、`README.md`、`docs/project.md`、`docs/desktop_runbook.md`、`docs/guide/desktop_runbook.md` | 主启动链路已不依赖历史绝对路径，README / runbook 也已统一到端口覆盖与 API base 契约；剩余风险主要在历史纪要文档和 artifact 中的旧路径，不在主入口脚本本身 | 后续补一轮真实联调记录，并视需要把历史 artifact 中的旧路径做分层说明 |
| 3 | 项目主入口不统一 | **基本收敛** | `README.md`、`README_en.md`、`README_zh.md`、`start_all.ps1`、`start_dev.ps1`、`scripts/dev-all.ps1`、`docs/project.md`、`docs/desktop_runbook.md`、`docs/guide/desktop_runbook.md`、`app.py`、`frontend/`、`.streamlit/` | README、runbook 与脚本主线都已收口到 `FastAPI + React + Electron`；`app.py` 也已改成默认禁用、需 `KB_ALLOW_LEGACY_STREAMLIT=1` 显式 opt-in 的 legacy compatibility shim，但 `frontend/` / `.streamlit/` 仍在仓库内保留，说明“主入口统一”与“遗留入口治理完成”不是一回事 | 继续把 legacy 入口限定在兼容 / 排障说明，并持续避免新增文档把它写回默认启动方式 |
| 4 | 请求级 `QueryRequest` 参数疑似没有完整打进 chat 主链路 | **已修并补强到 semireal smoke** | `api/schemas/__init__.py`、`api/services/chat_service.py`、`tests/api/test_runtime_model_loading.py`、`tests/api/test_chat_routes.py`、`tests/api/test_chat_scope_contract.py`、`tests/api/test_chat_single_kb_qa_smoke.py`、`webapp/src/api/chat.test.js`、`api/routers/open_api.py`、`api/services/open_api_service.py`、`tests/api/test_open_api.py`、`tests/api/test_open_api_service.py`、`tests/api/test_open_api_integration.py` | `top_k / response_mode / use_reranker / top_n / reranker_model` 已形成 chat 主链路的 schema → route → query engine → semireal smoke → frontend API 闭环；OpenAPI 也已明确成 `/search` 只承诺 `top_k`、`/answer` 额外承诺 `response_mode / use_reranker / top_n / reranker_model` | 保留回归测试即可；后续若还想继续补强，更值得做“接参影响行为”的对照题，而不是继续重复协议边界单测 |
| 5 | 前端把 query 成功和 history 成功绑死 | **已修并持续收口结构** | `webapp/src/domain/chatWorkflow.js`、`webapp/src/domain/chatWorkflow.test.js`、`webapp/src/pages/AgentPage.jsx`、`webapp/src/pages/useAgentChatWorkspace.js`、`webapp/src/pages/agent-page/QaWorkbench.jsx`、`tests/scripts/test_webapp_contracts.py` | 当前是 query 成功优先，history 同步失败只降级成 notice，不再把问答整体判成失败；同时 `chatNotice` 已真实串到 `QaWorkbench`，问答 workflow 已抽到 hook，本轮又把问答展示层拆成 workbench + conversation + source list + kb selector 叶子组件 | 主契约已稳，下一步前端更值得继续压 `AgentRuntimePanel` 或补 UI 交互测试，而不是回头补救 query/history 主链路 |
| 6 | 评测 harness 对 refusal / negative contract 覆盖不足 | **进一步收敛** | `tests/fixtures/rag_quality/eval_v7/schema.json`、`tests/fixtures/rag_quality/eval_v7/cases.json`、`tests/fixtures/rag_quality/eval_v8_main/cases.json`、`tests/fixtures/rag_quality/eval_v8_hard/cases.json`、`scripts/build_eval_v7_holdout.py`、`scripts/build_eval_v8_layered.py`、`tests/test_rag_quality_eval_dataset_v7.py`、`tests/test_rag_quality_eval_dataset_v8.py`、`tests/test_rag_quality_eval_builders.py`、`tests/test_rag_quality_fixtures.py`、`tests/api/test_chat_eval_runner.py`、`tests/api/test_chat_markdown_qa_semireal.py`、`tests/api/test_chat_pdf_semireal.py`、`tests/api/test_chat_image_ocr_semireal.py` | 现在不只是“refusal 样本比以前多”：`eval_v7` 已有 3 条 `no_evidence` refusal + 6 条 negative contract，且 smoke 层 schema 已显式要求 `minimum_negative_contract_cases_per_modality = 2`；`eval_v8_main` 有 23 条 refusal + 19 条 negative contract，并且 `history_grounded_case_count = 6`、markdown / pdf / image_ocr 各 2 条；`eval_v8_hard` 有 6 条 refusal + 6 条 negative contract。另外 semireal 多轮 follow-up 也已补齐 Markdown / PDF / Image OCR 三模态的 refusal 对称性。builder 与 checked-in fixture 的 schema 也已重新对齐，降低后续重建数据集时回退 gate 的风险；但 OCR / preview hygiene / source_count 负向题仍值得继续补 | 继续补 OCR 负向题、preview hygiene 负向题和 source_count 负向题，并优先补更像真实面试会追问的范围约束题 |
| 7 | Prompt 契约偏弱，后处理 heuristic 太重 | **部分收敛（source projection + answer repair + composite answers 已独立模块化）** | `api/services/chat_service.py`、`api/services/chat_source_answers.py`、`api/services/chat_answer_repair.py`、`api/services/chat_composite_answers.py`、`tests/api/test_chat_source_answers.py`、`tests/api/test_chat_answer_repair.py`、`tests/api/test_chat_composite_answers.py` | 现在不再是所有 source-backed 修复都堆在 `chat_service.py`：table / preview / boundary / scope-definition 已在 `chat_source_answers.py`，brief-answer expansion / exact-term repair / answer-support segmentation 已在 `chat_answer_repair.py`，multi-fact merge / summary bundle 也已下沉到 `chat_composite_answers.py` 并补齐独立契约测试；对应 bundle `python -m pytest tests/api/test_chat_composite_answers.py tests/api/test_chat_postprocessors.py tests/api/test_chat_service.py -q` 当前为 `98 passed`。 `chat_service.py` 进一步从 `1585` 行降到 `1166` 行。当前剩余更重的规则链主要集中在 targeted-fact orchestration 与其邻近的 scoring / source-selection 流程 | 下一步优先继续下沉 targeted-fact orchestration，并整理 hook builder / dependency registry，同时持续把可稳定的能力前移到 prompt / response contract 层 |
| 8 | Docker / requirements / 端口 / 启动脚本存在配置漂移 | **持续收敛** | `Dockerfile`、`scripts/docker-entrypoint.sh`、`scripts/docker_smoke.py`、`tests/scripts/test_docker_smoke.py`、`requirements-runtime.txt`、`requirements-eval.txt`、`requirements-prod.txt`、`requirements-minimal.txt`、`tests/test_requirements_profiles.py`、`README.md`、`temp/runtime-report-after-langchain-pin.json` | Docker 现在已经把“安装哪套依赖”和“默认跑什么进程”拆开：默认 `INSTALL_PROFILE=runtime` + API 模式，`eval` / `prod` 退到显式模式；误导性的 `minimal` Docker profile 已退场；进一步确认 runtime build 变慢的根因是 `requirements-runtime.txt` 中的顶层 `llama_index` metapackage 会额外拉入 OpenAI / LlamaCloud / LlamaParse 依赖链，当前已改成只保留 `llama-index-core` + 显式 integrations，并把 dry-run 选中的 `langchain-core==0.3.63` / `langchain-text-splitters==0.3.8` 显式 pin 住。最新 dry-run 报告已确认不再出现 `llama-parse / llama-cloud-services / llama-cloud / llama-index`；另外 `scripts/docker_smoke.py` 默认已改为 Docker 自分配 loopback host port + `docker port` 反查映射，避免 smoke helper 本身重复引入宿主机端口竞争 | 继续补完整 build/run smoke，并评估是否需要进一步收紧 `sentence-transformers / torch` 这类重依赖的安装口径 |
| 9 | 仓库根目录临时文件、日志、调试脚本较多 | **已收敛** | `scripts/cleanup_local_artifacts.py`、三份 manifest、`python scripts/cleanup_local_artifacts.py --dry-run`、`python scripts/cleanup_local_artifacts.py --dry-run --include-directories` | 当前 file-mode / directory-mode 均已回到 `managed_count = 0`；问题已从‘根目录极乱’收敛到‘如何长期防回脏’ | 后续重点转为防回脏、定期巡检与受控 apply 预案固化 |
| 10 | 文档闭环不够满 | **部分收敛** | `docs/20260820-rag-interview-eval/`、`docs/20260821-project-audit-remediation/`、`docs/project.md`、`docs/desktop_runbook.md`、`docs/guide/desktop_runbook.md` | README / runbook 已收口到当前主入口；剩余漂移主要在历史阶段纪要、旧 artifact 和更细粒度的长期整理 | 继续统一到“20260821 审计目录优先引用”的规则，并逐步拆分 `docs/project.md` 的历史章节 |
| 11 | 日志与临时产物治理需要规范化 | **已收敛** | `scripts/cleanup_local_artifacts.py`、`tests/scripts/test_cleanup_local_artifacts.py`、三份 manifest、directory-mode dry-run 输出 | 当前已经做到 file-mode / directory-mode 均已回到 `managed_count = 0`；问题已从“如何清 backlog”切到“如何长期防回脏” | 把使用时机写进 runbook / 提交流程，并围绕后续重点转为防回脏、定期巡检与受控 apply 预案固化做周期化巡检 |
| 12 | 面试表述需要主动区分“能力完成度”和“工程完成度” | **已整理，但需统一引用** | `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-interview-brief.md`、`docs/20260820-rag-interview-eval/20260820-rag-interview-eval-test-report.md` | 当前已经能清楚讲“能力闭环已成型、工程仍在收尾”；但还需要统一大家引用哪份材料、用哪组数字 | 对外优先引用 20260821 审计目录和当前 layered suite 产物 |

## 4. 当前最关键的结构性判断

### 4.1 已经不再是“功能做不通”

如果系统主能力没成型，通常会先看到：scope 崩、evidence 崩、preview 崩、主入口乱。现在并不是这个状态，当前 semireal layered suite 已全绿。

### 4.2 也不能直接说“已经完全 finished”

当前剩余问题的重心已经从“答不对题”转到了：

- 启动 / 端口 / 文档口径统一；
- prompt 与 heuristic 的职责边界；
- legacy 入口的保留与退场策略；
- Docker runtime / eval build 的确定性；
- file-mode / directory-mode 均已回到 `managed_count = 0`后的治理收口，重点转为巡检、防回脏与 runbook 固化。

### 4.3 最合理的项目定位

> **这是一个“主能力闭环与评测闭环都已形成，文件级根目录治理已经收敛，但工程治理、目录级临时产物治理和长期维护体验仍在继续收口”的本地知识库助手项目。**

## 5. 下一步优先级建议

### P0
1. 继续补 Docker runtime / eval 的真实 build smoke，并验证移除顶层 metapackage 后的解析稳定性
2. 给 reranker / response_mode 设计少量行为差异题，证明新增参数不仅能透传，还会稳定影响结果
3. 把目录治理从‘清 backlog’切到‘防回脏 + 定期巡检 + 受控 apply 预案’；当前 file-mode / directory-mode 均已回到 `managed_count = 0`。

### P1
1. 继续清理 legacy 入口叙事
2. 继续拆 `kb_service.py` 与 `AgentRuntimePanel`（`AgentPage.jsx` 已抽出 `useAgentChatWorkspace.js` 与 `QaWorkbench` 子组件层，`QaWorkbench` 静态契约也已补到 4 条）
3. 把真实执行型 smoke 从当前的 `start_dev.ps1` / `scripts/dev-all.ps1` 继续扩到 packaged desktop + Docker 联调记录

### P2
1. 统一面试材料引用路径
2. 继续收敛历史 runbook / project 文档
3. 把“能力完成度 vs 工程完成度”写成固定话术模板


## 补充更新（2026-08-22 refusal contract gate）

- 新增证据：`python -m pytest tests/test_rag_quality_fixtures.py tests/test_rag_quality_eval_dataset_v7.py tests/test_rag_quality_eval_dataset_v8.py -q` → `20 passed`。
- 当前 refusal harness 已同时具备三层 gate：总量 / modality 分布、refusal subtype 分布、category 内关键 contract wording 分布。
- 这使“负向题是不是只凑了几个 refusal 样本”的风险进一步下降，但 OCR / preview hygiene / source_count 负向题仍值得继续扩充。

## 补充更新（2026-08-25 negative contract smoke refresh）

### 新增验证

- `python -m pytest tests/test_rag_quality_eval_dataset_v7.py tests/test_rag_quality_eval_builders.py tests/test_rag_quality_fixtures.py -q` → `16 passed`
- `python -m pytest tests/test_rag_quality_eval_dataset_v8.py -q` → `12 passed`
- `python -m pytest tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py -q` → `41 passed`

### 这轮新增真实结论

1. `eval_v7` smoke 层现在不再只有 refusal gate，`process_boundary / scope_contract` 已被显式纳入 negative contract gate，且三种模态各有 2 条边界类样本。
2. 这轮没有盲目新增 case，而是把原本就存在的 6 条边界类样本正式纳入统计，因此没有破坏 v7 当前总题量、难度分布和模态分布。
3. `chat_eval_runner` 现在也已把 refusal / negative contract 的 contract gate 直接联动到最终 `run_passed`，不再只是 markdown / summary 展示层。
4. 这意味着单题通过不再自动等于 suite 通过；如果 required refusal marker 或 required negative contract categories 缺口存在，最终运行结果会被显式拦下。
5. `scripts/build_eval_v7_holdout.py` 与 `scripts/build_eval_v8_layered.py` 已和 checked-in fixture schema 再次对齐，builder 重新生成数据集时不容易把 negative contract gate 覆盖回旧版本。
6. 这使 #6 更准确的状态从“部分收敛”推进到“进一步收敛”；剩余真正值得继续补的是 OCR / preview hygiene / source_count 这类更难刷分、也更像真实边界风险的负向题。
## 补充更新（2026-08-22 directory backlog sizing + docker eval smoke）

### 新增验证

- `python -m pytest tests/scripts/test_cleanup_local_artifacts.py -q` → `13 passed`
- `python -m pytest tests/scripts/test_repo_hygiene_contracts.py tests/scripts/test_docs_entry_contracts.py -q` → `11 passed`
- `python -m pytest tests/scripts/test_docker_smoke.py -q` → `9 passed`
- `python scripts/cleanup_local_artifacts.py --dry-run --include-directories` → `managed_count = 0`

### 这轮新增真实结论

1. 这段 directory backlog sizing 属于历史留痕；截至最新 dry-run，file-mode / directory-mode 均已回到 `managed_count = 0`。后续更重要的是继续保留这套 sizing / 排序能力，避免下次回脏时只能人工平铺扫描。
   - `summary.total_size_bytes = 1159774`
   - `summary.size_bytes_by_category = { scratch_debug_dir: 26998, scratch_eval_dir: 1132776 }`
   - `summary.largest_records`（前 5 个最大目录）
2. 当前 latest dry-run 已不再命中 root scratch 目录；下方 top 5 仅保留为历史 backlog sizing 留痕。
   - `tmp_eval_out` → `112417` bytes
   - `tmp_eval_out5` → `107567` bytes
   - `tmp_eval_debug_codex3` → `106632` bytes
   - `tmp_eval_debug_codex5` → `106632` bytes
   - `tmp_eval_out8` → `100760` bytes
3. 这意味着目录治理的价值已经从“清 backlog”转到“保留体积 + 类别 + top offender 视角”，用于下次回脏时快速决定巡检与受控 apply 顺序；当前 file-mode / directory-mode 均已回到 `managed_count = 0`。
4. `scripts/docker_smoke.py` 已经补到 runtime-mode aware：`eval` 模式不再错误探测 `/api/health`，而是等待容器退出码；但真实 `docker_smoke` live build 也暴露出新的主要瓶颈：`llama-index-embeddings-huggingface -> sentence-transformers -> torch` 在 Linux Docker 下继续拉起超重 GPU 依赖链。
5. 当前 live build 日志里已确认下载了多组超大依赖，例如：
   - `torch-2.13.0` → `526.6 MB`
   - `nvidia_cudnn_cu13` → `366.2 MB`
   - `nvidia_cusparselt_cu13` → `170.1 MB`
   - `nvidia_nccl_cu13` → `206.0 MB`
   - `triton-3.7.1` → `197.7 MB`
   - `nvidia_cublas` → `423.1 MB`
   - `nvidia_cufft` → `214.1 MB`
6. 因此这轮对 Docker 的更准确说法应是：**smoke helper 契约已修正，但 runtime / eval 镜像的首要风险已从“helper 误判”转成“默认 embedding 依赖链过重，导致真实 build 时间和镜像体积继续失控”。**

### 对矩阵项的影响

- #8（Docker runtime baseline / requirements profile）应继续保留 **“部分收敛”**，且下一步重点要从 metapackage 根因继续推进到 `torch` / GPU transitive chain 的安装口径收紧。
- #9 / #11（根目录治理）当前已经从“存量 backlog 问题”转成“长期治理机制问题”；file-mode / directory-mode 均已回到 `managed_count = 0`，下一步重点就是后续重点转为防回脏、定期巡检与受控 apply 预案固化。

## 补充更新（2026-08-22 docker smoke lighter profile + startup retry fix）

### 新增验证

- `python -m pytest tests/scripts/test_docker_smoke.py -q` → `18 passed`
- `python -m pytest tests/test_requirements_profiles.py -q` → `9 passed`
- `python -m pip install --dry-run --ignore-installed --report temp/smoke-profile-report.json -r requirements-smoke.txt` → 生成 dry-run 报告
- `python -c "..."` 解析 `temp/smoke-profile-report.json` → `flagged=[]`，未再看到 `torch / sentence-transformers / nvidia / triton`
- `python scripts/docker_smoke.py --tag agent-kb-smoke:local --install-profile smoke --app-runtime-mode api` → build + run + `/api/health` 成功

### 这轮新增真实结论

1. 现在已经不只是“建议做 lighter profile”，而是**真的新增了 `requirements-smoke.txt`**，并让 Docker 支持 `INSTALL_PROFILE=smoke`。
2. 这个 smoke profile 以 runtime baseline 为基础，但有意识地移除了 `llama-index-embeddings-huggingface`，因此 dry-run 报告里不再出现 `torch / sentence-transformers / nvidia / triton` 这条超重链。
3. 在真实 Docker smoke 里又暴露并修掉了两个 Linux 容器侧问题：
   - Windows checkout 下 `scripts/docker-entrypoint.sh` 的 CRLF 会导致容器启动时报 `exec /app/scripts/docker-entrypoint.sh: no such file or directory`；现在 Dockerfile 已在镜像内显式做 `sed -i 's/\r$//'` 归一化。
   - 容器刚启动时 `/api/health` 可能短暂返回 `RemoteDisconnected`；`scripts/docker_smoke.py` 现在会把这类 startup race 当作可重试瞬时错误处理，而不是第一次断连就直接失败。
4. 因此 #8（Docker runtime baseline / requirements profile）的状态应更新为：**runtime/eval baseline 仍偏重，但 Docker health smoke 已经拥有单独的轻量安装口径，并且 build + run 证据已补上。**
5. 这并不意味着 runtime / eval 已完全变轻：`requirements-runtime.txt` 仍保留 `llama-index-embeddings-huggingface` 契约，真正的推理 / 检索链路仍要继续沿 baseline 优化，而不是把 smoke profile 当成生产替代。


## 补充更新（2026-08-24 composite answers modularization）

### 新增验证

- `python -m pytest tests/api/test_chat_composite_answers.py tests/api/test_chat_postprocessors.py tests/api/test_chat_service.py -q` → `98 passed`
- `python -m pytest tests/api/test_chat_question_intents.py tests/api/test_chat_targeted_fact.py tests/api/test_chat_source_answers.py tests/api/test_chat_answer_repair.py -q` → `49 passed`
- `python -m pytest tests/test_rag_quality_eval_dataset_v7.py tests/test_rag_quality_eval_builders.py tests/test_rag_quality_fixtures.py -q` → `16 passed`
- `python -m pytest tests/test_rag_quality_eval_dataset_v8.py -q` → `12 passed`
- `python -m pytest tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py -q` → `41 passed`

### 这轮新增真实结论

1. `api/services/chat_composite_answers.py` 已不再是“只新建未接入”的孤立文件，而是已经真正接入 `chat_service.py`，承接 multi-fact merge 与 summary bundle 两段组合型 heuristic。
2. `chat_service.py` 新增 `_build_composite_answer_hooks()` 后，source-backed heuristic 现在已经形成三块独立模块：
   - `chat_source_answers.py`
   - `chat_answer_repair.py`
   - `chat_composite_answers.py`
3. `chat_service.py` 行数已从上一轮的 `1585` 行进一步降到 `1166` 行，说明这轮不是只换文件名，而是确实继续把纯函数逻辑外移。
4. `tests/api/test_runtime_model_loading.py` 已补足 QueryRequest 到 query engine effective config 的关键证据：默认值与请求级覆盖值都会真实传进 `create_query_engine(...)`。
5. 当前 Prompt / heuristic 方向的主要剩余瓶颈，已经从 multi-fact merge / summary bundle 转移到 targeted-fact orchestration，以及逐渐增多的 hook builder / dependency registry 分散问题；与此同时，前端 query/history 主契约已经稳定，下一步更适合压复杂度热点而不是继续回头补同质边界测试。

### 对矩阵项的影响

- #7（Prompt 契约偏弱，后处理 heuristic 太重）应更新为 **“部分收敛（source projection + answer repair + composite answers 已独立模块化）”**。
- 该项下一步优先级应从“继续拆 multi-fact / summary”推进到“继续拆 targeted-fact orchestration，并整理 hook builder / dependency registry”。

## Desktop release lane source of truth

- `scripts/build-desktop.ps1/.sh` = local desktop build helper.
- `npm run build:mac` + `npm run verify:package` = ad-hoc package verification.
- `npm run release:preflight` = strict Apple preflight.
- `npm run release:mac` + `npm run verify:mac-release` = signed/notarized distribution lane.


