# 项目总览 (docs/project.md)

> 本文档面向所有协作者（含 AI 助手），用于快速了解项目当前进度、架构和已知问题。
> **维护规则**：每次有意义的提交后更新本文的「最近提交」与「当前进度」「已知问题」三节；重大架构变化更新「架构」节。日期使用绝对日期。

最近更新：2026-07-13

---

## 1. 项目简介

本项目是 **ThinkRAG**（基于 LlamaIndex + Streamlit 的本地知识库 RAG 系统）的改造分支，代号 **agent-kb** / 桌面端 **NorthAgent**。

在原版「单库 Streamlit 问答」基础上做了两条改造主线：

1. **多知识库 + 后端化**：用 FastAPI 重写后端，支持多 KB 管理，React 重写前端，Electron 做桌面壳。
2. **Agent 化**：加入任务规划、工具注册、命令风险分级（L0-L3）、人工审批流，往「智能体 + 工具调用」方向走。

面向国内用户优化：中文分词、DeepSeek/Moonshot/Zhipu 等国产 LLM、BGE 中英双语嵌入模型。

---

## 2. 技术栈

| 层 | 技术 |
|---|---|
| RAG 框架 | LlamaIndex |
| 后端 API | FastAPI（`api/`）、uvicorn、日志轮转 |
| RAG 核心 | `server/`（engine、index、retriever、splitters、stores、security、agent） |
| 前端 Web | React 18 + Vite 5 + React Query + Zustand + React Router（`webapp/`） |
| 桌面端 | Electron + React（`desktop/`，产品名 NorthAgent） |
| 嵌入模型 | BAAI/bge-small-zh-v1.5（开发）/ bge-large-zh-v1.5（生产） |
| 重排模型 | BAAI/bge-reranker-base / large |
| PDF/OCR | PyMuPDF + PaddleOCR（扫描件回退） |
| 本地 LLM | Ollama 0.3.3（注意：不兼容 0.4） |

---

## 3. 架构

```
desktop/ (Electron 壳, NorthAgent)
  └─ webapp/ (React + Vite, 也独立跑)
       └─ api/ (FastAPI 路由层)
            ├─ routers/: agent, chat, health, kb, settings
            ├─ services/: agent_runtime, chat_service, kb_service,
            │              command_filter/parser, risk_assessor,
            │              approval_service, tool_registry, session_store ...
            └─ runtime.py (runtime_state, bootstrap)
                 └─ server/ (RAG 核心)
                      ├─ engine.py / index.py / retriever.py / ingestion.py
                      ├─ text_splitter.py / splitters/
                      ├─ readers/pdf_ocr.py  ← 新增: PDF OCR 回退
                      ├─ kb_registry.py / kb_filter.py  ← 多知识库
                      ├─ agent/ (task_planner, plan_executor)
                      ├─ security/ (命令风险分级, 硬拒绝)
                      ├─ models/ (embedding, llm_api, ollama, reranker)
                      └─ stores/ (config_store)
```

**入口**：
- 后端 API：`python run_api.py`（端口 18080）
- 一键联调：`.\start_dev.ps1`（拉起 API + Web）
- 桌面联调：`.\scripts\dev-all.ps1`（API + Web + Desktop）
- 旧 Streamlit：`streamlit run app.py`（保留作迁移回退，未达功能对等前不删）

---

## 4. 当前进度

### 已完成
- **多知识库后端**（`6dbc6d5` 起）：`KBRegistry`、`KBIdFilter` 按 kb_id 过滤、KB CRUD 路由、启动自动建 default KB。
- **Agent runtime + 审批流**：命令解析、风险分级 L0-L3、硬拒绝过滤、pending action 审批（approve/reject）、session 持久化、SQLite 回执存储。
- **PDF OCR 回退**（`4a10f54`）：`PDFOCRReader` 先 PyMuPDF 提文字层，无效则 PaddleOCR 逐页识别；`server/index.py` 统一走 `_load_documents()`。
- **OCR 质量评估**（`4a10f54`）：`scripts/pdf_ocr_quality.py` 关键词召回率评估。
- **Windows 环境修复**：torch DLL 冲突（移除 PATH 中 Python 3.10）、懒加载 embedding/splitter、文本分割器按上传参数重建、日志轮转、路由顺序修复。

### 测试
- 快测（默认）：`python -m pytest tests/ -q -m "not slow"`
- 当前快测全绿：PDF OCR 功能 + 质量、KBRegistry、KB 路由、M2 多 KB、agent runtime、command filter/parser、tool registry 等共 50+ 用例。
- 慢测（真实 PaddleOCR，约 12 分钟/样本）：`python -m pytest -q -m slow -s`，默认不跑。

---

## 5. 已知问题和限制

- **Windows 环境脆弱**：torch/onnxruntime 对 PATH 中其他 Python 版本的 DLL 敏感。`start_dev.ps1` 会清理 PATH 只保留 Python 3.12，手动跑命令也需注意。详见 `docs/troubleshooting/20260710-0953-path-conflict-torch-dll.md`。
- **运行环境分裂**：当前依赖只装在**系统 Python 3.12**，`.venv` 已废弃（缺 pymupdf/paddleocr/torch）。新机器应直接用系统 py312 或重新装 venv。
- **OCR 慢**：PaddleOCR 在 CPU 上整本扫描件约 2 分钟/页，6 页国标样本约 12 分钟。已用 `slow` marker 隔离。
- **OCR 质量口径**：目前只做关键词召回率，未覆盖 CER 字符准确率、表格结构、版面顺序。
- **PDF 中文文件名**：Windows 下 `SimpleDirectoryReader` 对中文文件名可能出问题，`PDFOCRReader` 用绝对路径规避。
- **Streamlit 并存**：`app.py` 仍是迁移回退，功能未与后端 API 对等，不要据此判断后端能力。
- **Ollama 版本**：必须 0.3.3，0.4 与 LlamaIndex 不兼容。

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
| `docs/desktop_runbook.md` | 桌面端开发/打包 runbook |
| `docs/desktop_api_contract.md` | 页面到 API 的契约映射 |
| `docs/desktop_regression_checklist.md` | 桌面版回归清单 |
| `docs/desktop_project_design.md` | 桌面端项目设计 |
| `docs/agent_v1_*.md` | Agent v1 PRD/FRD/RTM/设计/计划 |
| `docs/20260713-pdf-ocr-quality/` | PDF OCR 进展文档 |
| `docs/interview/dev-stories/` | 开发故事沉淀（面试复盘材料） |
| `docs/troubleshooting/` | 按时间戳组织的排查记录 |
| `评审建议.txt` | 最新评审意见（仓库根） |

---

## 8. 最近提交

| hash | 说明 |
|---|---|
| `052cc81` | test(api): 补录多知识库与 agent runtime 测试覆盖（历史被 .gitignore 误伤） |
| `4a10f54` | feat(pdf): PDF OCR 回退解析 + 质量评估 |
| `3bce696` | fix: 按上传参数重建 text splitter 让 Settings 生效 |
| `d1073b4` | fix: 移除 PATH 中 Python 3.10 解决 torch DLL 冲突，BGE 嵌入跑通 |
| `1e0bda8` | docs: 排查日志重构为按会话时间戳文件 |
| `d864aac` | fix: splitter/embedding/lm 懒加载，规避 Windows torch DLL 崩溃 |

查看完整历史：`git log --oneline -30`
