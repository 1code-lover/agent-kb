# 项目总览

> 本文档面向所有协作者（含 AI 助手），用于快速了解项目当前进度、架构、验证证据和已知问题。
> **维护规则**：每次有意义的提交后更新「当前进度」「测试与验证」「已知问题」「最近提交」四节；重大架构变化更新「架构」节。日期使用绝对日期。

最近更新：2026-08-07

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
| 桌面端 | Electron 31，`desktop/` 启动 Python API 后加载 Web |
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
- **粮仓知识库真实 QA 评测已新增脚本和报告**：
  - 脚本：`scripts/run_grain_qa_eval.py`
  - 输入：`data/grain-knowledge-base/qa/verified.jsonl`，当前 30 条人工标注用例
  - 报告产物：`docs/20260722-local-multi-kb-assistant/artifacts/grain-qa/qa-eval-report.json`
  - 2026-08-07 重新生成报告摘要：`total=30`、`answerable_total=29`、`unanswerable_total=1`、`error_count=0`、`Recall@5=1.0`、`MRR@5=0.977`、`citation_hit_rate=1.0`、`refusal_accuracy=1.0`、`kb_isolation_rate=1.0`
  - 报告已补充 `api_base`、`timeout`、`cases_sha256`、逐条 `source_kb_ids` 与 `kb_id_missing_count`，避免引用来源缺失 `kb_id` 时误判隔离通过。
  - 说明：该评测不做 LLM 裁判，主要验证检索命中、引用来源、拒答和 KB 隔离。

### 4.3 当前 Git 状态

- 当前分支：`codex/desktop-agent-stage3`
- 远端跟踪：`origin/codex/desktop-agent-stage3`
- 当前分支已完成 2026-08-07 稳定性收口提交，并已推送到远端：
  - `575ff3d fix(kb): recognize docx/office documents as importable file kind`
  - `64c402b fix(ingest,retrieve): adapt to llama_index 0.11.19 internal API changes`
  - `7b0037d feat(eval): add grain KB real QA evaluation script`
  - `ed8368f docs(grain-qa): add real KB QA evaluation report artifacts`
  - `1520aef fix(kb): harden import filtering and grain qa eval`
  - `6f1ef56 fix(ocr): stabilize paddle runtime and diagnostics`
  - `ddf8317 refactor(web): replace router dependency with local navigation`
  - `ca34b66 docs(dev): record local kb stability closure`
  - `82b6cba docs(project): sync closure status before push`
- 当前工作区状态：2026-08-07 本轮收口提交推送后，`git status --short --branch` 显示本地分支与 `origin/codex/desktop-agent-stage3` 同步且工作区干净。

### 4.4 下一步建议

- **先扩测试，再做优化**：当前 `verified.jsonl` 只有 30 条，且已全绿，说明核心链路稳定，但还不足以代表整个知识库质量。
- **优先补齐真实评测集**：先把 `draft.jsonl` 里可转正的题补成 `verified`，再按正向、负向、跨库隔离、PDF、扫描件、表格、重复资料几个维度把题池扩到至少 80 条。
- **把评测结果做成分组失败清单**：后续 `run_grain_qa_eval.py` 需要按“召回失败 / 排序差 / sources 过多 / OCR 质量差 / 资料冲突 / 超范围应拒答”输出样例，方便按问题类型治理。
- **再针对失败项做优化**：等评测集足够大后，再决定是调 chunk、rerank、top-k、OCR，还是前端证据展示，而不是先凭感觉改参数。

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
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.run_grain_qa_eval --cases data/grain-knowledge-base/qa/verified.jsonl --api-base http://127.0.0.1:18080 --kb-id grain-knowledge-base --output docs/20260722-local-multi-kb-assistant/artifacts/grain-qa/qa-eval-report.json`：30 条用例评测完成，`Recall@5=1.0`、`MRR@5=0.977`、`kb_isolation_rate=1.0`
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

---

## 6. 已知问题和限制

- **macOS 要使用 conda `agent-kb` 环境**：默认 `python` 仍可能指向 Miniconda base 3.13，缺项目依赖；非交互命令建议直接用 `/opt/miniconda3/envs/agent-kb/bin/python`。
- **mixed batch 正向问答会返回多个候选 sources**：2026-08-07 真实 roundtrip 中 4 个正向用例的首要/目标文档、preview 和核心关键词均命中，但精确 `source_count_match/evidence_count_match` 为 false，因为接口会返回多个相关候选证据；这不影响当前核心 gate，但后续若产品要求“一问一证据”或更少引用噪声，需要收口 rerank/top-k 或前端展示策略。
- **多知识库仍是逻辑隔离，不是物理多索引隔离**：原始文件已按 `data/{kb_id}/` 目录化，但 `storage/` 仍是共享索引/共享存储，隔离主要依赖 metadata filter。
- **旧数据兼容仍可能放宽过滤**：迁移期对缺失 `kb_id` metadata 的历史节点仍需谨慎处理；真实数据重建或清理策略仍是后续工作。
- **粮仓知识库评测报告仍需注意样本边界**：当前 30 条 verified QA 报告指标全绿，且已补充运行参数和用例 hash，但样本规模仍有限，不能等同于全量资料质量验收。
- **OCR 质量口径仍偏基础**：当前主要关注 OCR 成功、关键词/问答命中和回执诊断，尚未系统覆盖 CER、表格结构、版面顺序等细指标。
- **README 与实际主线有代际差异**：README 仍以 ThinkRAG + Streamlit 为主叙述，当前实际主线是 FastAPI + React + Electron + Agent 工作台。
- **命名仍在过渡**：仓库、README、Web package 仍出现 ThinkRAG；桌面端 package/product 已使用 NorthAgent。
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
| `ca34b66` | docs(dev): record local kb stability closure |
| `ddf8317` | refactor(web): replace router dependency with local navigation |
| `6f1ef56` | fix(ocr): stabilize paddle runtime and diagnostics |
| `1520aef` | fix(kb): harden import filtering and grain qa eval |
| `82b6cba` | docs(project): sync closure status before push |
| `ed8368f` | docs(grain-qa): add real KB QA evaluation report artifacts |
| `7b0037d` | feat(eval): add grain KB real QA evaluation script |
| `64c402b` | fix(ingest,retrieve): adapt to llama_index 0.11.19 internal API changes |
| `575ff3d` | fix(kb): recognize docx/office documents as importable file kind |
| `57e6a30` | feat(kb): close local multi-kb ingestion qa loop |
| `7d0533a` | refactor(import): add persist stage diagnostics breakdown |
| `f7cc351` | chore: update dev story capture state |
| `4d2abb7` | refactor: batch index persistence during kb imports |
| `7889bc1` | feat: add knowledge workspace and import diagnostics |
| `25dc20a` | feat(kb): add asset registry and preview api |

查看完整历史：`git log --oneline -30`
