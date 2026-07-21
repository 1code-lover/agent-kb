# 20260717-agent-qa-page-refactor-rtm

| FR | 需求 | 设计落点 | 验证方式 | 通过标准 |
|---|---|---|---|---|
| FR-01 | `/agent` 顶层提供基础问答 / 知识库问答 / Agent 高级模式三个入口 | `AgentPage.jsx` 顶层模式切换 | 手工烟测 + 构建 | 三个入口可见且可切换 |
| FR-02 | 基础问答走纯问答 API | `queryChat()` + `AgentPage.jsx` | Node 规则测试 + 手工问答 | 不传 `kb_ids` 也能提交并显示回答 |
| FR-03 | 知识库问答要求显式选择 active KB | `KbProvider` + `agentExperience.js` | Node 规则测试 + 手工问答 | 未选禁发，选中后可发 |
| FR-04 | 知识库问答将选中 KB 转为 `kb_ids=[selectedKbId]` | `agentExperience.js` | Node 规则测试 | payload 正确 |
| FR-05 | 页面明确展示当前问答范围与 KB 信息 | `AgentPage.jsx` + `agent-page.css` | 手工烟测 | 可见范围文案与 KB 元数据 |
| FR-06 | 最新一次问答结果展示来源信息 | `AgentPage.jsx` | 手工烟测 | 来源卡片显示 file / kb / page / score |
| FR-07 | Agent 高级模式保留原运行时链路 | 现有 Agent 子面板复用 | 手工烟测 | 可进入高级模式且详情抽屉仍可用 |
| FR-08 | 导航文案更贴近问答产品 | `ShellLayout.jsx` | 手工烟测 | 侧边导航从“Agent”调整为“问答” |
| FR-09 | 文档与项目进度同步 | `docs/project.md` / `DOCS_INDEX.md` / 本专题文档 | 文档检查 | 文档反映新页面定位 |
