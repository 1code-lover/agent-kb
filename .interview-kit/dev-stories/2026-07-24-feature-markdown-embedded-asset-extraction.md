# 为知识库导入补齐 Markdown 内嵌图片资产抽取

## 基本信息
- 类型：feature
- 日期：2026-07-24
- 相关模块：知识库导入链路、Markdown 资产抽取、导入回执
- 相关文件：`api/services/kb_service.py`、`server/markdown_asset_extractor.py`、`tests/api/test_markdown_asset_extraction.py`

## 需求背景
我们前面已经把知识库内部的目录树、`relative_path` 和 `folder_path` 立住了，但导入链路仍然只把 Markdown 当成纯文本切块，文档里引用的本地图片、流程图和架构图不会进入任何结构化回执。这样一来，用户虽然把 `readme.md` 和配套图片一起传进来了，系统却不知道这篇文档还依赖哪些内嵌资产，更谈不上后面做图片预览、资产检索和引用闭环。

## 设计与实现方案
1. 新建 `server/markdown_asset_extractor.py`，专门负责解析 Markdown 图片语法和 HTML `<img src=...>`，抽取本地图片引用。
2. 在抽取器里区分可接受和不可接受的引用：
   - 忽略 `http/https`、`data:`、协议相对路径等远程资源；
   - 对越出知识库根目录的路径、绝对本地路径标记为 `invalid`；
   - 对库内存在的文件标记为 `ready`，不存在的标记为 `missing`。
3. 扩展 `api/services/kb_service.py` 的单文件导入回执，新增 `embedded_assets` 和 `asset_warning_count`，让 Markdown 文档在导入阶段就能回显“引用了哪些图片资产、当前状态是什么”。
4. 把 `import_files()` 的处理顺序从“写一个索引一个”改成“三阶段”：先全部落盘，再统一索引，最后再做 Markdown 资产抽取。这样同一批上传里即使 Markdown 在前、图片在后，也能按最终落盘结果把兄弟文件解析成 `ready`。
5. 用 `tests/api/test_markdown_asset_extraction.py` 覆盖 Markdown/HTML 两种语法、本地相对路径解析、远程引用忽略、越界/绝对路径拒绝、缺失资产 warning，以及“Markdown 和图片同批上传”的核心场景。

## 为什么选这个方案
我这次故意先做“导入时的轻量结构化抽取”，而没有一上来做完整的 Asset Registry 或图片理解。一方面，当前最痛的真实问题不是图片内容识别，而是导入后根本没有资产对象的基础信息，后续所有预览和检索能力都无从建立；另一方面，把解析放在导入阶段成本最低，因为这时已经有 `kb_id`、`relative_path` 和最终落盘位置，可以顺手把资产依赖关系收集出来。把顺序改成“先全量落盘再抽取”，也是为了兼容你最关心的目录批量导入场景，避免同批文件因为上传顺序不同而得到不稳定结果。

## 其他方案与为什么没选
- 方案一：等完整 Asset Registry 做好后再统一回扫 Markdown。没选，因为那会把当前导入缺口继续留着，用户还是看不到图片依赖关系。
- 方案二：导入阶段只返回原始 Markdown 文本，不做任何结构化资产抽取。没选，因为这对后续预览、引用和问题排查没有帮助。
- 方案三：直接接入 OCR 或多模态模型理解图片内容。没选，因为当前阶段首先要解决的是“图片是否被识别为知识对象”和“路径是否闭环”，不是内容理解深度。

## 风险与权衡
- 这次抽取的是“路径级资产依赖”，不是完整资产注册表；因此它先解决可见性和闭环问题，后续仍需要在下一阶段把资产对象持久化。
- `embedded_assets` 是新增回执字段，但我保留了原有导入成功/失败主流程，缺失图片只记 warning，不阻断 Markdown 导入，避免把存量文档一刀切判失败。
- 解析范围目前只覆盖 Markdown 图片语法和 HTML `img` 标签，没有扩展到更复杂的前端框架语法；这是有意控制范围，先把最常见、最稳定的文档场景打通。

## 验证与结果
- 执行命令：`python -m pytest tests/api/test_markdown_asset_extraction.py tests/api/test_folder_registry.py tests/api/test_kb_folder_listing.py tests/api/test_kb_directory_import_tree.py tests/api/test_kb_directory_storage.py tests/api/test_m2_multi_kb.py tests/api/test_index_manager_coverage.py -q`
- 结果：`80 passed, 2 warnings`
- 结论：Markdown 内嵌图片抽取、同批目录上传解析、缺失图片 warning 和既有目录化导入回归均通过验证；warnings 为 FastAPI `on_event` 既有弃用提示，不是本轮新增问题。

## 面试表达版本
我在做本地知识库助手时，发现一个很实际的问题：用户把 Markdown 和流程图图片一起导入了，但系统只会把 Markdown 当文本切块，根本不知道这篇文档依赖了哪些本地图片。于是我先做了一个轻量但关键的后端闭环：在导入阶段解析 Markdown 和 HTML 里的图片引用，区分 ready、missing、invalid，并把结果直接写进单文件导入回执。为了支持同批目录上传，我还把导入顺序改成先全部落盘、再统一索引、最后抽取资产，这样 Markdown 在前图片在后也能稳定识别。这样后面做资产注册、预览甚至多模态检索时，就不是从零开始，而是建立在一个已经有对象关系的底座上。
