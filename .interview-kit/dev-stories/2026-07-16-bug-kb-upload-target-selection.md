# 修复知识库上传静默落入 default

## 基本信息
- 类型：bug
- 日期：2026-07-16
- 相关模块：知识库选择上下文、知识库侧边栏、文件上传、网页导入、文档列表、前端 API 响应处理
- 相关文件：`webapp/src/components/kb/KbContext.jsx`、`webapp/src/components/kb/KbSidebar.jsx`、`webapp/src/components/kb/KbUpload.jsx`、`webapp/src/components/kb/KbWebImport.jsx`、`webapp/src/components/kb/KbDocumentList.jsx`、`webapp/src/api/kb.js`、`webapp/src/api/response.js`、`webapp/src/domain/kbSelection.js`

## 问题现象
知识库页面初始化时会静默选中 `default`。用户即使没有确认目标知识库，也能进入上传或网页导入流程，存在资料被误导入默认库的风险；同时知识库列表一度显示为空，阻断了“先选库、再上传”的正常链路。

## 根因分析
`KbContext` 把 `selectedKbId` 初始值直接设为 `default`，上传、网页导入和文档列表没有统一的“已登记且 active”选择校验。另一个独立根因是 Axios 响应拦截器已经返回 `response.data`，部分组件仍按未解包响应读取 `res.data.data`，导致真实知识库列表被错误解析为空。

## 解决方案
将初始选择改为空值，并抽取知识库选择规则与 API 数据解包函数。只有用户显式选中的 active KB 才能驱动文档查询、文件上传和网页导入；未选择时禁用相关标签和提交操作。新建 active KB 后自动选中，删除当前 KB 后清空选择，不再回退到 `default`。上传区域同时展示知识库名称、`kb_id` 和 `data/{kb_id}/` 目标目录，并修正侧边栏嵌套交互控件。

## 为什么选这个方案
该方案在前端入口尽早阻止误操作，同时保留后端对 `kb_id` 的最终校验，形成双层保护。把“是否可选择”和“响应如何解包”变成纯函数后，可以用低成本单元测试覆盖关键分支，也避免各组件自行判断造成规则漂移。

## 其他方案与为什么没选
- 只依赖后端拒绝缺少 `kb_id` 的请求：无法在用户操作前明确展示目标，也不能解决默认库静默选择带来的误导。
- 保留自动选择 `default`，仅在上传按钮旁提示：仍然违反“用户必须显式选择知识库”的产品约束，不能消除误导入风险。

## 验证与结果
- `node --test webapp/src/api/response.test.js webapp/src/domain/kbSelection.test.js webapp/src/store/agentState.test.js`：16 passed，0 failed。
- `node --experimental-test-coverage --test webapp/src/api/response.test.js webapp/src/domain/kbSelection.test.js`：8 passed，两个新增模块的行、分支、函数覆盖率均为 100%。
- `npm run build`：Vite 构建通过，174 个模块完成转换。
- `python -m pytest tests/api/test_kb_routes.py tests/api/test_kb_directory_storage.py -q`：29 passed，2 条既有弃用 warning。
- 浏览器 smoke：初始不选择 `default`；未选择时上传/导入不可用；选择 `grain-knowledge-base` 后 14 个文档的目录和 `kb_id` 均正确，控制台无 error/warn。
- 为避免污染正式粮仓库，本轮未执行真实文件上传、新建和删除；真实上传保留在临时 smoke KB 中人工复验。

## 面试表达版本
我修复过一个多知识库上传会静默落入默认库的问题。根因既有选择状态默认成 `default`，也有 Axios 响应被重复解包，导致知识库列表异常。我把选择规则和响应解包抽成纯函数，要求用户显式选择 active KB，并让上传、网页导入和文档列表共享同一目标状态。新建库会自动选中，删除当前库会清空选择，同时界面明确展示实际落盘目录。最后我用 Node 单测、100% 的新增模块覆盖率、Vite 构建、29 条后端回归和浏览器 smoke 完成验证。
