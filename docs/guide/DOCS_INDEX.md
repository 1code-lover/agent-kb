# ThinkRAG 文档总索引

## 1. 目录结构
当前 `docs/` 采用下面的目录规则：

- `spec/`：设计方案、需求、接口、架构、产品规划
- `plan/`：执行方案、实施计划
- `test/`：测试方案、测试清单
- `test_report/`：测试报告、测试结果
- `interview/`：面试和项目表达材料
- `guide/`：运行说明、环境说明、模型下载、开发规范
- `archive/`：历史材料，不再作为当前主方案依据
- `images/`：README 与文档配图

补充建议：
- 你提的 5 类是主干目录，没问题。
- 我额外补了 `guide/` 和 `archive/`，这是有必要的。否则运行说明和历史材料没地方放，后面还会重新混乱。

## 2. 当前主文档
以下文档是当前“知识库智能问答”主线的唯一主入口：

1. [需求文档 PRD](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/spec/agent_v1_prd.md)
2. [功能设计 FRD](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/spec/agent_v1_frd.md)
3. [需求追踪矩阵 RTM](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/spec/agent_v1_rtm.md)
4. [产品规划](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/spec/knowledge_agent_product_plan.md)
5. [实施计划](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/plan/agent_v1_execution_plan.md)
6. [测试方案](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/test/knowledge_qa_test_plan.md)
7. [测试报告](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/test_report/knowledge_qa_test_report_2026-06-29.md)

## 3. 当前专题参考

### 3.1 扩展方案
- [多行业知识库实施方案](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/archive/superpowers/plans/2026-05-02-multi-industry-kb.md)
- [多人多知识库可见性与检索设计方案](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/spec/knowledge_base_visibility_and_multi_kb_design.md)

### 3.2 手工测试准备
- [PDF 手工测试检查清单](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/test/pdf_manual_test_checklist.md)

### 3.3 通用设计与运行文档
- [桌面 API Contract](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/spec/desktop_api_contract.md)
- [桌面项目设计](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/spec/desktop_project_design.md)
- [桌面回归清单](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/test/desktop_regression_checklist.md)
- [桌面运行手册](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/guide/desktop_runbook.md)
- [模型下载说明](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/guide/HowToDownloadModels.md)
- [Python 虚拟环境说明](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/guide/HowToUsePythonVirtualEnv.md)

## 4. 历史材料
以下文档保留，但仅用于回溯背景，不作为当前主方案依据：

### 4.1 早期 Agent 方向
- [智能体 + 知识库设计方案](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/archive/agent_kb_design.md)
- [开发前准备检查清单](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/archive/agent_v1_dev_readiness_checklist.md)
- [知识库智能问答 MVP 实施方案](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/archive/superpowers/plans/2026-05-28-desktop-knowledge-agent-mvp.md)
- [知识库智能问答二期实施方案](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/archive/superpowers/plans/2026-06-10-phase2-hybrid-receipt-store.md)

### 4.2 旧测试计划与阶段记录
- [Agent 逐步开发测试计划](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/archive/superpowers/plans/agent_逐步开发测试计划.md)
- [阶段 1 测试记录](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/archive/superpowers/plans/阶段1_模型配置基础链_测试记录_2026-05-28.md)
- [阶段 2 测试记录](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/archive/superpowers/plans/阶段2_模型连接测试链_测试记录_2026-05-28.md)
- [阶段 3 测试记录](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/archive/superpowers/plans/阶段3_Agent纯模型路径_测试记录_2026-05-28.md)
- [阶段 4 测试记录](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/archive/superpowers/plans/阶段4_Agent快速切模_测试记录_2026-05-28.md)

### 4.3 Phase 2 专题
- `docs/archive/phase2/`

## 5. 后续新增规则
1. 需求、设计、架构统一进 `spec/`
2. 实施和阶段推进统一进 `plan/`
3. 测试方案和清单统一进 `test/`
4. 测试执行结果统一进 `test_report/`
5. 面试材料统一进 `interview/`
6. 运行和环境说明统一进 `guide/`
7. 老方案、实验稿、阶段记录统一进 `archive/`

## 6. 当前建议阅读顺序
如果接下来准备做知识库问答手工测试，建议按这个顺序看：

1. [需求文档 PRD](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/spec/agent_v1_prd.md)
2. [实施计划](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/plan/agent_v1_execution_plan.md)
3. [测试方案](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/test/knowledge_qa_test_plan.md)
4. [PDF 手工测试检查清单](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/docs/test/pdf_manual_test_checklist.md)
