# ThinkRAG 知识库智能问答测试方案

## 1. 文档目的
用于指导 ThinkRAG 当前“知识库智能问答”主线的测试执行，覆盖真实代码中的核心接口、核心页面、主流程场景和异常路径。

## 2. 测试范围

### 2.1 后端接口
- `POST /api/kb/file/import`
- `POST /api/kb/web/import`
- `GET /api/kb/list`
- `DELETE /api/kb/docs`
- `POST /api/chat/query`
- `GET /api/chat/history`
- `DELETE /api/chat/history`

### 2.2 关键服务
- `api/services/kb_service.py`
- `api/services/chat_service.py`
- `api/services/session_store.py`

### 2.3 前端页面
- `frontend/Document_QA.py`
- `frontend/KB_File.py`
- `frontend/KB_Web.py`
- `frontend/KB_Manage.py`

## 3. 测试目标
1. 验证知识库导入、管理、问答、历史四条主链路可用。
2. 验证问答结果能够稳定返回，并具备来源信息。
3. 验证常见异常路径有明确提示，不出现静默失败。
4. 验证当前已有测试覆盖与主业务目标的一致性。

## 4. 测试分层

### 4.1 单元测试
目标：
- 验证 `kb_service`、`chat_service` 的核心逻辑。
- 验证请求模型和返回结构。

建议覆盖：
- `chat_service.query`
- `chat_service.get_history`
- `chat_service.clear_history`
- `kb_service.import_files`
- `kb_service.import_urls`
- `kb_service.list_docs`
- `kb_service.delete_docs`

### 4.2 接口测试
目标：
- 验证 `/api/kb/*` 与 `/api/chat/*` 的 HTTP 行为。

建议覆盖：
- 成功导入文件
- 成功导入网页
- 查询文档列表
- 删除文档
- 发起问答
- 查询历史
- 清理历史
- 异常输入返回 4xx

### 4.3 集成测试
目标：
- 验证“导入 -> 查询 -> 查看结果/历史”的业务闭环。

建议覆盖：
1. 导入一个文件后，立刻针对该文件内容发问。
2. 导入一个网页后，发起相关问题。
3. 删除文档后，再查询应体现结果变化或为空。
4. 多轮问答后，历史记录完整可读。

### 4.4 手工页面测试
目标：
- 验证 Streamlit 页面能完成核心操作。

建议覆盖：
1. `KB_File` 页面上传文件并导入。
2. `KB_Web` 页面导入 URL。
3. `KB_Manage` 页面查看与删除文档。
4. `Document_QA` 页面问答并查看来源。

## 5. 核心测试用例

### TC-01 文件导入成功
- 前置条件：系统已启动，知识库可写。
- 操作：上传 1 个合法文档并执行导入。
- 预期结果：
  - 接口返回成功
  - 文档出现在 `/api/kb/list`

### TC-02 网页导入成功
- 前置条件：系统可访问目标 URL。
- 操作：提交 1 个合法 URL。
- 预期结果：
  - 接口返回成功
  - 文档出现在文档列表

### TC-03 文档删除成功
- 前置条件：知识库中已有文档。
- 操作：调用 `/api/kb/docs` 删除指定文档。
- 预期结果：
  - 返回 `deleted > 0`
  - 文档列表同步减少

### TC-04 问答成功
- 前置条件：知识库非空。
- 操作：调用 `/api/chat/query` 发问。
- 预期结果：
  - 返回回答内容
  - 返回来源信息
  - 会话历史增加用户消息和助手消息

### TC-05 空知识库问答失败
- 前置条件：知识库为空。
- 操作：调用 `/api/chat/query` 发问。
- 预期结果：
  - 返回明确错误：知识库为空或需先导入文档

### TC-06 历史查询与清理
- 前置条件：已完成至少 1 轮问答。
- 操作：
  - 调用 `GET /api/chat/history`
  - 调用 `DELETE /api/chat/history`
- 预期结果：
  - 可查到历史
  - 清理后历史为空

## 6. 当前重点风险
1. 当前现有自动化测试主要集中在 agent runtime、risk、receipt 等能力，直接覆盖 `/api/kb/*` 与 `/api/chat/*` 主线的测试仍不足。
2. 前端页面层缺少明确的自动化回归用例。
3. 文件导入、网页导入与真实问答闭环的集成测试尚需补齐。

## 7. 建议执行顺序
1. 先补 `/api/chat/*` 和 `/api/kb/*` 接口测试。
2. 再补“导入 -> 问答 -> 历史”集成测试。
3. 最后补页面手工验收记录。

## 8. 通过标准
1. 核心接口用例通过率 100%。
2. 主流程集成测试通过率 100%。
3. 阻断问题为 0。
4. 关键异常路径均可返回可读错误。
