# 知识库上传目标显式选择实施计划

## 1. 实施依据

本轮不增加产品范围，直接落实 `20260706-multi-kb-frontend-refactor` 已批准需求。采用 TDD：先以纯规则测试固定失败行为，再修改 React 状态与页面。

## 2. Task

### Task 1：选择规则与失败测试

- 新增 `webapp/src/domain/kbSelection.test.js`。
- 覆盖初始空选择、active 校验、刷新协调、创建后选择、删除后清空、缺少目标立即失败。
- 首次运行预期因实现模块不存在失败。

### Task 2：统一响应体解包

- 新增 `webapp/src/api/response.js` 与测试。
- 修复 Axios 拦截器已返回 `response.data` 后，组件仍二次读取 `res.data.data` 的问题。

### Task 3：知识库上下文与列表

- 修改 `KbContext.jsx`，初始选择为空，刷新时只保留仍存在且 active 的选择。
- 修改 `KbSidebar.jsx`，展示真实列表并支持创建、重命名、删除；创建成功自动选择新库。
- 将知识库选择按钮与操作按钮分离，满足键盘和辅助技术语义。

### Task 4：导入和文档链路

- 修改 `KbUpload.jsx`、`KbWebImport.jsx`、`KbDocumentList.jsx`、`KnowledgePage.jsx`。
- 未选择目标时禁用功能；选中后显示目标名称、`kb_id` 和目录。
- 修改 `webapp/src/api/kb.js`，所有相关调用强制携带 `kb_id`，且文件上传不再手动写 `multipart/form-data` 头。

### Task 5：验证与文档

- 运行 Node 测试与覆盖率、Vite 构建、后端 KB 回归、`git diff --check`。
- 浏览器验证初始状态、粮仓库 14 个文档、两个导入目标和控制台。
- 更新粮仓测试指南、`docs/project.md`、文档索引和测试报告。

## 3. 命令

```powershell
node --test webapp/src/api/response.test.js webapp/src/api/kb.test.js webapp/src/domain/kbSelection.test.js webapp/src/store/agentState.test.js
node --experimental-test-coverage --test webapp/src/api/response.test.js webapp/src/api/kb.test.js webapp/src/domain/kbSelection.test.js
cd webapp; npm run build; cd ..
python -m pytest tests/api/test_kb_routes.py tests/api/test_kb_directory_storage.py -q
git diff --check
```

## 4. 预期结果

- Node 回归全部通过。
- 新增规则模块覆盖率不低于 80%。
- Vite 构建成功。
- 后端定向回归全部通过，只允许保留已知 FastAPI `on_event` 弃用提示。
- 浏览器控制台无 error/warn，且不执行真实文件上传以避免污染粮仓库。
