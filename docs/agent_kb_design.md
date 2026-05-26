# ThinkRAG 智能体 + 知识库设计方案

## 1. 目标

在现有桌面化 ThinkRAG 基础上，建设一个可观测、可控、可扩展的本地智能体能力，满足：

- 结合知识库进行问答与任务执行；
- 支持工具调用并输出步骤化执行轨迹；
- 支持本地优先与安全边界控制；
- 保持与当前桌面 API 架构兼容。

## 2. 能力边界

第一阶段（MVP）仅聚焦：

- 单 Agent 循环（不做多 Agent 协同）；
- 工具集：`kb_search`、`read_file`、`run_cmd`；
- 工具回执（Action Receipt）可查询可展示；
- 失败场景可读错误（不崩溃）。

## 3. 架构分层

```mermaid
flowchart LR
user[User] --> queryUi[QueryPage AgentMode]
queryUi --> agentApi[/api/agent/run]
agentApi --> orchestrator[AgentService]
orchestrator --> toolKb[kb_search]
orchestrator --> toolRead[read_file]
orchestrator --> toolCmd[run_cmd allowlist]
toolKb --> ragCore[server/engine + index]
orchestrator --> receiptStore[tool_receipt_store]
queryUi --> receiptsApi[/api/agent/receipts]
receiptsApi --> receiptStore
```

## 4. 核心流程

### 4.1 Agent 执行流程

1. 前端发送 `question/session_id` 至 `/api/agent/run`；
2. `agent_service` 根据规则决定工具路径：
   - 问题包含本地路径 -> `read_file`
   - `cmd:` 前缀 -> `run_cmd`（白名单）
   - 其他问题 -> `kb_search`
3. 每一步写入回执（输入、输出、状态、时间）；
4. 返回 `answer + steps + receipts` 给前端。

### 4.2 回执展示流程

1. 前端调用 `/api/agent/receipts` 获取最近回执；
2. 在 Query 页侧栏展示工具、状态、输出摘要；
3. 用户可据此追踪智能体执行链路。

## 5. 数据结构（最小）

- `AgentRunRequest`: `question/session_id/mode`
- `Receipt`: `id/session_id/tool_name/input/output/status/created_at`
- `AgentResult`: `answer/steps/receipts`

## 6. 安全策略

- `run_cmd` 仅允许白名单命令；
- 文件读取仅允许存在且可读的本地文件；
- 高风险命令默认拒绝（后续可加审批流）；
- API key 在模型配置返回中统一脱敏。

## 7. 当前实现状态（已落地）

- 已新增 `/api/agent/run`、`/api/agent/receipts`；
- 已新增 `/api/agent/pending`、`/api/agent/approvals` 审批链路；
- 已新增 `tool_receipt_store`；
- Query 页面支持 Agent 模式与执行轨迹侧栏；
- 已实现命令风险分级（low/medium/high）与待审批队列；
- 审批动作已记录审计字段（审批人、审批理由、审批时间、审批结果）；
- 已补充接口测试与构建验证。

## 8. 下一阶段建议

- 增加 “计划步骤” 显式输出（Plan 文本）；
- 增加工具参数结构化校验（Schema）；
- 增加工具超时与重试策略；
- 增加工具风险等级与 UI 审批；
- 引入会话级长期记忆（摘要压缩 + 关键事实存储）。

## 9. 验收标准

- Agent 模式下至少 1 个工具步骤可见；
- 回执包含工具名、状态、输出摘要；
- 错误场景返回明确错误消息；
- 相关 API 测试通过，前端构建通过。
