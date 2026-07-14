# 项目总览 (docs/project.md)

> 本文档面向所有协作者（含 AI 助手），用于快速了解项目当前进度、架构和已知问题。
> **维护规则**：每次有意义的提交后更新本文的「最近提交」与「当前进度」「已知问题」三节；重大架构变化更新「架构」节。日期使用绝对日期。

最近更新：2026-07-14

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
- **Agent runtime + 审批流已可用**：命令解析、风险分级 L0-L3、硬拒绝过滤、pending action 审批（approve/reject）、回执存储、session 快照持久化已接通。
- **PDF OCR 回退已落地**（`4a10f54`）：`PDFOCRReader` 先用 PyMuPDF 读文字层，无有效文字层时回退 PaddleOCR 逐页识别；`server/index.py` 统一走 `_load_documents()`。
- **OCR 质量评估已补齐**（`4a10f54`）：`scripts/pdf_ocr_quality.py` 可做关键词召回率评估，并有配套测试。
- **Windows 环境稳定性显著提升**：修复 torch DLL / PATH 冲突，embedding / splitter / LLM 相关导入改为懒加载，文本分割器可按上传参数重建，启动链更稳。

### 当前阶段判断
项目已经不是“只有想法或 Demo”的阶段，而是进入了 **主干功能可运行、近期重点在稳定性收口与架构继续演进** 的阶段：

1. 主产品骨架已经具备；
2. 最近一轮重点成果是 PDF OCR、Windows 环境修复、多知识库最小闭环补齐，以及本地 API/Web 联调链路修复；
3. 当前主要矛盾已经从“接口是否打通”转为“共享单索引方案是否继续收紧与升级”，同时继续补齐桌面/浏览器真实运行路径的回归覆盖。

### 测试
- 快测（默认）：`python -m pytest tests/ -q -m "not slow"`
- 2026-07-14 本地全量快测结果：`python -m pytest tests/ -q -m "not slow"` -> `88 passed, 1 deselected, 2 warnings in 5.88s`
- 2026-07-14 本地定向回归结果：`python -m pytest tests/api/test_app_cors.py tests/api/test_agent_runtime.py tests/api/test_kb_routes.py tests/api/test_m2_multi_kb.py -q` -> `44 passed, 2 warnings in 4.73s`
- 2026-07-14 本地运行烟测：`powershell -NoProfile -ExecutionPolicy Bypass -File .\start_dev.ps1` 可拉起 API/Web；`GET /api/health` 返回 `code=0,message=ok`；`OPTIONS /api/kb` 对 `Origin: http://127.0.0.1:5173` 返回 `200` 且 `Access-Control-Allow-Origin=http://127.0.0.1:5173`；`GET http://127.0.0.1:5173/` 返回 `200`；Chrome headless 打开 `/knowledge` 显示 `ID: default`、`暂无文档`，无 `Network Error`，console errors 为空。
- 当前快测已覆盖：PDF OCR 功能 + 质量、KBRegistry、KB 路由、M2 多 KB、agent runtime、CORS 预检、command filter/parser、tool registry、receipt persistence 等主线能力。
- 慢测（真实 PaddleOCR，约 12 分钟 / 样本）：`python -m pytest -q -m slow -s`，默认不跑。
- 当前 warning 主要来自 FastAPI 的 `@app.on_event("startup")` 弃用提示，后续宜迁移到 lifespan 写法。

---

## 5. 已知问题和限制

- **多知识库仍是过渡架构**：当前实现更接近“单索引 + `kb_id` metadata 过滤”，不是物理多索引隔离。`config.DEFAULT_INDEX_NAME` 仍是单个 `knowledge_base`，`RuntimeState` 也只维护一个 `IndexManager`。
- **旧数据兼容策略会放宽过滤**：`KBIdFilter` 目前仍保留“没有 `kb_id` metadata 的节点”，适合迁移期，但意味着旧数据可能绕过严格库过滤。
- **Windows 环境仍然脆弱**：torch / onnxruntime 对 PATH 中其他 Python 版本的 DLL 敏感。`start_dev.ps1` 会清理 PATH 并保留 Python 3.12 与当前 Node 目录，手动跑命令也需注意。详见 `docs/troubleshooting/20260710-0953-path-conflict-torch-dll.md`。
- **运行环境分裂**：当前依赖主要装在**系统 Python 3.12**，`.venv` 已不再可信（缺 pymupdf / paddleocr / torch 等关键依赖）。新机器建议直接用系统 py312，或重新构建新的 venv。
- **OCR 仍然较慢**：PaddleOCR 在 CPU 上整本扫描件约 2 分钟 / 页，6 页国标样本约 12 分钟，已用 `slow` marker 隔离。
- **OCR 质量口径仍偏基础**：目前只做关键词召回率，未覆盖 CER 字符准确率、表格结构还原、版面顺序等更细指标。
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
