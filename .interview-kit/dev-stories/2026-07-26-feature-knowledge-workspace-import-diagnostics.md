# 为本地知识库工作台补齐导入诊断、OCR 预热状态与对象浏览

## 基本信息
- 类型：feature
- 日期：2026-07-26
- 相关模块：Knowledge Workspace、知识库导入链路、OCR 运行状态、导入回执、对象浏览
- 相关文件：
  - `api/app.py`
  - `api/routers/health.py`
  - `api/routers/kb.py`
  - `api/services/kb_service.py`
  - `api/services/kb_import_receipt_store.py`
  - `server/ingestion.py`
  - `server/index.py`
  - `server/readers/image_ocr.py`
  - `server/text_file_loader.py`
  - `webapp/src/pages/KnowledgePage.jsx`
  - `webapp/src/components/kb/KbWorkspaceHeader.jsx`
  - `webapp/src/components/kb/KbReceiptSummary.jsx`
  - `webapp/src/components/kb/KbObjectExplorer.jsx`
  - `webapp/src/components/kb/KbDetailPanel.jsx`
  - `webapp/src/components/kb/KbAssetList.jsx`
  - `webapp/src/domain/importSummary.js`
  - `webapp/src/domain/ocrWarmup.js`
  - `webapp/src/api/health.js`
  - `start_dev.ps1`

## 需求背景
这轮工作的目标不是再写一版抽象 PRD，而是把项目真实跑起来，直接看清“导入、解析、OCR、嵌入到底哪里在出问题”。现有知识库页虽然已经有导入入口，但缺少一个面向调试和日常使用的统一工作台：看不到 OCR 运行时是否就绪，看不到最近一次导入回执，也很难把 Markdown、PDF、独立图片和 Markdown 内嵌图片放到同一个对象视图下理解。没有这层可观测性，后面不管是做嵌入优化、Agent 接入，还是知识库内文件夹/资产对象模型，都会一直靠猜。

## 设计与实现方案
1. 在 `api/app.py`、`api/routers/health.py` 补齐服务启动与健康信息：后端健康检查除了 `status=ok` 以外，还回传 OCR 预热状态，启动时支持后台预热 OCR 运行时，让前端可以明确区分“服务活着”和“OCR 可用”。
2. 在 `api/services/kb_service.py` 新增导入回执沉淀能力，并通过 `api/services/kb_import_receipt_store.py` 为每个知识库保存最近一次导入结果，字段里包含文档数、节点数、嵌入节点数、OCR 成败、内嵌资产统计、shadowed 资源等细粒度诊断信息；`api/routers/kb.py` 对外开放最近回执读取接口。
3. 在 `server/ingestion.py`、`server/index.py`、`server/readers/image_ocr.py`、`server/readers/pdf_ocr.py`、`server/text_file_loader.py` 继续收紧导入对象模型：
   - Markdown / PDF / 图片统一回到“知识对象 + 诊断信息”的回执结构。
   - 图片先只支持 OCR 提取与图片入库，不提前承诺复杂图像理解。
   - Markdown 内嵌图片与独立图片同时出现时，用 `shadowed_by_embedded_asset` 标出独立资源为何被跳过，避免重复入索引。
4. 在前端 `webapp/src/pages/KnowledgePage.jsx` 重做 Knowledge Workspace：以 `KbWorkspaceHeader`、`KbReceiptSummary`、`KbObjectExplorer`、`KbDetailPanel`、`KbAssetList`、`KbUpload` 组合成单一工作区，把知识库摘要、OCR 状态、导入动作、对象树、最近回执和资产详情放到同一个视图里。
5. 在 `webapp/src/domain/importSummary.js`、`webapp/src/domain/ocrWarmup.js`、`webapp/src/domain/folderTree.js`、`webapp/src/domain/knowledgeWorkspace.js` 等领域层做前端归一化，把后端回执字段转换成可稳定渲染的摘要、指标和对象导航模型，避免页面组件里散落一堆临时字段拼接。
6. 在 `start_dev.ps1`、`run_api.py` 增强本地开发启动路径，支持显式端口启动，便于在已有旧实例未完全退出时拉起新的干净环境做真实导入诊断。

## 为什么选这个方案
我这轮没有直接跳去做“更强 OCR”或“更智能图片理解”，而是先把知识库工作台、导入回执和运行时状态做成一层可观测底座。原因很直接：当前最需要解决的是“项目现状看不清”，而不是“先承诺一个更复杂的新能力”。只要导入回执、对象树和 OCR 状态是透明的，我们就能用真实样本判断慢在哪里、失败在哪里、哪些对象被跳过；后面无论要优化嵌入性能、改存储隔离，还是开放给其他 Agent，都有一套稳定的排障入口和契约可以复用。与此同时，图片能力先收敛到 OCR 提取 + 资产入库，也符合当前迭代节奏，避免在对象模型还没站稳前把多模态语义理解做得过深。

## 其他方案与为什么没选
- 方案一：先继续深挖 OCR 或图像理解能力。没选，因为实测纯 Markdown 导入也慢，说明瓶颈并不只在 OCR，先补可观测性收益更高。
- 方案二：直接做物理隔离或多库存储重构。没选，因为这是更重的架构改造，当前先把“工作台 + 回执 + 对象模型”立住，能让后续重构更有证据，而不是盲改。
- 方案三：只加几个调试日志，不改前端工作台。没选，因为调试日志只对开发阶段有用，不能成为知识库助手长期可用的产品能力；工作台能同时服务开发排障和用户心智建设。

## 风险与权衡
- 当前多知识库底层仍然是共享存储 + 过滤隔离，这轮工作并没有解决物理隔离问题；导入回执和工作台只是把现状看得更清楚，不应被误解成安全边界已经升级。
- 实测显示导入慢的主要瓶颈更像 `index_insert` / 持久化路径，而不是 OCR 本身；这意味着工作台能帮助定位问题，但性能优化还需要下一轮专门处理。
- 图片目前只承诺 OCR 提取与入库，不做复杂图表语义解析；这是有意收敛，先确保“图片能进入知识库、能被回执看见、能在需要时进入索引”。
- 在真实页面里已经观察到“最近导入回执首次进入偶发不显示、刷新后恢复”的时序问题，因此前端状态同步仍有后续修补空间。

## 验证与结果
- 启动命令：`powershell -ExecutionPolicy Bypass -File .\start_dev.ps1 -BackendPort 18081 -FrontendPort 5175`
- 环境结果：后端 `http://127.0.0.1:18081/api/health` 返回成功，`openapi.json` 中确认存在 `/api/kb/import-receipt/latest`。
- 手工验证：创建知识库 `live-import-debug-20260726-b` 后，分别导入了 4 组真实样本：
  1. 纯 Markdown：`document_count=1`、`node_count=1`、`nodes_with_embedding_count=1`，总耗时约 51 秒，其中 `ensure_models_ready_ms≈21.7s`、`get_index_manager_ms≈17.6s`、`index_insert_ms≈11.5s`。
  2. 纯图片：OCR 成功、`indexed_from_ocr=true`、`asset_registered=true`，总耗时约 22 秒，其中 `ocr_predict_ms≈11.7s`、`index_insert_ms≈10.2s`。
  3. Markdown + 内嵌图片：内嵌图片 OCR 成功，独立导入的同名图片被标记为 `shadowed_by_embedded_asset`，批次中 `embedded_asset_count=1`、`embedded_asset_ready_count=1`、`embedded_ocr_success_count=1`、`skip_standalone_asset_count=1`，总耗时约 40 秒。
  4. 扫描版 PDF：`document_count=1`、`input_text_chars=60`、`node_count=1`，总耗时约 20.9 秒，其中 `document_load_ms≈13.4s`、`index_insert_ms≈7.4s`。
- 结论：当前导入慢的核心问题不是 OCR 独有开销，而是索引写入 / 持久化路径偏慢；Knowledge Workspace 和导入回执已经足以把这个判断暴露出来。
- 额外说明：本轮主要验证方式是真实启动与真实导入样本回归，没有额外补跑前端全量测试。

## 面试表达版本
我在做本地多知识库助手时，发现团队最缺的不是再加一个算法点，而是一层能把“导入到底发生了什么”讲清楚的工作台。于是我先把 Knowledge Workspace 做起来：后端暴露 OCR 预热状态和最近导入回执，前端把知识库摘要、对象树、资产列表和导入诊断放到一个页里。这样我们用真实样本一跑，就能马上看到纯 Markdown 也慢、图片 OCR 只是部分成本、真正更重的是索引写入。图片能力我也刻意收敛到 OCR 提取和图片入库，没有过早承诺复杂图像理解。这个底座搭好以后，后面不管是做性能优化、存储隔离，还是给其他 Agent 开接口，都有了可复用的观察面和对象契约。
