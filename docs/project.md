# 项目总览 (docs/project.md)

> 本文档面向所有协作者（含 AI 助手），用于快速了解项目当前进度、架构和已知问题。
> **维护规则**：每次有意义的提交后更新本文的「最近提交」与「当前进度」「已知问题」三节；重大架构变化更新「架构」节。日期使用绝对日期。

最近更新：2026-07-16

---

## 1. 项目简介

本项目是 **ThinkRAG**（基于 LlamaIndex + Streamlit 的本地知识库 RAG 系统）的改造分支，代号 **agent-kb** / 桌面端 **NorthAgent**。

在原版「单库 Streamlit 问答」基础上，当前主要有两条改造主线：

1. **多知识库 + 后端化**：用 FastAPI 重写后端，支持知识库管理、导入、问答接口，React 重写 Web 前端，Electron 作为桌面壳。
2. **Agent 化**：加入任务规划、工具注册、命令风险分级（L0-L3）、人工审批流，往「智能体 + 工具调用」方向演进。

面向国内用户的工程取向比较明确：中文文本处理、DeepSeek/Moonshot/Zhipu 等国产 LLM、BGE 中英双语嵌入模型、本地桌面运行体验。

---

## 2. 技术栈

| 层 | 技术 |
|---|---|
| RAG 框架 | LlamaIndex |
| 后端 API | FastAPI（`api/`）、uvicorn、日志轮转 |
| RAG 核心 | `server/`（engine、index、retriever、splitters、stores、security、agent） |
| 前端 Web | React 18 + Vite 5 + React Query + Zustand + React Router（`webapp/`） |
| 桌面端 | Electron + React（`desktop/`，产品名 NorthAgent） |
| 旧前端 | Streamlit（`frontend/` + `app.py`，作为迁移回退保留） |
| 嵌入模型 | BAAI/bge-small-zh-v1.5（开发）/ bge-large-zh-v1.5（生产） |
| 重排模型 | BAAI/bge-reranker-base / large |
| PDF/OCR | PyMuPDF + PaddleOCR（扫描件回退） |
| 本地 LLM | Ollama 0.3.3（注意：不兼容 0.4） |

---

## 3. 架构

```
desktop/ (Electron 壳, NorthAgent)
  └─ webapp/ (React + Vite, 也可独立运行)
       └─ api/ (FastAPI 路由层)
            ├─ routers/: agent, chat, health, kb, settings
            ├─ services/: agent_runtime, chat_service, kb_service,
            │              command_filter/parser, risk_assessor,
            │              approval_service, tool_registry, session_store ...
            └─ runtime.py (runtime_state, bootstrap)
                 └─ server/ (RAG 核心)
                      ├─ engine.py / index.py / retriever.py / ingestion.py
                      ├─ text_splitter.py / splitters/
                      ├─ readers/pdf_ocr.py        ← PDF OCR 回退
                      ├─ kb_registry.py / kb_filter.py ← 最小多知识库基础能力
                      ├─ agent/ (task_planner, plan_executor)
                      ├─ security/ (命令风险分级, 硬拒绝)
                      ├─ models/ (embedding, llm_api, ollama, reranker)
                      └─ stores/ (config_store)

frontend/ + app.py (旧 Streamlit 入口，尚未完全退场)
```

**入口**：
- 后端 API：`python run_api.py`（端口 18080）
- 一键联调：`.\start_dev.ps1`（拉起 API + Web）
- 桌面联调：`.\scripts\dev-all.ps1`（API + Web + Desktop）
- 旧 Streamlit：`streamlit run app.py`（保留作迁移回退，未达功能对等前不删）

---

## 4. 当前进度

### 已完成
- **API / 桌面骨架已成型**：FastAPI 后端、React Web、Electron 桌面壳、会话持久化、配置存储、日志轮转都已落地。
- **最小多知识库基础能力已落地**：`KBRegistry`、`KBIdFilter`、KB CRUD 路由、默认 `default` KB 启动自动创建、`QueryRequest.kb_ids` 查询入口已存在。
- **多知识库最小闭环已补齐**（2026-07-13）：Agent `knowledge_scope.kb_id` 现已透传为 `kb_ids` 参与 KB 查询，Agent evidence 会返回真实 `kb_id`，`POST /api/kb/web/import` 也会把请求里的 `kb_id` 继续传给 `kb_service.import_urls()`。
- **本地开发联调链路已修复**（2026-07-14）：`start_dev.ps1` 可在 Windows PowerShell 下正常解析并同时拉起 API 18080 + Web 5173；FastAPI 已放行 Vite 开发源的 CORS 预检，知识库页面不再因 `Network Error` 卡在加载失败。
- **知识库导入与嵌入质量基线已实测**（2026-07-14）：未配置 LLM 时，独立测试库成功导入 UTF-8 中文文档并完成向量检索；20 组语义烟测结果为 Recall@1 50%、Recall@3 95%、Recall@5 100%、MRR 0.71，证明候选召回可用但首位排序仍需优化。
- **多知识库目录化存储阶段 5 测试已通过**（2026-07-15）：`docs/20260714-kb-directory-storage/` 已形成 PRD、FRD、RTM、Plan、Test Plan 和 Test Report；代码已实现 `data/{kb_id}/` 原始文件目录化、导入前 KB active 校验、共享索引 metadata 写入、list/delete 严格隔离、空 KB 删除保护、registry 原子写与迁移脚本。正式测试覆盖核心目录化、KB/Agent 回归、非 slow 全量和覆盖率门禁，测试报告已于 2026-07-15 审核通过，当前进入阶段 6 的开发故事沉淀、commit 与 push。
- **粮仓知识库本地资料已规范化整理**（2026-07-15）：`data/grain-knowledge-base/` 已按 `docs/01-*` 至 `docs/07-*` 主题目录组织主资料，并将重复副本隔离到 `docs/98-duplicates-to-review/`；已维护知识库级 `readme.md`、`index.md`、分类 README、`qa/` 评测资料和 `data/kb-index.md` 多知识库总索引。当前目录共 255 个原始资料文件，其中主资料 126 个、重复/隔离副本 129 个；本地 registry 中 `grain-knowledge-base` 为 active，`doc_count=25`（含 smoke/手动重复导入副本），因此目录整理完成但向量索引尚非全量导入。已新增 `scripts/import_grain_kb_batches.py` 分批导入工具，支持 dry-run 计划、DOCX/PDF 分批 apply 和 JSON 报告；2026-07-15 已完成 5 个 DOCX 的脚本化 apply smoke（120 chunks）和 5 组 HTTP 问答 smoke。
- **粮仓知识库 smoke 问答链路已跑通**（2026-07-15）：修复 LlamaIndex 默认 OpenAI fallback、索引加载前 embedding 预热、非字符串 `file_path` metadata、陈旧向量 id KeyError 以及非 default 查询混入 default 来源的问题；最终 Q1-Q4 领域问题回答正确，Q5 实时价格越界问题能说明上下文无相关信息，sources 均限定在 `grain-knowledge-base`。
- **导入功能独立 smoke 已通过**（2026-07-15）：为避免污染正式粮仓知识库，新增临时 KB `import-smoke-20260715-192353` 验证创建 KB、`POST /api/kb/file/import`、`data/{kb_id}/` 落盘、文档列表、问答召回和跨 KB 负向隔离；测试问题“导入功能烟测代号是什么？”在临时 KB 回答“蓝麦”，在 `grain-knowledge-base` 不泄漏该答案。报告位于 `data/grain-knowledge-base/qa/import-function-smoke-20260715-192353.json`。
- **上传目标知识库显式选择 P1 已修复**（2026-07-16）：`/knowledge` 初始不再静默选中 `default`；只有用户显式选择已登记且 active 的 KB 后，文档列表、文件上传和网页导入才可用。知识库列表支持创建、重命名、删除，新建成功后自动选择；导入区显示目标名称、`kb_id` 和 `data/{kb_id}/`。同时修复 Axios 统一响应体二次解包导致列表误显示为空的问题，并补充上传 API 回归测试。Node 回归 18/18、前端 API/规则覆盖率 80.92%、后端定向回归 29/29、Vite 构建和浏览器 smoke 均通过。
- **上传 400 根因已修复**（2026-07-16）：定位到 `webapp/src/api/kb.js` 与 `webapp/src/api/agent.js` 手动设置了 `Content-Type: multipart/form-data`，导致浏览器未自动补齐 multipart boundary，请求到 FastAPI 时返回 `Missing boundary in multipart.` 并报 400。现已移除该请求头，并新增 `webapp/src/api/kb.test.js` 回归验证上传调用仅传 `FormData` 与 `kb_id`，不再显式覆盖 multipart 头；定向 Node 回归、覆盖率与 `npm run build` 已通过。
- **Agent runtime + 审批流已可用**：命令解析、风险分级 L0-L3、硬拒绝过滤、pending action 审批（approve/reject）、回执存储、session 快照持久化已接通。
- **PDF OCR 回退已落地**（`4a10f54`）：`PDFOCRReader` 先用 PyMuPDF 读文字层，无有效文字层时回退 PaddleOCR 逐页识别；`server/index.py` 统一走 `_load_documents()`。
- **OCR 质量评估已补齐**（`4a10f54`）：`scripts/pdf_ocr_quality.py` 可做关键词召回率评估，并有配套测试。
- **Windows 环境稳定性显著提升**：修复 torch DLL / PATH 冲突，embedding / splitter / LLM 相关导入改为懒加载，文本分割器可按上传参数重建，启动链更稳。

### 当前阶段判断
项目已经不是“只有想法或 Demo”的阶段，而是进入了 **主干功能可运行、近期重点在稳定性收口与架构继续演进** 的阶段：

1. 主产品骨架已经具备；
2. 最近一轮重点成果是 PDF OCR、Windows 环境修复、多知识库最小闭环补齐，以及本地 API/Web 联调链路修复；
3. 当前主要矛盾已经从“接口是否打通”转为“共享单索引方案是否继续收紧与升级”；原始文件从 `data/` 根目录平铺改为 `data/{kb_id}/` 的编码、阶段 5 正式测试与测试报告评审均已完成，下一步进入 commit 与 push。
4. 粮仓知识库的本地资料分类、索引和 QA 骨架已经具备，上传前显式选择目标 KB 的 P1 已解除；下一步先在专用 smoke KB 完成一次用户真实上传复验，再补齐粮仓主资料导入、阿里云/百炼配置下的嵌入质量评测，以及基于 verified QA 的问答效果报告。

### 测试
- 快测（默认）：`python -m pytest tests/ -q -m "not slow"`
- 2026-07-14 本地全量快测最新复跑结果：`python -m pytest tests/ -q -m "not slow"` -> `88 passed, 1 deselected, 2 warnings in 11.29s`
- 2026-07-14 本地定向回归结果：`python -m pytest tests/api/test_app_cors.py tests/api/test_agent_runtime.py tests/api/test_kb_routes.py tests/api/test_m2_multi_kb.py -q` -> `44 passed, 2 warnings in 4.73s`
- 2026-07-14 多知识库现状基线：`python -m pytest tests/api/test_kb_registry.py tests/api/test_kb_routes.py tests/api/test_m2_multi_kb.py tests/api/test_agent_runtime.py -q` -> `55 passed, 2 warnings in 4.54s`。该结果仅验证编码前逻辑多库链路。
- 2026-07-15 多知识库目录化存储阶段 5 正式测试通过：语法自检通过；`git diff --check` 退出码 0 且仅有 LF/CRLF 提示；占位词检查无命中；核心目录化功能 `90 passed in 9.36s`；KB/多 KB/Agent 定向回归 `45 passed, 2 warnings in 3.70s`；API + integration + scripts + utils + QA fixture 扩展回归 `164 passed, 2 warnings in 5.18s`；默认非 slow 全量门禁 `168 passed, 1 deselected, 2 warnings in 5.74s`；目录化相关文件覆盖率最终 `84%`，高于 `>=80%` 门禁。详见 `docs/20260714-kb-directory-storage/20260714-kb-directory-storage-test-report.md`。
- 2026-07-15 粮仓知识库资料整理校验：本地扫描 `data/grain-knowledge-base/docs/` 得到 255 个资料文件，格式为 157 个 PDF、98 个 DOCX；主资料目录唯一 SHA256 数为 126，重复/隔离区 129 个文件；已生成 `_maintenance/2026-07-15-main-duplicate-isolation/move-manifest.json` 记录 2 个主目录重复别名的隔离移动。
- 2026-07-16 粮仓知识库 UI 基线：`/api/kb` 可见 `grain-knowledge-base`，浏览器文档列表当前显示 14 个已索引文档，路径和 `kb_id` 均限定在粮仓库；上传目标显式选择修复后，初始不选库，选择粮仓库后文件与网页导入目标提示一致。人工真实上传步骤见 `docs/20260715-grain-kb-evaluation/20260715-grain-kb-evaluation-test-guide.md`。
- 2026-07-16 本地浏览器 smoke：`/knowledge` 初始显示“请选择知识库”，三个功能标签禁用；侧边栏展示 4 个真实 KB；选中 `grain-knowledge-base` 后显示 14 个文档以及明确的文件/网页导入目标，console error/warn 为空。服务启动与 CORS 基线仍沿用 2026-07-14 已通过结果。
- 2026-07-14 嵌入与导入烟测：`bge-small-zh-v1.5` 可输出 512 维向量；20 组 UTF-8 中文检索 Recall@1=50%、Recall@3=95%、Recall@5=100%、MRR=0.71；测试库 `embedding-quality-smoke-20260714` 导入 1 个文件并生成 1 个分块，限定 KB 检索命中；未配置 LLM 时问答接口按设计返回 503。详见 `docs/20260714-embedding-rag-quality-evaluation/`。
- 当前快测已覆盖：PDF OCR 功能 + 质量、KBRegistry、KB 路由、M2 多 KB、agent runtime、CORS 预检、command filter/parser、tool registry、receipt persistence 等主线能力。
- 慢测（真实 PaddleOCR，约 12 分钟 / 样本）：`python -m pytest -q -m slow -s`，默认不跑。
- 当前 warning 主要来自 FastAPI 的 `@app.on_event("startup")` 弃用提示，后续宜迁移到 lifespan 写法。

---

## 5. 已知问题和限制

- **多知识库仍是过渡架构**：当前实现更接近“单索引 + `kb_id` metadata 过滤”，不是物理多索引隔离。`config.DEFAULT_INDEX_NAME` 仍是单个 `knowledge_base`，`RuntimeState` 也只维护一个 `IndexManager`；本轮已把新导入原始文件改为 `data/{kb_id}/`，但 `storage/` 不拆分，旧索引 metadata/query 一致性仍需通过重导或重建索引验收。
- **旧数据兼容策略会放宽过滤**：`KBIdFilter` 目前仍保留“没有 `kb_id` metadata 的节点”，适合迁移期，但意味着旧数据可能绕过严格库过滤。
- **Windows 环境仍然脆弱**：torch / onnxruntime 对 PATH 中其他 Python 版本的 DLL 敏感。`start_dev.ps1` 会清理 PATH 并保留 Python 3.12 与当前 Node 目录，手动跑命令也需注意。详见 `docs/troubleshooting/20260710-0953-path-conflict-torch-dll.md`。
- **运行环境分裂**：当前依赖主要装在**系统 Python 3.12**，`.venv` 已不再可信（缺 pymupdf / paddleocr / torch 等关键依赖）。新机器建议直接用系统 py312，或重新构建新的 venv。
- **OCR 仍然较慢**：PaddleOCR 在 CPU 上整本扫描件约 2 分钟 / 页，6 页国标样本约 12 分钟，已用 `slow` marker 隔离。
- **OCR 质量口径仍偏基础**：目前只做关键词召回率，未覆盖 CER 字符准确率、表格结构还原、版面顺序等更细指标。
- **嵌入首位排序质量仍需优化**：20 组项目领域合成语义测试中 Recall@3=95%、Recall@5=100%，但 Recall@1=50%、MRR=0.71，且 10/20 用例的正确段落分数低于最高干扰项；当前 `use_reranker=false`，尚未完成重排模型和 `bge-large-zh-v1.5` 对照测试。
- **粮仓知识库还未完成全量向量化**：`data/grain-knowledge-base/` 目录已整理并建立索引，但本地 registry 当前 `doc_count=25`，且包含 smoke/手动重复导入副本，仍低于主资料 126 个文件；正式问答验收前需要按 `index.md` 的主资料清单补齐导入或重建索引，并输出检索/问答评测报告。
- **空知识库下问答仍会明确失败**：默认 `default` KB 启动可见，但未导入文档时真实检索会返回 `Knowledge base is empty. Please import documents first.`；这是当前预期行为，不代表 API/Web 链路异常。
- **文档需要联动维护**：`docs/project.md`、`docs/guide/DOCS_INDEX.md`、`docs/spec/knowledge_base_visibility_and_multi_kb_design.md` 已持续按当前代码口径同步；后续代码变更时仍需同步更新，避免再次漂移。
- **Streamlit 仍在并存**：`app.py` / `frontend/` 作为迁移回退保留，功能未与后端 API 完全对等，不能再作为判断当前主线能力的唯一依据。
- **Ollama 版本受限**：当前要求 0.3.3，0.4 与现有 LlamaIndex 组合不兼容。

---

## 6. 快速上手

```powershell
# 安装依赖（系统 Python 3.12）
python -m pip install -r requirements.txt
cd webapp; npm install; cd ..
cd desktop; npm install; cd ..   # 桌面端可选

# 一键联调（API 18080 + Web 5173）
.\start_dev.ps1

# 健康检查
python -c "import requests;print(requests.get('http://127.0.0.1:18080/api/health',timeout=5).json())"

# 跑测试
python -m pytest tests/ -q -m "not slow"
```

模型配置：LLM API key 可在应用界面配置，或设环境变量 `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` / `MOONSHOT_API_KEY` / `ZHIPU_API_KEY`。本地 LLM 用 Ollama 0.3.3。

---

## 7. 文档导航

| 文档 | 内容 |
|---|---|
| `AGENTS.md` | 开发流程规范（PRD→实施→测试→提交）、文档命名、评审流程 |
| `docs/project.md` | 面向协作者的当前项目总览、进度与问题 |
| `docs/guide/DOCS_INDEX.md` | 当前 docs 体系总索引与主文档入口 |
| `docs/spec/knowledge_base_visibility_and_multi_kb_design.md` | 最小多知识库设计与边界 |
| `docs/spec/desktop_api_contract.md` | 页面到 API 的契约映射 |
| `docs/spec/desktop_project_design.md` | 桌面端项目设计 |
| `docs/test/desktop_regression_checklist.md` | 桌面版回归清单 |
| `docs/20260713-pdf-ocr-quality/` | PDF OCR 进展文档 |
| `docs/20260714-dev-runtime-cors-startup/` | 本地开发运行链路与 CORS 修复测试报告 |
| `docs/20260714-embedding-rag-quality-evaluation/` | 嵌入检索、真实导入和 RAG 问答前置条件测试方案与报告 |
| `docs/20260714-kb-directory-storage/` | 多知识库目录化存储 PRD/FRD/RTM/Plan/Test Plan/Test Report |
| `docs/20260715-grain-kb-evaluation/` | 粮仓知识库导入、嵌入检索与问答人工验收测试指南 |
| `docs/20260716-kb-upload-target-selection/` | 上传前显式选择目标知识库的修复说明、计划、测试方案与报告 |
| `docs/interview/dev-stories/` | 开发故事沉淀（面试复盘材料） |
| `docs/troubleshooting/` | 按时间戳组织的排查记录 |
| `评审建议.txt` | 最新评审意见（仓库根） |

---

## 8. 最近提交

| hash | 说明 |
|---|---|
| `cc80145` | fix: repair local dev runtime startup and cors |
| `35ff8bf` | fix: close multi-kb agent and web import loop |
| `b31babe` | docs: add project overview for AI context |
| `052cc81` | test(api): add multi-kb and agent runtime coverage |
| `4a10f54` | feat(pdf): add OCR fallback and quality evaluation |
| `3bce696` | fix: recreate text splitter with per-upload chunk_size/chunk_overlap so Settings actually takes effect |
| `d1073b4` | fix: remove Python 3.10 from PATH to resolve torch DLL conflict + real BGE embedding now works |
| `1e0bda8` | docs: restructure troubleshooting log into timestamped per-session files under docs/troubleshooting/ |

查看完整历史：`git log --oneline -30`


## 9. 2026-07-17 incremental update

- Topic folder: `docs/20260717-agent-qa-page-refactor/`
- Scope: `/agent` page refactor, question-first workflow, and retriever hardening for historical bad index data.
- Front-end status: `/agent` now supports basic chat, KB-scoped chat, and Agent advanced mode in one page.
- Backend status: stale wrong-dimension embeddings are pruned before vector retrieval; BM25 build skips empty or unserializable historical nodes, so `/api/chat/query` no longer fails with the previous 400 regression.
- Validation on 2026-07-17: Node rule tests passed (14/14), `pytest tests/api/test_retriever_stale_vectors.py -q` passed (7 passed), `npm run build` passed, direct HTTP verification returned 200, and browser smoke on `http://127.0.0.1:5173/agent` succeeded.
- Known data caveat: KB `20260716` is still a smoke dataset and can return noisy sources; use `grain-knowledge-base` for formal QA.

## 10. 2026-07-17 grain KB QA set expansion

- `data/grain-knowledge-base/qa/verified.jsonl` ?? 24 ???? 30 ??????????????????????????????????
- `data/grain-knowledge-base/qa/draft.jsonl` ?? 20 ???? 26 ?????????????/?????????????????
- ?? `data/grain-knowledge-base/qa/question-groups.md`?? QA ???? 6 ??????? 12 ? smoke / ?? verified / hard draft ????????
- ?? Grain QA ???? 56 ?????????????????????????
