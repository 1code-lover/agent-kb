# ThinkRAG 多知识库 + React 前端重构 实施计划

## 1. 计划目标
实现最小多知识库能力 + React 统一知识库页面 + 废弃 Streamlit。分 4 个阶段，共 13 天。

## 2. 分阶段计划

### M1：后端多知识库核心（3天，估算依据：4个任务，每个0.5-1天，复杂度低）

**依赖关系：** 1.1 → 1.2 → 1.3+1.4（1.3和1.4可并行）
**验收标准：** 4个 CRUD 接口全部可用，创建/查询/更新/删除正常

#### 任务 1.1：kb_registry 模块
- 文件：`server/kb_registry.py`
- 功能：基于 JSON 文件的知识库目录管理
- 存储路径：`storage/kb_registry.json`

```python
# 核心方法
def list_kbs() -> list[dict]
def get_kb(kb_id: str) -> dict | None
def create_kb(kb_id: str, kb_name: str) -> dict
def update_kb(kb_id: str, kb_name: str) -> dict
def delete_kb(kb_id: str) -> bool
def exists(kb_id: str) -> bool
```

预期结果：`pytest tests/api/test_kb_registry.py` 通过

#### 任务 1.2：KB Schema
- 文件：`api/schemas/kb.py`
- Schema：
  - `KBCreateRequest(kb_id: str, kb_name: str)`
  - `KBUpdateRequest(kb_name: str)`
  - `KBResponse(kb_id, kb_name, created_at, updated_at, doc_count)`
  - `KBListResponse(items: list[KBResponse])`

#### 任务 1.3：KB 路由
- 文件：`api/routers/kb.py`（扩展）
- 新增路由：

```python
@router.post("/api/kb", response_model=KBResponse)
@router.get("/api/kb", response_model=KBListResponse)
@router.put("/api/kb/{kb_id}", response_model=KBResponse)
@router.delete("/api/kb/{kb_id}")
```

#### 任务 1.4：KB 服务层
- 文件：`api/services/kb_service.py`（扩展）
- 逻辑：
  - `create_kb()` → 校验唯一性 → 写入 registry
  - `list_kbs()` → 读取 registry
  - `update_kb()` → 校验存在 → 更新名称
  - `delete_kb()` → 校验存在 → 删除 registry + 级联清除文档索引

#### 测试
```bash
pytest tests/api/test_kb_routes.py -v
```

预期结果：所有 CRUD 接口 4 个测试用例通过（正常 + 重复 + 不存在 + 非空删除）

---

### M2：多知识库导入 + 查询改造（3天，估算依据：5个任务，每个0.5-1天，复杂度中）

**依赖关系：** 依赖 M1 完成；2.1+2.2 → 2.3+2.4+2.5（三者可并行）
**验收标准：** 导入指定库成功，查询带来源标识，存量迁移完成
**并发说明：** M2 与 M3 可部分并行（后端导入改造 2.1-2.2 完成后，前端即可开始 M3）

#### 任务 2.1：导入接口增加 kb_id
- 文件：`api/routers/kb.py`
- 改动：
  - `POST /api/kb/{kb_id}/file/import`
  - `POST /api/kb/{kb_id}/web/import`
  - 校验 `kb_id` 已登记 → 写入 metadata

#### 任务 2.2：索引 metadata 记录 kb_id
- 文件：`server/index.py`
- 改动：导入时在 document metadata 中追加 `kb_id` 字段

#### 任务 2.3：查询接口增加 kb_ids
- 文件：`api/schemas/__init__.py`
- 改动：`QueryRequest` 新增 `kb_ids: list[str] = []`

- 文件：`api/routers/chat.py`
- 改动：`POST /api/chat/query` 读取 `kb_ids`

- 文件：`api/services/chat_service.py`
- 改动：检索时根据 `kb_ids` 过滤（为空则查全部）

#### 任务 2.4：文档列表/删除接口增加 kb_id
- 文件：`api/routers/kb.py`
- 改动：
  - `GET /api/kb/{kb_id}/docs?page=1&page_size=20` → 按 kb_id 过滤 + 分页
  - `DELETE /api/kb/{kb_id}/docs/{doc_id}` → 校验 kb_id 归属

#### 任务 2.5：存量文档迁移
- 文件：`api/runtime.py`
- 改动：启动时检查 registry，若为空则自动创建 `default` 知识库
- 旧文档默认归入 `default` 库

#### 测试
```bash
pytest tests/api/test_multi_kb.py -v
```

预期结果：6 个测试用例通过（导入到指定库/无效库/查询单库/多库/空数组/结果带来源）

---

### M3：React 统一知识库页面（5天，估算依据：8个任务，前端组件开发每个0.5-1天，复杂度高）

**依赖关系：** 依赖 M1（registry API）完成；3.1 → 3.2~3.6（可并行）→ 3.7（3.7依赖3.1）→ 3.8
**验收标准：** 知识库页面可完成全部操作（创建/切换/上传/删除/搜索/分页），侧边栏导航正常
**并发说明：** 3.2~3.6 共5个组件可并行开发；M3 与 M2 可部分并行

#### 任务 3.1：KbContext（全局状态）
- 文件：`src/components/kb/KbContext.jsx`
- 功能：提供 `kbList`、`selectedKbId`、`selectKb`、`refreshKbs`
- 使用 React Context + useReducer

#### 任务 3.2：KbSidebar（知识库侧边栏）
- 文件：`src/components/kb/KbSidebar.jsx`
- 功能：
  - 展示知识库列表
  - 点击切换当前库
  - "+ 新建" 按钮 → 弹窗
  - 右键菜单：编辑名称 / 删除

#### 任务 3.3：KbDocumentList（文档列表）
- 文件：`src/components/kb/KbDocumentList.jsx`
- 功能：
  - 表格展示：名称 | 类型 | 大小 | 时间 | 操作
  - 搜索框（按名称过滤）
  - 分页控件

#### 任务 3.4：KbUpload（文件上传）
- 文件：`src/components/kb/KbUpload.jsx`
- 功能：
  - 拖拽 / 点击上传区域
  - 多文件支持
  - 进度条
  - 自动刷新列表

#### 任务 3.5：KbWebImport（网页导入）
- 文件：`src/components/kb/KbWebImport.jsx`
- 功能：
  - URL 输入框（多行）
  - 折叠的高级参数（chunk_size / chunk_overlap）
  - 导入按钮 + 进度反馈

#### 任务 3.6：KnowledgePage（主页面）
- 文件：`src/pages/KnowledgePage.jsx`
- 功能：组装 KbSidebar + Tab 内容区（文档列表 / 上传 / 网页导入）
- 布局：左侧 KbSidebar（240px），右侧内容区

#### 任务 3.7：API 层扩展
- 文件：`src/api/kb.js`
- 新增方法：
  ```javascript
  export const listKbs = () => api.get('/api/kb')
  export const createKb = (data) => api.post('/api/kb', data)
  export const updateKb = (kbId, data) => api.put(`/api/kb/${kbId}`, data)
  export const deleteKb = (kbId) => api.delete(`/api/kb/${kbId}`)
  export const listDocs = (kbId, params) => api.get(`/api/kb/${kbId}/docs`, { params })
  export const deleteDoc = (kbId, docId) => api.delete(`/api/kb/${kbId}/docs/${docId}`)
  export const previewDoc = (kbId, docId) => api.get(`/api/kb/${kbId}/docs/${docId}/preview`, { responseType: 'blob' })
  ```

#### 任务 3.8：ShellLayout 侧边栏
- 文件：`src/components/ShellLayout.jsx`
- 改动：侧边栏导航补全所有页面入口（/settings, /storage, /advanced, /kb-file, /kb-web, /kb-manage）

#### 测试
```bash
cd webapp && npm run dev
```
人工验证：
- 创建 3 个知识库，切换正常
- 上传文件到指定库，文档归属正确
- 搜索文档
- 分页正常

```bash
# 前端组件单元测试
cd webapp && npx vitest run
```
预期结果：KbContext、KbDocumentList、KbUpload 的单元测试通过，覆盖 TC-15~TC-18

---

### M4：文档预览 + 样式修复（2天，估算依据：5个任务，每个约0.5天，复杂度中）

**依赖关系：** 依赖 M3 完成
**验收标准：** PDF/文本预览正常，CSS 补全无遗漏，npm run build 无 warning

#### 任务 4.1：预览接口
- 文件：`api/routers/kb.py`
- 功能：`GET /api/kb/{kb_id}/docs/{doc_id}/preview`
  - PDF 返回二进制流
  - 文本返回 `{ content: "...", type: "text" }`

#### 任务 4.2：KbPreview 组件
- 文件：`src/components/kb/KbPreview.jsx`
- 功能：
  - 弹窗/侧边面板
  - PDF 使用 react-pdf 渲染
  - 文本使用 `<pre>` 展示
  - 分页翻页器
  - ESC / 点击遮罩关闭

#### 任务 4.3：CSS 补全
- 文件：`src/styles.css`
- 补全 97 个缺失 CSS 类，按功能分组：
  ```css
  /* Agent Chat */
  .agent-chat-layout { ... }
  .chat-bubble { ... }
  .chat-bubble-user { ... }
  .chat-bubble-assistant { ... }
  /* Buttons */
  .primary-button { ... }
  .secondary-button { ... }
  /* Layout */
  .stack-list { ... }
  .stack-card { ... }
  /* etc. */
  ```

#### 任务 4.4：死代码清理
- 删除 `src/api/chat.js`
- 删除 `src/pages/PlaceholderPage.jsx`
- 处理 `SessionPanel.jsx` 和 `AgentTaskStateBar.jsx`（保留作为归档或直接移除）

#### 任务 4.5：Streamlit 废弃
- 更新 `README.md`：React 为唯一前端，Streamlit 标记为归档
- `frontend/` 目录保留但 README 说明已废弃

#### 测试
```bash
cd webapp && npm run build
```
预期结果：构建成功，无 warning
```bash
pytest tests/api/test_multi_kb.py -v --cov
```
预期结果：覆盖率 >= 80%

---

## 3. 文件变更清单

### 新增文件
| 文件 | 所属阶段 |
|------|----------|
| `server/kb_registry.py` | M1 |
| `api/schemas/kb.py` | M1 |
| `src/components/kb/KbContext.jsx` | M3 |
| `src/components/kb/KbSidebar.jsx` | M3 |
| `src/components/kb/KbDocumentList.jsx` | M3 |
| `src/components/kb/KbUpload.jsx` | M3 |
| `src/components/kb/KbWebImport.jsx` | M3 |
| `src/components/kb/KbPreview.jsx` | M4 |

### 修改文件
| 文件 | 所属阶段 | 改动内容 |
|------|----------|----------|
| `api/routers/kb.py` | M1, M2 | 新增 CRUD + kb_id 参数 |
| `api/services/kb_service.py` | M1, M2 | registry 操作 + 导入逻辑 |
| `api/routers/chat.py` | M2 | kb_ids 参数 |
| `api/services/chat_service.py` | M2 | 按 kb_ids 检索 |
| `api/schemas/__init__.py` | M2 | 新增 kb_ids 字段 |
| `api/runtime.py` | M2 | 启动时创建 default 库 |
| `server/index.py` | M2 | metadata 记录 kb_id |
| `src/pages/KnowledgePage.jsx` | M3 | 完全重写 |
| `src/components/ShellLayout.jsx` | M3 | 导航补全 |
| `src/api/kb.js` | M3 | 新增方法 |
| `src/styles.css` | M4 | 补全 CSS |
| `README.md` | M4 | Streamlit 废弃说明 |

### 删除文件
| 文件 | 所属阶段 |
|------|----------|
| `src/api/chat.js` | M4 |
| `src/pages/PlaceholderPage.jsx` | M4 |

## 4. 测试命令

```bash
# 阶段 M1 — 覆盖 TC-01~TC-05
pytest tests/api/test_kb_routes.py -v

# 阶段 M2 — 覆盖 TC-06~TC-14
pytest tests/api/test_multi_kb.py -v

# 阶段 M3 — 覆盖 TC-15~TC-18
cd webapp && npm run dev  # 人工验证
cd webapp && npx vitest run  # 前端单元测试

# 阶段 M4 + 性能测试
cd webapp && npm run build
pytest tests/api/test_multi_kb.py -v --cov
cd webapp && npx vitest run --coverage
```

### 测试用例映射表

| Plan 测试 | 覆盖的 RTM 用例 | 阶段 |
|-----------|-----------------|------|
| `test_kb_routes.py` | TC-01~TC-05 | M1 |
| `test_multi_kb.py` | TC-06~TC-14 | M2 |
| KnowledgePage 人工验证 | TC-15~TC-16 | M3 |
| Vitest 单元测试 | TC-17~TC-18 | M3 |
| npm run build | TC-19 | M4 |

### 性能测试
- 文档列表加载：使用浏览器 DevTools Network 面板计时，目标 < 500ms
- 问答查询：使用 curl + `time` 命令测量，目标 < 2s
- 大文件上传：使用 50MB 测试文件测试，目标上传成功且进度条正常

## 5. 任务依赖关系总图

```text
M1: 1.1 → 1.2 → 1.3+1.4（并行）
                     ↓
M2: 2.1+2.2 → 2.3+2.4+2.5（并行）
                     ↓
M3: 3.1 → 3.2~3.6（并行）→ 3.7 → 3.8
                     ↓
M4: 4.1+4.2+4.3+4.4+4.5（可并行）

可并行流：
  M2 后端改造（2.1-2.2完成前）
  M3 前端开发（3.1完成后可启动）
```

## 6. 风险识别与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 存量文档迁移失败 | 高 | 低 | 迁移前备份 storage/ 目录，提供回滚脚本 |
| 97 个 CSS 类补全工作量低估 | 中 | 中 | 先跑一遍前端确认实际缺失类数量，预留 1 天 buffer |
| 前端与后端接口契约不一致 | 中 | 中 | 接口定义先在 FRD 中锁定，前后端并行开发时以 schema 为准 |
| 并发写入 JSON 文件冲突 | 低 | 低 | 使用文件锁 + threading.Lock |
| react-pdf 兼容性问题 | 中 | 低 | 备选方案：后端转图片流返回 |

## 7. 回滚策略

| 阶段 | 回滚操作 | 影响范围 |
|------|----------|----------|
| M1 | 删除 `storage/kb_registry.json`，还原 `api/routers/kb.py` 和 `api/services/kb_service.py` | 仅 KB 管理接口 |
| M2 | 还原 `api/routers/kb.py`、`api/routers/chat.py`、`api/services/chat_service.py`、`api/schemas/__init__.py` 的导入/查询参数 | 导入和查询接口 |
| M3 | 还原 `src/pages/KnowledgePage.jsx`、`src/components/ShellLayout.jsx`、`src/api/kb.js`，删除 `src/components/kb/` 目录 | 前端知识库页面 |
| M4 | 还原 `src/styles.css`，恢复被删除的文件（chat.js, PlaceholderPage.jsx） | 前端样式和文件 |

## 8. 前端测试补充（在 M3/M4 阶段执行）

### 单元测试（使用 Vitest，M3 阶段执行）
- `KbContext.test.jsx`：测试 createKb / selectKb / refreshKbs 状态变更
- `KbDocumentList.test.jsx`：测试列表渲染、搜索过滤、分页交互
- `KbUpload.test.jsx`：测试文件选择、上传进度、完成回调

### 集成测试（M3 阶段执行）
- `KnowledgePage.test.jsx`：测试整体页面渲染、Tab 切换、知识库切换联动
- 使用 `@testing-library/react` 渲染组件，模拟 API 调用

### 测试命令（已整合到 §4 测试命令中）

## 9. 时间估算汇总

| 阶段 | 任务数 | 复杂度 | 时间 | 估算依据 |
|------|--------|--------|------|----------|
| M1 | 4 | 低 | 3天 | 每个任务 0.5-1 天，无外部依赖 |
| M2 | 5 | 中 | 3天 | 每个任务 0.5-1 天，依赖 M1 |
| M3 | 8 | 高 | 5天 | 前端组件开发，每个 0.5-1 天 |
| M4 | 5 | 中 | 2天 | CSS 补全 + 预览 + 清理，每个约 0.5 天 |
| **总计** | **22** | | **13天** | |

## 10. 质量门禁
- 每个阶段任务完成后运行对应测试
- M4 结束时全量回归
- 后端接口覆盖率 >= 80%
- 前端单元测试通过
- npm run build 无错误
- 阻断问题为 0
