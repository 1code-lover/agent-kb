# ThinkRAG 知识库 V2 + React 前端重构 需求文档（PRD）

## 1. 文档信息
- 文档版本：v1.0
- 文档状态：初稿
- 编码要求：UTF-8
- 适用范围：ThinkRAG 知识库 V2 改造 + React 前端重构

## 2. 项目背景

### 2.1 当前现状
ThinkRAG 当前具备基础的知识库导入、管理、问答能力，但存在以下问题：

后端：
- 仅支持单知识库，`IndexManager` 硬编码 `knowledge_base` 单索引
- 所有文档导入/查询接口没有 `kb_id` 参数
- 没有知识库目录（registry）管理接口
- 没有文档预览接口
- 已有完整的多 KB 设计文档（`docs/spec/knowledge_base_visibility_and_multi_kb_design.md`），但未落地

前端：
- 两个前端并存：旧版 Streamlit（`frontend/`）和新版 React（`webapp/`）
- React 前端有 97 个 CSS 类在 JSX 中使用但未定义，页面实际无样式
- 7 个页面在侧边栏没有导航入口，只能手动输 URL 访问
- 多个组件实现了但未使用（SessionPanel、AgentTaskStateBar）
- 存在死代码（chat.js API、PlaceholderPage）
- 知识库相关页面（KbFilePage、KbWebPage、KbManagePage、KnowledgePage）功能简陋或纯占位

### 2.2 本轮目标
1. 实现最小多知识库能力（基于已有设计文档）
2. 重写 React 前端知识库页面，打造统一的知识库管理体验
3. 废弃 Streamlit 前端，只保留 React 版本
4. 补全前端基础样式和导航体系

## 3. 目标与成功标准

### 3.1 业务目标
1. 用户可创建多个知识库，实现资料分类管理
2. 文件/网页导入必须归属到指定知识库
3. 问答可按知识库范围检索
4. 知识库管理在统一页面内完成，交互流畅

### 3.2 成功标准
1. 用户可在界面中创建/切换/删除知识库
2. 导入文档时先选知识库，再上传
3. 文档列表按知识库隔离显示
4. 问答结果标注来源知识库
5. React 前端所有页面样式完整、导航可达
6. Streamlit 前端不再作为产品入口

## 4. 目标用户与场景

### 4.1 目标用户
- 个人知识工作者：需要分类管理不同主题的资料
- 团队内部使用者：需要按项目/部门隔离知识库

### 4.2 核心场景
1. 创建个人知识库（如"产品文档"、"技术方案"、"项目记录"）
2. 向指定知识库上传 PDF 等文件
3. 向指定知识库导入网页内容
4. 查看知识库内的文档列表
5. 按知识库范围发起问答
6. 预览知识库内文档内容
7. 在知识库内搜索文档
8. 删除知识库中的文档

## 5. 范围定义

### 5.1 优先级划分

| 需求 | 优先级 | 说明 |
|------|--------|------|
| FR-01 知识库目录管理 | P0 | 核心能力，必须先做 |
| FR-02 多知识库导入 | P0 | 依赖 FR-01 |
| FR-03 多知识库查询 | P0 | 依赖 FR-01 |
| FR-07 React 统一页面 | P1 | 前端核心体验 |
| FR-08 样式与导航修复 | P1 | 前端基础能力 |
| FR-04 文档列表 | P2 | 依赖 FR-01 |
| FR-05 文档删除 | P2 | 依赖 FR-01 |
| FR-06 文档预览 | P2 | 独立功能 |
| FR-09 Streamlit 废弃 | P3 | 最后收尾 |

### 5.2 In Scope
- 后端：知识库目录（registry）CRUD 接口
- 后端：导入接口支持 `kb_id`
- 后端：查询接口支持 `kb_ids`
- 后端：文档列表/删除接口支持 `kb_id`
- 后端：文档预览接口（读取文件内容返回）
- 后端：存量文档迁移方案
- 前端：React 统一知识库页面（KB 列表侧栏 + 文档管理主区）
- 前端：知识库创建/切换/删除 UI
- 前端：文件上传 UI（含目标 KB 选择）
- 前端：网页导入 UI
- 前端：文档列表展示（分页/搜索）
- 前端：文档预览（PDF/文本）
- 前端：补全 97 个缺失 CSS 类
- 前端：侧边栏导航补全
- 前端：废弃 Streamlit

### 5.3 Out of Scope
- 用户权限系统（user_id/role/group）
- 知识库共享与协作
- 文档在线编辑
- 批量文档操作（除批量删除外）
- 移动端适配
- 桌面端

### 5.4 技术约束

1. 后端必须遵循已有设计文档 `knowledge_base_visibility_and_multi_kb_design.md` 的接口契约
2. `kb_id` 生成规则：UUID v4 格式（小写，无连字符，如 `a1b2c3d4e5f6`）
3. 现有单知识库数据迁移：默认创建 `default` 知识库，将存量文档迁移至该库
4. 前端状态管理：使用 React Context + useReducer
5. PDF 预览库：使用 `react-pdf`（基于 pdf.js）
6. 后端框架：FastAPI，保持现有技术栈
7. 前端框架：React 18 + TypeScript，保持现有技术栈

### 5.5 数据模型

**删除策略：** 采用硬删除，直接删除数据和索引记录，不支持软删除。

**版本控制：** 当前版本不做文档历史版本保留，后续版本可考虑。

#### KnowledgeBase（知识库）

| 字段 | 类型 | 说明 |
|------|------|------|
| kb_id | string (UUID v4) | 唯一标识，不可修改 |
| kb_name | string | 知识库名称 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |
| doc_count | int | 文档数量（冗余字段） |

#### Document（文档，需扩展）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 文档唯一标识 |
| kb_id | string | 所属知识库ID（新增） |
| name | string | 文档名称 |
| type | enum | 类型：file / url |
| size | int | 文件大小（字节） |
| created_at | datetime | 创建时间 |
| metadata | json | 扩展元数据 |

## 6. 功能需求

### FR-01 知识库目录管理
- 支持创建知识库（`kb_id` + `kb_name`）
- 支持更新知识库名称（`kb_name`），不允许修改 `kb_id`
- 支持获取全部知识库列表
- 支持删除知识库（含级联删除关联文档），硬删除
- `kb_id` 唯一且不可修改
- 并发控制：同一知识库的写操作通过后端锁控制，避免竞态

### FR-02 多知识库导入
- 文件导入时必须指定 `kb_id`
- 网页导入时必须指定 `kb_id`
- 导入参数仍支持 `chunk_size` / `chunk_overlap`
- 导入失败返回明确错误信息

### FR-03 多知识库查询
- 问答接口支持 `kb_ids` 数组参数
- 支持单知识库查询（`kb_ids` 长度=1）
- 支持多知识库查询（`kb_ids` 长度>1）
- `kb_ids` 未传或为空数组：查询所有知识库
- `kb_ids` 含未登记 `kb_id` 时返回 400，错误信息："未知的知识库ID: {kb_id}"
- 结果标明来源 `kb_id` / `kb_name`

### FR-04 文档列表（按 KB 隔离）
- 获取指定 `kb_id` 下的文档列表
- 文档信息包含：名称、类型（file/url）、大小、日期
- 支持按文档名称搜索
- 支持分页：`page`（从 1 开始）、`page_size`（默认 20，最大 100）
- 返回总数 `total_count`

### FR-05 文档删除（按 KB 隔离）
- 删除指定 `kb_id` 下的文档
- 只能删除当前 KB 下的文档，不能跨库删除

### FR-06 文档预览
- 支持预览已导入的文档内容
- PDF 文件支持分页浏览
- 文本文件显示全文
- 网页导入的内容显示原文

### FR-07 React 统一知识库页面
- 左侧：知识库列表（可创建/切换/删除）
- 右侧（选中 KB 后）：
  - Tab/分区：文档列表 | 上传文件 | 导入网页
  - 文档列表展示名称、类型、时间，支持搜索
  - 点击文档可预览内容
- 全局上传入口（可指定目标 KB）

### FR-08 前端样式与导航修复
- 补全 97 个缺失的 CSS 类定义
- 侧边栏导航补全所有页面入口
- 删除死代码（chat.js、PlaceholderPage）
- 集成或移除未使用组件（SessionPanel、AgentTaskStateBar）

**工作量评估：**
| 子任务 | 预估时间 | 说明 |
|--------|----------|------|
| CSS 类补全 | 8-12小时 | 需逐个确认样式定义 |
| 导航修复 | 2-3小时 | 侧边栏组件修改 |
| 死代码清理 | 1-2小时 | 删除未使用文件 |
| 未使用组件处理 | 2-3小时 | 评估后决定保留或移除 |
| **总计** | **13-20小时** | |

### FR-09 Streamlit 废弃
- Streamlit 前端文件标记为废弃
- 入口 `app.py` 不再作为产品启动入口

## 7. 接口示例

### 7.1 创建知识库
```
POST /api/kb
Content-Type: application/json

{
  "kb_id": "product-docs",
  "kb_name": "产品文档"
}

Response 201:
{
  "kb_id": "product-docs",
  "kb_name": "产品文档",
  "created_at": "2026-07-06T10:00:00Z",
  "doc_count": 0
}
```

### 7.2 获取知识库列表
```
GET /api/kb

Response 200:
{
  "items": [
    {"kb_id": "product-docs", "kb_name": "产品文档", "doc_count": 5},
    {"kb_id": "tech-design", "kb_name": "技术方案", "doc_count": 3}
  ]
}
```

### 7.3 上传文件到指定知识库
```
POST /api/kb/{kb_id}/upload
Content-Type: multipart/form-data

file: <binary>

Response 201:
{
  "id": "doc-001",
  "kb_id": "product-docs",
  "name": "需求文档.pdf",
  "type": "file",
  "size": 1024000,
  "created_at": "2026-07-06T10:05:00Z"
}
```

### 7.4 更新知识库
```
PUT /api/kb/{kb_id}
Content-Type: application/json

{
  "kb_name": "新产品文档"
}

Response 200:
{
  "kb_id": "product-docs",
  "kb_name": "新产品文档",
  "updated_at": "2026-07-06T11:00:00Z"
}
```

### 7.5 删除知识库
```
DELETE /api/kb/{kb_id}

Response 200:
{
  "kb_id": "product-docs",
  "deleted": true
}
```

### 7.6 文档预览
```
GET /api/kb/{kb_id}/docs/{doc_id}/preview

Response 200:
Content-Type: application/octet-stream
（文件二进制流，前端根据类型渲染）

或 Response 200 (文本/网页):
{
  "content": "文档文本内容...",
  "type": "text",
  "page_count": 5
}
```

### 7.7 删除文档
```
DELETE /api/kb/{kb_id}/docs/{doc_id}

Response 200:
{
  "doc_id": "doc-001",
  "kb_id": "product-docs",
  "deleted": true
}
```

### 7.8 按知识库查询
```
POST /api/query
Content-Type: application/json

{
  "question": "项目进度如何？",
  "kb_ids": ["product-docs", "tech-design"]
}

Response 200:
{
  "answer": "...",
  "sources": [
    {"kb_id": "product-docs", "kb_name": "产品文档", "doc_name": "进度报告.pdf"}
  ]
}
```

## 8. 非功能需求

### NFR-01 易用性
- 知识库管理在一个页面内完成，无需跳转
- 上传流程不超过 3 步：选 KB -> 选文件 -> 确认上传
- 操作反馈明确（加载态、成功态、错误态）

### NFR-02 可维护性
- 后端接口职责清晰，`/api/kb/*` 管理知识库
- 遵循已有设计文档（`knowledge_base_visibility_and_multi_kb_design.md`）的接口契约
- 前端组件拆分合理，每个文件职责单一

### NFR-03 性能
- 知识库列表加载 < 1s（本地环境）
- 文档列表加载 < 500ms
- 问答查询响应 < 2s（本地环境）
- 文件上传支持 100MB 以内
- 文档预览支持大文件分页加载
- 上传进度条反馈

### NFR-04 稳定性
- 错误场景有明确提示，不出现静默失败
- React 前端有 Error Boundary 兜底

## 9. 错误场景定义

| 场景 | 错误码 | 提示信息 |
|------|--------|----------|
| kb_id 不存在 | 404 | "知识库不存在" |
| kb_id 重复创建 | 409 | "知识库ID已存在" |
| kb_name 为空 | 400 | "知识库名称不能为空" |
| 上传文件为空 | 400 | "请选择要上传的文件" |
| 文件格式不支持 | 415 | "不支持的文件格式，支持：PDF, TXT, MD, DOCX" |
| 预览文件过大 | 413 | "文件过大，无法预览（限制：50MB）" |
| kb_ids 含未登记值 | 400 | "未知的知识库ID: {kb_id}" |
| 文档不属于该知识库 | 403 | "无权操作此文档" |
| 导入网页URL无效 | 400 | "无效的网页URL" |
| 知识库非空无法删除 | 409 | "知识库非空，请先删除所有文档" |

## 10. 验收口径
1. 可在界面创建 3 个以上知识库
2. 向不同知识库上传文件，文档归属正确
3. 按知识库查看文档列表，内容隔离正确
4. 指定知识库问答，结果带来源标识
5. 文档预览正常（PDF/文本）
6. React 前端所有页面样式完整可用
7. 侧边栏导航可到达所有页面
8. Streamlit 不再作为默认入口

## 11. 里程碑与排期

| 阶段 | 交付物 | 预估时间 | 依赖 |
|------|--------|----------|------|
| M1 | 后端多知识库核心（registry CRUD） | 3天 | 无 |
| M2 | 多知识库导入 + 查询改造 | 3天 | M1 |
| M3 | React 统一知识库页面 | 5天 | M1（与 M2 部分并行） |
| M4 | 文档预览 + 样式修复 + 清理 | 2天 | M3 |
| **总计** | | **13天** | |
