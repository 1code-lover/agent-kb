# 多知识库 Agent 查询与网页导入闭环修复

## 基本信息
- 类型：bug
- 日期：2026-07-13
- 相关模块：多知识库、Agent KB 查询、网页导入、Evidence 回执
- 相关文件：`api/services/agent_tools.py`、`api/services/agent_runtime.py`、`api/routers/kb.py`、`tests/api/test_agent_runtime.py`、`tests/api/test_kb_routes.py`、`tests/api/test_m2_multi_kb.py`、`docs/project.md`、`docs/spec/knowledge_base_visibility_and_multi_kb_design.md`

## 问题现象

项目已经有多知识库基础设施：`QueryRequest.kb_ids`、KB Registry、导入接口里的 `kb_id` 字段以及 Agent 会话中的 `knowledge_scope`。但本轮收口前仍有三个闭环断点：

1. Agent 进入 `kb_search` 模式时，前端/会话里选中的 `knowledge_scope.kb_id` 没有传给 `run_kb_search()`，实际查询仍会落到默认查询范围。
2. Agent evidence 归一化时把 `kb_id` 固定写成 `default`，即使底层 source 已经携带真实 `kb_id`，回执和前端也看不到真实来源库。
3. `POST /api/kb/web/import` 的请求模型已经包含 `kb_id`，但路由调用 `kb_service.import_urls()` 时没有透传，导致网页导入无法稳定落入指定知识库。

这些问题会让“多知识库可见性”在 UI 状态、查询结果、导入链路之间表现不一致：用户以为自己在指定库中查或导入，但后端关键路径没有完全消费这个范围。

## 根因分析

根因不是缺少多知识库底层能力，而是已有契约没有沿调用链完整传递：

- `api/services/agent_runtime.py` 的 `kb_search` 分支只调用 `run_kb_search(session_id, question)`，没有从 `request.knowledge_scope` 派生 `kb_ids`。
- `api/services/agent_tools.py` 中 `run_kb_search()` 原本没有 `kb_ids` 参数，因此也无法构造带范围的 `QueryRequest`。
- 同文件里的 `normalize_evidence()` 在数据归一化阶段丢弃了 source 里的真实 `kb_id`。
- `api/routers/kb.py` 的网页导入路由只取了 URL 和切分参数，漏掉了请求体中的 `kb_id`。

也就是说，多知识库状态已经进入了 schema 和部分 service，但 Agent 与网页导入这两条真实用户路径没有完成端到端接线。

## 解决方案

本次修复按“最小闭环”处理，没有重写多知识库架构：

1. 在 `api/services/agent_tools.py` 中扩展 `run_kb_search(session_id, question, kb_ids=None)`，构造 `QueryRequest(question=question, session_id=session_id, kb_ids=kb_ids)`。
2. 在 `api/services/agent_runtime.py` 的 `kb_search` 分支读取 `request.knowledge_scope.kb_id`，去空白后转成 `[kb_id]`，没有选择库时保持 `None`，继续沿用默认范围。
3. 在 `normalize_evidence()` 中把 `kb_id` 改为 `source.get("kb_id", "default")`，保留底层检索来源；旧数据没有 metadata 时仍兼容默认库。
4. 在 `api/routers/kb.py` 中把 `request.kb_id` 透传给 `kb_service.import_urls(..., kb_id=request.kb_id)`。
5. 新增三类回归测试，分别覆盖 Agent scope 透传、网页导入 `kb_id` 透传、Agent evidence 保留真实 `kb_id`。
6. 同步更新 `docs/project.md` 和 `docs/spec/knowledge_base_visibility_and_multi_kb_design.md`，把“已补齐的闭环”和“仍需承认的旧数据兼容风险”写成当前状态。

## 为什么选这个方案

这个方案优先保持现有接口语义和兼容性：

- `kb_ids=None` 继续代表默认/未限定查询范围，不会影响没有选择知识库的旧 Agent 调用。
- evidence 只是在归一化时保留已存在的 source metadata，没有引入新的回执结构。
- 网页导入和已有文件导入统一使用 `kb_id` 参数，避免为不同导入来源维护两套规则。
- 测试使用 mock 验证边界参数，能直接锁住这次断开的调用链，不需要依赖真实向量索引或外部 LLM。

## 其他方案与为什么没选

- 直接重构 Agent 工具协议为多库数组选择：这能支持更复杂的多库并查，但当前前端和 session 主要暴露单个 `knowledge_scope.kb_id`，本轮目标是修复闭环断点，扩大协议会增加额外迁移成本。
- 对缺少 `kb_id` metadata 的旧数据直接硬过滤：这样隔离更严格，但会让历史数据突然不可查。当前文档已明确 `KBIdFilter` 对旧节点仍有兼容放宽，后续如果要收紧，应作为单独迁移任务处理。
- 在前端做兜底提示而不改后端：只能改善展示，不能解决查询和导入实际没有带范围的问题，因此没有选择。

## 验证与结果

聚焦回归测试：

```bash
python -m pytest tests/api/test_agent_runtime.py tests/api/test_kb_routes.py tests/api/test_m2_multi_kb.py -q
```

结果：

```text
42 passed, 2 warnings in 4.22s
```

非 slow 全量快测：

```bash
python -m pytest tests/ -q -m "not slow"
```

结果：

```text
86 passed, 1 deselected, 2 warnings in 3.38s
```

测试中保留了 FastAPI `on_event` 的既有弃用警告，本次修复没有改动该生命周期实现。

## 面试表达版本

我在这个项目里收口了多知识库的一组端到端断点。问题不是底层完全不支持多库，而是 Agent 查询、evidence 回执和网页导入没有把已有的 `kb_id` 契约传到底，导致用户选择了知识库但真实路径可能仍按默认范围执行。我做的修复是把 Agent 的 `knowledge_scope.kb_id` 转成 `QueryRequest.kb_ids`，让 evidence 保留 source 里的真实 `kb_id`，同时补上网页导入路由到 service 的 `kb_id` 透传。为了防止之后再断，我加了三个回归测试分别锁住这三条链路，并跑了相关 API 测试和非 slow 全量测试。这个方案没有扩大协议，只补齐最小闭环，所以兼容旧调用，也把旧数据 `kb_id` metadata 不完整的风险留在文档里明确说明。
