# 为本地知识库导入补齐文件夹注册与目录树保留能力

## 基本信息
- 类型：feature
- 日期：2026-07-24
- 相关模块：知识库导入链路、Folder Registry、KB 路由、索引删除清理
- 相关文件：`api/services/kb_service.py`、`api/services/folder_service.py`、`api/routers/kb.py`、`server/folder_registry.py`、`server/index.py`、`tests/api/test_folder_registry.py`、`tests/api/test_kb_folder_listing.py`、`tests/api/test_kb_directory_import_tree.py`、`tests/api/test_kb_directory_storage.py`、`tests/api/test_index_manager_coverage.py`

## 需求背景
我们前面的多知识库 PRD/FRD 已经明确：知识库是一级对象，文件夹只是组织层，不是安全边界。但现有导入链路仍然偏“单文件平铺”，既不保留目录树，也没有稳定的 folder 视图；另外导入失败和删除旧索引残留引用时，还存在 doc_count 统计和 ref_doc 清理不够稳的问题。若不先把这层底座补齐，后面做 Markdown 资产抽取、图片/流程图预览和前端目录上传时，知识对象模型会越来越乱。

## 设计与实现方案
1. 在 `api/services/kb_service.py` 重写文件导入结果模型：为每个文件返回 `receipt_id`、逐项 `status`、`indexed_chunks`、`success/failed/empty` 统计，并把导入流程改成逐文件处理，避免一批文件中单个失败拖垮整个批次。
2. 在同一服务里新增 `relative_paths` 与 `import_mode` 参数，支持 `preserve_tree` / `flatten` 两种写入模式：
   - `preserve_tree` 时写入 `data/<kb_id>/<relative_path>`，同时回显 `relative_path`、`folder_path`。
   - `flatten` 时保持原有拍平导入习惯，作为兼容路径。
3. 新建 `server/folder_registry.py`，把 folder 视图独立成最小注册表，支持：
   - 规范化 `relative_path`
   - 从文档路径推导 folder 链
   - 以当前 KB 文档集合重建 / 修剪 registry
   - 每个 KB 独立持久化到 `storage/kb_folders/<kb_id>.json`
4. 新建 `api/services/folder_service.py`，在列 folder 时先扫描当前 docstore/ref_doc，再刷新 registry，保证 folder 视图来源于真实文档集合，而不是单纯依赖历史残留。
5. 在 `api/routers/kb.py` 新增 `GET /api/kb/folders`，并扩展 `POST /api/kb/file/import` 的表单参数，让后端形成“导入目录树 → 列 folder 节点”的最小闭环。
6. 在 `server/index.py` 的删除链路里补一层 stale `node_id` 引用清理，避免旧索引遗留 ref_doc 时删除异常，和导入侧的 doc_count 修正形成一前一后的稳定性兜底。
7. 用新增 / 更新的 API 测试覆盖 folder registry、目录树导入、文档路径回显与索引删除边界。

## 为什么选这个方案
我这次故意没有直接上“文件夹即权限边界”或“资产系统一次做完”，而是先把 folder 作为组织层能力落成最小闭环。这样做有三个好处：第一，能和当前“KB 才是边界对象”的产品原则保持一致，不会把现阶段共享索引 + metadata 过滤的现实重新包装成更重的承诺；第二，后端先把 `relative_path`、`folder_path`、folder registry 和批次回执这些底层契约立住，后续前端目录上传和 Markdown 资产抽取都能复用；第三，逐文件处理和失败清理能直接改善现在你最关心的“导入/嵌入容易出问题”这一条主链路，而不是只做 UI 表面增强。

## 其他方案与为什么没选
- 方案一：继续只保留平铺导入，不建 folder registry。没选，因为后续目录上传、树状浏览和资产挂载都会缺少稳定对象模型。
- 方案二：把文件夹直接做成权限边界。没选，因为当前安全边界仍然是 KB，不应该在 P0/P1 阶段引入错误心智。
- 方案三：先做前端目录上传 UI，再反推后端结构。没选，因为没有 `relative_path` / `folder_path` / folder registry 这些契约，前端做出来也只是临时拼装。

## 风险与权衡
- 这次仍然是“folder 组织层”而不是“物理隔离层”；真正的跨库安全边界问题依然取决于 KB 范围控制与后续存储隔离改造，不能把 folder registry 误解成安全能力。
- `preserve_tree` 会让路径合法性校验变重要，所以我在导入链路里显式拒绝 `../` 这类路径穿越，并要求 `relative_paths` 数量与上传文件一一对应。
- 目前只打通了后端闭环，还没有做前端目录选择器、Markdown 图片资产抽取和资产级预览；这是有意分阶段推进，避免同一轮把对象模型、导入链路和 UI 一起搅在一起。

## 验证与结果
- 执行命令：`python -m pytest tests/api/test_folder_registry.py tests/api/test_kb_folder_listing.py tests/api/test_kb_directory_import_tree.py tests/api/test_kb_docs_isolation.py tests/api/test_kb_directory_storage.py tests/api/test_m2_multi_kb.py tests/api/test_index_manager_coverage.py -q`
- 结果：`83 passed, 2 warnings`
- 结论：目录树导入、folder 列表、KB 文档路径回显、隔离回归和索引删除兜底均通过验证；warnings 为 FastAPI `on_event` 既有弃用提示，不是本轮新增问题。

## 面试表达版本
我在做本地多知识库助手时，发现真正卡住后续扩展的不是“再加一个上传按钮”，而是导入底座太平铺：目录结构丢失、失败回执粗糙、folder 视图也不存在。所以我先在后端把导入链路重做成逐文件处理，补上 `receipt_id`、单文件状态、`relative_path` 和 `folder_path`，同时做了一个最小的 folder registry，让知识库内部可以稳定地还原目录树。为了避免把 folder 误当成安全边界，我把它明确定位为组织层，而真正的边界仍然是 KB。这样后面不管是做 Markdown 图片资产抽取、预览，还是接外部 agent，都有一层可扩展的知识对象底座可以接。
