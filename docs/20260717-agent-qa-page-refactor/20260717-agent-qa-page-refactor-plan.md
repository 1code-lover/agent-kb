# 20260717-agent-qa-page-refactor-plan

## 1. 实施依据

依据本专题 PRD / FRD / RTM，采用最小前端改造策略：不新增后端接口，优先复用已有 `KbContext`、`queryChat()`、`getHistory()` 和 Agent runtime 组件，将 `/agent` 收口成“问答优先 + 高级模式折叠”的产品结构。

## 2. TDD 顺序与任务拆分

### Task 1：先补纯规则测试
- 新增 `webapp/src/domain/agentExperience.test.js`
- 覆盖：
  - 三种体验模式的标签和描述
  - 基础问答 payload 不传 `kb_ids`
  - 知识库问答 payload 传 `kb_ids=[selectedKbId]`
  - 未提供 KB 时知识库问答应抛错
  - 问答范围摘要文案
- 首次运行预期失败：实现模块不存在

### Task 2：实现问答体验规则模块
- 新增 `webapp/src/domain/agentExperience.js`
- 输出：
  - `AGENT_EXPERIENCES`
  - `buildChatPayload()`
  - `buildExperienceSummary()`
  - `buildChatSessionId()`

### Task 3：重构 `/agent` 页面
- 修改 `webapp/src/pages/AgentPage.jsx`
- 做法：
  - 用 `KbProvider` 包裹页面
  - 问答页默认进入基础问答
  - 基础问答 / 知识库问答接入 `queryChat()` 与 `getHistory()`
  - 知识库问答复用 `useKb()` 显式选择 KB
  - Agent 高级模式内嵌保留旧 runtime 结构

### Task 4：补充页面样式和导航文案
- 新增 `webapp/src/pages/agent-page.css`
- 修改 `webapp/src/components/ShellLayout.jsx`
- 内容：
  - 问答工作台卡片、模式切换、消息气泡、来源区、空态和高级模式容器样式
  - 侧边栏“Agent”文案改为“问答”

### Task 5：测试与文档
- 执行 Node 测试、Vite 构建、浏览器烟测、`git diff --check`
- 更新：
  - `docs/project.md`
  - `docs/guide/DOCS_INDEX.md`
  - 本专题 `test-plan` / `test-report`

## 3. 执行命令

```powershell
node --test webapp/src/domain/agentExperience.test.js webapp/src/api/response.test.js webapp/src/domain/kbSelection.test.js
cd webapp; npm run build; cd ..
git diff --check
```

## 4. 预期结果

- 新增纯规则测试通过
- `/agent` 页面默认呈现问答工作台
- 可在页面上区分基础问答、知识库问答和 Agent 高级模式
- Vite 构建通过
- 文档同步后无格式错误
