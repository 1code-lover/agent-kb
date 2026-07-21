# 20260717-agent-qa-page-refactor-frd

## 1. 功能范围

本期仅调整前端问答产品层，不修改后端 API 契约。

## 2. 页面结构

### 2.1 顶层体验模式
`/agent` 顶层分为三种体验：

1. `basic`
   - 标签：基础问答
   - 行为：调用 `/api/chat/query`，不传 `kb_ids`
   - 目标：让用户直接开始问答

2. `knowledge`
   - 标签：知识库问答
   - 行为：调用 `/api/chat/query`，传 `kb_ids=[selectedKbId]`
   - 约束：未选择 active KB 时禁止发送

3. `agent`
   - 标签：Agent 高级模式
   - 行为：保留现有 `/api/agent/run` 链路与运行时侧边抽屉

### 2.2 问答主区
基础问答与知识库问答共用一个聊天工作台，包含：
- 顶部标题与模式说明
- 问答范围卡片
- 知识库选择器（仅 knowledge 模式显示）
- 聊天记录区
- 问题输入区
- 最新回答来源卡片

### 2.3 高级模式区
复用现有 `AgentTimeline`、`AgentInputPanel`、`AgentApprovalPanel`、`AgentReceiptsPanel`、`AgentEvidencePanel`。

## 3. 数据流

### 3.1 基础问答
1. 用户输入问题。
2. 前端拼装：`{ question, session_id }`。
3. 调用 `queryChat()`。
4. 成功后刷新 `getHistory(session_id)`，并展示 `answer + sources`。

### 3.2 知识库问答
1. 用户在页面内显式选择一个 active KB。
2. 前端拼装：`{ question, session_id, kb_ids: [selectedKbId] }`。
3. 调用 `queryChat()`。
4. 成功后刷新该会话历史，并展示范围提示与来源卡片。

### 3.3 Agent 高级模式
沿用现有行为：`runAgent()`、`getAgentSession()`、`getPendingActions()`、`getAgentReceipts()` 等不变。

## 4. 状态管理

### 4.1 本地问答体验状态
新增纯前端体验状态（页面内管理即可）：
- `experience`: `basic | knowledge | agent`
- `latestChatResult`
- `chatDraft`

### 4.2 知识库范围同步
- 复用 `KbProvider` / `useKb()` 获取 KB 列表和当前选择。
- 当选中 KB 时，同步更新 Agent store 中的 `knowledgeScope`，保证高级模式也能感知当前 KB 范围。

## 5. 交互规则

1. 进入 `/agent` 默认落到“基础问答”。
2. 切到“知识库问答”后，如果未选择 KB，展示空态引导和“前往知识库管理”入口。
3. 切到“Agent 高级模式”后，原有详情抽屉能力保留。
4. 最新一次问答成功后，在主区下方展示来源卡片；无来源时显示“本轮未返回来源”。
5. 问答请求失败时，在聊天区显示错误提示，不影响用户继续输入。

## 6. 文件变更

- `webapp/src/pages/AgentPage.jsx`
- `webapp/src/api/chat.js`
- `webapp/src/components/ShellLayout.jsx`
- `webapp/src/domain/agentExperience.js`（新增）
- `webapp/src/domain/agentExperience.test.js`（新增）
- `webapp/src/pages/agent-page.css`（新增）
- `docs/project.md`
- `docs/guide/DOCS_INDEX.md`
