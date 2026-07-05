# 知识库检索 Agent 执行计划（更新版）

## 1. 项目信息
- 项目名称：知识库检索 Agent（LangGraph 版）
- 文档版本：v2.0（根据评审意见更新）
- 预计周期：8天

## 2. 任务分解

### Phase 1：基础框架（Day 1-2）

#### Task 1.1：环境准备
- **目标**：安装依赖，配置开发环境
- **任务清单**：
  - [ ] 更新 `requirements.txt` 添加 langgraph 相关依赖
  - [ ] 安装依赖：`pip install langgraph`
  - [ ] 验证安装：`python -c "import langgraph; print(langgraph.__version__)"`
- **验收标准**：langgraph 可正常导入
- **预计时间**：0.5天

#### Task 1.2：定义 AgentState
- **目标**：定义 LangGraph 状态结构
- **任务清单**：
  - [ ] 创建 `server/agent/state.py`
  - [ ] 定义 `AgentState` TypedDict
  - [ ] 添加状态字段说明注释
- **验收标准**：AgentState 可正常实例化
- **预计时间**：0.5天

**代码示例**：
```python
# server/agent/state.py
from typing import TypedDict, List, Optional

class AgentState(TypedDict):
    """知识库问答 Agent 状态"""
    # 用户输入
    question: str
    session_id: str
    kb_ids: List[str] | str  # "auto" 或 知识库ID列表
    
    # Query 改写
    rewritten_query: str
    is_clarify: bool
    context: Optional[dict]
    
    # 检索结果
    evidence: List[dict]
    retrieval_score: float
    top_k: int
    
    # 回答
    answer: str
    confidence: float
    sources: List[dict]
    
    # 控制
    retry_count: int
    max_retries: int
    need_clarify: bool
    clarify_question: str
```

#### Task 1.3：创建工作流骨架
- **目标**：创建 LangGraph 工作流骨架
- **任务清单**：
  - [ ] 创建 `server/agent/graph.py`
  - [ ] 实现 `create_kb_agent_graph()` 函数
  - [ ] 添加节点占位符
  - [ ] 定义边和条件边
- **验收标准**：工作流可编译通过
- **预计时间**：1天

---

### Phase 2：核心模块（Day 3-5）

#### Task 2.1：Query 改写模块
- **目标**：实现 QueryRewriter
- **任务清单**：
  - [ ] 创建 `server/agent/query_rewriter.py`
  - [ ] 实现澄清追问检测
  - [ ] 实现话题结合改写
  - [ ] 添加单元测试
- **验收标准**：澄清追问可正确识别和改写
- **预计时间**：1天

#### Task 2.2：语义检索模块
- **目标**：实现 SemanticRetriever
- **任务清单**：
  - [ ] 创建 `server/agent/retriever.py`
  - [ ] 实现向量检索
  - [ ] 实现 BM25 检索
  - [ ] 实现结果融合
  - [ ] 支持多知识库检索
  - [ ] 添加单元测试
- **验收标准**：可正确检索并返回结果
- **预计时间**：2天

#### Task 2.3：答案生成模块
- **目标**：实现 AnswerGenerator
- **任务清单**：
  - [ ] 创建 `server/agent/answer_generator.py`
  - [ ] 实现提示词构建
  - [ ] 集成 LLM 调用
  - [ ] 实现置信度计算
  - [ ] 添加单元测试
- **验收标准**：可正确生成回答
- **预计时间**：1天

---

### Phase 3：集成测试（Day 6-7）

#### Task 3.1：端到端测试
- **目标**：验证完整工作流
- **任务清单**：
  - [ ] 创建测试用例
  - [ ] 测试正常流程
  - [ ] 测试重试流程
  - [ ] 测试追问流程
- **验收标准**：所有测试用例通过
- **预计时间**：1天

#### Task 3.2：执行轨迹验证
- **目标**：验证 LangGraph 执行轨迹
- **任务清单**：
  - [ ] 获取执行轨迹
  - [ ] 验证每一步记录
  - [ ] 测试轨迹持久化
- **验收标准**：执行轨迹完整可追踪
- **预计时间**：0.5天

#### Task 3.3：性能优化
- **目标**：优化检索和响应速度
- **任务清单**：
  - [ ] 测量各节点耗时
  - [ ] 优化慢节点
  - [ ] 添加缓存（可选）
- **验收标准**：响应时间 < 2秒
- **预计时间**：0.5天

---

## 3. 文件清单

### 新增文件
```
server/agent/
├── __init__.py
├── state.py              # AgentState 定义
├── graph.py              # LangGraph 工作流
├── query_rewriter.py     # Query 改写模块
├── retriever.py          # 语义检索模块
└── answer_generator.py   # 答案生成模块

tests/
├── test_agent_state.py
├── test_agent_graph.py
├── test_query_rewriter.py
├── test_retriever.py
├── test_answer_generator.py
└── test_kb_agent.py
```

### 修改文件
```
requirements.txt      # 添加 langgraph 相关依赖
api/routers/kb.py    # 添加检索接口
```

## 4. 依赖关系

```
Task 1.1 (环境准备)
    ↓
Task 1.2 (AgentState)
    ↓
Task 1.3 (工作流骨架)
    ↓
Task 2.1 (Query改写) ─┐
Task 2.2 (检索)    ─┼→ Task 3.1 (端到端测试)
Task 2.3 (回答生成) ─┘   ↓
                    Task 3.2 (轨迹验证)
                        ↓
                    Task 3.3 (性能优化)
```

## 5. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| langgraph 版本兼容 | 安装失败 | 锁定版本，测试兼容性 |
| 检索效果差 | 回答质量低 | 优化检索算法，调整阈值 |
| 响应慢 | 用户体验差 | 异步处理，添加缓存 |

## 6. 验收标准

1. 工作流可正常执行
2. Query 改写功能正常
3. 检索功能正常
4. 回答生成功能正常
5. 执行轨迹完整
6. 单元测试覆盖率 >= 80%
7. 响应时间 < 2秒

## 7. 交付物

1. 完整的代码实现
2. 单元测试用例
3. 集成测试用例
4. 测试报告
5. 使用文档
