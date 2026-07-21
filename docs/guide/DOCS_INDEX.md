# ThinkRAG 文档总索引

> 定位：`docs/project.md` 负责“项目当前状态”，本文负责“文档怎么找”。如果两者与代码不一致，应优先修正文档，而不是继续沿用过期口径。
> 最近更新：2026-07-16

## 1. 协作快速入口

| 入口 | 用途 |
|---|---|
| `AGENTS.md` | 仓库级开发流程规范：PRD → 计划 → 编码 → 测试方案 → 测试报告 → 提交推送 |
| `docs/project.md` | 面向协作者的项目总览、当前进度、已知问题、运行方式 |
| `docs/guide/DOCS_INDEX.md` | 当前 docs 体系导航索引，帮助快速定位文档 |
| `评审建议.txt` | 最新评审结论与整改建议；后续修改应以此为依据 |
| `docs/troubleshooting/README.md` | 排障记录入口，按时间戳索引问题与修复过程 |
| `docs/interview/dev-stories/README.md` | 开发故事沉淀说明与文档命名约定 |

## 2. 当前 docs 目录结构

当前仓库同时存在“分类目录”与“历史根目录文件”两套形态。**新文档优先遵循 `AGENTS.md` 的目录规范**；阅读旧文档时，优先看分类目录中的版本。

| 目录 | 作用 | 当前状态 |
|---|---|---|
| `docs/20260706-multi-kb-frontend-refactor/` | 2026-07-06 多知识库前端重构需求包 | 当前专题文档 |
| `docs/20260713-pdf-ocr-quality/` | 2026-07-13 PDF OCR 质量专题 | 当前专题文档 |
| `docs/20260714-embedding-rag-quality-evaluation/` | 2026-07-14 嵌入检索、真实导入与问答质量评估专题 | 当前专题文档 |
| `docs/20260714-kb-directory-storage/` | 2026-07-14 多知识库原始文件目录化存储需求包 | 阶段 5 正式测试与测试报告评审已通过，待提交推送 |
| `docs/20260715-grain-kb-evaluation/` | 2026-07-15 粮仓知识库导入、嵌入检索与问答测试指南 | 当前专题文档；已补充分批导入脚本、运行时修复和 5 组 HTTP 问答 smoke 结果。 |
| `docs/20260716-kb-upload-target-selection/` | 上传目标知识库显式选择修复、multipart 400 根因定位与验证记录 |
| `docs/spec/` | 需求、设计、接口、产品规划等规范文档 | 当前主分类目录 |
| `docs/plan/` | 实施方案、执行计划 | 当前主分类目录 |
| `docs/test/` | 测试方案、回归清单、手工测试清单 | 当前主分类目录 |
| `docs/test_report/` | 测试结果与报告 | 当前主分类目录 |
| `docs/guide/` | 运行说明、环境说明、文档总索引 | 当前主分类目录 |
| `docs/troubleshooting/` | 按时间戳组织的问题排查记录 | 当前主分类目录 |
| `docs/interview/` | 面试材料与开发故事沉淀 | 当前主分类目录 |
| `docs/archive/` | 已归档的历史方案和旧材料 | 非当前主方案 |
| `docs/phase2/` | 旧 Phase 2 资料 | 历史专题 |
| `docs/superpowers/` | 旧 superpowers 方向材料 | 历史专题 |
| `docs/dev/` | 开发规范、标准、变更记录等 | 辅助目录 |
| `docs/ai-skills/` | AI 技能/流程说明 | 辅助目录 |
| `docs/images/` | 文档配图 | 辅助目录 |

## 3. 当前主线文档

### 3.1 项目与协作总览
- `docs/project.md`：最新项目状态、架构、风险、测试现状。
- `docs/spec/knowledge_base_visibility_and_multi_kb_design.md`：多知识库最小设计及当前实现边界。
- `docs/spec/desktop_api_contract.md`：桌面 / Web 页面到 API 的契约映射。
- `docs/spec/desktop_project_design.md`：桌面端整体设计。

### 3.2 基线需求文档
这组文档描述“知识库智能问答 / agent 化”主线的原始基线：
- `docs/spec/agent_v1_prd.md`
- `docs/spec/agent_v1_frd.md`
- `docs/spec/agent_v1_rtm.md`
- `docs/spec/knowledge_agent_product_plan.md`
- `docs/plan/agent_v1_execution_plan.md`
- `docs/test/knowledge_qa_test_plan.md`
- `docs/test_report/knowledge_qa_test_report_2026-06-29.md`

### 3.3 当前活跃专题
- `docs/20260706-multi-kb-frontend-refactor/`：多知识库前端交互重构专题，已按新命名规范组织。
- `docs/20260713-pdf-ocr-quality/`：PDF OCR 回退与质量评估专题。
- `docs/20260714-embedding-rag-quality-evaluation/`：本地 BGE 嵌入质量、独立知识库真实导入、LLM 问答前置条件及后续阿里百炼测试口径。
- `docs/20260714-kb-directory-storage/`：将新导入原始文件调整为 `data/{kb_id}/`，并建立 QA fixture schema；当前已完成 PRD/FRD/RTM/Plan/Test Plan/Test Report，阶段 5 正式测试与测试报告评审已通过，待提交推送。
- `docs/20260715-grain-kb-evaluation/`：粮仓知识库 `grain-knowledge-base` 的导入、嵌入检索、问答质量和人工验收测试指南；记录 DOCX apply smoke、stale vector 容错和多 KB 来源隔离验证。
- `docs/20260716-kb-upload-target-selection/`：`/knowledge` 页上传目标显式选择专题；已补充 Markdown 上传 400 的真正根因——前端手动写 multipart 头导致 boundary 丢失——以及对应的 API 回归测试。


### 3.4 运行、测试与排障
- `docs/guide/desktop_runbook.md`：本地启动 / 联调说明。
- `docs/guide/HowToDownloadModels.md`：模型下载说明。
- `docs/guide/HowToUsePythonVirtualEnv.md`：Python 环境说明。
- `docs/test/desktop_regression_checklist.md`：桌面版回归清单。
- `docs/test/pdf_manual_test_checklist.md`：PDF 手工测试清单。
- `docs/troubleshooting/`：Windows PATH、后端 503/400、日志配置等问题排查记录。

### 3.5 复盘与沉淀
- `docs/interview/dev-stories/`：开发故事沉淀，供复盘 / 面试表达复用。
- `docs/interview/ThinkRAG_面试全集_合并版.md`：项目表达材料。
- `docs/archive/`：早期方案回溯资料。

## 4. docs 根目录旧入口文件说明

当前 `docs/` 根目录仍保留一批历史入口文件。它们并非都应继续作为“主入口”使用，建议按下面规则理解：

### 4.1 已有分类目录版本，阅读时优先看分类目录
| docs 根目录旧文件 | 优先阅读版本 |
|---|---|
| `docs/agent_v1_prd.md` | `docs/spec/agent_v1_prd.md` |
| `docs/agent_v1_frd.md` | `docs/spec/agent_v1_frd.md` |
| `docs/agent_v1_rtm.md` | `docs/spec/agent_v1_rtm.md` |
| `docs/agent_v1_execution_plan.md` | `docs/plan/agent_v1_execution_plan.md` |
| `docs/knowledge_agent_product_plan.md` | `docs/spec/knowledge_agent_product_plan.md` |
| `docs/desktop_api_contract.md` | `docs/spec/desktop_api_contract.md` |
| `docs/desktop_project_design.md` | `docs/spec/desktop_project_design.md` |
| `docs/desktop_regression_checklist.md` | `docs/test/desktop_regression_checklist.md` |
| `docs/desktop_runbook.md` | `docs/guide/desktop_runbook.md` |
| `docs/HowToDownloadModels.md` | `docs/guide/HowToDownloadModels.md` |
| `docs/HowToUsePythonVirtualEnv.md` | `docs/guide/HowToUsePythonVirtualEnv.md` |
| `docs/Code_of_Conduct.md` | `docs/guide/Code_of_Conduct.md` |

### 4.2 仍主要保留在 docs 根目录的文件
这批文件暂时没有更合适的分类副本，阅读时直接使用根目录版本：
- `docs/project.md`
- `docs/agent_kb_design.md`
- `docs/agent_v1_dev_readiness_checklist.md`
- `docs/code_commenting_requirement.md`
- `docs/ThinkRAG_面试问答.md`

> 说明：这些根目录文件是否要后续迁移，应单独作为文档治理任务处理，不建议在普通功能改动中顺手挪动，以免继续制造链接漂移。

## 5. 使用建议

1. **先看 `docs/project.md` 再深入专题**：先掌握当前项目状态，再进入具体设计或排障文档。
2. **多知识库相关问题优先看两份文档**：
   - 项目状态看 `docs/project.md`
   - 设计边界看 `docs/spec/knowledge_base_visibility_and_multi_kb_design.md`
3. **遇到代码与文档不一致时，以代码和最新测试为准**，并同步更新：
   - `docs/project.md`
   - `docs/guide/DOCS_INDEX.md`
   - 受影响的专题设计文档
4. **新需求文档必须落在同一个 `docs/YYYYMMDD-topic/` 目录下**，不要再把 PRD / 计划 / 测试报告散落回 `docs/` 根目录。
5. **评审后先写 `评审建议.txt`，再按建议修改**，保持“评审结论 → 修改动作”链路可追溯。


## 6. 2026-07-17 addendum

- New topic folder: `docs/20260717-agent-qa-page-refactor/`
- Focus: `/agent` question-first workspace refactor, retriever 400 root-cause fix, and smoke test evidence.
- Key outputs: PRD / FRD / RTM / plan / test plan / test report in the same topic directory.
- Recommended use: when the current question is about `/agent` page UX, KB-scoped chat, stale embeddings, or empty Markdown causing 400, read this folder together with `docs/project.md`.
