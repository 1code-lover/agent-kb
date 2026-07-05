# 基于知识库的智能体（Multi-KB RAG Agent）PRD v2

## 1. 文档信息

| 字段 | 值 |
|---|---|
| 文档类型 | PRD（产品需求文档） |
| 版本 | v2.0（方案C：混合模式） |
| 日期 | 2026-06-19 |
| 状态 | 草稿 |
| 更新说明 | 基于用户反馈，采用混合模式方案 |

## 2. 背景与目标

### 2.1 背景

当前系统的 Agent 智能体已具备基本能力（kb_search、read_file、run_cmd、llm_chat 四个工具），但存在以下问题：

1. **知识库搜索硬编码**：`run_kb_search()` 默认只搜索 default 知识库，无法利用已创建的多个知识库
2. **单知识库限制**：`KnowledgeScope` 只支持单个 `kb_id`，无法同时检索多个知识库
3. **chat_service 不支持指定知识库**：`chat_service.query()` 没有 `kb_id` 参数，无法将检索限定到特定知识库
4. **缺乏智能选择**：用户无法让 Agent 根据问题自动判断该搜哪个知识库
5. **用户控制不足**：纯自动模式下用户无法指定搜索范围，可能搜到不相关内容

### 2.2 目标

- **用户控制优先**：用户可以在提问时指定要搜索的知识库（1个或多个）
- **智能补充**：用户不指定时，Agent 自动选择最相关的知识库
- **混合模式**：用户指定 + Agent 智能扩展，既保证用户意图，又不错过相关内容
- **检索结果标注来源**，支持溯源

### 2.3 非目标

- 不实现知识库间的知识图谱关联
- 不实现跨知识库的语义去重（后续优化）
- 不修改现有知识库管理的 CRUD 接口

## 3. 核心设计：混合模式

### 3.1 模式说明

混合模式结合了用户手动指定和Agent自动选择的优点：

```
用户提问
    ↓
┌─────────────────────────────────────┐
│ 用户是否指定了知识库？               │
│   - 是：使用用户指定的知识库         │
│   - 否：Agent 自动选择相关知识库     │
│   - 部分指定：用户指定 + Agent 补充  │
└─────────────────────────────────────┘
    ↓
多知识库并行检索
    ↓
结果合并、排序、标注来源
    ↓
LLM 综合回答
```

### 3.2 用户指定知识库的方式

**方式一：前端界面选择（推荐）**
- 在输入框上方显示知识库多选列表
- 用户可以勾选1个或多个知识库
- 不勾选 = 使用Agent自动选择

**方式二：对话中文字指定**
- 用户在问题中明确提到知识库名称
- 例如："只在技术文档里搜索 FastAPI 的用法"
- Agent 通过 LLM 理解用户意图，提取知识库名称

### 3.3 Agent 自动选择逻辑

当用户未指定知识库时：

1. LLM 分析用户问题
2. 参考所有知识库的 `description`（描述）
3. 选择 1-3 个最相关的知识库
4. 并行检索这些知识库
5. 如果都不相关，fallback 到搜索全部知识库

## 4. 用户场景

### 场景 1：用户手动指定知识库

```
用户操作：
  1. 在界面上勾选"公司制度"知识库
  2. 输入问题："报销流程是什么？"

系统行为：
  1. 检测到用户指定了知识库，不走Agent自动选择
  2. 直接调用 kb_search(kb_ids=["kb_公司制度"], query="报销流程")
  3. 结果标注来源：[公司制度]

Agent回答："根据【公司制度】知识库，报销流程如下：..."
```

### 场景 2：用户未指定，Agent 自动选择

```
用户操作：
  1. 不勾选任何知识库
  2. 输入问题："我们公司的报销流程是什么？"

系统行为：
  1. LLM 分析问题，发现"报销流程"与"公司制度"知识库最相关
  2. 调用 kb_search(kb_ids=["kb_公司制度"], query="报销流程")
  3. 结果标注来源：[公司制度]

Agent回答："根据【公司制度】知识库，报销流程如下：..."
```

### 场景 3：用户指定 + Agent 智能补充

```
用户操作：
  1. 勾选"Python技术文档"知识库
  2. 输入问题："如何用Python部署到公司的K8s集群？"

系统行为：
  1. 检测到用户指定了"Python技术文档"
  2. Agent 分析发现"K8s部署"还与"运维手册"相关
  3. 并行调用：
     - kb_search(kb_ids=["kb_python"], query="Python部署K8s")
     - kb_search(kb_ids=["kb_运维"], query="Kubernetes部署")
  4. 结果分别标注来源：[Python技术文档]、[运维手册]

Agent回答："结合【Python技术文档】和【运维手册】，部署步骤如下：..."
```

### 场景 4：问题涉及多个知识库（用户未指定）

```
用户操作：
  1. 不勾选任何知识库
  2. 输入问题："Python 项目如何部署到公司的 Kubernetes 集群？"

系统行为：
  1. LLM 分析发现同时涉及"Python技术文档"和"运维部署手册"
  2. 并行调用：
     - kb_search(kb_ids=["kb_python"], query="Python部署")
     - kb_search(kb_ids=["kb_运维"], query="Kubernetes部署")
  3. 合并结果，去重排序

Agent回答："结合【Python技术文档】和【运维手册】，部署步骤如下：..."
```

## 5. 功能需求

### 5.1 前端：知识库多选组件

**需求 ID：** F-KB-001

**描述：** 在聊天输入区域增加知识库多选组件

**验收标准：**
- [ ] 显示所有可用知识库列表（带描述）
- [ ] 支持多选（checkbox 或 tag 选择）
- [ ] 不选 = Agent自动选择
- [ ] 选择状态持久化（同一会话内）
- [ ] 显示当前选择的知识库名称

### 5.2 后端：chat_service 支持指定知识库

**需求 ID：** F-KB-002

**描述：** `chat_service.query()` 接受可选的 `kb_ids` 参数

**验收标准：**
- [ ] `query()` 方法增加 `kb_ids: Optional[List[str]]` 参数
- [ ] 传入 `kb_ids` 时，检索限定到指定知识库
- [ ] 不传时保持原有行为（Agent自动选择）
- [ ] 传入多个 `kb_ids` 时，并行检索多个知识库

### 5.3 KnowledgeScope 支持多知识库

**需求 ID：** F-KB-003

**描述：** `KnowledgeScope` schema 改为支持多个知识库 ID

**验收标准：**
- [ ] `kb_id` 字段改为 `kb_ids: List[str]`
- [ ] `kb_name` 字段改为 `kb_names: List[str]`
- [ ] 向后兼容：单个 ID 也能正常工作
- [ ] 增加 `auto_selected: bool` 标记是否为自动选择

### 5.4 Agent 自动选择知识库

**需求 ID：** F-KB-004

**描述：** 当用户未指定知识库时，Agent 根据问题自动选择

**验收标准：**
- [ ] LLM system prompt 中注入所有可用知识库的描述
- [ ] LLM 根据问题内容选择 1-3 个最相关的知识库
- [ ] 选择结果作为 `kb_search` 的 `kb_ids` 参数
- [ ] 提供 fallback：当 LLM 无法判断时搜索全部知识库

### 5.5 多知识库并行检索

**需求 ID：** F-KB-005

**描述：** `run_kb_search` 工具支持并行检索多个知识库

**验收标准：**
- [ ] `kb_ids` 参数接受 `List[str]`
- [ ] 同时检索多个知识库（使用 asyncio.gather 或线程池）
- [ ] 结果按相关性合并排序
- [ ] 每条结果标注来源知识库名称
- [ ] 向后兼容：不传 `kb_ids` 时仍搜索默认知识库

### 5.6 检索结果溯源标注

**需求 ID：** F-KB-006

**描述：** 每条检索结果标注来源知识库

**验收标准：**
- [ ] 检索结果包含 `kb_name` 字段
- [ ] LLM 回答时引用知识库来源
- [ ] 前端展示时用不同颜色/标签区分来源知识库

## 6. 技术设计

### 6.1 数据流

```
用户输入 + 选择的知识库
    ↓
API 层：chat_service.query(question, kb_ids=[...] or None)
    ↓
┌─────────────────────────────────────────┐
│ if kb_ids is not None:                  │
│   → 使用用户指定的知识库                │
│ else:                                   │
│   → Agent 自动选择（LLM 判断）          │
└─────────────────────────────────────────┘
    ↓
Agent 决策：选择 kb_search 工具，传入 kb_ids
    ↓
kb_search 工具：并行检索多个知识库
    ↓
结果合并 + 标注来源
    ↓
LLM 综合回答（引用来源知识库）
    ↓
返回带溯源标注的回答
```

### 6.2 API 变更

```python
# chat_service.py
async def query(
    self,
    question: str,
    kb_ids: Optional[List[str]] = None,  # 新增参数
    session_id: Optional[str] = None,
    stream: bool = False
) -> AsyncGenerator:
    ...

# schemas.py
class KnowledgeScope(BaseModel):
    kb_ids: List[str]  # 改为列表
    kb_names: List[str]  # 改为列表
    auto_selected: bool = False  # 标记是否自动选择
```

### 6.3 Agent Tool 变更

```python
# agent/tools.py
async def run_kb_search(
    question: str,
    kb_ids: Optional[List[str]] = None
) -> List[SearchResult]:
    """
    搜索知识库，支持多知识库并行检索
    """
    if kb_ids is None:
        # Fallback：搜索全部知识库
        kb_ids = await get_all_kb_ids()
    
    # 并行检索
    tasks = [search_single_kb(kb_id, question) for kb_id in kb_ids]
    results = await asyncio.gather(*tasks)
    
    # 合并结果并标注来源
    merged = []
    for kb_id, kb_results in zip(kb_ids, results):
        for result in kb_results:
            result.kb_name = get_kb_name(kb_id)
            merged.append(result)
    
    # 按相关性排序
    return sorted(merged, key=lambda x: x.score, reverse=True)
```

## 7. 非功能需求

| 维度 | 要求 |
|---|---|
| 性能 | 多知识库并行检索，总延迟不超过最慢单库检索的 1.5 倍 |
| 可用性 | 向后兼容，现有单知识库使用不受影响 |
| 用户体验 | 界面清晰显示当前选择的知识库，方便切换 |

## 8. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| 用户选错知识库 | 检索结果不相关 | 提供知识库描述；支持随时切换 |
| LLM 选错知识库（自动模式） | 检索结果不相关 | 给知识库加详细描述；提供 fallback 搜全部 |
| 多库结果冲突 | 回答矛盾 | LLM 综合时标注来源差异 |
| 检索延迟增加 | 用户体验下降 | 并行检索；设置超时 |

## 9. 成功指标

| 指标 | 目标 |
|---|---|
| 用户指定模式使用率 | >= 40%（用户主动选择知识库的比例） |
| 多知识库检索准确率 | >= 85%（选对知识库的比例） |
| 端到端回答质量 | 用户满意度 >= 85% |
| 检索延迟 | P95 < 5 秒 |
