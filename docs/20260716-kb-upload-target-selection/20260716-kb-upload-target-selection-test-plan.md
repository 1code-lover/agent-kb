# 知识库上传目标显式选择测试方案

## 1. 目标

验证 `/knowledge` 页面必须先显式选择 active 知识库，文件上传、网页导入和文档列表始终绑定同一 `kb_id`；同时确认上传 API 不再显式覆盖 multipart 请求头，避免 Markdown 文件因 boundary 缺失返回 400。

## 2. 覆盖率门禁

- 目标：本轮新增纯规则模块 `webapp/src/domain/kbSelection.js` 与 `webapp/src/api/response.js` 的行、分支、函数覆盖率均 `>=80%`。
- 工具：Node.js 18 内置 `--experimental-test-coverage`。
- 失败处理：任一指标低于门禁即判定阶段 5 不通过，先补测试或收紧实现后重跑。

## 3. 测试用例

| 编号 | 场景 | 预期 |
|---|---|---|
| TC-01 | 首次打开页面 | 不自动选择 `default`，功能标签禁用 |
| TC-02 | KB 列表响应 | 正确解包统一响应体并展示真实列表 |
| TC-03 | 选择 active KB | 标题、文档列表、上传和网页导入均使用该 KB |
| TC-04 | 选择不存在或非 active KB | 选择被清空，导入不可执行 |
| TC-05 | 创建 active KB | 刷新列表后自动选择新库 |
| TC-06 | 删除当前 KB | 当前选择清空，不回退到 `default` |
| TC-07 | API 缺少 `kb_id` | 前端立即抛错，不发起请求 |
| TC-08 | 粮仓库文档隔离 | 14 个文档的路径和 `kb_id` 均属于 `grain-knowledge-base` |
| TC-09 | 可访问性 | 选择按钮与重命名/删除按钮不嵌套，键盘可聚焦 |
| TC-10 | 控制台 | 页面操作后无 error/warn |
| TC-11 | Markdown 文件上传 | 前端不显式写 multipart 头，避免 boundary 缺失导致 400 |

## 4. 正式命令

```powershell
node --test webapp/src/api/response.test.js webapp/src/api/kb.test.js webapp/src/domain/kbSelection.test.js webapp/src/store/agentState.test.js
node --experimental-test-coverage --test webapp/src/api/response.test.js webapp/src/api/kb.test.js webapp/src/domain/kbSelection.test.js
cd webapp; npm run build; cd ..
python -m pytest tests/api/test_kb_routes.py tests/api/test_kb_directory_storage.py -q
git diff --check
```

前两条分别用于全量前端规则回归与本轮模块覆盖率门禁，其中 `kb.test.js` 专门回归 multipart boundary 400 修复；后端命令用于确认前端修复没有改变 KB API 契约。浏览器 smoke 只读检查现有粮仓知识库，不创建、删除或上传真实数据。

## 5. 通过标准

- 所有正式命令通过。
- 前端 API/规则相关覆盖率 `>=80%`。
- 浏览器 smoke 满足未选库保护、粮仓库文档隔离、导入目标提示和控制台干净四项要求。
- `.md` 文件上传问题根因被回归锁定为“前端不再手动写 multipart 头”。
