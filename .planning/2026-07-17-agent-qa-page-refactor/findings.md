# Findings

## Confirmed before implementation
- `/agent` 当前默认入口是 `AgentPage`，并且首页 `/` 也直接指向它。
- `AgentPage` 提交主链路走 `/api/agent/run`，不是纯问答页。
- 前端已有 `queryChat()` 与 `getHistory()`，后端 `QueryRequest` 已支持 `kb_ids`，具备“全局问答 / 指定知识库问答”的底层能力。
- 现有知识库显式选择逻辑已集中在 `KbContext` 和 `kbSelection` 规则模块中，可复用。
- 现有 `/agent` 视觉上更像 Agent runtime 调试台，且大量类名缺失样式定义，用户反馈“丑”和“不像问答页”与代码事实一致。

## Design direction
- `/agent` 顶层拆成三个体验层级：基础问答、知识库问答、Agent 高级模式。
- 基础问答与知识库问答共用聊天 UI，但知识库问答增加显式 KB 选择、作用域提示和来源展示。
- Agent 高级模式保留原时间线、工具模式、审批、回执、证据等运行时能力。
