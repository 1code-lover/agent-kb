# 知识库智能问答 Agent 设计建议（V2）

> 基于现有代码架构的全面分析，结合 LangGraph 引入需求，给出的设计建议

## 一、现有架构分析

### 1.1 核心模块盘点

| 模块 | 路径 | 能力 | 复用评估 |
|------|------|------|----------|
| engine.py | server/engine.py | 异步文档索引引擎，管理 pipeline、docstore、index、vector store | ✅ 直接复用入库能力 |
| ingestion.py | server/ingestion.py | 封装 engine.run() 的同步调用 | ✅ 复用 |
| text_splitter.py | server/text_splitter.py | DEV 用 SentenceSplitter，PROD 用 Spacy（中文优化） | ✅ 复用，但需扩展为可配置 chunk_size |
| retriever.py | server/retriever.py | 检索引擎，封装 VectorIndexRetriever + BM25（混合检索） | ✅ **核心复用** |
| vector_store.py | server/stores/vector_store.py | Milvus 向量库，按 collection 隔离 | ✅ 直接复用 |
| chat_store.py | server/stores/chat_store.py | Redis 持久化聊天记录，支持 per-collection | ✅ **可作为 LangGraph state 外部存储** |
| config_store.py | server/stores/config_store.py | 系统配置 KV 存储 | ✅ 复用 |
| llm_api.py | server/models/llm_api.py | OpenAI 兼容 LLM 创建 | ✅ 直接复用 |
| ollama.py | server/models/ollama.py | Ollama LLM 创建 | ✅ 直接复用 |
| embedding.py | server/models/embedding.py | HuggingFace Embedding | ✅ 直接复用 |
| reranker.py | server/models/reranker.py | BGE Reranker（可选） | ✅ 直接复用 |
| prompt.py | server/prompt.py | QA 系统 prompt 模板 | ⚠️ 需新增 Agent 专用 prompt |

### 1.2 关键发现

**发现 1：基础设施完备**
- 向量存储（Milvus）、文档存储（Redis）、Embedding、LLM 均已就绪
- 不需要重新引入存储层，直接复用 `server/stores/`

**发现 2：retriever.py 已支持混合检索**
- 已实现 VectorIndexRetriever + BM25 双路召回 + ScoreFusion
- reranker 是可选的（async 且需要 CUDA/MPS）
- 这是问答 Agent 的核心能力，必须直接复用

**发现 3：ChatHistoryStore 已支持 per-collection 隔离**
- `get_history(collection, user_id, limit)` 已有
- 但当前仅存储 messages 列表，没有 LangGraph 所需的 state 管理

**发现 4：当前问答流程是单轮的**
- `frontend/Document_QA.py` 中 `generate_query_engine()` 每次调用都重建引擎
- 没有 session 概念，没有上下文窗口管理
- **这正是引入 LangGraph 的核心价值**

## 二、LangGraph 引入定位

### 2.1 为什么需要 LangGraph

| 现状问题 | LangGraph 解决方案 |
|----------|-------------------|
| 单轮问答，无上下文 | StateGraph 维护 conversation state |
| 无法做查询改写（query rewriting） | 图节点中增加 query_rewriter 节点 |
| 无法做意图路由（路由到不同知识库） | 条件边实现动态路由 |
| 无法做多步推理（追问、追问后检索） | 图支持循环和分支 |
| 大上下文窗口无法精细管理 | State 中管理 context window，支持摘要压缩 |
| 无法做答案质量检查 | 增加 reflection/critique 节点 |

### 2.2 LangGraph 在架构中的位置

```
用户问题
   ↓
┌─────────────────────────────────────┐
│         LangGraph StateGraph        │  ← 新增：Agent 编排层
│                                     │
│  ┌─────────┐    ┌─────────────┐    │
│  │ query   │───→│  retriever  │    │  ← 复用 server/retriever.py
│  │ rewrite │    │  (混合检索)  │    │
│  └─────────┘    └──────┬──────┘    │
│                        ↓           │
│                ┌──────────────┐    │
│                │ context_mgr  │    │  ← 新增：大上下文管理
│                │ (窗口压缩)    │    │
│                └──────┬───────┘    │
│                       ↓            │
│                ┌──────────────┐    │
│                │  generator   │    │  ← 复用 LLM (llm_api/ollama)
│                └──────┬───────┘    │
│                       ↓            │
│                ┌──────────────┐    │
│                │  reflection  │    │  ← 新增：答案质量检查
│                └──────────────┘    │
│                                     │
└─────────────────────────────────────┘
   ↓
用户答案 + 引用
```

## 三、核心设计建议

### 3.1 State 定义（LangGraph 的核心）

```python
from typing import TypedDict, Annotated
from langgraph.graph import add_messages

class KBAgentState(TypedDict):
    # 对话消息（LangGraph 自动管理）
    messages: Annotated[list, add_messages]
    
    # 当前问题（原始）
    user_query: str
    
    # 改写后的查询（可能多条，用于多路召回）
    rewritten_queries: list[str]
    
    # 检索结果
    retrieved_nodes: list[dict]  # {text, score, metadata, collection}
    
    # 压缩后的上下文窗口
    context_window: str  # 经过摘要/截断后送给 LLM 的文本
    
    # 答案
    answer: str
    
    # 引用来源
    citations: list[dict]  # {text_preview, collection, score}
    
    # 知识库集合名
    collection: str
    
    # 用户 ID（多用户隔离）
    user_id: str
    
    # 配置
    config: dict  # {top_k, rerank, score_threshold, ...}
```

### 3.2 Graph 节点设计

**节点 1：query_rewriter（查询改写）**
- 输入：`user_query` + 最近 N 轮对话历史
- 输出：`rewritten_queries`
- 作用：将多轮对话中的指代消解（"它"、"这个"）补全为独立问题
- 实现：调用 LLM，prompt 中注入对话历史摘要

**节点 2：retriever（检索）**
- 输入：`rewritten_queries` + `collection`
- 输出：`retrieved_nodes`
- 实现：**直接调用 `server/retriever.py` 的 `get_query_engine()`**
- 无需重写检索逻辑

**节点 3：context_manager（上下文窗口管理）**
- 输入：`retrieved_nodes` + `messages`（历史）
- 输出：`context_window`
- 作用：**这是大上下文优化的核心**
  - 策略 1：截断 - 取 Top-K 节点，超过 token 限制则截断
  - 策略 2：摘要 - 对检索结果做 extractive summary
  - 策略 3：滑动窗口 - 保留最近 3 轮完整对话 + 更早的摘要
  - 策略 4：分层压缩 - 高相关度节点全文保留，低相关度节点只保留摘要句

**节点 4：generator（答案生成）**
- 输入：`context_window` + `messages`（带 system prompt）
- 输出：`answer` + `citations`
- 实现：**复用 `server/models/llm_api.py` 或 `ollama.py` 创建的 LLM**
- Prompt 需新增，支持引用标注（[1][2]）

**节点 5：reflection（答案反思，可选）**
- 输入：`answer` + `retrieved_nodes`
- 输出：评分 + 是否需要重新检索的信号
- 作用：检查答案是否忠实于检索结果（faithfulness check）
- 第一版可跳过，作为 Phase 2

### 3.3 与现有代码的集成点

| LangGraph 组件 | 对接的现有模块 | 对接方式 |
|---------------|---------------|---------|
| retriever 节点 | `server/retriever.py` | `get_query_engine(index, collection, top_k, rerank)` |
| generator 节点 LLM | `server/models/llm_api.py` | `create_openai_llm()` 创建的实例 |
| embedding | `server/models/embedding.py` | 模块加载时自动注册到 Settings |
| vector store | `server/stores/vector_store.py` | 通过 engine.py 间接使用 |
| chat history | `server/stores/chat_store.py` | `ChatHistoryStore.get_history()` 提供对话历史 |
| 入库流程 | `server/ingestion.py` | 完全复用，不改动 |

### 3.4 Context Window 管理策略（大上下文优化）

这是引入 LangGraph 的核心价值之一。建议分三个层次：

**Layer 1：对话历史窗口管理**
```
完整保留：最近 3 轮对话
摘要保留：更早的对话压缩为摘要（每轮一句话）
最大 token 预算：总 context 的 30%
```

**Layer 2：检索结果窗口管理**
```
相关度 > 0.8：全文保留
相关度 0.6-0.8：保留前 200 字
相关度 < 0.6：丢弃
最大 token 预算：总 context 的 60%
```

**Layer 3：System Prompt**
```
固定 token 预算：总 context 的 10%
```

**实现建议：**
```python
def manage_context_window(state: KBAgentState, max_tokens: int = 4000):
    """
    大上下文窗口管理器
    
    token 预算分配：
    - system prompt: 10% (400 tokens)
    - 对话历史: 30% (1200 tokens)  
    - 检索结果: 60% (2400 tokens)
    """
    system_budget = int(max_tokens * 0.10)
    history_budget = int(max_tokens * 0.30)
    retrieval_budget = int(max_tokens * 0.60)
    
    # 1. 对话历史压缩
    history = compress_history(state["messages"], history_budget)
    
    # 2. 检索结果筛选与截断
    nodes = rank_and_truncate(state["retrieved_nodes"], retrieval_budget)
    
    # 3. 组装最终 context
    context = assemble_context(system_prompt, history, nodes)
    
    return {"context_window": context}
```

### 3.5 大上下文模型适配

当使用大上下文模型（如 32k、128k 窗口的模型）时，策略可以更宽松：

```python
CONTEXT_PROFILES = {
    "small": {  # 4k context
        "history_rounds": 3,
        "top_k_nodes": 3,
        "strategy": "truncate"
    },
    "medium": {  # 16k context
        "history_rounds": 10,
        "top_k_nodes": 10,
        "strategy": "truncate"
    },
    "large": {  # 128k context
        "history_rounds": 50,
        "top_k_nodes": 50,
        "strategy": "full_with_summary"
    }
}
```

## 四、新增文件清单

### 4.1 必须新增

| 文件 | 用途 |
|------|------|
| `server/agent/__init__.py` | 包初始化 |
| `server/agent/graph.py` | LangGraph StateGraph 定义与编排 |
| `server/agent/state.py` | KBAgentState TypedDict 定义 |
| `server/agent/nodes/query_rewriter.py` | 查询改写节点 |
| `server/agent/nodes/context_manager.py` | 大上下文窗口管理节点 |
| `server/agent/nodes/generator.py` | 答案生成节点 |
| `server/agent/nodes/reflection.py` | 答案反思节点（Phase 2） |
| `server/agent/prompts.py` | Agent 专用 prompt 模板 |
| `server/api/agent_api.py` | Agent API 接口 |
| `webapp/api/agent.py` | Agent API 封装 |
| `webapp/src/pages/KnowledgeQA.jsx` | 知识库问答前端页面 |
| `webapp/src/components/ChatWindow.jsx` | 对话窗口组件 |
| `webapp/src/components/CitationPanel.jsx` | 引用来源面板 |

### 4.2 需要修改的现有文件

| 文件 | 修改内容 |
|------|---------|
| `server/stores/chat_store.py` | 新增 `save_agent_state()` / `get_agent_state()` 方法 |
| `server/text_splitter.py` | 新增 `create_text_splitter_for_collection()` 支持自定义 chunk_size |
| `config.py` | 新增 Agent 相关配置项 |
| `requirements.txt` | 新增 `langgraph`、`langchain-core` 依赖 |

### 4.3 不需要改动的文件

| 文件 | 原因 |
|------|------|
| `server/retriever.py` | 直接复用 `get_query_engine()` |
| `server/ingestion.py` | 入库流程不变 |
| `server/engine.py` | 引擎不变 |
| `server/stores/vector_store.py` | 向量库不变 |
| `server/models/*` | LLM/Embedding/Reranker 不变 |
| `server/prompt.py` | 现有 prompt 保留，Agent 用新 prompt |

## 五、依赖变更建议

```txt
# 新增（requirements.txt 末尾）
langgraph>=0.2.0
langchain-core>=0.3.0
tiktoken>=0.7.0  # token 计数，用于上下文窗口管理
```

注意：
- 项目已有 `langchain>=0.3.0`，与 LangGraph 兼容
- 不需要引入 `langchain-community` 额外依赖
- LangGraph 只依赖 `langchain-core`

## 六、与设计方案 V1 的关键差异

| 方面 | V1 设计 | 本建议 |
|------|--------|--------|
| 存储层 | 重新设计 Milvus/Pinecone/Weaviate | 直接复用现有 stores/ |
| 检索层 | 重新设计 SemanticRetriever | 直接复用 server/retriever.py |
| 入库层 | 重新设计 | 直接复用 server/ingestion.py |
| LangGraph | StateGraph（正确） | StateGraph + context_manager 节点 |
| 上下文管理 | 未涉及 | **三层上下文管理策略（核心新增）** |
| 问答流程 | 单轮 | 多轮有状态对话 |

## 七、分阶段实施建议

### Phase 1：MVP（2 周）
- StateGraph 基础流程：query_rewrite → retrieve → generate
- 复用现有 retriever.py 和 LLM
- 基础上下文窗口管理（截断策略）
- 单知识库问答
- API 接口 + 最简前端

### Phase 2：增强（1.5 周）
- 大上下文优化（摘要压缩、滑动窗口）
- 多知识库路由
- 引用溯源展示
- 答案质量反思节点

### Phase 3：优化（1 周）
- 缓存策略（相同问题缓存答案）
- 性能优化（并发检索）
- 多用户隔离完善
- 流式输出支持

## 八、需要确认的决策点

1. **LLM 选择**：Agent 的 query_rewriter 和 generator 可以用不同的 LLM 吗？比如 query_rewriter 用小模型（快），generator 用大模型（质量高）？
2. **上下文窗口大小**：默认按 4k 还是 16k 配置？是否需要支持用户自选？
3. **聚类功能**：是否纳入 Phase 1？建议降为 Phase 2
4. **流式输出**：Phase 1 是否需要？LangGraph 的流式输出需要 async 支持
5. **前端技术栈**：继续 Vue 还是用 Streamlit 快速验证？
