# 知识库上传目标显式选择测试报告

- 执行日期：2026-07-16
- 仓库：`C:\Users\ethan1.zhao\Downloads\agent-kb-main\github-agent-kb`
- 前端：React 18 + Vite 5
- Node.js：v18.19.0
- Python：3.12
- 结论：通过，真实文件上传保留给用户在可控测试库中复验

## 1. TDD 记录

1. `kbSelection.test.js` 首次运行时因 `kbSelection.js` 不存在，按预期失败；实现后 6 条规则测试通过。
2. `response.test.js` 首次运行时因 `response.js` 不存在，按预期失败；实现后 2 条响应解包测试通过。
3. 浏览器首次显示“暂无知识库”时确认后端实际有 4 个 KB，定位为 Axios 响应已解包但组件再次读取 `res.data.data`；统一改为 `readApiData()` 后列表恢复。
4. 实施中曾出现 PowerShell 换行替换和相对子目录路径错误，均在最终门禁前修正；最终构建和浏览器控制台不包含这些临时错误。
5. 用户在真实新建 KB 中上传 `.md` 返回 400 后，复盘定位到前端手动设置 `Content-Type: multipart/form-data` 导致 boundary 丢失；移除显式请求头后补充 `kb.test.js`，用 API 调用层回归锁定“只传 `FormData`，不覆盖 multipart 头”的行为。

## 2. 自动化结果

### 2.1 Node 回归

```powershell
node --test webapp/src/api/response.test.js webapp/src/api/kb.test.js webapp/src/domain/kbSelection.test.js webapp/src/store/agentState.test.js
```

结果：`18 passed, 0 failed`。其中 `kb.test.js` 额外覆盖文件上传不显式设置 multipart 头的回归。

### 2.2 覆盖率

```powershell
node --experimental-test-coverage --test webapp/src/api/response.test.js webapp/src/api/kb.test.js webapp/src/domain/kbSelection.test.js
```

结果：`10 passed, 0 failed`；本轮前端 API/规则相关文件总覆盖率为 `80.92%`，其中 `response.js`、`kbSelection.js` 与 `kb.test.js` 均为 `100%`，高于 `>=80%` 门禁。

### 2.3 前端构建

```powershell
cd webapp
npm run build
```

结果：174 个模块转换完成，Vite 构建成功，耗时 4.03 秒。

### 2.4 后端定向回归

```powershell
python -m pytest tests/api/test_kb_routes.py tests/api/test_kb_directory_storage.py -q
```

结果：`29 passed, 2 warnings in 7.68s`。两条 warning 均为既有 FastAPI `on_event` 弃用提示，不阻断本轮验收。

## 3. 浏览器 smoke

测试地址：`http://127.0.0.1:5173/knowledge`。

| 检查项 | 结果 |
|---|---|
| 初始选择 | 通过；标题为“请选择知识库”，未自动选中 `default` |
| 知识库列表 | 通过；展示 4 个后端真实 KB |
| 功能保护 | 通过；未选择时文档列表、文件上传、网页导入标签禁用 |
| 粮仓库选择 | 通过；选中 `grain-knowledge-base` 后标题和目录提示正确 |
| 文档隔离 | 通过；显示 14 个文档，路径均位于 `data/grain-knowledge-base/`，`kb_id` 均正确 |
| 文件上传目标 | 通过；显示名称、`kb_id` 和 `data/grain-knowledge-base/`，无文件时按钮禁用 |
| 网页导入目标 | 通过；显示名称与 `kb_id`，URL 为空时按钮禁用 |
| 浏览器控制台 | 通过；error/warn 为空 |

未执行真实上传、新建或删除操作，避免给粮仓知识库和 registry 增加测试副作用。创建后自动选择由纯规则测试覆盖，用户可在临时空 KB 中继续人工复验。

## 4. 格式与文档门禁

最终执行 `git diff --check` 和精确占位词扫描。`git diff --check` 退出码为 0，仅保留 LF/CRLF 转换提示，没有空白格式错误；精确占位词扫描通过，共检查 39 个相关文件，未发现禁止占位标记。扫描范围包括本专题文档、前端代码、测试和项目进度文档，并通过单词边界规则避免误匹配 `HowToDownloadModels`。

## 5. 验收结论

本轮 P1 已完成代码修复和自动化、构建、后端回归、浏览器 smoke。上传链路不再静默使用 `default`，用户必须明确选择知识库后才能继续；同时前端已移除会导致 multipart boundary 丢失的显式请求头，`.md`/其他文件上传不应再因该问题报 400。真实小文件上传应在专用 smoke KB 中执行，验证落盘、计数和列表刷新后再开始粮仓主资料批量导入。
