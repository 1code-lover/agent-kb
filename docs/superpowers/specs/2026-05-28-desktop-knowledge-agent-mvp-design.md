# 桌面端 Knowledge Agent MVP 设计方案

## 1. 产品目标

ThinkRAG 不应该继续表现为“一个本地 RAG 应用外加一个附属 Agent 入口”，而应该演进成“桌面端优先的知识型 Agent 产品”。第一版的优化重点不是最大化自治能力，而是优先保证可见性、可控性和可扩展性。

MVP 的目标是：用户打开桌面应用后，可以输入一个任务，看到 Agent 实际调用了什么工具，查看证据和回执，对高风险命令进行审批，并在不切换页面的情况下拿到结构化结果。

## 2. 范围定义

### 2.1 第一阶段要做的

- 桌面端唯一产品形态
- Electron 作为应用外壳
- React 作为嵌入 Electron 的前端界面
- FastAPI 作为本地运行时
- Agent Workspace 作为首页
- 支持四种执行模式：
  - `agent`
  - `kb_search`
  - `read_file`
  - `run_cmd`
- 混合路由：
  - 规则优先
  - 当规则无法明确判断时，允许 LLM 决策
- 返回结构化运行结果：
  - `task_state`
  - `plan`
  - `steps`
  - `timeline`
  - `evidence`
  - `receipts`
  - `pending_actions`
- 对命令执行增加风险分级和审批流程
- 将 `kb_search` 作为一等 Agent 工具接入

### 2.2 第一阶段不做的

- 浏览器优先或公网 Web 产品
- 自动代码编辑
- patch apply 和 diff preview
- 多知识库隔离
- WebSocket 或 SSE 实时流
- 长期 memory
- 动态插件或工具市场
- 全自治多步规划循环

## 3. 用户体验设计

桌面应用打开后直接进入 Agent Workspace，而不是传统问答页。页面必须允许用户输入一个任务、选择一个模式、执行它，并在同一个页面里查看完整执行过程。

### 3.1 工作台核心区域

- 输入区
  - 任务输入框
  - 模式切换器
  - 执行按钮
- 状态栏
  - 当前状态
  - 待审批数量
  - 最近更新时间
- 时间线面板
  - 用户消息
  - 工具步骤
  - 助手响应
- 证据面板
  - 证据摘录
  - 来源元数据
  - 与 receipt 的关联关系
- 审批面板
  - 待审批命令
  - 批准 / 拒绝操作
- 回执面板
  - 当前 session 的工具回执

### 3.2 模式语义

- `agent`
  - 由系统决定应该调用哪个工具
  - 常见场景优先由规则处理
  - 只有规则不够用时才允许 LLM 路由
- `kb_search`
  - 强制只做知识检索
- `read_file`
  - 强制只做本地文件读取
- `run_cmd`
  - 强制走命令执行和风险审批流程

## 4. 总体架构

MVP 建议稳定拆成五层。

### 4.1 Desktop Shell

位置：`desktop/`

职责：
- 启动本地 Python API
- 打开桌面窗口
- 管理应用生命周期

非目标：
- 不放业务逻辑
- 不做 Agent 路由
- 不做知识库逻辑

### 4.2 Workspace UI

位置：`webapp/`

职责：
- 渲染 Agent Workspace
- 收集用户输入
- 展示 API 返回的结构化结果

非目标：
- 不做工具决策
- 不从零散后端数据自行拼时间线
- 不承担审批策略逻辑

### 4.3 Agent API

位置：`api/routers` 和 `api/services`

职责：
- 接收前端请求
- 触发一次 Agent 运行
- 返回稳定的结构化响应 contract

传输方式选择：
- MVP 继续采用 HTTP 请求响应和轮询
- 第一阶段不引入实时流

### 4.4 Agent Runtime

位置：`api/services` 下新增独立模块

职责：
- 构建本次运行的 plan 摘要
- 选择工具路由
- 执行工具
- 写入 receipts
- 组装 session 级运行结果

这一层是 MVP 最核心的结构性改造。

### 4.5 Knowledge Core

位置：`server/` 和 `api/runtime.py`

职责：
- ingestion
- 索引加载
- 检索
- 回答生成

知识系统仍然很重要，但在第一阶段它被定义为工具后端，而不是产品主入口。

## 5. 后端边界设计

当前的 `api/services/agent_service.py` 应该被瘦身并拆分成多个职责清晰的模块。

### 5.1 推荐新增模块

- `api/services/agent_runtime.py`
  - 负责一次 agent run 的完整调度
- `api/services/agent_router.py`
  - 负责规则优先、LLM 兜底的路由判断
- `api/services/agent_tools.py`
  - 提供统一工具注册表，封装：
    - `kb_search`
    - `read_file`
    - `run_cmd`
- `api/services/approval_service.py`
  - 负责风险分级与审批状态流转
- `api/services/timeline_service.py`
  - 将执行结果映射成前端直接可渲染的 timeline、steps 和 evidence

### 5.2 继续复用的现有模块

- `api/runtime.py`
- `api/services/chat_service.py`
- `api/services/kb_service.py`
- `api/services/tool_receipt_store.py`
- `server/engine.py`
- `server/retriever.py`

## 6. 前端边界设计

### 6.1 现有文件建议修改

- `webapp/src/App.jsx`
- `webapp/src/components/ShellLayout.jsx`
- `webapp/src/store/appStore.js`
- `webapp/src/store/agentState.js`
- `webapp/src/api/agent.js`

### 6.2 建议新增文件

- `webapp/src/pages/AgentPage.jsx`
- `webapp/src/components/agent/AgentInputPanel.jsx`
- `webapp/src/components/agent/AgentTaskStateBar.jsx`
- `webapp/src/components/agent/AgentTimeline.jsx`
- `webapp/src/components/agent/AgentEvidencePanel.jsx`
- `webapp/src/components/agent/AgentApprovalPanel.jsx`
- `webapp/src/components/agent/AgentReceiptsPanel.jsx`

### 6.3 前端基本规则

前端只负责把后端返回的结构化结果映射成 UI 状态，不允许从部分数据自行推导业务含义，也不应该自行重建 Agent 执行图。

## 7. API Contract

第一阶段应先冻结稳定 contract，再扩大 UI 开发范围。

### 7.1 运行请求

`POST /api/agent/run`

```json
{
  "session_id": "default",
  "mode": "agent",
  "question": "帮我总结知识库里的部署流程。",
  "tool_hint": null,
  "knowledge_scope": {
    "kb_id": "default",
    "kb_name": "Default KB"
  }
}
```

### 7.2 运行响应

```json
{
  "session_id": "default",
  "question": "帮我总结知识库里的部署流程。",
  "knowledge_scope": {
    "kb_id": "default",
    "kb_name": "Default KB"
  },
  "answer": "...",
  "task_state": {
    "status": "completed",
    "pending_approval_count": 0,
    "updated_at": "2026-05-28T10:00:00Z"
  },
  "plan": [],
  "steps": [],
  "timeline": [],
  "evidence": [],
  "receipts": [],
  "pending_actions": []
}
```

### 7.3 其他接口

- `GET /api/agent/receipts`
- `GET /api/agent/pending`
- `POST /api/agent/approvals`

### 7.4 响应规则

- 四种模式都必须返回相同的顶层结构
- 即使失败，也应尽量返回可展示的结构化状态
- 前端不应依赖“某些模式缺字段”这种行为

## 8. Runtime 行为定义

### 8.1 路由策略

MVP 采用混合路由：

- 常见场景规则优先
- 规则无法明确判断时，才启用 LLM 辅助路由

### 8.2 规则优先的场景

- 明确本地路径 -> `read_file`
- 命令模式或明显命令意图 -> `run_cmd`
- 明确知识问答意图 -> `kb_search`

### 8.3 审批策略

`run_cmd` 必须把命令分成：

- `low`
- `medium`
- `high`

策略要求：
- `low` 可直接执行
- `medium` 和 `high` 必须进入审批队列
- 被拒绝的动作需要留下审计记录，且不得执行

## 9. 实施里程碑

### 里程碑 1：冻结 Contract

- 定义 schemas
- 稳定 endpoint 返回结构
- 确保四种模式都走同一套结构

### 里程碑 2：拆分 Agent Runtime

- 抽出运行时模块
- 保持当前功能不倒退
- 集中审批和时间线逻辑

### 里程碑 3：交付 Agent Workspace

- 创建 `AgentPage`
- 将它设为首页
- 渲染 plan、steps、evidence、approvals、receipts

### 里程碑 4：优化混合路由体验

- 优化步骤摘要
- 改进证据展示
- 优化审批提示文案
- 将 LLM 路由限制在明确需要的场景

## 10. 风险与取舍

### 10.1 主要风险

- 如果不尽早拆分，`agent_service.py` 会继续膨胀
- 前端可能开始从局部状态自行推导业务语义
- LLM 路由可能过早成为主逻辑
- 产品容易重新退回“问答页升级版”
- 浏览器端诉求可能重新进入范围

### 10.2 当前取舍

- 用 HTTP 轮询，不上实时流
- 用规则优先，而不是完全自治规划
- 第一阶段只保留单默认知识范围
- MVP 不做代码编辑工具
- 产品边界明确为桌面端

## 11. 后续扩展：多知识库支持

第二阶段应该引入明确的 knowledge scope，但不能推翻第一阶段架构。

### 11.1 第一阶段需要预留的兼容位

请求和响应中应从一开始就预留：

- `knowledge_scope.kb_id`
- `knowledge_scope.kb_name`

MVP 阶段可以只用一个默认 scope。

### 11.2 第二阶段方向

- knowledge registry
- 按 `kb_id` 获取 index manager
- `kb_search(question, kb_id)`
- session 与 scope 绑定
- UI 顶部增加知识库选择器

第一版多知识库只允许“一次任务绑定一个明确知识库”，不做跨库联合检索。

## 12. 验收标准

- 桌面应用打开后直接进入 Agent Workspace
- 用户可以在同一个页面执行四种模式
- 每次运行都能看到 plan、steps、timeline、evidence、receipts 和 pending approvals
- `run_cmd` 审批能在同一个 session 内完成闭环
- `kb_search` 返回的证据带有足够的来源元数据，前端可直接展示
- 后端结构不再集中在一个单体 agent service 文件中
