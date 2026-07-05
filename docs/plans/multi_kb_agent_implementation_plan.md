# Multi-KB RAG Agent 实施方案

## 1. 文档信息

| 字段 | 值 |
|---|---|
| 文档类型 | 实施方案（详细开发计划） |
| 版本 | v1.0 |
| 日期 | 2026-06-19 |
| 对应 PRD | multi_kb_agent_prd_v2.md（方案C：混合模式） |

## 2. 实施概览

本方案采用**增量开发**策略，分6个Task完成，每个Task可独立提交：

1. Schema 层：KnowledgeScope 支持多知识库
2. Service 层：chat_service.query() 支持 kb_ids 参数
3. Agent 工具层：run_kb_search 支持并行多库检索
4. Agent 决策层：LLM 自动选择知识库逻辑
5. 测试：单元测试 + 集成测试
6. 文档更新

## 3. Task 详细计划

### Task 1: Schema 层改造

**目标：** `KnowledgeScope` 支持多个知识库 ID

**文件：** `app/schemas.py`

**变更内容：**
```python
# 修改前
class KnowledgeScope(BaseModel):
    kb_id: str = "default"
    kb_name: str = "default"

# 修改后
class KnowledgeScope(BaseModel):
    kb_ids: List[str] = ["default"]  # 改为列表，向后兼容
    kb_names: List[str] = ["default"]  # 改为列表
    auto_selected: bool = False  # 标记是否为Agent自动选择

    @validator('kb_ids', pre=True)
    def ensure_list(cls, v):
        """向后兼容：单个字符串转为列表"""
        if isinstance(v, str):
            return [v]
        return v

    @validator('kb_names', pre=True)
    def ensure_name_list(cls, v):
        """向后兼容：单个字符串转为列表"""
        if isinstance(v, str):
            return [v]
        return v
```

**测试命令：**
```bash
python -m pytest tests/test_schemas.py -v -k "knowledge_scope"
```

**验收标准：**
- [ ] `KnowledgeScope(kb_id="default")` 向后兼容
- [ ] `KnowledgeScope(kb_ids=["kb1", "kb2"])` 正常工作
- [ ] 所有现有测试通过

---

### Task 2: chat_service 层改造

**目标：** `chat_service.query()` 支持 `kb_ids` 参数

**文件：** `app/services/chat_service.py`

**变更内容：**
```python
async def query(
    self,
    question: str,
    kb_ids: Optional[List[str]] = None,  # 新增参数
    session_id: Optional[str] = None,
    stream: bool = False
) -> AsyncGenerator[str, None]:
    """
    查询接口，支持指定知识库
    
    Args:
        question: 用户问题
        kb_ids: 指定的知识库ID列表，None表示Agent自动选择
        session_id: 会话ID
        stream: 是否流式返回
    """
    # 构建 knowledge_scope
    if kb_ids:
        kb_names = [self.kb_service.get_kb_name(kb_id) for kb_id in kb_ids]
        knowledge_scope = KnowledgeScope(
            kb_ids=kb_ids,
            kb_names=kb_names,
            auto_selected=False
        )
    else:
        knowledge_scope = None  # 由Agent自动选择
    
    # 传递给agent
    async for chunk in self.agent.run(
        question=question,
        knowledge_scope=knowledge_scope,
        stream=stream
    ):
        yield chunk
```

**测试命令：**
```bash
python -m pytest tests/test_chat_service.py -v -k "multi_kb"
```

**验收标准：**
- [ ] `query("问题")` 不传 kb_ids 时正常工作
- [ ] `query("问题", kb_ids=["kb1"])` 传单个 kb_id 正常工作
- [ ] `query("问题", kb_ids=["kb1", "kb2"])` 传多个 kb_ids 正常工作

---

### Task 3: Agent 工具层改造（核心）

**目标：** `run_kb_search` 支持并行多库检索 + 溯源标注

**文件：** `app/agent/tools.py`

**变更内容：**
```python
import asyncio
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class SearchResult:
    """带溯源标注的检索结果"""
    content: str
    score: float
    kb_id: str
    kb_name: str
    source_file: Optional[str] = None

async def run_kb_search(
    question: str,
    kb_ids: Optional[List[str]] = None,
    top_k: int = 5
) -> List[SearchResult]:
    """
    多知识库并行检索
    
    Args:
        question: 查询问题
        kb_ids: 知识库ID列表，None则搜索全部
        top_k: 每个知识库返回的结果数
    """
    from app.services.kb_service import kb_service
    
    # 获取所有知识库（用于fallback或用户未指定时）
    all_kbs = await kb_service.list_knowledge_bases()
    
    if kb_ids is None:
        # Fallback：搜索全部知识库
        kb_ids = [kb.kb_id for kb in all_kbs]
    
    # 构建知识库名称映射
    kb_name_map = {kb.kb_id: kb.name for kb in all_kbs}
    
    # 并行检索
    async def search_single_kb(kb_id: str) -> List[SearchResult]:
        """搜索单个知识库"""
        try:
            index_manager = kb_service.get_index_manager(kb_id)
            if index_manager is None:
                return []
            
            results = await index_manager.search(question, top_k=top_k)
            
            # 标注来源
            return [
                SearchResult(
                    content=r.content,
                    score=r.score,
                    kb_id=kb_id,
                    kb_name=kb_name_map.get(kb_id, kb_id),
                    source_file=r.metadata.get('source_file')
                )
                for r in results
            ]
        except Exception as e:
            logger.error(f"搜索知识库 {kb_id} 失败: {e}")
            return []
    
    # 并行执行所有搜索任务
    tasks = [search_single_kb(kb_id) for kb_id in kb_ids]
    results_per_kb = await asyncio.gather(*tasks)
    
    # 合并结果
    merged_results = []
    for results in results_per_kb:
        merged_results.extend(results)
    
    # 按相关性排序（降序）
    merged_results.sort(key=lambda x: x.score, reverse=True)
    
    # 返回top_k结果
    return merged_results[:top_k]
```

**测试命令：**
```bash
python -m pytest tests/test_agent_tools.py -v -k "multi_kb_search"
```

**验收标准：**
- [ ] `run_kb_search("问题")` 搜全部知识库
- [ ] `run_kb_search("问题", kb_ids=["kb1"])` 搜指定知识库
- [ ] `run_kb_search("问题", kb_ids=["kb1", "kb2"])` 并行搜多个
- [ ] 每条结果包含 `kb_name` 字段
- [ ] 结果按 score 降序排列
- [ ] 单个知识库搜索失败不影响其他知识库

---

### Task 4: Agent 决策层改造（核心）

**目标：** LLM 自动选择最相关的知识库

**文件：** `app/agent/react_agent.py`

**变更内容：**

#### 4.1 System Prompt 增强

```python
def build_system_prompt(self, knowledge_scope: Optional[KnowledgeScope] = None) -> str:
    """构建系统提示词，注入知识库信息"""
    
    base_prompt = """你是一个智能助手，可以使用以下工具帮助用户：
- kb_search: 搜索知识库
- read_file: 读取文件
- run_cmd: 执行命令
- llm_chat: 直接对话
"""
    
    if knowledge_scope and not knowledge_scope.auto_selected:
        # 用户指定了知识库，直接使用
        kb_info = "、".join(knowledge_scope.kb_names)
        base_prompt += f"\n用户已指定搜索以下知识库：{kb_info}\n"
    else:
        # Agent需要自动选择，注入所有知识库信息
        all_kbs = self.kb_service.list_knowledge_bases()
        kb_list = "\n".join([
            f"- {kb.kb_id}: {kb.description or kb.name}"
            for kb in all_kbs
        ])
        base_prompt += f"""
可用知识库列表：
{kb_list}

当用户问题涉及特定领域时，请选择最相关的知识库进行搜索。
如果无法确定，可以搜索多个知识库或全部知识库。
"""
    
    return base_prompt
```

#### 4.2 知识库选择逻辑

```python
async def select_knowledge_bases(
    self,
    question: str,
    user_specified_kb_ids: Optional[List[str]] = None
) -> List[str]:
    """
    选择要搜索的知识库
    
    Args:
        question: 用户问题
        user_specified_kb_ids: 用户指定的知识库ID列表
    
    Returns:
        最终要搜索的知识库ID列表
    """
    if user_specified_kb_ids:
        # 用户已指定，直接返回
        return user_specified_kb_ids
    
    # Agent自动选择
    all_kbs = await self.kb_service.list_knowledge_bases()
    
    # 使用LLM选择
    selection_prompt = f"""根据用户问题，选择最相关的知识库。

用户问题：{question}

可选知识库：
{self._format_kb_list(all_kbs)}

请返回JSON格式：
{{"kb_ids": ["kb_id1", "kb_id2"]}}

如果无法确定，返回：{{"kb_ids": "all"}}"""
    
    response = await self.llm.achat(selection_prompt)
    
    try:
        result = json.loads(response)
        if result.get("kb_ids") == "all":
            return [kb.kb_id for kb in all_kbs]
        return result.get("kb_ids", [])
    except:
        # Fallback：返回全部
        return [kb.kb_id for kb in all_kbs]
```

#### 4.3 工具调用改造

```python
async def _execute_kb_search(
    self,
    question: str,
    knowledge_scope: Optional[KnowledgeScope] = None
) -> str:
    """执行知识库搜索"""
    
    # 选择要搜索的知识库
    kb_ids = await self.select_knowledge_bases(
        question=question,
        user_specified_kb_ids=knowledge_scope.kb_ids if knowledge_scope else None
    )
    
    # 执行多库搜索
    results = await run_kb_search(
        question=question,
        kb_ids=kb_ids,
        top_k=5
    )
    
    # 格式化结果（带溯源标注）
    formatted_results = []
    for i, r in enumerate(results, 1):
        formatted_results.append(
            f"[{i}] 来源：{r.kb_name}\n"
            f"内容：{r.content}\n"
            f"相关性：{r.score:.2f}"
        )
    
    return "\n\n".join(formatted_results)
```

**测试命令：**
```bash
python -m pytest tests/test_react_agent.py -v -k "kb_selection"
```

**验收标准：**
- [ ] 用户指定 kb_ids 时，直接使用
- [ ] 用户未指定时，LLM 自动选择相关知识库
- [ ] System prompt 正确注入知识库信息
- [ ] Fallback 机制：LLM 选择失败时搜索全部
- [ ] 检索结果包含来源标注

---

### Task 5: 测试

**目标：** 编写全面的单元测试和集成测试

**文件：**
- `tests/test_schemas.py`（Schema 测试）
- `tests/test_chat_service.py`（Service 测试）
- `tests/test_agent_tools.py`（工具测试）
- `tests/test_react_agent.py`（Agent 测试）

**测试用例：**

#### 5.1 Schema 测试
```python
def test_knowledge_scope_backward_compatibility():
    """向后兼容测试：单个字符串自动转列表"""
    scope = KnowledgeScope(kb_id="test", kb_name="测试")
    assert scope.kb_ids == ["test"]
    assert scope.kb_names == ["测试"]

def test_knowledge_scope_multi_kb():
    """多知识库测试"""
    scope = KnowledgeScope(
        kb_ids=["kb1", "kb2"],
        kb_names=["知识库1", "知识库2"],
        auto_selected=True
    )
    assert len(scope.kb_ids) == 2
```

#### 5.2 工具测试
```python
@pytest.mark.asyncio
async def test_multi_kb_search():
    """多知识库并行检索测试"""
    results = await run_kb_search(
        question="测试问题",
        kb_ids=["kb1", "kb2"],
        top_k=5
    )
    assert len(results) <= 5
    assert all(hasattr(r, 'kb_name') for r in results)
    # 验证按score降序
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)

@pytest.mark.asyncio
async def test_kb_search_failure_isolation():
    """单个知识库失败不影响其他"""
    results = await run_kb_search(
        question="测试问题",
        kb_ids=["valid_kb", "invalid_kb"],
        top_k=5
    )
    # 应该有结果（来自valid_kb）
    assert len(results) > 0
```

**测试命令：**
```bash
python -m pytest tests/ -v --cov=app --cov-report=html
```

**验收标准：**
- [ ] 测试覆盖率 >= 80%
- [ ] 所有测试通过
- [ ] 包含正常路径和异常路径测试

---

### Task 6: 文档更新

**目标：** 更新 API 文档和使用说明

**文件：**
- `docs/api_reference.md`（API 文档）
- `README.md`（使用说明）

**变更内容：**
- 新增 `kb_ids` 参数说明
- 新增多知识库检索示例
- 新增溯源标注说明

## 4. 提交计划

| Task | Commit Message | 依赖 |
|---|---|---|
| Task 1 | `feat(schemas): KnowledgeScope 支持多知识库ID` | 无 |
| Task 2 | `feat(chat-service): query 接口支持 kb_ids 参数` | Task 1 |
| Task 3 | `feat(agent-tools): run_kb_search 支持并行多库检索` | Task 2 |
| Task 4 | `feat(react-agent): LLM 自动选择知识库逻辑` | Task 3 |
| Task 5 | `test: 多知识库检索功能测试` | Task 4 |
| Task 6 | `docs: 更新多知识库检索 API 文档` | Task 5 |

## 5. 验证命令汇总

```bash
# 1. 运行所有测试
python -m pytest tests/ -v

# 2. 检查测试覆盖率
python -m pytest tests/ --cov=app --cov-report=term-missing

# 3. 类型检查
mypy app/

# 4. 代码风格检查
flake8 app/
```
