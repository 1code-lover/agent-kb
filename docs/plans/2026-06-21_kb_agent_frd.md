# 知识库检索 Agent 功能设计（FRD）

## 1. 文档目的
将 PRD 转换为可执行的功能清单，为研发排期和测试设计提供统一依据。

## 2. 功能模块总览

| 模块 | 功能 | 优先级 |
|------|------|--------|
| 知识库管理 | 文档上传、分块、向量化 | P0 |
| 语义检索 | 向量检索 + BM25 混合检索 | P0 |
| 答案生成 | LLM 基于检索结果回答 | P0 |
| Query 改写 | 澄清追问检测、话题结合 | P1 |
| 自动路由 | 关键词匹配选择知识库 | P1 |

## 3. 功能清单

### M1 知识库管理模块（P0）
- **目标**：支持创建和管理多个知识库
- **包含**：
  - 知识库创建/更新/删除
  - 文档上传（PDF/DOCX/TXT）
  - 文档分块（Chunk）
  - 文档向量化（Embedding）
  - 知识库列表查询
- **验收要点**：
  - 可创建多个知识库
  - 可上传文档到指定知识库
  - 文档自动分块和向量化
  - 知识库列表正确显示

### M2 语义检索模块（P0）
- **目标**：根据问题检索相关文档
- **包含**：
  - 向量检索（语义相似度）
  - BM25 检索（关键词匹配）
  - 结果融合排序
  - Top-K 返回
- **验收要点**：
  - 向量检索返回语义相似文档
  - BM25 检索返回关键词匹配文档
  - 混合检索结果合理排序
  - 支持多知识库联合检索

### M3 答案生成模块（P0）
- **目标**：基于检索结果生成答案
- **包含**：
  - 提示词构建
  - LLM 调用
  - 答案生成
  - 来源标注
- **验收要点**：
  - 答案基于知识库内容
  - 标注引用来源

### M4 Query 改写模块（P1）
- **目标**：基于上下文优化检索效果
- **包含**：
  - 澄清追问检测
  - 话题结合改写
  - 语义保持
- **验收要点**：
  - 澄清追问可正确识别
  - 改写后语义正确

### M5 自动路由模块（P1）
- **目标**：根据问题自动选择知识库
- **包含**：
  - 关键词匹配
  - 知识库选择
- **验收要点**：
  - 可正确匹配相关知识库

### M6 置信度评估模块（P2）
- **目标**：评估检索结果与答案的置信度
- **包含**：
  - 检索结果相关性评分
  - 答案置信度计算
- **验收要点**：
  - 置信度评分合理可解释

## 4. 检索流程

```
用户输入
    ↓
┌─────────────────────────────────────┐
│         Query 改写                   │
│  ┌─────────┐  ┌─────────┐          │
│  │ 澄清追问 │  │ 话题结合 │          │
│  └────┬────┘  └────┬────┘          │
│       └────────────┴────→ 改写查询   │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│         知识库选择                   │
│  ┌─────────┐  ┌─────────┐          │
│  │ 用户选择 │  │ 自动路由 │          │
│  └────┬────┘  └────┬────┘          │
│       └────────────┴────→ 选定知识库 │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│         语义检索                     │
│  ┌─────────┐  ┌─────────┐          │
│  │ 向量检索 │  │ BM25    │          │
│  └────┬────┘  └────┬────┘          │
│       └────────────┴────→ 结果融合   │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│         答案生成                     │
│  ┌─────────┐  ┌─────────┐          │
│  │ 构建提示 │  │ 调用LLM  │          │
│  └────┬────┘  └────┬────┘          │
│       └────────────┴────→ 生成答案   │
└─────────────────────────────────────┘
    ↓
返回结果（answer + evidence + confidence）
```

## 5. 数据结构设计

### 5.1 知识库元数据
```json
{
  "kb_id": "string",
  "name": "string",
  "description": "string",
  "created_at": "datetime",
  "updated_at": "datetime",
  "doc_count": "integer",
  "chunk_count": "integer",
  "status": "active|inactive"
}
```

### 5.2 检索请求
```json
{
  "question": "string",
  "session_id": "string",
  "kb_ids": ["string"] | "auto",
  "context_mode": "auto|none|refresh",
  "max_results": "integer",
  "max_retries": "integer"
}
```

### 5.3 检索响应
```json
{
  "answer": "string",
  "evidence": [
    {
      "kb_id": "string",
      "source": "string",
      "page": "string",
      "score": "float",
      "excerpt": "string"
    }
  ],
  "confidence": "float",
  "rewritten_query": "string",
  "kb_used": ["string"]
}
```

## 6. 接口设计

### 6.1 知识库管理接口
```python
# 创建知识库
POST /api/kb/create
Request: { name, description }
Response: { kb_id, name, created_at }

# 列出知识库
GET /api/kb/list
Response: { kb_list: [{ kb_id, name, doc_count }] }

# 更新知识库
PUT /api/kb/{kb_id}
Request: { name, description }
Response: { success: true }

# 删除知识库
DELETE /api/kb/{kb_id}
Response: { success: true }

# 导入文档
POST /api/kb/{kb_id}/import
Request: multipart/form-data (files)
Response: { imported_count, chunk_count }
```

### 6.2 检索接口
```python
# 知识库检索
POST /api/kb/search
Request: { question, kb_ids, session_id, context_mode, max_results }
Response: { answer, evidence, confidence, rewritten_query, kb_used, sources }
```

## 7. 技术选型

| 组件 | 选型 | 说明 |
|------|------|------|
| Embedding | BAAI/bge-large-zh-v1.5 | 中文优化，1024维 |
| LLM | OpenAI 兼容 API | 支持 GPT/DeepSeek/Moonshot |
| 向量库 | LlamaIndex SimpleVectorStore | 开发模式 |
| 检索 | 向量检索 + BM25 | 混合检索 |
| 工作流 | LangGraph | 有状态、可观测 |

## 8. 开发拆分

### 后端
- 知识库管理服务（kb_service.py）
- 语义检索模块（retriever.py）
- 答案生成模块（answer_generator.py）
- Query 改写模块（query_rewriter.py）
- LangGraph 工作流（graph.py）

### 前端
- 知识库选择组件
- 检索结果展示

### 测试
- 知识库管理测试
- 检索流程测试
- 答案生成测试
- 集成测试

## 9. DoD（功能完成定义）
1. 知识库管理功能通过测试
2. 语义检索功能通过测试
3. 答案生成功能通过测试
4. Query 改写功能通过测试
5. 端到端流程通过测试
6. 单元测试覆盖率 >= 80%
