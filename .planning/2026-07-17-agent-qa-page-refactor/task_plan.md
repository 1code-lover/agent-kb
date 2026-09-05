# Task Plan: Agent QA Page Refactor

## Goal
把 `/agent` 从偏调试的 Agent 控制台整理为“问答优先”的工作台：支持基础问答、显式选择知识库后的定向问答，并保留原有 Agent 高级模式能力。

## Scope
- `/agent` 页面信息架构重组与样式重做
- 基础问答与知识库问答的前端链路接入 `/api/chat/query`
- 显式知识库选择、范围提示、来源展示与空态/异常态
- 原 Agent runtime 面板保留为高级模式，不破坏审批/回执/证据能力
- 文档、测试方案、测试报告与项目概览同步

## Phases
1. [completed] 固化本次 PRD/FRD/RTM/Plan/Test Plan
2. [completed] 先写纯前端规则测试，固定问答模式与请求拼装行为
3. [completed] 实现问答优先页面、知识库选择与高级模式收纳
4. [completed] 执行 Node 测试、Vite 构建、必要手工烟测
5. [completed] 更新测试报告、project.md、DOCS_INDEX 与阶段结论

## Constraints
- 不改动后端问答协议，仅复用现有 `/api/chat/query`、`/api/chat/history`、`/api/agent/run`
- 基础问答必须可用；知识库问答必须要求用户显式选中 active KB
- Agent 高级模式能力保留，不能因为 UI 重构破坏审批/回执/证据链路
- 尽量避免覆盖当前 working tree 中其他未提交改动；对共享文件采用增量修改
- 遵循仓库流程：先文档/计划，后实现，后测试报告

## Validation Gates
- 新增纯规则测试先失败后通过
- 前端 Node 测试通过
- `npm run build` 通过
- 浏览器 smoke 覆盖基础问答、知识库选择、Agent 高级模式入口
- 文档同步后 `git diff --check` 通过
