# ThinkRAG 最小多知识库设计

## 1. 文档目的
这份文档只解决最小多知识库能力，不讨论权限系统。

本版目标只保留三件事：
1. 文档导入时必须归属某个 `kb_id`
2. 查询时可以指定一个或多个 `kb_id`
3. 返回结果必须标明来源知识库

## 2. 当前明确不做的事
这一版设计明确不做下面这些内容：

- 不做 `user_id`
- 不做 `role`
- 不做 `group_ids`
- 不做 `visibility`
- 不做 `GET /api/kb/visible`
- 不做 owner/admin 删除校验

这些内容如果未来真的要做多人共享，再单独出权限设计文档，不放在当前最小多知识库设计里。

## 3. 现状与改造边界
这版文档必须建立在当前代码现实上，而不是抽象概念上。

### 3.1 当前代码现状
1. 当前只有单个默认索引 `knowledge_base`
   - 见 [config.py](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/config.py)
2. 运行时只有一个 `IndexManager`
   - 见 [api/runtime.py](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/api/runtime.py)
3. `QueryRequest` 目前没有 `kb_ids` / `search_scope`
   - 见 [api/schemas/__init__.py](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/api/schemas/__init__.py)
4. `AgentRunRequest` 里的 `knowledge_scope` 目前只有 `kb_id` / `kb_name` 两个展示字段
   - 见 [api/schemas/__init__.py](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/api/schemas/__init__.py)
5. `run_kb_search()` 仍然直接走单库查询
   - 见 [api/services/agent_tools.py](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/api/services/agent_tools.py)
6. 证据结果里的 `kb_id` 现在还是写死 `"default"`
   - 见 [api/services/agent_tools.py](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/api/services/agent_tools.py)
7. `import_files()` / `import_urls()` 当前没有任何 `kb_id` 入参
   - 见 [api/services/kb_service.py](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/api/services/kb_service.py)

### 3.2 当前改造边界
因此这次改造不是“在现有多库基础上补字段”，而是：
1. 从单默认库演进成最小多知识库
2. 先解决“导入归属哪个知识库、查询查哪些知识库、结果来自哪个知识库”
3. 暂时不解决“谁能看哪些知识库”

## 4. 目标场景

### 场景 1：导入到指定知识库
- 用户上传 PDF / DOCX / URL
- 导入请求里必须带 `kb_id`
- 文档入库后归属该 `kb_id`

### 场景 2：查询单个知识库
- 用户查询时显式指定 1 个 `kb_id`
- 系统只在该知识库中检索

### 场景 3：查询多个知识库
- 用户查询时显式指定多个 `kb_id`
- 系统在这些知识库中检索并聚合结果

### 场景 4：结果标明来源知识库
- 每条来源都必须带 `kb_id`
- 同时返回 `kb_name`

## 5. 设计原则
1. 先做多知识库，不做权限系统。
2. `kb_id` 必须在导入阶段写入，不能只在查询阶段临时拼接。
3. 查询契约必须只有一种正式输入，不允许前后端各做一套。
4. 不能继续所有文档共用匿名全局索引作为长期方案。
5. 结果返回必须能让用户分辨“这段内容来自哪个知识库”。

## 6. 最小数据模型

### 6.1 KnowledgeBase
先收敛到最小集合：

```json
{
  "kb_id": "kb_product",
  "kb_name": "产品知识库",
  "status": "active"
}
```

字段说明：
- `kb_id`：知识库唯一标识
- `kb_name`：知识库名称
- `status`：状态，建议保留 `active / disabled`

### 6.2 Document Metadata
导入文档时，metadata 先收敛到最小集合：

```json
{
  "doc_id": "doc_001",
  "kb_id": "kb_product",
  "source_type": "file",
  "file_name": "需求说明.pdf",
  "url_source": ""
}
```

字段说明：
- `doc_id`：文档唯一标识
- `kb_id`：文档归属知识库
- `source_type`：`file` 或 `url`
- `file_name`：文件来源时填写
- `url_source`：网页来源时填写

## 7. 知识库目录（Registry）设计
当前文档需要一个不带权限语义的知识库目录，否则：
- 前端不知道下拉框里有哪些知识库
- 返回结果里的 `kb_name` 没有权威来源
- 导入时无法校验 `kb_id` 是否存在

### 7.1 最小目录模型
目录记录只保留：
- `kb_id`
- `kb_name`
- `status`

### 7.2 最小存储方式
第一版建议使用一个本地 registry 文件，例如：
- `storage/kb_registry.json`

### 7.3 最小接口
建议补一个不带权限语义的目录接口：
- `GET /api/kb/registry`

返回当前全部已登记知识库列表，用于：
1. 上传页选择目标知识库
2. 问答页选择检索知识库
3. 管理页显示当前知识库名称
4. 查询结果根据 `kb_id` 回填 `kb_name`

### 7.4 kb_id 合法性来源
这一版必须明确：

1. `kb_id` 的合法性来源只有 registry
2. 导入和查询都只能使用“已登记知识库”
3. 收到未登记 `kb_id` 时，后端直接拒绝请求

也就是说：
- 不做“首次写入时自动建库”
- 不做“查询时隐式创建知识库”

原因：
1. 自动建库会让前后端和测试口径再次分叉
2. registry 既然已经存在，就应该成为唯一权威来源
3. 第一版应优先保证接口语义稳定，而不是追求隐式便捷

### 7.5 创建方式
第一版不强行要求做完整知识库创建 UI，但必须有确定的建库入口。

这一版直接拍板最小入口：
- 新增管理接口 `POST /api/kb/registry`

建议请求示例：

```json
{
  "kb_id": "kb_product",
  "kb_name": "产品知识库"
}
```

接口规则：
1. `kb_id` 必填，且必须唯一
2. `kb_name` 必填
3. 成功创建时默认写入 `status=active`
4. 已存在的 `kb_id` 返回 400
5. 导入接口和查询接口都不能隐式创建知识库

配套约束：
1. 启动时从 registry 文件加载已登记知识库
2. registry 由该管理接口写入和维护
3. registry 变更不由导入/查询接口触发

这样做的原因：
1. 先把“建库入口唯一”定死
2. 前后端、测试、实施方案都能围绕同一个契约落地
3. 不需要先做完整管理 UI，也不会把建库逻辑散落到导入链路里

## 8. 正式查询契约
这一版必须拍板唯一正式输入，避免实现分叉。

### 8.1 结论
正式输入统一采用：`kb_ids`

不采用 `search_scope` 作为正式契约。

原因：
1. 这版只支持 `single` 和 `selected`
2. 两种模式都可以直接用 `kb_ids` 表达
3. 这样最少改 schema、前端状态和测试用例
4. 可以避免 `/api/chat/query`、`/api/agent/run`、前端、测试各自实现一套

### 8.2 QueryRequest
建议改成：

```json
{
  "question": "这个需求的核心目标是什么？",
  "session_id": "s_001",
  "kb_ids": ["kb_product", "kb_rnd"]
}
```

规则：
- `kb_ids` 长度为 1：等价于 `single`
- `kb_ids` 长度大于 1：等价于 `selected`
- `kb_ids` 长度为 0：直接返回 400
- `kb_ids` 中出现重复值：后端先去重，再继续处理
- `kb_ids` 中出现未登记 `kb_id`：直接返回 400
- `kb_ids` 中出现 `status != active` 的知识库：直接返回 400

### 8.3 AgentRunRequest
`AgentRunRequest` 也统一采用：
- 新增 `kb_ids: list[str]`

同时：
- 现有 `knowledge_scope` 保留一段兼容期
- 但后续不再把它作为真实检索范围输入

## 9. 检索范围设计

### 9.1 只保留两种模式
本版只保留：
- `single`
- `selected`

### 9.2 模式定义
- `single`：`kb_ids` 只有 1 个元素
- `selected`：`kb_ids` 有多个元素

### 9.3 删除的模式
这一版明确删除：
- `all_accessible`

原因：
- 这个模式带有明显权限语义
- 当前产品现实里还没有“可访问知识库全集”的定义
- 先删掉，避免文档逻辑跑在产品现实前面

### 9.4 非法输入规则
为避免 schema、后端、前端、测试各自理解不同，这一版把 `kb_ids` 非法输入规则定死：

1. `kb_ids` 不能为空数组
2. `kb_ids` 允许前端重复提交，但后端需要在进入查询前去重
3. 去重后若为空，返回 400
4. 只要包含任一未登记 `kb_id`，返回 400
5. 只要包含任一 `disabled` 知识库，返回 400
6. 不做“自动忽略非法 kb_id 后继续查剩余合法项”的宽松逻辑

原因：
- 这版目标是稳定契约，不是容错式猜测用户意图
- 否则测试用例和前端提示会变得不一致

## 10. 返回结果要求
问答返回结果中的每条来源至少要带：

- `kb_id`
- `kb_name`
- `file_name`
- `page`
- `score`
- `text`

否则用户无法判断答案到底来自哪个知识库。

## 11. 索引策略

### 11.1 必须明确的结论
不能继续所有文档共用一个匿名全局库。

### 11.2 推荐方案
优先推荐两种方式之一：
1. 按 `kb_id` 做索引隔离
2. 按 `kb_id` 做 namespace 隔离

这样做的好处：
- 查询范围天然可控
- 删除和重建更清晰
- 后续如果要接权限系统，成本更低

### 11.3 过渡方案
如果第一版做不到物理隔离，至少必须先把 `kb_id` 写进 metadata。

但要明确：
- 只有 metadata 过滤是过渡方案
- 不是长期方案

原因：
- 共享同一个匿名全局索引时，后续检索边界仍然容易混乱
- metadata 过滤只能先让接口语义成立，不能替代长期索引隔离

## 12. 存量文档迁移方案
当前最大风险不是新导入文档，而是已有文档怎么进入多知识库。

因为：
- 现有 `import_files()` / `import_urls()` 没有 `kb_id`
- 现有存量索引里的文档也没有多库归属元数据

如果不补迁移方案，落地后只能处理新导入文档，处理不了已有大量文档。

### 12.1 迁移目标
把当前单库存量文档迁移到：
- 一个或多个显式 `kb_id`
- 且迁移后查询结果能返回来源知识库

### 12.2 迁移原则
1. 存量迁移不能只改接口，必须处理已有索引数据
2. 如果目标是长期多知识库，推荐全量重建
3. 直接给旧结果“补显示字段”不算完成迁移

### 12.3 推荐迁移路径

#### 路径 A：全量重建（推荐）
1. 冻结旧库写入窗口
2. 导出现有文档清单
3. 生成迁移映射：
   - `doc_id / file_name / url_source -> target kb_id`
4. 建立知识库目录 registry
5. 按映射重新导入各知识库
6. 重建各知识库索引或 namespace
7. 回归验证后切换

优点：
- 数据最干净
- 能保证 `kb_id` 从导入阶段就存在
- 后续索引隔离更自然

#### 路径 B：metadata 过渡迁移（仅过渡）
1. 对现有文档补迁移映射
2. 尽量给旧 metadata 补 `kb_id`
3. 查询阶段临时按 `kb_id` 做过滤
4. 后续仍安排全量重建

限制：
- 这只是过渡
- 不适合作为长期正式方案

### 12.4 切换窗口建议
建议至少定义一个迁移切换窗口：
1. 旧单库只读
2. 执行迁移 / 重建
3. 验证返回 `kb_id / kb_name`
4. 再切到新多库逻辑

### 12.5 特别说明
如果现有文档来源文件还能重新获取，优先全量重建。

如果有部分旧文档来源已丢失：
- 可以暂时归到一个 `legacy_kb`
- 但必须标记为过渡数据

## 13. 接口改造建议

### 13.1 导入接口
导入文件和网页时，必须要求传入 `kb_id`。

当前导入接口需要从：
- 默认写入全局知识库

改成：
- 显式写入某个 `kb_id`

### 13.2 问答接口
问答接口需要支持：
- 指定 1 个 `kb_id`
- 指定多个 `kb_id`

正式输入统一为：
- `kb_ids`

### 13.3 文档列表与删除接口
这一版只需要按 `kb_id` 过滤即可，不引入用户权限校验。

必须把契约定具体：

#### `GET /api/kb/list`
- 使用 query param：`kb_id`
- 第一版只支持单个 `kb_id`
- 不支持多值 `kb_id`

示例：
```http
GET /api/kb/list?kb_id=kb_product
```

行为：
1. `kb_id` 必填
2. `kb_id` 未登记时返回 400
3. `kb_id` 为 disabled 时返回 400
4. 只返回该知识库下的文档

#### `DELETE /api/kb/docs`
- 使用 request body，同时带：
  - `kb_id`
  - `doc_ids` 或 `paths`

示例：
```json
{
  "kb_id": "kb_product",
  "doc_ids": ["doc_001", "doc_002"],
  "paths": []
}
```

行为：
1. `kb_id` 必填
2. `kb_id` 未登记时返回 400
3. 删除范围只允许落在该 `kb_id` 下
4. 如果传入的 `doc_id` 不属于该 `kb_id`，返回 400，而不是跨库删除

这样可以避免：
- 前端不知道怎么传 `kb_id`
- 后端默默按全局文档表删除
- 测试无法明确写断言

### 13.4 知识库目录接口
新增：
- `GET /api/kb/registry`

这是当前最小实现里必须补的接口。

## 14. 前端交互建议

### 14.1 问答页
增加知识库选择能力：
- 单选一个知识库
- 或多选多个知识库

### 14.2 上传页
上传前必须先选择目标知识库。

### 14.3 管理页
文档列表需要能按 `kb_id` 查看和切换。

### 14.4 知识库名称来源
前端所有 `kb_name` 都应来自 registry，不应自行写死。

## 15. 分阶段建议

### Phase 1：文档重写，只做最小多知识库，不谈权限
输出：
- 本文档
- 统一后的最小多知识库口径

### Phase 2：导入接口支持 `kb_id`，查询接口支持 `kb_ids`
目标：
- 导入文件时强制归属某个 `kb_id`
- 查询时支持单个或多个 `kb_id`
- 返回结果中的每条来源必须带 `kb_id` / `kb_name`
- 如果第一版暂时还没做物理隔离，也必须先基于 metadata + registry 把来源库标识返回正确

### Phase 3：索引 / namespace 按 `kb_id` 隔离
目标：
- 查询路径不再依赖匿名全局索引
- 从“metadata 过滤过渡方案”升级到正式隔离方案
- 为后续删除、重建、扩容和权限演进打基础

### Phase 4：如果未来真有多人共享，再单独出权限设计文档
目标：
- 再讨论 `user_id`
- 再讨论 `role`
- 再讨论 `group_ids`
- 再讨论 `visibility`

## 16. 当前建议结论
当前最重要的不是把文档做大，而是把最小多知识库能力做实。

这版设计只应推动四件事：
1. 文档导入必须绑定 `kb_id`
2. 查询正式契约统一采用 `kb_ids`
3. 返回结果必须标明来源知识库
4. 现有存量文档必须有明确迁移方案

先把这四件事做出来，再进入权限设计，才符合当前产品现实。
