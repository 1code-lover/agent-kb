# 为知识库导入补齐资产注册表与最小预览闭环

## 基本信息
- 类型：feature
- 日期：2026-07-24
- 相关模块：资产注册表、知识库导入链路、资产列表/预览接口
- 相关文件：`server/asset_registry.py`、`api/services/asset_service.py`、`api/services/kb_service.py`、`api/routers/kb.py`、`tests/api/test_asset_registry.py`、`tests/api/test_image_asset_import.py`

## 需求背景
前一轮我已经把 Markdown 内嵌图片解析出来了，但那时这些图片资产只存在于“导入回执”里，是一次性信息，不是知识库里真正可持续引用的对象。这样做能帮助排查导入问题，却还不能支撑后续更重要的能力，比如资产列表、图片预览、回答结果附带资产追溯，或者未来把图片资产开放给别的 agent 使用。所以这一步的重点，就是把图片从“回执里的临时字段”推进成“知识库里的持久化对象”。

## 设计与实现方案
1. 新建 `server/asset_registry.py`，按知识库拆分存储到 `storage/kb_assets/<kb_id>.json`，并提供原子写入、按 `asset_id` upsert、按 source doc 替换 embedded 资产，以及删除整个 KB 资产文件的能力。
2. 新建 `api/services/asset_service.py`，把资产相关规则集中起来：
   - 识别独立图片文件导入，登记为 `standalone` 资产；
   - 识别 Markdown 回执中的 embedded 图片，登记为 `embedded` 资产；
   - 对 embedded 资产按 source markdown 文档做“替换式写入”，避免重复导入后残留旧引用。
3. 在 `kb_service.import_files()` 里把资产注册接到主导入流程上，让“目录导入 → 文本索引 → 图片资产登记”形成一个连续闭环。
4. 在 `api/routers/kb.py` 新增两个接口：
   - `GET /api/kb/assets?kb_id=...`：按 KB 列出资产对象；
   - `GET /api/kb/assets/{asset_id}?kb_id=...`：返回单个资产的最小预览信息。
5. 给资产对象补一层运行时状态刷新：
   - 图片文件存在时是 `active`；
   - 图片文件缺失时是 `missing`；
   - embedded 资产如果源 Markdown 文档已经不存在，则标成 `orphaned`。
6. 用新增测试覆盖 registry 的 upsert/隔离、纯图片导入即使没有文本 chunk 也能登记资产，以及资产列表/预览接口不跨 KB 泄露。

## 为什么选这个方案
我这次没有直接上完整前端资产页、也没有把资产强行塞进现有 docstore，而是先落一个独立的 per-KB 资产注册表。原因很明确：第一，当前多知识库的真实边界还是 KB，不是 folder，也不是共享索引里的一段 metadata，所以资产最合理的最小落点也是“按 KB 分文件持久化”；第二，图片文件常常不会产出文本 chunk，如果继续把它们当成“只有进入向量库才算成功”，图片永远成不了一等对象；第三，先有稳定的 registry 和最小 API，后面不管是前端资产 Tab、evidence 携带 `asset_id`，还是对接外部 agent，都有一个可以复用的对象层，不用每次重新从 Markdown 原文里猜路径关系。

## 其他方案与为什么没选
- 方案一：继续只在导入回执里保留 `embedded_assets`。没选，因为回执是一次性结果，不适合承担持久对象职责。
- 方案二：把图片资产强耦合到现有 docstore/ref_doc。没选，因为当前系统还没有正式 Document 表，过早强绑会把这轮工作升级成架构级重构。
- 方案三：先做前端页面，再回头补后端资产对象。没选，因为没有后端 registry，前端拿到的仍然只是临时拼接数据，后面会反复返工。

## 风险与权衡
- 这次的资产 registry 仍然是“最小闭环”，还没有做到 asset 与 evidence 的全链路绑定，也还没做专门的前端资产页；这是刻意收住范围，先保证对象模型站得住。
- 目前图片内容理解仍然没有展开，资产状态更多是文件层和引用层的可追溯性，而不是语义理解深度。
- 资产注册走的是独立 JSON 持久化，而不是物理隔离存储引擎；它能表达边界，但不等于已经解决所有更深层的隔离问题，这一点仍然要和总 PRD 的“共享索引现实”保持一致。

## 验证与结果
- 执行命令：`python -m pytest tests/api/test_asset_registry.py tests/api/test_image_asset_import.py tests/api/test_markdown_asset_extraction.py tests/api/test_folder_registry.py tests/api/test_kb_folder_listing.py tests/api/test_kb_directory_import_tree.py tests/api/test_kb_directory_storage.py tests/api/test_m2_multi_kb.py tests/api/test_index_manager_coverage.py -q`
- 结果：`84 passed, 2 warnings`
- 结论：资产注册表、纯图片导入登记、Markdown embedded 资产登记、资产列表/预览接口，以及既有导入/多 KB/目录化回归均通过；warnings 仍是 FastAPI `on_event` 既有弃用提示，不是本轮新增问题。

## 面试表达版本
我在做本地知识库助手时，发现只把 Markdown 里的图片解析出来还不够，因为它们只是导入回执里的临时字段，不是系统里真正的对象。于是我往前推进了一步：专门做了一个按知识库分文件持久化的资产注册表，把独立图片导入和 Markdown embedded 图片都登记进去，再补了最小的资产列表和预览接口。这里有个关键判断是，图片文件即使没有文本 chunk 也必须成为一等对象，所以我把资产登记从“依赖向量化成功”里解耦出来。这样后面不管是做前端资产页、evidence 追溯，还是接外部 agent，都已经有了一个稳定的资产对象层，而不是继续靠回执临时拼装。
