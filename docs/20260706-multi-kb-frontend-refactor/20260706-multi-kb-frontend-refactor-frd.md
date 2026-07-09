# ThinkRAG 多知识库 + React 前端重构 功能设计（FRD）

## 1. 文档目的
将 PRD 需求拆解为可开发、可联调、可测试的功能模块，统一前后端实现方向。

## 2. 功能模块总览

| 模块 | 对应 PRD 需求 | 说明 |
|------|---------------|------|
| M1 后端多知识库核心 | FR-01 知识库目录管理 | registry CRUD |
| M2 多知识库导入 | FR-02 多知识库导入 | 文件+网页导入绑定 kb_id |
| M3 多知识库查询 | FR-03 多知识库查询 | 按 kb_ids 过滤检索 |
| M4 React 统一知识库页面 | FR-04 文档列表、FR-05 文档删除、FR-07 统一页面 | 左侧 KB 列表 + 右侧文档管理 |
| M5 前端样式与导航修复 | FR-08 样式与导航修复 | CSS 补全 + 导航 |
| M6 文档预览 | FR-06 文档预览 | PDF/文本预览 |
| M7 Streamlit 废弃 | FR-09 Streamlit 废弃 | 标记废弃 |

## 3. 技术选型

| 层面 | 技术 | 说明 |
|------|------|------|
| 前端框架 | React 18 | 保持现有技术栈 |
| 路由 | React Router v6 | 保持现有，ShellLayout 作为根布局 |
| 状态管理 | React Context + useReducer | 轻量方案，避免引入 Redux 额外负担 |
| HTTP 请求 | Axios | 保持现有 `src/api/client.js` 封装 |
| PDF 预览 | react-pdf (pdf.js) | 基于 canvas 渲染 PDF |
| 后端框架 | FastAPI | 保持现有技术栈 |
| 数据存储 | JSON 文件 (`storage/kb_registry.json`) | 轻量方案，无需数据库 |
| UI 组件库 | 纯 CSS（无组件库） | 保持现有风格，不引入 Ant Design 等外部依赖 |

## 4. 数据流设计

### 4.1 后端数据流
```
Client → FastAPI Router → Service Layer → Registry (JSON file)
                                     ↓
                              IndexManager (LlamaIndex)
                                     ↓
                          VectorStore / DocStore / IndexStore
```

### 4.2 前端数据流
```
KnowledgePage
  ├── KbContext.Provider (全局 KB 状态)
  │   ├── KbSidebar → 读取 kbList，选中 kbId
  │   ├── KbDocumentList → 根据 selectedKbId 请求文档列表
  │   ├── KbUpload → 上传后刷新文档列表
  │   ├── KbWebImport → 导入后刷新文档列表
  │   └── KbPreview → 根据 docId 请求预览内容
  └── 页面级 State
      ├── selectedKbId (当前选中知识库)
      ├── documentList (当前文档列表 + 分页)
      ├── previewContent (预览内容)
      └── uiState (加载中/错误/成功)
```

### 4.3 状态层次
- **全局 Context**：kbList（知识库列表）、selectedKbId（当前选中）
- **页面 State**：documentList（文档列表）、pagination（分页）、searchQuery（搜索关键词）
- **组件 State**：uploadProgress（上传进度）、previewContent（预览内容）

## 5. 功能设计

### M1 后端多知识库核心
- 目标：支持知识库的创建、查询、更新、删除，建立 registry 机制。
- 新增文件：
  - `api/routers/kb.py` — 扩展现有路由
  - `api/services/kb_service.py` — 扩展现有服务
  - `api/schemas/kb.py` — 新增 KB 请求/响应 schema
  - `server/kb_registry.py` — 知识库目录管理（JSON 文件存储）
- 接口：
  - `POST /api/kb` — 创建知识库（kb_id + kb_name）
  - `GET /api/kb` — 获取全部知识库列表
  - `PUT /api/kb/{kb_id}` — 更新知识库名称
  - `DELETE /api/kb/{kb_id}` — 删除知识库（级联删除关联文档和索引）
- 数据存储：`storage/kb_registry.json`（本地 JSON 文件）
- 并发控制：通过文件锁 + Python `threading.Lock` 控制写操作

### M2 多知识库导入 + 文档管理（FR-02, FR-04, FR-05）
- 目标：文件和网页导入时必须绑定 `kb_id`，文档入库后归属该知识库；文档列表/删除按 kb_id 隔离。
- 改动文件：
  - `api/routers/kb.py` — 导入/列表/删除接口增加 `kb_id` 参数
  - `api/services/kb_service.py` — 导入逻辑写入 `kb_id`，列表按 kb_id 过滤
  - `server/index.py` — 索引时在 metadata 中记录 `kb_id`
- 接口：
  - `POST /api/kb/{kb_id}/file/import` — 上传文件到指定知识库（FR-02）
  - `POST /api/kb/{kb_id}/web/import` — 导入网页到指定知识库（FR-02）
  - `GET /api/kb/{kb_id}/docs?page=&page_size=` — 按 kb_id 过滤文档列表（FR-04）
  - `DELETE /api/kb/{kb_id}/docs/{doc_id}` — 只能删除当前 KB 下的文档（FR-05）
- 规则：
  - `kb_id` 必须已登记，否则返回 400
  - 存量文档迁移：启动时自动创建 `default` 库，旧文档归入该库

### M3 多知识库查询
- 目标：问答接口支持指定一个或多个知识库检索，结果标明来源。
- 改动文件：
  - `api/routers/chat.py` — 查询接口增加 `kb_ids` 参数
  - `api/services/chat_service.py` — 按 `kb_ids` 过滤检索范围
  - `api/schemas/__init__.py` — `QueryRequest` 新增 `kb_ids` 字段
- 接口：
  - `POST /api/chat/query` — 新增 `kb_ids` 参数
- 规则：
  - `kb_ids` 为空数组：查询所有知识库
  - `kb_ids` 含未登记值：返回 400
  - 返回结果每条 source 带 `kb_id` / `kb_name`

### M4 React 统一知识库页面
- 目标：一个页面完成知识库全部操作（创建/切换/删除/上传/管理/预览）。
- 改动文件：
  - `src/pages/KnowledgePage.jsx` — 完全重写（主页面容器）
  - `src/components/kb/KbSidebar.jsx` — 知识库侧边栏
  - `src/components/kb/KbDocumentList.jsx` — 文档列表
  - `src/components/kb/KbUpload.jsx` — 上传组件
  - `src/components/kb/KbWebImport.jsx` — 网页导入
  - `src/components/kb/KbPreview.jsx` — 预览面板
  - `src/components/kb/KbContext.jsx` — KB 全局 Context
  - `src/components/ShellLayout.jsx` — 侧边栏 KB 菜单完善
  - `src/api/kb.js` — 扩展 API 调用
- 组件拆分：
  ```
  KnowledgePage
    ├── KbSidebar           ← 知识库列表、新建/编辑/删除
    ├── KbContent
    │   ├── KbDocumentList  ← 文档表格 + 搜索 + 分页
    │   ├── KbUpload        ← 拖拽/点击上传
    │   └── KbWebImport     ← URL 输入 + 参数配置
    └── KbPreview           ← 文档预览弹窗
  ```
- 页面布局：
  ```
  ┌──────────────────────────────────────────────┐
  │  侧边栏         │  主内容区                    │
  │  ───────────    │  ┌─────────────────────┐    │
  │  Agent          │  │  知识库: 产品文档    │    │
  │  模型           │  │  [文档列表] [上传]   │    │
  │  知识库         │  │  [导入网页]         │    │
  │    ├ 产品文档   │  │                     │    │
  │    ├ 技术方案   │  │  文档列表 (带分页)   │    │
  │    └ + 新建     │  │  ┌─────┬──────┬───┐ │    │
  │                 │  │  │名称 │类型  │操作│ │    │
  │                 │  │  ├─────┼──────┼───┤ │    │
  │                 │  │  │xxx  │ PDF  │预览│ │    │
  │                 │  │  └─────┴──────┴───┘ │    │
  │                 │  └─────────────────────┘    │
  └──────────────────────────────────────────────┘
  ```
- 交互：
  - 左侧点击知识库 → 右侧切换显示该库内容
  - 点击 "+ 新建" → 弹窗输入 kb_id + kb_name
  - 上传/导入在当前知识库上下文中操作，默认归属当前库
  - 文档列表支持搜索和分页
  - 点击文档行 → 预览面板

### M5 前端样式与导航修复
- 目标：补全缺失的 CSS，修复侧边栏导航，清理死代码。
- 改动文件：
  - `src/styles.css` — 补全 97 个缺失 CSS 类
  - `src/components/ShellLayout.jsx` — 补全导航入口
  - 清理：删除 `src/api/chat.js`、`src/pages/PlaceholderPage.jsx`
  - 处理：`SessionPanel.jsx`、`AgentTaskStateBar.jsx`（评估后集成或移除）
- CSS 类补全范围：`agent-chat-*`、`chat-bubble-*`、`compact-picker-*`、`banner-info`、`stack-*`、`primary-button`、`secondary-button` 等

### M6 文档预览
- 目标：支持已导入文档的内容预览。
- 新增接口：
  - `GET /api/kb/{kb_id}/docs/{doc_id}/preview`
- 前端实现：
  - PDF 使用 `react-pdf` 渲染
  - 文本文件使用 `<pre>` 或代码块展示
  - 网页内容以纯文本展示
- 预览面板：
  - 侧边弹出或叠加层
  - 支持 PDF 分页翻页

### M7 Streamlit 废弃
- 目标：标记 Streamlit 前端为废弃，React 为唯一前端。
- 改动：
  - `README.md` 更新为 React 版本启动说明
  - `frontend/` 目录保留但标记为已归档
  - 主入口明确为 `webapp/` + `run_api.py`

## 6. 性能优化策略

### 文档列表
- 后端分页 + 前端本地搜索过滤
- 每页默认 20 条，最大 100 条
- 使用 `page` + `page_size` 参数控制

### 文档预览
- PDF 使用 react-pdf 的 `lazy loading`，按需渲染当前页
- 文本内容直接返回全文，前端不做额外处理
- 大文件（>50MB）限制预览，提示"文件过大"

### 文件上传
- 单文件上传，不支持分片（当前阶段）
- 前端显示上传进度条（Axios `onUploadProgress`）
- 后端限制单文件 100MB

## 7. API 响应格式



### 成功响应
```json
{
  "code": 0,
  "message": "ok",
  "data": { ... },
  "request_id": "uuid"
}
```

### 错误响应
```json
{
  "code": 400,
  "message": "知识库ID已存在",
  "data": null,
  "request_id": "uuid"
}
```

### 分页响应
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [ ... ],
    "total_count": 42,
    "page": 1,
    "page_size": 20
  },
  "request_id": "uuid"
}
```

## 8. 页面级设计

### P1 知识库列表（左侧侧边栏）
- 展示所有知识库名称
- 当前选中库高亮
- 右键或操作菜单：编辑名称 / 删除
- 底部 "+ 新建知识库" 按钮

### P2 文档列表（主内容区默认 Tab）
- 表格形式：名称 | 类型 | 大小 | 时间 | 操作
- 操作列：预览、删除
- 顶部搜索框（按名称过滤）
- 底部分页控件

### P3 上传 Tab
- 拖拽或点击上传区域
- 支持多文件上传
- 进度条反馈
- 上传完成后自动刷新文档列表

### P4 导入网页 Tab
- URL 输入框（支持多行，每行一个 URL）
- chunk_size / chunk_overlap 参数配置（折叠可选）
- 导入按钮 + 进度反馈

### P5 文档预览弹窗
- 覆盖层或侧边面板
- PDF 模式：分页器 + 页面渲染
- 文本模式：全文展示
- 关闭按钮 / ESC 关闭

## 9. 交互规则
1. 操作上下文中，上传/导入默认归属当前选中的知识库
2. 新建知识库后自动选中该库并清空内容区
3. 删除知识库前弹窗确认，提示"将同时删除库内所有文档"
4. 文档预览只读，不支持编辑
5. 所有操作有 loading 态和结果反馈（toast 或内联提示）

## 10. 异常处理
1. 创建知识库失败：kb_id 冲突返回 409，网络异常返回通用错误提示
2. 上传失败：文件过大、格式不支持、磁盘空间不足各有明确提示
3. 预览失败：文件被删除或损坏时提示"文档无法预览"
4. 查询失败：模型未配置时引导用户去模型页面配置

## 11. 开发拆分建议

### 阶段 M1：后端多知识库核心
- `server/kb_registry.py` — JSON 文件存储的 registry
- `api/routers/kb.py` — 扩展 CRUD 路由
- `api/services/kb_service.py` — registry 操作逻辑
- `api/schemas/kb.py` — 新增 schema

### 阶段 M2：导入 + 查询改造
- 导入接口增加 `kb_id` 参数
- 查询接口增加 `kb_ids` 参数
- 存量文档迁移

### 阶段 M3：React 页面
- 重写 KnowledgePage.jsx
- ShellLayout.jsx 侧边栏完善
- API 层扩展

### 阶段 M4：预览 + 样式
- 预览接口 + 前端预览组件
- CSS 补全 + 导航修复
- 死代码清理

## 12. DoD（Definition of Done）
1. 后端：所有 KB 接口可用，单元测试覆盖
2. 前端：知识库页面功能完整，可通过 UI 完成全部操作
3. 样式：所有页面导航可达，样式无缺失
4. 预览：PDF 和文本文件可正常预览
5. 废弃：Streamlit 不再作为默认入口
6. 文档：FRD + RTM + 实施计划已对齐
