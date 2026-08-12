# 项目总览

> 本文档面向所有协作者（含 AI 助手），用于快速了解项目当前进度、架构、验证证据和已知问题。
> **维护规则**：每次有意义的提交后更新「当前进度」「测试与验证」「已知问题」「最近提交」四节；重大架构变化更新「架构」节。日期使用绝对日期。

最近更新：2026-08-12

---

## 1. 项目简介

本项目是 **ThinkRAG** 的本地知识库 RAG 改造分支，仓库代号 **agent-kb**，桌面端产品名正在向 **NorthAgent** 收敛。

项目已从原始的「单库 Streamlit 问答」演进为一个本地运行的 **多知识库 + 知识对象导入 + Agent 工作台 + 桌面客户端** 系统。当前主线不再是概念验证，而是围绕本地知识库助手做稳定性收口、导入/检索质量评测、粮仓知识库真实资料验收，以及桌面体验完善。

当前两条主线：

1. **多知识库与知识对象化**：FastAPI 后端、React 前端、Electron 桌面壳已经成型；知识库支持 CRUD、文件/网页导入、目录化原始文件存储、文件夹/资产 registry、导入回执、证据预览和 KB 范围问答。
2. **Agent 化工作台**：`/agent` 页面提供基础聊天、限定知识库聊天和 Agent 高级模式；后端已有任务路由、工具调用、命令风险分级、人工审批、回执与 session 快照。

工程取向仍然面向本地和中文资料场景：中文 splitter、BGE 嵌入模型、DeepSeek/Moonshot/Zhipu/兼容 OpenAI 的 LLM API、本地 Ollama、PDF 文本层读取与 PaddleOCR 回退。

---

## 2. 技术栈

| 层 | 技术 |
|---|---|
| RAG 框架 | LlamaIndex 0.11.x 口径，当前代码已做 0.11.19 内部 API 适配 |
| 后端 API | FastAPI、uvicorn、CORS、本地日志轮转 |
| RAG 核心 | `server/`：index、ingestion、retriever、readers、splitters、stores、security、agent |
| API 服务层 | `api/`：routers、services、schemas、runtime |
| Web 前端 | React 18 + Vite 8 + React Query + Zustand + 项目内轻量 router |
| 桌面端 | Electron 43，`desktop/` 启动 Python API 后加载 Web |
| 旧前端 | Streamlit：`app.py` + `frontend/`，保留为迁移回退，不代表当前主线体验 |
| PDF/OCR | PyMuPDF + PaddleOCR |
| 本地 LLM | Ollama 0.3.3；README 仍提示 0.4 与当前依赖组合不兼容 |

---

## 3. 架构

```text
desktop/ (Electron, NorthAgent)
  -> webapp/ (React + Vite)
      -> api/ (FastAPI 路由与服务层)
          routers/: agent, chat, health, kb, settings
          services/: agent_runtime, chat_service, kb_service,
                     asset_service, folder_service, evidence_service,
                     approval_service, session_store, tool_receipt_store ...
          runtime.py: RuntimeState, 模型预热, IndexManager 缓存
              -> server/ (RAG 核心)
                  index.py / ingestion.py / retriever.py
                  readers/: pdf_ocr, image_ocr, web readers
                  splitters/: Chinese splitters, title enhance
                  kb_registry.py / folder_registry.py / asset_registry.py
                  stores/: config/doc/index/vector/storage context
                  security/: path/filename/command validation

app.py + frontend/ (旧 Streamlit 入口，保留)
```

主要运行入口：

- 后端 API：`python run_api.py`，默认 `127.0.0.1:18080`
- Web 前端：`cd webapp && npm run dev`
- 桌面端：`cd desktop && npm run dev`
- 旧 Streamlit：`streamlit run app.py`

---

## 4. 当前进度

### 4.1 已完成的主干能力

- **API/Web/Desktop 骨架已落地**：FastAPI、React/Vite、Electron 壳、会话快照、设置存储、运行日志与本地健康检查已具备。
- **多知识库最小闭环已完成**：KB registry、KB CRUD、`kb_id` 范围查询、Agent `knowledge_scope.kb_id` 透传、网页/文件导入目标 KB 透传、证据返回真实 `kb_id`。
- **原始文件目录化存储已完成**：新导入文件按 `data/{kb_id}/` 保存；导入前校验 KB active；list/delete 与问答链路按 metadata 做逻辑隔离。
- **导入对象模型已显著增强**：支持逐文件导入结果、导入回执、stage timings、文件夹树、Markdown 内嵌资产抽取、资产 registry、图片 OCR 路径、证据预览。
- **DOCX 文档类型识别已补齐**：`api/services/kb_service.py` 已显式识别当前依赖验证可导入的 `.docx` 与对应 MIME，避免 DOCX zip 容器被当作二进制提前拒绝；`pptx/xlsx/odt/ods` 在补齐依赖和真实导入测试前仍按不支持类型处理。
- **LlamaIndex 0.11.19 适配已推进**：`server/ingestion.py` 避免依赖缺失的私有 `_update_docstore`；`server/retriever.py` 改为通过当前版本的 `_build_node_list_from_query_result` 组装节点，并保留 stale vector id / 维度不兼容 embedding 的过滤。
- **Knowledge Workspace 已形成当前主界面**：`/knowledge` 支持知识库选择、文件导入、网页导入、对象浏览、导入诊断、OCR 预热状态、资产/证据预览入口。
- **`/agent` 页面已重构为问题优先工作区**：支持基础聊天、限定知识库聊天、Agent 高级模式；知识库聊天要求显式选择 active KB。
- **前端路由依赖风险已收口**：Web 前端只使用顶层页面切换、`Link`、`useLocation` 与 `useNavigate` 的基础能力，已用项目内 `webapp/src/router.jsx` 替代 `react-router-dom`，并对协议 URL、双斜杠和反斜杠导航做本地拒绝；`npm audit --json` 当前为 0 vulnerabilities。
- **Agent runtime + 审批流可用**：命令解析、风险分级、硬拒绝、pending action、approve/reject、工具回执、session 持久化已接通。
- **PDF/OCR 回退链路已落地**：文本层优先，扫描件回退 PaddleOCR；图片 OCR 可进入导入与诊断路径。
- **PaddleOCR 本地运行时已补齐并加固默认模型源**：`server/readers/image_ocr.py` 在用户未显式配置时默认使用 ModelScope 并跳过 PaddleX 不稳定的模型源探测；同时预加载 LangChain text splitter bridge，避免 PaddleOCR/PaddleX 污染 `langchain.text_splitter` 后导致问答 400。本机已完成 PP-OCRv6 检测/识别模型下载缓存，图片 OCR、扫描 PDF OCR 与 mixed batch API roundtrip 验证通过；诊断脚本已补充 macOS/Linux/Windows 字体候选，降低 macOS 默认小字体导致 OCR 样本误识别的概率。

### 4.2 质量与评测进展

- **本地多知识库助手 Stage 3 评测闭环已形成**：`docs/20260722-local-multi-kb-assistant/` 是当前正式基线，包含 PRD/FRD/RTM/spec/plan/test-plan/test-report 与 artifacts。
- **2026-07-31 测试报告给出的当前工作树证据**：
  - 全量 Python 回归：`667 passed, 2 warnings`
  - `api + server` 覆盖率：`82%`，高于仓库 `>= 80%` 门禁
  - broad ingestion + QA 回归：`354 passed, 2 warnings`
  - 正式 QA eval：`eval_v4 54/54`、`eval_v5 72/72`、`eval_v6 78/78`
  - live roundtrip 覆盖 Markdown、PDF 文本层、扫描 PDF OCR、图片 OCR、mixed batch
- **粮仓知识库真实 QA 评测已扩展到 80 条 verified 用例并完成索引覆盖修复**：
  - 脚本：`scripts/run_grain_qa_eval.py`
  - 输入：`data/grain-knowledge-base/qa/verified.jsonl`，当前 80 条人工标注用例
  - 报告产物：`docs/20260722-local-multi-kb-assistant/artifacts/grain-qa/qa-eval-report.json`
  - 2026-08-07 使用恢复后的 `阿里百联 / qwen3.7-plus` 重新生成完整报告：`total=80`、`answerable_total=77`、`unanswerable_total=3`、`error_count=0`、`Recall@5=0.5325`、`MRR@5=0.5238`、`citation_hit_rate=1.0`、`refusal_accuracy=0.6667`、`kb_isolation_rate=1.0`
  - 2026-08-10 完成索引覆盖修复：新增 `scripts/diagnose_grain_qa_coverage.py`，确认 QA 期望文档 `local=82/82`、`docstore=82/82`、正确 `kb_id=82/82`；定向导入 19 个唯一缺失文件全部通过。
  - 2026-08-10 复跑 80 条 QA 后，answerable `Recall@5` 从 `0.5325` 提升到 `0.974`，`MRR@5` 提升到 `0.8961`，`error_count=0`、`citation_hit_rate=1.0`、`refusal_accuracy=1.0`、`kb_isolation_rate=1.0`；后端已按 `kb_id + file` 合并重复 sources，source 噪声明显下降。
  - 报告已补充 `api_base`、`timeout`、`cases_sha256`、逐条 `requested_kb_ids`、`relevant_doc_types`、`source_kb_ids` 与 `kb_id_missing_count`，避免引用来源缺失 `kb_id` 时误判隔离通过。
  - 报告新增 `failure_groups`。2026-08-07 旧基线分组为：`retrieval_miss=17`、`rank_miss=1`、`source_noise=37`、`ocr_text_quality=19`、`refusal_miss=1`；2026-08-10 修复后分组为：`api_error=0`、`retrieval_miss=1`、`rank_miss=11`、`source_noise=4`、`ocr_text_quality=1`、`duplicate_or_conflict=0`、`kb_isolation_failure=0`、`refusal_miss=0`。
  - 本轮将原 36 条 answerable Recall@5=0 用例中的绝大部分恢复召回，剩余 2 条 answerable 漏召回，已定位为后续检索排序/语义相似度优化候选，不再是索引覆盖缺口。
  - 说明：该评测不做 LLM 裁判，主要验证检索命中、引用来源、拒答和 KB 隔离。

### 4.3 当前 Git 状态

- 当前分支：`codex/desktop-agent-stage3`
- 远端跟踪：`origin/codex/desktop-agent-stage3`
- 同步状态：2026-08-12 复核 `HEAD...@{u}` 为 `0 0`，当前分支与远端一致；本轮进一步补齐 embedding 预热卡住时的 stale 诊断。
- 最近已推送提交：
  - `fb0ec89 chore: update dev story capture state`
  - `2b6c74d feat(chat): ground table field answers from sources`
  - `9e037b8 chore: update dev story capture state`
  - `9ce1be3 feat(desktop): reuse running api on launch`
  - `06f72a8 chore: update dev story capture state`
  - `a182ba5 feat(eval): add cross-domain preflight`
  - `9a04909 chore: update dev story capture state`
  - `1391d4d feat(eval): flag systemic model failures`
  - `9b7e5b8 chore: update dev story capture state`
  - `bd4a190 feat(model): probe selected model health`
  - `8e9257f chore: update dev story capture state`
  - `e084e4c feat(eval): expand cross-domain v6 diagnostics`
- 当前优化状态：模型 fallback、`fallback_attempts` / `fallback_attempt_summary` / `probeSummary` UI 展示、Ollama 本地候选提示、Ollama 动态发现失败诊断候选、模型选择后即时探活、桌面 CSP、发布配置校验、release preflight、notarize hook、packaged resources 校验、mac release 后置签名/公证校验和跨领域真实门禁均已落地；`release:mac` 现已串起 `build:preflight` + `release:preflight` + `electron-builder --mac` + `verify:package` + `verify:mac-release`，正式发布会在打包后继续检查 packaged runtime contents、codesign、Gatekeeper assess 和 stapler ticket。`npm run build` 的 macOS 路径也会先跑发布配置校验和非严格预检，`verify-package` 已有单测覆盖并能发现 `mac-arm64` / `mac` / `mac-universal` 等产物布局，避免打包与产物校验入口绕过门禁，也避免旧架构产物残留时误选错误 artifact。2026-08-11 新增外部 extra cases 追加能力、多轮 `turns` 评测、来源文件级断言、evidence 文本断言、失败检查项归因汇总和耗时诊断后，默认 23 条基线 + v1 外部 4 条 + v2 外部 6 条 + v3 多轮 3 条 + v4 source-grounding 5 条 + v5 evidence-text 4 条真实业务追加样本合计 `45/45 passed`，逐轮统计 `48/48 passed`，并按 tag 维度切出了 `long-question`、`multi-hop`、`multi-turn`、`follow-up`、`source-grounding`、`evidence-text`、`ocr`、`scan`、`refusal` 和 `cross-kb-isolation` 的细分门禁；报告新增 `failure_check_summary`、`failure_case_summary` 和 `duration_summary`，当前稳定基线失败归因为空，最慢 case 为 `grain-negative-utf8-exact-boundary`。2026-08-12 已针对 v6 README 表格误答补充 source-backed Markdown 表格字段兜底，并把 `Broken pipe`/timeout 等断流归入 `network_error`；runtime ready 后 v6 定向复跑 `4/4 cases`、`6/6 turns` 全部通过。健康检查也补齐 embedding 本地缓存/远程下载诊断，便于解释冷启动慢或模型缓存缺失。跨领域评测脚本现已支持 `--suite v1-v6` 一键加载默认 23 条 + v1-v6 外部 26 条真实样本，并输出逐 case 进度；当前临时模型 `qwen-math-turbo` 下全量 suite 为 `26/49 passed`、逐轮 `30/54 passed`，负向隔离 `15/15` 和 contract `1/1` 全通过，失败集中在正向 expected terms、长多轮和 source/evidence grounding。本轮已针对其中一类高频失败补 source-backed 精确短语保真修复，覆盖 passcode 连字符被改写、`OCR fallback` 被粘连等情况；`scripts.prepare_embedding_model_cache --download` 因 HuggingFace mirror 连接超时失败后，runtime 已改为默认禁止 embedding 初始化走远程下载，缓存缺失时快速失败并提示预下载或显式设置 `EMBEDDING_ALLOW_REMOTE_DOWNLOAD=1`，避免新 API/桌面启动再次卡到 stale。正式 macOS 签名/公证仍未完成，原因是本机缺少 Apple 发布环境变量和 Developer ID Application 证书。

### 4.4 下一步建议

- **优先收口桌面依赖安全**：`desktop npm audit` 已清零，`electron-builder` 升级到 `26.15.3` 后重新跑通 release config、mac 打包和 packaged resource 校验；`release-preflight` 也已兼容新版不再安装 `app-builder-bin` 的情况。
- **发布入口已经串起配置预检和后置校验**：`desktop/package.json` 的 `release:mac` 现在会先跑 `build:preflight`，再进入严格 `release:preflight`、`electron-builder --mac`、`verify:package` 和 `verify:mac-release`；`desktop/scripts/build-target.js` 也让 `npm run build` 在 macOS 上先跑配置校验和非严格预检，`verify-package` 也已模块化并补齐多布局产物校验单测，`verify-mac-release` 会验证 codesign、Gatekeeper 和 stapler。
- **Apple 凭证到位后完成正式发布闭环**：补齐 `APPLE_ID`、`APPLE_APP_SPECIFIC_PASSWORD`、`APPLE_TEAM_ID` 和 Developer ID Application 证书后，按 release checklist 执行严格 preflight、签名、公证、安装后桌面工作流回归。
- **fallback 继续补真实失败提示**：当前已能区分云端候选失败、Ollama 模型未安装、Ollama 服务不可达和 Ollama 已连接但没有本地模型；`/api/model/select` 也会在保存模型后即时探活并把失败写入 `model_health`，桌面启动时若发现 `18080` API 已可用会复用现有服务，不再额外拉起一个失败的 API 子进程；配置落盘已改为缩进 JSON，方便人工恢复模型配置时核对。下一步可把这些结构化原因接入桌面 E2E 报告，复核用户重新配置模型后的恢复路径。
- **继续收口 embedding 冷启动体验**：当前 API/Web 可用，embedding 最终 ready，但本机冷启动曾耗时约 626 秒；健康检查已补 `elapsed_ms` / stale 状态和 `embedding_diagnostics`，能提示本地缓存缺失、远程 HuggingFace mirror 回退和预下载建议。2026-08-12 直接执行 `scripts.prepare_embedding_model_cache --download` 仍因 `ConnectTimeout` 失败；当前 runtime 已默认禁用启动期远程下载，让缓存缺失快速失败。下一步应把该诊断接入前端/诊断脚本，并解决模型缓存来源或下载代理后再复跑完整评测。
- **继续扩大真实业务知识库评测**：跨领域门禁已支持 `--extra-cases` 追加外部 JSON 样本、`--suite v1-v6` 一键追加 v1-v6 外部真实样本、`turns` 多轮追问用例、来源文件级断言、evidence 文本级断言、失败检查项归因汇总、超时归一、逐 case 进度输出和耗时诊断；v6 表格、长多轮和更多跨库拒答样本已在 runtime ready 后定向跑到 `4/4 cases`、`6/6 turns`。当前 v1-v6 全量 suite 在临时 `qwen-math-turbo` 下为 `26/49 passed`，下一步应优先修正正向 expected terms / source grounding 失败，或恢复更合适的通用模型后复跑。
- **保留粮仓质量门禁作为基础回归**：粮仓检索质量已达到 `Recall@5=1.0`、`MRR@5=1.0`；后续导入、重建索引或调整检索参数时仍应保留 coverage / retrieval-only / API QA 三段验证。
- **补发布后的桌面安装体验验证**：当前已验证 packaged app 主进程、API 和前端加载；签名/公证后还需要覆盖首次安装、模型重新配置、文件上传/导入、preview、引用来源和跨 KB 隔离。

---

## 5. 测试与验证

### 5.1 可复用命令

```bash
# Python 全量回归，macOS 当前推荐使用 conda agent-kb 环境
/opt/miniconda3/envs/agent-kb/bin/python -m pytest -q

# api + server 覆盖率
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api tests/readers tests/utils \
  tests/test_rag_quality_eval_dataset.py \
  tests/test_rag_quality_eval_dataset_v2.py \
  tests/test_rag_quality_eval_dataset_v3.py \
  tests/test_rag_quality_eval_dataset_v4.py \
  tests/test_rag_quality_eval_dataset_v5.py \
  tests/test_rag_quality_eval_dataset_v6.py \
  tests/test_diag_roundtrip_support.py \
  tests/test_diag_utf8_import_roundtrip.py \
  tests/test_logging_utils.py tests/test_retriever.py tests/test_run_api.py \
  --cov=api --cov=server

# 前端纯函数/API/store 单测
node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js

# 前端构建
cd webapp && npm run build

# 粮仓知识库真实 QA 评测，需要 API 服务已启动且目标 KB 已具备索引
/opt/miniconda3/envs/agent-kb/bin/python -m scripts.run_grain_qa_eval \
  --cases data/grain-knowledge-base/qa/verified.jsonl \
  --api-base http://127.0.0.1:18080 \
  --kb-id grain-knowledge-base \
  --output docs/20260722-local-multi-kb-assistant/artifacts/grain-qa/qa-eval-report.json
```

### 5.2 2026-08-07 本机复核结果

本次复核使用 `/opt/miniconda3/envs/agent-kb/bin/python`（Python 3.12.13，`llama-index==0.11.19`）作为权威 Python 环境；默认 `/opt/miniconda3/bin/python` 是 base Python 3.13，不适合作为项目测试环境。

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest -q`：`677 passed, 35 warnings in 7.62s`
- `node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js`：`75 passed`
- `npm install` 后修复本地 `node_modules` 依赖；`chmod +x node_modules/.bin/vite node_modules/vite/bin/vite.js && npm run build`：通过，Vite 构建输出 `dist/`
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.run_grain_qa_eval --cases data/grain-knowledge-base/qa/verified.jsonl --api-base http://127.0.0.1:18080 --kb-id grain-knowledge-base --output docs/20260722-local-multi-kb-assistant/artifacts/grain-qa/qa-eval-report.json`：80 条用例评测完成，`error_count=0`、`Recall@5=0.5325`、`MRR@5=0.5238`、`citation_hit_rate=1.0`、`refusal_accuracy=0.6667`、`kb_isolation_rate=1.0`
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diagnose_grain_qa_coverage --cases data/grain-knowledge-base/qa/verified.jsonl --kb-id grain-knowledge-base --storage-dir storage --data-root data/grain-knowledge-base --output docs/20260807-grain-index-coverage-repair/artifacts/grain-coverage-diagnostic.json`：覆盖诊断通过，`local=82/82`、`docstore=82/82`、`kb_id=82/82`、`top5=78/82`；未命中项包含不可回答的隔离用例，不影响 answerable Recall gate。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diagnose_grain_qa_coverage.py tests/scripts/test_import_grain_kb_batches.py tests/scripts/test_run_grain_qa_eval.py tests/api/test_chat_service.py -q`：相关回归 `50 passed`。
- 2026-08-10 粮仓检索质量调优完成：检索-only 最终矩阵 `top5-dist_based_score-no-rerank` 达到 `answerable_total=77`、`Recall@5=1.0`、`MRR@5=1.0`、`retrieval_miss=0`、`rank_miss=0`、`source_noise=0`。
- 2026-08-10 切换可用模型 `阿里百联 / qwen-plus-2025-07-28` 后复跑粮仓 80 条 API QA：`error_count=0`、`Recall@5=1.0`、`MRR@5=1.0`、`citation_hit_rate=1.0`、`refusal_accuracy=1.0`、`kb_isolation_rate=1.0`；`retrieval_miss/rank_miss/source_noise/refusal_miss` 全部为 0。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"`：`702 passed, 1 deselected, 35 warnings`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pip install paddleocr==3.7.0 paddlepaddle==3.2.2`：补齐 OCR 运行时依赖；`paddle==3.2.2` 与 `paddleocr==3.7.0` 可直接导入。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pip check`：`No broken requirements found.`
- `/opt/miniconda3/envs/agent-kb/bin/python -c "from api.routers.health import _build_import_capabilities; ..."`：`pdf_text_extraction.ready=true`，`image_ocr.ready=true`，`fitz/paddleocr/paddle/pillow` 均 installed。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/readers/test_image_ocr.py -q`：`20 passed, 1 warning`
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/readers/test_image_ocr.py tests/api/test_chat_pdf_semireal.py -q`：`31 passed, 8 warnings in 2.99s`
- `/opt/miniconda3/envs/agent-kb/bin/python - <<'PY' ... extract_image_ocr_result(data/diag-image-ocr-1785485977/images/diag-ocr.png) ... PY`：`status=success`、`text_length=129`，PP-OCRv6 模型从 ModelScope 下载并缓存到 `~/.paddlex/official_models/` 后可复用。
- `KB_API_PORT=18083 /opt/miniconda3/envs/agent-kb/bin/python run_api.py` 后检查 `/api/health`：`embedding_warmup.state=ready`、`ocr_warmup.state=ready`、`image_ocr.ready=true`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_image_ocr_roundtrip --base-url http://127.0.0.1:18083 --kb-id diag-image-ocr-20260807-r2 --source-path temp/diag-ocr-20260807-r2.png --output-path temp/diag-image-ocr-20260807-r2-report.json --timeout 240`：通过；`ocr_attempted=true`、`indexed_from_ocr=true`、`source_saved_hash_match=true`、`chat_answer_has_expected_terms=true`、`preview_has_expected_terms=true`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_pdf_scan_roundtrip --base-url http://127.0.0.1:18083 --kb-id diag-pdf-scan-20260807-r2 --source-path temp/diag-scan-20260807-r2.pdf --output-path temp/diag-pdf-scan-20260807-r2-report.json --timeout 240`：通过；源文件和保存文件 hash 一致，PDF 文字层为空，`ocr_attempted=true`、`ocr_status=success`、`indexed_from_ocr=true`、`ocr_text_length=293`，问答、source、evidence 和 preview 均命中预期关键词。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_mixed_batch_roundtrip --base-url http://127.0.0.1:18083 --kb-id diag-mixed-batch-20260807-r2 --workspace-dir temp/diag-mixed-batch-20260807-r2 --output-path temp/diag-mixed-batch-20260807-r2-report.json --timeout 240`：通过；`run_passed=true`，文件保存 hash、嵌入图片 OCR、独立图片 OCR、PDF 文本层、资产注册和无证据拒答核心 gate 均通过；导入诊断为 `ocr_success_count=1`、`indexed_from_ocr_count=1`、`embedded_ocr_success_count=1`、`embedded_indexed_from_ocr_count=1`、`asset_registered_count=2`、`failed_files=0`。
- `cd webapp && npm audit fix` 后继续升级 `vite` 到 `8.2.1`、`@vitejs/plugin-react` 到 `6.0.5`，并用项目内轻量 router 替代 `react-router-dom`；`npm run build` 通过，前端 Node 单测仍为 `75 passed`。
- `cd webapp && npm audit --json`：`0 vulnerabilities`。
- `git diff --check`：通过。

### 5.3 2026-08-10 模型韧性与桌面 E2E 复核结果

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"`：`709 passed, 1 deselected, 35 warnings`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py tests/api/test_settings_routes.py tests/api/test_chat_service.py tests/scripts/test_run_grain_qa_eval.py -q`：`65 passed, 8 warnings`。
- `node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js`：`80 passed`，新增模型健康状态映射回归。
- `node --test desktop/src/python-process.test.js`：`2 passed`，确认桌面端优先使用 `NORTHAGENT_PYTHON` 或 `/opt/miniconda3/envs/agent-kb/bin/python`。
- `cd webapp && npm run build`：通过，桌面端可加载 `webapp/dist/index.html`。
- `electron@31.7.7` 在 macOS 上触发 `notarization indicates this code has been revoked`，表现为 `Electron.app` 被系统移除；已升级到 `electron@43.3.0` 后复核通过。
- `ELECTRON_ENABLE_LOGGING=1 NORTHAGENT_PYTHON=/opt/miniconda3/envs/agent-kb/bin/python npm run dev`：桌面端干净启动成功，runtime log 记录 `desktop_app_ready`、`python_api_starting`、`python_api_ready`、`renderer_resolved source=dist`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_desktop_model_workflow --base-url http://127.0.0.1:18080 --output-path docs/20260810-model-fallback-desktop-e2e/artifacts/desktop-model-workflow-report-after-electron-fix.json`：`run_passed=true`；验证模型选择/探活/健康状态、文件导入、定向 KB 问答、引用来源、preview 与 `default` 跨 KB 隔离。

### 5.4 2026-08-10 桌面发布预检与 Ollama fallback 增量验证

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py -q`：`17 passed, 2 warnings`，新增覆盖无 API Key 的 Ollama 本地模型 fallback 候选。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`5 passed, 1 warning`，覆盖跨 KB 正向命中、禁止精确泄漏、相似但允许的目标 KB 内容、来源 kb_id 缺失失败和报告落盘。
- `node --test webapp/src/domain/modelHealth.test.js`：`5 passed`，覆盖 fallback action hint 与 `source -> target` 切换标签。
- `node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js`：`80 passed`。
- `node --test desktop/scripts/*.test.js desktop/src/*.test.js`：`8 passed`。
- `cd webapp && npm run build`：通过。
- `cd desktop && npm run build:mac && npm run verify:package`：通过，产物包括 `desktop/dist/NorthAgent-0.1.0-arm64.dmg` 和 `desktop/dist/NorthAgent-0.1.0-arm64-mac.zip`；packaged resources 包含 `webapp/dist`、`run_api.py`、`config.py`、`requirements.txt`、`api/`、`server/` 和 `utils/`。
- 直接从 packaged app resources 启动 API 并检查 `/api/health`、`/api/model/options`：通过。
- packaged app 主进程启动验证：通过，加载 packaged `webapp/dist/index.html`，前端请求 `/api/model/options`、`/api/kb`、`/api/chat/history`。
- `node desktop/scripts/release-preflight.js`：通过非严格预检，确认 Electron bundle 存在；当前本机缺少 `APPLE_ID`、`APPLE_APP_SPECIFIC_PASSWORD`、`APPLE_TEAM_ID` 和 Developer ID Application 证书，但 `notarytool` 可用，严格签名/公证预检需补齐凭证后再跑。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report.json`：`6/6 passed`；覆盖 `grain-knowledge-base`、`diag-desktop-e2e-1786353063`、`diag-kb-utf8-1785505921` 三个 KB 的正向回答和负向隔离。UTF-8 边界问题打到粮仓 KB 时允许 grain 自身相似边界内容，但禁止 `文件夹只承担组织作用` 等精确短语和来源泄漏。
- `cd desktop && npm audit fix` 后 `npm audit --json`：剩余 `8 vulnerabilities`，其中 `7 high`、`1 critical`；主要需要单独评估 `electron-builder` 大版本升级。
- `git diff --check`：通过。

### 5.5 2026-08-11 跨 KB 泛化扩容验证

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`8 passed, 1 warning`，新增覆盖多 KB 契约拒绝、focus 汇总、同义关键词组和更宽的真实 KB 用例。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v3.json`：`17/17 passed`；覆盖 grain、desktop、image-ocr、pdf-scan、mixed-batch、boundary、exttext、cross-domain 和 contract 九类 focus，`positive/negative/contract` 均为 `100%`。
- 报告产物 `cross-domain-kb-eval-report-v3.json` 中，image-ocr、pdf-scan、mixed-batch、boundary、exttext 等领域的正向回答与负向隔离均通过；多 KB 查询契约拒绝也按预期 `400` 返回。

### 5.6 2026-08-11 桌面发布预检边界加固

- `node --test desktop/scripts/release-preflight.test.js desktop/scripts/notarize-mac.test.js`：`15 passed`，新增覆盖非严格缺项摘要、严格缺凭证失败、严格全量 gate 通过、Electron bundle 缺失失败、Developer ID 解析和 `notarytool` 探测。
- `node --test desktop/scripts/*.test.js desktop/src/*.test.js`：`17 passed`。
- `cd desktop && node scripts/release-preflight.js --strict`：按预期失败，原因是本机缺少 `APPLE_ID`、`APPLE_APP_SPECIFIC_PASSWORD`、`APPLE_TEAM_ID`。
- `cd desktop && npm run build:preflight`：非严格模式通过；`verify-release-config` 确认 release config ready，随后提示本机缺少 Apple 签名/公证环境变量和 Developer ID Application 证书，但 `notarytool` 可用。
- `node --test desktop/src/*.test.js desktop/scripts/*.test.js`：`24 passed`，新增 `desktop/src/csp.test.js` 覆盖 CSP 连接源与 URL origin 解析，`desktop/scripts/verify-release-config.test.js` 覆盖 notarize hook、hardened runtime、entitlements、mac target 和 packaged runtime resources。
- `git diff --check`：通过。

### 5.7 2026-08-11 fallback 探测摘要增量复核

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py tests/api/test_settings_routes.py tests/api/test_chat_service.py -q`：`55 passed, 8 warnings`。
- `node --test webapp/src/domain/modelHealth.test.js webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js`：`81 passed`。
- `cd webapp && npm run build`：通过，`ModelsPage` 和 `AgentPage` 能展示 `probeSummary`。

### 5.8 2026-08-11 跨 KB 泛化扩容复核

- `node --test webapp/src/domain/modelHealth.test.js`：`7 passed`，覆盖 Ollama 本地候选提示。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`9 passed, 1 warning`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v4.json`：`21/21 passed`。
- 新增用例覆盖 grain 安全生产、desktop evidence preview、UTF-16 边界、旧 desktop passcode 隔离和更多 cross-domain 负向组合。

### 5.9 2026-08-11 跨 KB 泛化再扩容 v5

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`9 passed, 1 warning`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v5.json`：`23/23 passed`。
- 新增用例继续补强旧桌面 passcode、extensionless UTF-8 folder boundary 和真实跨域隔离组合，评测面扩到 23 条。

### 5.10 2026-08-11 当前状态复核

- `git fetch --prune` 后 `git status --short --branch`：工作区干净，当前分支 `codex/desktop-agent-stage3` 跟踪 `origin/codex/desktop-agent-stage3`。
- `git rev-list --left-right --count HEAD...@{u}`：`0 0`，确认本地与远端一致。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"`：`719 passed, 1 deselected, 35 warnings in 7.78s`。
- `node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js`：`82 passed`。
- `node --test desktop/src/*.test.js desktop/scripts/*.test.js`：`24 passed`。
- `cd webapp && npm run build`：通过，Vite 生产构建输出 `dist/`。
- `cd desktop && npm run build:preflight`：release config verifier 通过；非严格 preflight 提示缺少 Apple 发布环境变量和 Developer ID Application 证书，`notarytool` 和 Electron bundle 可用。
- `cd desktop && npm run build`：通过，已产出 `dist/NorthAgent-0.1.0-arm64.dmg` 与 `dist/NorthAgent-0.1.0-arm64-mac.zip`，`electron-builder` 26.15.3 在未签名环境下可正常打包。
- `security find-identity -v -p codesigning`：`0 valid identities found`，确认正式签名/公证仍被外部证书条件阻塞。
- `cd webapp && npm audit --json`：`0 vulnerabilities`。
- `cd desktop && npm audit --json`：`0 vulnerabilities`。
- `git diff --check`：通过。

### 5.11 2026-08-11 外部跨领域样本追加验证

- `scripts/diag_cross_domain_kb_eval.py` 新增 `{ "cases": [...] }` 外部用例格式、可重复 `--extra-cases` 追加、`case_source` 报告字段和重复 case id 失败保护，后续扩真实资料集时不再需要直接修改 Python 内置用例。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`12 passed, 1 warning`。
- 新增外部样本文件：`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json`，覆盖粮仓适用对象、一卡通收储库点和跨库负向隔离。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6.json`：`27/27 passed`；默认基线 `23/23`，外部追加样本 `4/4`，`positive/negative/contract` 均为 `100%`。

### 5.12 2026-08-11 fallback 结构化探测摘要复核

- `api/services/model_service.py` 新增 `fallback_attempt_summary`，汇总 fallback 候选探测的总数、可用数、失败数、Ollama 候选数、Ollama 可用数和最近一次候选明细。
- `webapp/src/domain/modelHealth.js` 优先使用结构化摘要生成 `probeSummary`；当 Ollama 候选全部不可用时，`unavailable` 提示会明确提醒检查 Ollama 是否启动、目标模型是否已拉取。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py -q`：`18 passed, 2 warnings`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py tests/api/test_settings_routes.py tests/api/test_chat_service.py -q`：`56 passed, 8 warnings`。
- `node --test webapp/src/domain/modelHealth.test.js`：`8 passed`。
- `node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js`：`83 passed`。

### 5.13 2026-08-11 多轮追问跨领域评测复核

- `scripts/diag_cross_domain_kb_eval.py` 新增 `turns` 多轮用例格式；同一 case 内按顺序复用同一个本次评测专用 `session_id`，报告记录顶层 case 结果、`turn_count`、`passed_turn_count`、`failed_turn_ids` 和每一轮的 checks / answer preview / source KB。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`14 passed, 1 warning`，新增覆盖多轮 session 复用、逐轮汇总和任一轮失败时顶层 case 失败。
- 新增外部样本文件：`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v3.json`，覆盖粮仓正向追问、桌面 evidence preview 正向追问和粮仓 KB 内追问桌面 passcode 的负向隔离。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v2.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v3.json --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v8.json`：`36/36 passed`；默认基线 `23/23`，v1 `4/4`，v2 `6/6`，v3 多轮 `3/3`，逐轮 `39/39 passed`；`multi-turn`、`follow-up`、`cross-kb-isolation` 等 tag 切片均为 `100%`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"`：`725 passed, 1 deselected, 35 warnings`。

### 5.14 2026-08-11 来源文件级跨领域评测复核

- `scripts/diag_cross_domain_kb_eval.py` 新增 `required_source_files` / `forbidden_source_files` 断言，报告同步输出 `source_files`，用于证明回答不只命中目标 KB，还命中了目标文件或避开了禁止文件。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`16 passed, 1 warning`，新增覆盖 required source file 命中和 forbidden source file 失败。
- 新增外部样本文件：`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v4.json`，覆盖粮仓守则、桌面 workflow、扫描 PDF、图片 OCR 和 mixed batch cutover 的来源文件落点。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v2.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v3.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v4.json --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v9.json`：`41/41 passed`；默认基线 `23/23`，v1 `4/4`，v2 `6/6`，v3 `3/3`，v4 source-grounding `5/5`，逐轮 `44/44 passed`；`source-grounding` tag 切片为 `100%`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"`：`727 passed, 1 deselected, 35 warnings`。

### 5.15 2026-08-11 Evidence 文本级跨领域评测复核

- `scripts/diag_cross_domain_kb_eval.py` 新增 `required_source_text_terms` / `forbidden_source_text_terms` 断言，检查范围只包含 `sources` / `evidence` 正文，不把模型最终答案计入证据文本。
- `scripts/diag_cross_domain_kb_eval.py` 新增 `duration_ms`、`turn_duration_total_ms`、`duration_summary` 和 `--slow-threshold-ms`，用于记录 case/turn 耗时、平均耗时、最慢 case/turn 与慢用例列表。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`20 passed, 1 warning`，新增覆盖 required evidence text 命中、forbidden evidence text 泄漏失败、失败检查项 / case / turn 归因汇总，以及耗时诊断汇总。
- 新增外部样本文件：`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v5.json`，覆盖桌面 evidence preview、扫描 PDF OCR fallback、图片 OCR 边界和 mixed batch rollback approval 的 evidence 文本依据。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v2.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v3.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v4.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v5.json --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v10.json`：`45/45 passed`；默认基线 `23/23`，v1 `4/4`，v2 `6/6`，v3 `3/3`，v4 `5/5`，v5 evidence-text `4/4`，逐轮 `48/48 passed`；`source-grounding` 和 `evidence-text` tag 切片均为 `100%`，`failure_check_summary={}`、`failure_case_summary=[]`；`duration_summary.case_total_ms=73247.147`、`case_avg_ms=1627.714`，最慢 case 和 slow case 均为 `grain-negative-utf8-exact-boundary`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"`：`731 passed, 1 deselected, 35 warnings`。

### 5.16 2026-08-11 macOS release 后置校验链路

- `desktop/scripts/verify-mac-release.js` 新增 `.app` 发布信任链校验：`codesign --verify --deep --strict`、`spctl --assess --type execute` 和 `xcrun stapler validate`。
- `desktop/package.json` 的 `release:mac` 已在 `electron-builder --mac` 后串起 `verify:package` 和 `verify:mac-release`；`desktop/scripts/verify-release-config.js` 同步把这两步纳入 release config gate，避免正式发布绕过包内容、签名、Gatekeeper 和 notarization ticket 校验。
- `node --test desktop/scripts/verify-mac-release.test.js desktop/scripts/verify-release-config.test.js desktop/scripts/verify-package.test.js desktop/scripts/release-preflight.test.js desktop/scripts/notarize-mac.test.js desktop/scripts/build-target.test.js`：`36 passed`。
- `cd desktop && npm run build:preflight`：通过；非严格预检仍提示缺少 `APPLE_ID`、`APPLE_APP_SPECIFIC_PASSWORD`、`APPLE_TEAM_ID` 和 Developer ID Application 证书，`notarytool` 可用。
- `cd desktop && npm run verify:package`：通过，当前 `desktop/dist` 包内容可解析。
- `cd desktop && node scripts/verify-mac-release.js`：非严格诊断按预期指出当前 `.app` 尚未完成正式签名/公证，codesign/Gatekeeper 校验失败且没有 stapled notarization ticket；补齐 Apple 凭证和 Developer ID Application 证书后，正式 `npm run release:mac` 会把这些后置检查作为阻断 gate。

### 5.17 2026-08-11 fallback Ollama 动态发现边角复核

- `api/services/model_service.py` 在 Ollama provider 配置为 `models: []` 且动态发现失败时，会保留一个 `discovery_only` 诊断候选，不再让 UI 只看到 `candidate_count=0` 的泛化不可用状态。
- `fallback_attempt_summary` 现在能把 `ollama_unreachable`、`ollama_no_models`、`model_not_found` 等 Ollama 边角原因传给前端；`webapp/src/domain/modelHealth.js` 会分别提示启动 Ollama / 修正 `http://localhost:11434` 地址、执行 `ollama pull qwen2.5:7b`、或拉取缺失目标模型。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py -q`：`19 passed, 2 warnings`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py tests/api/test_settings_routes.py tests/api/test_chat_service.py -q`：`57 passed, 8 warnings`。
- `node --test webapp/src/domain/modelHealth.test.js`：`10 passed`。
- `node --test webapp/src/domain/*.test.js webapp/src/api/*.test.js webapp/src/store/*.test.js`：`85 passed`。
- `cd webapp && npm run build`：通过。

### 5.18 2026-08-11 v6 跨领域扩面试跑

- 当前模型配置复核：`阿里百联 / qwen-plus-2025-07-28` 和 `qwen3.7-plus` 返回 `AllocationQuota.FreeTierOnly`；`ely / qwen-flash` 返回 401；`阿里百炼 / qwen-flash` 与 `deepseek-v4-flash` 返回 `model_not_found`；临时切到 `阿里百联 / qwen-math-turbo` 后基础粮仓 RAG smoke 通过。
- `scripts/diag_cross_domain_kb_eval.py` 新增底层 `TimeoutError` 捕获，超时会落为 `_http_status=-1` 的失败响应，不再中断整轮评测。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`21 passed, 1 warning`。
- 新增试验样本文件：`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v6.json`，覆盖 README 表格、mixed batch 三轮追问、桌面对 grain README 的负向隔离、图片 OCR 对 mixed rollback approval 的负向隔离。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --timeout 45 --cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v6.json --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6-only-v2.json`：`2/4 passed`，两个 cross-KB negative case 均通过；失败集中在 README 表格 expected terms 未命中，以及 mixed batch `approval` turn 在 45 秒内超时。

### 5.19 2026-08-12 模型选择即时探活

- `api/services/model_service.py` 的 `/api/model/select` 服务路径现在会在保存当前模型后立即调用轻量探活；坏 token、额度耗尽、模型不存在或 Ollama 未就绪时会把 `model_health.state` 写为 `unavailable`，并写入 `last_error_kind`、`fallback_attempts` 和 `fallback_attempt_summary`，不再把只保存成功的配置误标为 `healthy`。
- 自动 fallback 已经探活过候选时，会把探活结果传给 `select_model` 复用，避免成功切换时重复请求同一个候选。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py -q`：`20 passed, 2 warnings`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_model_service.py tests/api/test_settings_routes.py tests/api/test_chat_service.py -q`：`58 passed, 8 warnings`。
- `node --test webapp/src/domain/modelHealth.test.js`：`10 passed`。

### 5.20 2026-08-12 跨领域评测系统性故障归因

- `scripts/diag_cross_domain_kb_eval.py` 的 summary 新增 `systemic_failure_summary`，会按 turn 粒度统计 `http_status_ok` 失败比例，并把大面积 quota、401、model_not_found、network/timeout 等问题归因为 `model_or_api_unavailable`，避免把模型层故障误读为知识库泛化整体退化。
- 对 `cross-domain-kb-eval-report-v11.json` 这类额度耗尽报告重新汇总时，可识别 `suspected=true`、`dominant_error_kind=quota_exhausted`、`http_failure_rate=0.9815`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`23 passed, 1 warning`。

### 5.21 2026-08-12 跨领域评测 preflight

- `scripts/diag_cross_domain_kb_eval.py` 新增 `--preflight` 参数；开启后会先用首个 case 做模型/API 探活，若发现 quota、401、model_not_found、network/timeout 等模型/API 层故障，会提前写出带 `preflight.aborted=true` 的诊断报告，不再继续消耗完整评测矩阵。
- preflight 通过时仍会继续执行完整 case 集；默认不启用，既有评测命令和历史报告结构保持兼容。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`25 passed, 1 warning`。

### 5.22 2026-08-12 桌面复用已运行 API

- `desktop/src/python-process.js` 新增 `ensurePythonApi`：桌面启动时先检查 `http://127.0.0.1:18080/api/health`，如果 API 已经可用，就记录 `python_api_reusing_existing` 并直接进入渲染，不再额外 spawn `run_api.py` 造成端口占用错误日志。
- 如果 API 不可用，仍会按原逻辑选择 conda `agent-kb` Python 并启动 `run_api.py`。
- `server/stores/config_store.py` 在 `put/delete` 后会把 `config_store.json` 重新写成缩进 JSON，并保留中文原文，便于桌面/网页重新配置模型后人工核对和恢复。
- `node --test desktop/src/python-process.test.js`：`4 passed`。
- `node --test desktop/src/python-process.test.js desktop/src/csp.test.js desktop/scripts/verify-release-config.test.js desktop/scripts/release-preflight.test.js desktop/scripts/build-target.test.js desktop/scripts/verify-package.test.js desktop/scripts/verify-mac-release.test.js desktop/scripts/notarize-mac.test.js`：`44 passed`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_config_store.py -q`：`2 passed, 2 warnings`。
- 实测在 API 已运行时重启桌面，`storage/logs/desktop_runtime.log` 写入 `python_api_reusing_existing`，不再出现新的 `address already in use` 子进程错误。

### 5.23 2026-08-12 README 表格字段问答兜底

- `api/services/chat_service.py` 新增 source-backed Markdown 表格字段兜底：当问题明确询问“表里/字段”的具体值，且来源文本包含 Markdown 表格时，优先按表格行抽取字段值补齐答案，避免模型把 `file_type=text/markdown` 这类 metadata 误答成正文表格里的“主要格式”。
- `scripts/diag_cross_domain_kb_eval.py` 将 `Broken pipe`/timeout 等断流归为 `network_error`，preflight/summary 能更明确地区分模型链路问题和真实业务断言失败。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_chat_service.py tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`50 passed, 7 warnings`。
- 真实 v6 extra 复跑时 preflight 首个 case 在 60 秒内 `timed out`，报告输出 `dominant_error_kind=network_error`；同时重启后 embedding warmup 仍处于 `warming`，因此本轮不把真实 v6 结果作为功能回归失败结论；待稳定通用模型和 runtime ready 后继续复跑。

### 5.24 2026-08-12 embedding 预热 stale 诊断

- 现状复核：`git status --short --branch` 显示当前分支 `codex/desktop-agent-stage3...origin/codex/desktop-agent-stage3`，`git rev-list --left-right --count HEAD...@{u}` 为 `0 0`；API `http://127.0.0.1:18080/api/health` 可访问，Web `http://127.0.0.1:5174/` 可访问。
- 运行态问题：API 进程使用 `/opt/miniconda3/envs/agent-kb/bin/python`，OCR 预热 `ready`，但 `embedding_warmup.state=warming`、`loaded_model=null`、`is_ready=false` 持续数分钟；独立进程初始化 `bge-small-zh-v1.5` 在 45 秒内未返回。
- `api/runtime.py` 的 embedding 预热状态新增 `elapsed_ms`、`is_stale`、`stale_after_ms` 和 `thread_alive`；当后台预热超过 120 秒或线程已不存活但状态仍是 warming 时，健康检查对外显示 `state=stale`，避免长期误读为正常预热中。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_runtime_model_loading.py -q`：`32 passed, 2 warnings`。

### 5.25 2026-08-12 embedding 缓存诊断与 v6 复跑

- `server/models/embedding.py` 新增 `get_embedding_model_diagnostics()`，返回当前 embedding 名称、支持列表、HuggingFace 模型路径、本地 `localmodels/` 路径、缓存是否存在、加载来源、HF mirror 和预下载建议。
- `/api/health` 新增 `embedding_diagnostics` 字段。注意：当前 18080 运行中的旧 API 进程尚未重启，因此实时 curl 暂不包含该新字段；代码和 TestClient 路径已通过测试，API 下次启动后生效。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/test_embedding_model_diagnostics.py tests/api/test_health_route.py tests/api/test_runtime_model_loading.py -q`：`38 passed, 3 warnings`。
- runtime ready 后复跑 v6 extra：`/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --timeout 60 --preflight --cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v6.json --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6-after-embedding-diagnostics.json`，结果 `4/4 passed`、逐轮 `6/6 passed`，`systemic_failure_summary.suspected=false`。

### 5.26 2026-08-12 v1-v6 全量 suite 基线

- `scripts/diag_cross_domain_kb_eval.py` 新增 `--suite v1-v6`，一键加载默认 23 条和 `cross-domain-extra-cases-v1.json` 到 `cross-domain-extra-cases-v6.json` 的 26 条外部真实样本；CLI 同步新增逐 case 进度输出，避免长评测无反馈。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`29 passed, 1 warning`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --timeout 60 --preflight --suite v1-v6 --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v1-v6-suite.json`：`26/49 passed`、逐轮 `30/54 passed`；`negative_total=15`、`negative_pass_rate=1.0`，`contract_total=1`、`contract_pass_rate=1.0`，`positive_pass_rate=0.303`。
- 当前失败不是系统性模型/API 故障：`systemic_failure_summary.suspected=false`，HTTP/network 失败仅 2 个 turn；主要失败项为 `expected_terms_hit=24`，并集中在桌面诊断正向、UTF-16/extensionless 文本、长问题、多跳、多轮追问和 source/evidence grounding。

### 5.27 2026-08-12 source-backed 精确短语保真与 embedding 缓存准备

- 失败分析显示，部分正向 expected terms 已经由 source 命中，但模型会破坏精确 token/短语，例如把 `northagent-desktop-e2e-1786353063` 改成 `northagent desktop-e2e-1786353063`，或把 `OCR fallback` 粘成 `OCRfallback`。
- `api/services/chat_service.py` 新增 source-backed 精确短语修复：当问题明确索要 unique/exact/passcode 或 `what does/what should/what must` 类 source 原文短语，且 source `text/excerpt` 中存在高置信 hyphen token 或固定短语时，优先返回 source 原句或附加精确来源短语。该逻辑不处理拒答，不从文件名/title 抽词，降低误补风险。
- 使用 `KB_API_PORT=18084 /opt/miniconda3/envs/agent-kb/bin/python run_api.py` 验证新代码 health 路径，`embedding_diagnostics.local_path_exists=false`、`load_source=remote`、`hf_endpoint=https://hf-mirror.com`，并返回预下载 `localmodels/` 的建议；18084 在 120 秒后进入 `embedding_warmup.state=stale`，证明复跑全量 suite 的前置阻塞是本地 embedding 缓存缺失。
- `scripts/prepare_embedding_model_cache.py` 新增本地 embedding 缓存准备入口：默认 dry-run 输出诊断，显式 `--download` 才调用 `huggingface_hub.snapshot_download` 下载到 `localmodels/BAAI/bge-small-zh-v1.5`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.prepare_embedding_model_cache`：确认 `local_path_exists=false`、`load_source=remote`、`skipped=true`、`downloaded=false`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_prepare_embedding_model_cache.py tests/api/test_chat_service.py tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`59 passed, 7 warnings`。

### 5.28 2026-08-12 embedding 运行时远程下载禁用

- `config.py` 新增 `EMBEDDING_ALLOW_REMOTE_DOWNLOAD` 开关，默认关闭；只有显式设置为 `1/true/yes/on` 时，运行时 embedding 初始化才允许回退远程下载。
- `server/models/embedding.py` 在本地缓存缺失且未开启远程下载时会快速失败，清空 `Settings._embed_model` 并返回 `None`，避免 `Settings.embed_model = None` 被 LlamaIndex 转成 `MockEmbedding` 后误报可用。
- `scripts.prepare_embedding_model_cache` 显式传 `--download` 时仍会以允许远程的诊断口径执行预下载；普通 runtime health 则展示 `allow_remote_download=false` 和预下载建议。
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/test_embedding_model_diagnostics.py tests/api/test_health_route.py tests/api/test_runtime_model_loading.py tests/scripts/test_prepare_embedding_model_cache.py -q`：`44 passed, 3 warnings`。
- `KB_API_PORT=18084 /opt/miniconda3/envs/agent-kb/bin/python run_api.py` 后请求 `/api/health`：`embedding_warmup.state=failed`、`is_ready=false`、`embedding_diagnostics.allow_remote_download=false`、`local_path_exists=false`，临时 API 秒级返回诊断，不再等待到 120 秒 stale。

---

## 6. 已知问题和限制

- **macOS 要使用 conda `agent-kb` 环境**：默认 `python` 仍可能指向 Miniconda base 3.13，缺项目依赖；非交互命令建议直接用 `/opt/miniconda3/envs/agent-kb/bin/python`。
- **mixed batch 正向问答会返回多个候选 sources**：2026-08-07 真实 roundtrip 中 4 个正向用例的首要/目标文档、preview 和核心关键词均命中，但精确 `source_count_match/evidence_count_match` 为 false，因为接口会返回多个相关候选证据；这不影响当前核心 gate，但后续若产品要求“一问一证据”或更少引用噪声，需要收口 rerank/top-k 或前端展示策略。
- **多知识库仍是逻辑隔离，不是物理多索引隔离**：原始文件已按 `data/{kb_id}/` 目录化，但 `storage/` 仍是共享索引/共享存储，隔离主要依赖 metadata filter。
- **旧数据兼容仍可能放宽过滤**：迁移期对缺失 `kb_id` metadata 的历史节点仍需谨慎处理；真实数据重建或清理策略仍是后续工作。
- **粮仓知识库检索质量已收口，下一步转向扩样本泛化**：QA 期望文档已达到 `docstore=82/82`、正确 `kb_id=82/82`；本轮检索-only 与 API QA 均达到 `Recall@5=1.0`、`MRR@5=1.0`。跨 KB 泛化已有默认 23 条正/负向/契约用例门禁，并支持通过 `--extra-cases` 或 `--suite v1-v6` 追加外部真实样本、`turns` 多轮追问样本、来源文件级断言和 evidence 文本级断言；当前 v1-v6 全量 suite 暴露出正向泛化仍不足，但负向隔离和 contract 已稳定。下一步应先准备本地 embedding 缓存或显式允许远程下载，再复跑 source-backed 精确短语修复后的全量 suite，之后继续处理 UTF-16/extensionless、长多轮和 grounding 失败。
- **embedding 初始化仍需进一步收口**：2026-08-12 复核发现默认 `bge-small-zh-v1.5` 初始化冷启动耗时约 626 秒，独立进程 45 秒内不会返回；健康检查已能标记 stale，并补充本地缓存/远程下载诊断和预下载建议。当前新增 `scripts.prepare_embedding_model_cache` 可显式预下载本地缓存，但本机下载实测因 HuggingFace `ConnectTimeout` 失败，`local_path_exists=false` 仍未解除；runtime 已默认禁用远程下载并快速失败，剩余问题是准备模型缓存或提供可用下载代理。
- **OCR 质量口径仍偏基础**：当前主要关注 OCR 成功、关键词/问答命中和回执诊断，尚未系统覆盖 CER、表格结构、版面顺序等细指标。
- **README 与实际主线有代际差异**：README 仍以 ThinkRAG + Streamlit 为主叙述，当前实际主线是 FastAPI + React + Electron + Agent 工作台。
- **命名仍在过渡**：仓库、README、Web package 仍出现 ThinkRAG；桌面端 package/product 已使用 NorthAgent。
- **桌面端正式发布尚未完成**：已补 CSP、macOS release preflight、hardened runtime、entitlements、dmg/zip 打包、packaged app 启动验证、包内容校验和 mac release 后置签名/公证校验；preflight 已能检查 Apple Developer 环境变量、Developer ID Application 证书和 `notarytool`，`verify-mac-release` 已能检查 codesign、Gatekeeper 和 stapler，但本机尚未配置实际签名/公证凭证和 Developer ID 证书，不能宣称已完成正式公证发布。
- **桌面端依赖安全已收口**：Electron 已从被 macOS 撤销公证的 `31.7.7` 升级到 `43.3.0` 并恢复启动，`electron-builder` 也已升级到 `26.15.3`，`desktop npm audit` 当前为 `0 vulnerabilities`。
- **占位词扫描仍会命中规范和历史计划文本**：当前占位词扫描命中 `AGENTS.md` 的禁用规则本身，以及 `docs/superpowers/plans/2026-05-28-desktop-knowledge-agent-mvp.md` 的历史自查项；旧 Streamlit `frontend/state.py` 的占位注释已清理。

---

## 7. 文档导航

| 文档 | 内容 |
|---|---|
| `AGENTS.md` | 仓库级开发流程规范：PRD -> Plan -> Code -> Test Plan -> Test Report -> Commit/Push |
| `docs/project.md` | 当前项目总览、进度、验证和风险 |
| `docs/guide/DOCS_INDEX.md` | 文档体系导航索引 |
| `docs/20260722-local-multi-kb-assistant/` | 当前正式基线：本地多知识库助手主线 |
| `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-test-report.md` | 2026-07-31 Stage 3 测试报告 |
| `docs/20260722-local-multi-kb-assistant/artifacts/grain-qa/qa-eval-report.json` | 2026-08-07 粮仓知识库 QA 评测报告产物 |
| `docs/20260807-grain-qa-expansion/` | 粮仓 QA 80 条扩测与失败分组报告 |
| `docs/20260807-grain-index-coverage-repair/` | 粮仓知识库索引覆盖修复计划 |
| `docs/20260810-grain-retrieval-quality-tuning/` | 粮仓检索排序质量调优、实验矩阵和最终测试报告 |
| `docs/20260810-model-fallback-desktop-e2e/` | 模型 fallback、模型健康状态、评测断点续跑和桌面端 E2E 验证 |
| `docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-release-checklist.md` | macOS 签名、公证、打包和安装后回归清单 |
| `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v3.json` | 跨知识库、跨领域真实问答和隔离诊断报告 |
| `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v4.json` | 跨知识库、跨领域真实问答和隔离诊断报告（扩容版） |
| `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v5.json` | 跨知识库、跨领域真实问答和隔离诊断报告（再扩容版） |
| `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json` | 跨领域真实业务追加样本 |
| `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6.json` | 默认基线 + 外部追加样本的跨领域诊断报告 |
| `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v2.json` | 跨领域真实业务追加样本（长问题 / 多跳 / OCR / 拒答） |
| `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v7.json` | 默认基线 + v1/v2 外部追加样本的跨领域诊断报告 |
| `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v3.json` | 跨领域真实业务追加样本（多轮追问 / follow-up / 跨库隔离） |
| `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v8.json` | 默认基线 + v1/v2/v3 外部追加样本的跨领域多轮诊断报告 |
| `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v4.json` | 跨领域真实业务追加样本（来源文件级 grounding） |
| `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v9.json` | 默认基线 + v1/v2/v3/v4 外部追加样本的跨领域来源 grounding 诊断报告 |
| `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v5.json` | 跨领域真实业务追加样本（evidence 文本 grounding） |
| `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v10.json` | 默认基线 + v1/v2/v3/v4/v5 外部追加样本的跨领域 evidence 文本诊断报告 |
| `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v6.json` | 跨领域真实业务追加样本试验版（表格 / 长多轮 / 拒答隔离） |
| `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6-only-v2.json` | v6 试验样本定向诊断报告 |
| `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v11.json` | v1-v6 全量试跑失败报告，主要受模型额度耗尽影响 |
| `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v1-v6-suite.json` | `--suite v1-v6` 全量跨领域基线报告，当前用于正向泛化优化 |
| `docs/20260714-kb-directory-storage/` | 多知识库目录化存储专题 |
| `docs/20260715-grain-kb-evaluation/` | 粮仓知识库导入与人工验收指南 |
| `docs/20260716-kb-upload-target-selection/` | 上传目标显式选择与 multipart 400 修复专题 |
| `docs/20260717-agent-qa-page-refactor/` | `/agent` 页面重构与 retriever 加固专题 |
| `docs/spec/desktop_api_contract.md` | 页面到 API 契约 |
| `docs/spec/desktop_project_design.md` | 桌面端设计 |
| `docs/troubleshooting/` | 排障记录 |
| `docs/interview/dev-stories/` | 开发故事沉淀 |
| `评审建议.txt` | 最新评审意见 |

---

## 8. 最近提交

| hash | 说明 |
|---|---|
| `f86e030` | chore: update dev story capture state |
| `a4ce181` | feat(eval): summarize cross-domain failure checks |
| `3cee902` | chore: update dev story capture state |
| `3d3edc3` | feat(eval): assert cross-domain evidence text |
| `74bcf37` | chore: update dev story capture state |
| `fd19749` | feat(eval): assert cross-domain source files |
| `0236357` | chore: update dev story capture state |
| `7363acc` | feat(eval): add multi-turn cross-domain diagnostics |
| `80dfa50` | docs(project): sync matching artifact verifier status |
| `e488c87` | chore: update dev story capture state |
| `92238b9` | fix(desktop): prefer matching mac package artifacts |
| `e182ea4` | docs(project): sync universal package layout status |
| `ab1bc99` | chore: update dev story capture state |
| `d96e991` | test(desktop): cover universal package layout |
| `268071d` | docs(project): sync package layout verifier status |
| `3b408de` | chore: update dev story capture state |
| `af71677` | fix(desktop): discover mac package layouts |
| `5110e46` | docs(project): sync package verifier status |
| `bf89aa3` | chore: update dev story capture state |
| `e09bbf3` | refactor(desktop): make package verifier testable |
| `9ad676f` | chore: update dev story capture state |
| `06f26eb` | fix(desktop): gate mac build target with release preflight |
| `630bbee` | chore: update dev story capture state |
| `5a905a1` | fix(desktop): chain build preflight into release mac |
| `6b8bea9` | chore: update dev story capture state |
| `8b007f0` | feat(eval): add tagged cross-domain expansion |
| `e482db2` | chore: update dev story capture state |
| `c43bf1e` | feat(model): add structured fallback probe summary |
| `7968ac1` | docs(project): sync fallback probe status |
| `e6f5c41` | feat(eval): support extra cross-domain cases |
| `d85bcae` | chore: update dev story capture state |
| `3a7df45` | fix(desktop): upgrade builder release preflight |
| `005fc60` | docs(project): sync current project status |
| `4565955` | chore: update dev story capture state |
| `88044b7` | feat(desktop): verify release config gates |
| `b065cc7` | chore: update release story state |
| `63b4606` | docs(desktop): add mac release checklist |
| `537fe7a` | chore: update dev story capture state |
| `85795af` | feat(desktop): add csp unit coverage |
| `470bdf3` | chore: update dev story capture state |
| `3e17026` | feat(eval): expand cross-domain v5 coverage |
| `8e0cb12` | chore: update dev story capture state |
| `b6e3837` | docs(project): sync cross-domain expansion |
| `40ff7d8` | feat(ui): surface fallback probe summaries |
| `f82d316` | fix(model): support local ollama fallback discovery |
| `e9855fd` | test(eval): expand cross-domain kb diagnostics |
| `caad7b9` | docs(desktop): document fallback and release checks |
| `6005d4e` | feat(desktop): add release preflight checks |
| `fcf951f` | chore(desktop): update electron dependencies |
| `233f84c` | feat(desktop): add csp header |
| `4b5bab0` | feat(desktop): add mac release verification |
| `3d679d7` | chore: update dev story capture state |

查看完整历史：`git log --oneline -30`
