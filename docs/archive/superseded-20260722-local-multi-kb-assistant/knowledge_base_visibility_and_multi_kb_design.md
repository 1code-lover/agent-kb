> 已归档（2026-07-23）：本文件已被 `docs/20260722-local-multi-kb-assistant/` 下的新一轮 PRD / FRD / RTM / Plan / Test Plan 基线取代，不再作为当前正式基线，仅保留用于历史追溯。
# ThinkRAG 最小多知识库设计（代码对齐版）

> 文档目标：定义当前仓库“最小多知识库”应该解决什么，以及 **2026-07-13 这一天代码实际上做到哪一步**。
> 本文只讨论“导入归属哪个知识库、查询查哪些知识库、结果来自哪个知识库”，**不讨论权限系统**。

## 1. 本文解决的问题

当前最小多知识库只保留三件事：

1. 文档导入时必须归属某个 `kb_id`
2. 查询时可以指定一个或多个 `kb_id`
3. 返回结果必须标明来源知识库

## 2. 本文明确不做的事

这一版设计**不处理权限模型**，因此不引入：

- `user_id`
- `role`
- `group_ids`
- `visibility`
- owner / admin 删除授权
- “谁能看哪些知识库”的 ACL 规则

如果未来真的进入多人共享场景，应另起权限设计文档，而不是继续把权限逻辑混进当前最小多知识库方案。

## 3. 2026-07-14 代码现状

### 3.1 已经落地的部分

| 能力 | 当前状态 | 代码依据 |
|---|---|---|
| 默认索引 | 仍是单个 `knowledge_base` | `config.py` 的 `DEFAULT_INDEX_NAME` |
| 运行时索引管理 | `RuntimeState` 只维护一个 `IndexManager` | `api/runtime.py` |
| Query 契约 | `QueryRequest` 已有 `kb_ids: list[str] | None` | `api/schemas/__init__.py` |
| 聊天查询透传 | `chat_service.query()` 已把 `request.kb_ids` 传给 `runtime_state.build_query_engine()` | `api/services/chat_service.py` |
| 检索过滤 | `server/engine.py` 已支持 `kb_ids`，并通过 `KBIdFilter` 做 metadata 过滤 | `server/engine.py`、`server/kb_filter.py` |
| KB 目录 CRUD | 已有 `POST /api/kb`、`GET /api/kb`、`GET/PUT/DELETE /api/kb/{kb_id}` | `api/routers/kb.py`、`api/services/kb_service.py` |
| 文件导入绑定 KB | `POST /api/kb/file/import` 支持表单 `kb_id`，并透传到 `kb_service.import_files(..., kb_id=...)` | `api/routers/kb.py`、`api/services/kb_service.py` |
| 原始文件布局 | 文件仍由无参 `get_save_dir()` 写入共享 `data/` 根目录 | `server/utils/file.py`、`api/services/kb_service.py` |
| URL 导入数据模型 | `UrlImportRequest` 已有 `kb_id` 字段；`kb_service.import_urls(..., kb_id=...)` 也已支持 | `api/schemas/__init__.py`、`api/services/kb_service.py` |
| 文档列表 / 删除 | `GET /api/kb/list?kb_id=...`、`DELETE /api/kb/docs` 已存在 | `api/routers/kb.py`、`api/services/kb_service.py` |
| Agent 工作区状态 | `AgentRunRequest`、session snapshot、workspace state 都已携带 `knowledge_scope` | `api/schemas/__init__.py`、`api/services/agent_runtime.py` |

### 3.2 2026-07-13 已补齐的闭环与剩余缺口

| 项目 | 当前实际情况 | 结论 |
|---|---|---|
| Agent 查询消费 scope | `agent_runtime.run_agent()` 在 `kb_search` 分支会把 `knowledge_scope.kb_id` 转成 `kb_ids=[kb_id]`，并传入 `run_kb_search(..., kb_ids=...)` | Agent 路径已接入最小多知识库查询契约 |
| Agent evidence 的 KB 标识 | `normalize_evidence()` 已从 `source.get("kb_id", "default")` 回填 evidence | 前端 / 回执可看到真实来源库 |
| Web 导入透传 `kb_id` | `POST /api/kb/web/import` 已调用 `kb_service.import_urls(..., kb_id=request.kb_id)` | 网页导入与文件导入行为已对齐 |
| 旧数据兼容策略会放宽过滤 | `KBIdFilter` 对“没有 `kb_id` metadata 的节点”默认保留 | 仍是当前唯一需要明确承认的多库残余风险 |

### 3.3 当前实现的准确认知

因此，当前实现**不是物理隔离的多索引 / 多 namespace 方案**，而是：

- **一个共享索引**（`knowledge_base`）
- **写入时尽量给文档打上 `kb_id` metadata**
- **查询时按 `kb_ids` 做后置过滤**
- **为了兼容旧数据，未标注 `kb_id` 的节点暂时仍会被保留**
- **本轮目录化编码已将新导入原始文件写入 `data/{kb_id}/`；历史根目录文件需通过迁移脚本或重导处理**

这说明当前多知识库能力更准确的说法应是：

> **单共享索引 + `kb_id` metadata 过滤的过渡方案**

而不是“已经完成物理多库隔离”。

### 3.4 已编码的目录化存储

2026-07-15 已形成 `docs/20260714-kb-directory-storage/` PRD/FRD/RTM/Plan/Test Plan/Test Report，并完成阶段 5 正式测试。新导入文件保存为 `data/{kb_id}/`，导入前校验 KB active，列表和删除按 `kb_id` 严格隔离；旧无 `kb_id` 节点只归 `default`。第一阶段仍保留共享向量索引，迁移脚本只移动原始文件，不自动修复旧索引 metadata/query 一致性。当前等待测试报告评审。

## 4. 最小正式契约

### 4.1 知识库目录模型

当前 `KBRegistry` 的实际最小数据模型为：

```json
{
  "kb_id": "kb_product",
  "kb_name": "产品知识库",
  "created_at": "2026-07-13T00:00:00+00:00",
  "updated_at": "2026-07-13T00:00:00+00:00",
  "status": "active",
  "doc_count": 0
}
```

当前阶段真正必须稳定的字段是：
- `kb_id`：知识库唯一标识
- `kb_name`：展示名称
- `status`：当前状态（现阶段主要是 `active`）
- `doc_count`：文档计数（统计值）

### 4.2 查询契约

正式输入统一采用 `kb_ids`，而不是让不同入口各自发明 `kb_id` / `search_scope` / 其他变体。

示例：

```json
{
  "question": "报销单 OCR 支持到什么程度？",
  "session_id": "desktop-default",
  "kb_ids": ["kb_product", "kb_ops"]
}
```

约定：
1. 单库查询也统一写成 `kb_ids`，只是列表长度为 1。
2. 不传 `kb_ids` 时，代表“不过滤知识库范围”，这与当前 `chat_service.query()` 的行为一致。
3. Agent 路径如果从 `knowledge_scope` 出发，也应在进入 `QueryRequest` 前转换成 `kb_ids`。

### 4.3 导入契约

#### 文件导入
当前接口：`POST /api/kb/file/import`

请求形态（multipart/form-data）：
- `files`
- `chunk_size`
- `chunk_overlap`
- `kb_id`

当前实现已经支持把 `kb_id` 透传到服务层。

#### 网页导入
当前接口：`POST /api/kb/web/import`

请求体应为：

```json
{
  "urls": ["https://example.com/doc"],
  "chunk_size": 2048,
  "chunk_overlap": 512,
  "kb_id": "kb_product"
}
```

当前 router 已把请求中的 `kb_id` 透传到 `kb_service.import_urls()`，网页导入与文件导入已使用同一知识库归属契约。

### 4.4 文档管理契约

当前已落地接口：

- `GET /api/kb`：列出全部知识库
- `POST /api/kb`：创建知识库
- `GET /api/kb/{kb_id}`：获取单个知识库
- `PUT /api/kb/{kb_id}`：更新知识库名称
- `DELETE /api/kb/{kb_id}`：删除知识库
- `GET /api/kb/list?kb_id=...`：列文档，可按 `kb_id` 过滤
- `DELETE /api/kb/docs`：按请求体删除指定文档

这里要特别说明两点：
1. 目前“知识库目录接口”不是文档里曾经写的 `GET /api/kb/registry`，**实际代码已经使用 `GET /api/kb`**。
2. 当前 `GET /api/kb/list` / `DELETE /api/kb/docs` 的行为比文档里曾经设想的更宽松，并没有统一做到“未登记 `kb_id` 一律返回 400”。如果后续要收紧，应明确作为增量改造项，而不是把尚未实现的规则写成现状。

### 4.5 返回结果契约

至少三类返回应带真实来源库信息：

1. 聊天查询的 `sources`
2. Agent evidence
3. 文档列表 / 删除确认等管理结果

当前普通聊天查询的 `sources` 已按 metadata 回填：
- `kb_id = metadata.get("kb_id", "default")`

当前 Agent evidence 也已经复用同一条真实数据链路：
- `kb_id = source.get("kb_id", "default")`

## 5. 当前剩余工作应如何排序

### 5.1 已经完成的本轮收口

1. **Agent scope → `kb_ids` 已打通**
   - `run_kb_search()` 已支持显式接收 `kb_ids`
   - `agent_runtime.py` 会把 `knowledge_scope.kb_id` 转成 `[kb_id]` 再传入

2. **Agent evidence 的真实 `kb_id` 已修正**
   - `normalize_evidence()` 已从 `source` 中读取 `kb_id`
   - 不再写死 `"default"`

3. **网页导入 `kb_id` 已补齐**
   - `api/routers/kb.py` 的 `import_web()` 已改为调用
   - `kb_service.import_urls(request.urls, request.chunk_size, request.chunk_overlap, kb_id=request.kb_id)`

### 5.2 当前仍应继续推进的事

1. **明确旧数据兼容边界**
   - 当前 `KBIdFilter` 保留“无 `kb_id` metadata 节点”，适合过渡期
   - 但必须在产品和文档口径里明确这是泄漏风险，不是严格隔离

2. **继续演进隔离模型**
   - 本轮已完成并测试通过原始文件 `data/{kb_id}/` 目录归属
   - 物理多索引 / 多 namespace 隔离
   - 更严格的 `kb_id` 合法性校验
   - 删除动作的权限控制
   - 用户级可见性和角色管理

## 6. 存量数据迁移建议

### 6.1 首选方案：可重导就重导

如果旧文档源文件仍可获取，最稳妥的方式是：
1. 为每个目标知识库准备明确的 `kb_id`
2. 重新导入文件 / URL
3. 确保新数据从写入阶段就带上 `kb_id` metadata
4. 再逐步收紧过滤规则

这是最干净、也最容易演进到未来物理隔离方案的路径。

### 6.2 过渡方案：旧数据暂时兼容

如果部分历史文档暂时无法重导：
- 可以先保留“无 `kb_id` 仍可被检索”的兼容逻辑
- 但必须承认这只是过渡状态
- 后续仍应安排补标 / 重导 / 重建索引

不要把这种兼容策略包装成正式长期方案。

## 7. 测试与验证状态

当前仓库已经有多知识库相关测试基础，主要分布在：
- `tests/api/test_kb_registry.py`
- `tests/api/test_kb_registry_atomic.py`
- `tests/api/test_kb_routes.py`
- `tests/api/test_m2_multi_kb.py`
- `tests/api/test_agent_runtime.py`
- `tests/api/test_kb_directory_storage.py`
- `tests/api/test_kb_docs_isolation.py`
- `tests/api/test_index_manager_coverage.py`
- `tests/utils/test_file_kb_paths.py`
- `tests/scripts/test_migrate_kb_directory_storage.py`
- `tests/test_rag_quality_fixtures.py`

2026-07-13 本轮已补上三类回归断言：
1. Agent `kb_search` 会把 `knowledge_scope` 转成 `kb_ids`
2. Agent evidence 返回真实 `kb_id`
3. `POST /api/kb/web/import` 会把请求中的 `kb_id` 透传到 `kb_service.import_urls()`

本地验证结果：
- 2026-07-15 阶段 5 核心目录化功能：`python -m pytest tests/utils/test_file_kb_paths.py tests/api/test_kb_directory_storage.py tests/api/test_kb_docs_isolation.py tests/api/test_kb_registry.py tests/api/test_kb_registry_atomic.py tests/scripts/test_migrate_kb_directory_storage.py tests/test_rag_quality_fixtures.py tests/api/test_index_manager_coverage.py -q` -> `90 passed in 9.36s`
- 2026-07-15 KB / 多 KB / Agent 定向回归：`python -m pytest tests/api/test_kb_routes.py tests/api/test_m2_multi_kb.py tests/api/test_agent_runtime.py -q` -> `45 passed, 2 warnings in 3.70s`
- 2026-07-15 非 slow 全量门禁：`python -m pytest tests -q -m "not slow"` -> `168 passed, 1 deselected, 2 warnings in 5.74s`
- 2026-07-15 目录化相关文件覆盖率：`coverage report --include=... --fail-under=80` -> `84%`

## 8. 当前结论

当前这套多知识库实现已经**不再是“完全单库”**，同时也已经补齐了“导入归属、查询范围、结果来源”这条最小闭环；但它**仍然不是“真正隔离的多库”**。

更准确的项目口径应该是：

1. **基础设施与最小闭环都已落地**：registry、`kb_ids` 契约、查询过滤、KB CRUD、文件/网页导入绑定 KB、Agent scope 透传、Agent evidence 真值都已经有了。
2. **当前主要风险集中在旧数据迁移和共享索引架构层级**：新导入原始文件已进入 `data/{kb_id}/`，但历史根目录文件与旧索引 metadata/query 一致性需要迁移、重导或重建索引处理。
3. **当前方案是共享索引上的 metadata 过滤过渡态**：适合先把最小多知识库跑通，但不应对外宣称成“物理隔离多库架构”。

在当前阶段，最重要的不是继续扩展权限概念，而是决定何时收紧旧数据兼容策略，以及是否推进到物理隔离方案。
