# 本地多知识库知识助手平台 Folder / 目录导入 / Markdown 资产实施方案（Stage 2B）

## 1. 文档目的
本文档是 `20260722-local-multi-kb-assistant` 需求在 Stage 2 基线与 Stage 2A ingestion 加固之后追加的一份 **Stage 2B 实施方案**。

它不替代：
- `20260722-local-multi-kb-assistant-plan.md`
- `20260722-local-multi-kb-assistant-plan-ingestion-hardening.md`

它专门回答下面四个问题：
1. 知识库内部的文件夹层级在当前代码现实下怎么落；
2. 目录导入怎样做到“保留树结构”而不是把文件拍平；
3. Markdown 内嵌图片 / 流程图类资源怎样进入最小资产闭环；
4. 这一轮要先写哪些测试、改哪些文件、什么结果算通过。

> 说明：本轮属于 Stage 2B，优先级位于 Stage 2A 导入稳定性加固之后，目标是把“Folder + 目录导入 + Markdown 资源解析 + Asset 最小闭环”从设计推进到可编码状态。

---

## 2. 输入基线
本实施方案以下列文档为正式输入：
- `20260722-local-multi-kb-assistant-prd.md`
- `20260722-local-multi-kb-assistant-frd.md`
- `20260722-local-multi-kb-assistant-rtm.md`
- `20260722-local-multi-kb-assistant-plan.md`
- `20260722-local-multi-kb-assistant-plan-ingestion-hardening.md`
- `20260722-local-multi-kb-assistant-test-plan.md`
- `20260722-local-multi-kb-assistant-spec.md`
- 根目录 `评审建议.txt`

本方案必须与上面文档中已经确认的判断保持一致：
1. KnowledgeBase 是边界对象；
2. Folder 是组织对象，不是边界对象；
3. Chat 未声明范围默认拒绝；
4. 当前多知识库现实仍是共享单索引 + `kb_id` 逻辑过滤；
5. `evidence` 是正式契约，`sources` 只保留兼容；
6. `receipt_id` 必须保留；
7. 导入与索引结果不能继续“假成功”。

---

## 3. 当前代码现实（作为实施约束）

### 3.1 已核实现状
1. 当前文件导入入口是 `POST /api/kb/file/import`，由 `api/routers/kb.py::import_files()` 接收 `list[UploadFile]`。
2. 当前前端上传组件是 `webapp/src/components/kb/KbUpload.jsx`，只支持“平铺文件上传”，没有目录导入模式，也没有相对路径回传。
3. 当前 `api/services/kb_service.py::import_files()` 已在 Stage 2A 改成逐文件回执，但输入仍然只认 `file.filename`，没有 `relative_path` / `folder_path` 概念。
4. 当前 `server/index.py::load_files()` 会把 `kb_id`、`file_path`、`file_name` 写入节点 metadata，但不会写入 `folder_path`、`relative_path` 或资源关系信息。
5. 当前 `api/services/kb_service.py::list_docs()` 返回的是平铺文档列表，没有文件夹树，也没有资产列表。
6. 当前仓库里还没有真正落地的 `folder_registry` / `asset_registry` 代码；资产对象只存在于计划与测试方案中，还没有完整实现。
7. 当前 Markdown 文件会作为普通文本被读取并切分，但其内嵌图片、相对路径资源、流程图截图等内容不会进入单独的对象闭环。

### 3.2 当前直接暴露的问题
1. 用户即使按目录组织好了本地资料，导入后系统也看不到原目录结构；
2. Markdown 中的 `![img](./foo/bar.png)` 之类引用在导入后会丢失为“普通文本中的一串路径”；
3. 即使图片已经落盘到知识库目录，也没有独立资产对象去承载它；
4. 后续要做“按文件夹浏览 / 局部收窄 / 资产预览 / 资产证据引用”时没有稳定对象锚点；
5. 如果继续只做“文件上传 + 文本切分”，会导致你的知识库越大，结构感越差。

### 3.3 当前实现与产品目标之间的关键落差
当前产品已经明确：
- KnowledgeBase 是一级对象；
- Folder 是组织层；
- Asset 是一等知识对象；
- Markdown / PDF / 图片都应该进入统一知识体系。

但当前代码现实仍停留在：
- 平铺文件导入；
- 文档平铺列出；
- 图片只作为文件存在；
- Markdown 内嵌资源没有结构化承接。

因此，本轮的核心任务不是“再加一个小功能”，而是把知识内容组织从“平铺文件仓”升级到“有层级、有资源关系的知识对象体系”。

---

## 4. 本轮目标与非目标

### 4.1 本轮目标
本轮只做下面五类能力：
1. 在知识库内建立**最小 Folder 组织模型**；
2. 支持**目录导入 preserving tree**（保留源目录树）；
3. 把文档的 `relative_path / folder_path` 进入持久化语义；
4. 建立 **Markdown 内嵌本地图片资源** 的最小解析与资产登记闭环；
5. 让资产至少具备：可登记、可列出、可预览基础信息、可被 evidence 引用。

### 4.2 本轮明确不做
本轮不做：
1. Folder 手工 CRUD 完整产品化；
2. Folder 级权限或安全边界；
3. PDF 页内图片区域抽取；
4. 原生图像向量检索；
5. 高级视觉 caption / 图像理解；
6. 远程图片 URL 下载与缓存；
7. Data URI / Base64 内嵌资源完整支持；
8. 物理隔离 / 独立命名空间。

### 4.3 本轮交付原则
本轮目标不是“一次性把 Folder 和 Asset 做满”，而是：
- 先把最小对象模型立住；
- 先把目录结构保存下来；
- 先把 Markdown 内嵌本地图片从“看不见”变成“有对象可追”；
- 先让后续 Agent / 前端 / 检索链路有稳定锚点可接。

---

## 5. 实施总策略

### 5.1 策略一：Folder 先做“导入驱动对象”，不先做完整手工管理
本轮先不做完整的“新建文件夹 / 重命名 / 拖拽移动 / 树形编辑器”。

本轮先做：
1. 目录导入时自动生成 Folder 记录；
2. 文件导入时根据 `relative_path` 推导 `folder_path`；
3. 文档列表可以按 `folder_path` 分组或树状展示；
4. Folder 对象先由导入流程驱动生成与维护。

这是可落地且低风险的第一步。

### 5.2 策略二：目录导入优先扩展现有上传接口，不新造过重协议
当前已有 `/api/kb/file/import` 和 `KbUpload.jsx`，本轮优先在这条链路上扩展：
- 新增 `relative_paths[]`；
- 新增 `import_mode=preserve_tree|flatten`；
- 保持旧客户端不传时仍能按平铺文件工作。

即：
- **向后兼容旧入口**；
- **向前支持目录导入**；
- 不额外引入复杂任务协议。

### 5.3 策略三：Markdown 资产抽取先做“本地图片引用”这一条最稳路径
本轮只处理：
- `![alt](./x.png)`
- `![alt](../img/a.jpg)`
- `<img src="./diagram.png">`

且只在以下条件成立时登记资产：
1. 资源是本地相对路径；
2. 路径可解析到当前知识库目录内文件；
3. 资源文件类型属于支持的图片集合（png/jpg/jpeg/webp/gif/bmp 等）。

不处理：
- 远程 URL 图片；
- Data URI；
- Markdown 扩展语法中的所有特例。

### 5.4 策略四：资产先做“对象可见 + 可引用”，不强推复杂多模态理解
本轮资产进入系统的最低要求是：
1. 有 `asset_id`；
2. 有 `kb_id`；
3. 知道它从哪个文档/路径来；
4. 可以列出与预览；
5. 回答结果或 evidence 结构可以附带 `asset_id`（新增可选字段）。

本轮不要求：
- 每个图片资产都一定产生高质量 OCR / caption；
- 每个资产都一定能单独召回命中。

### 5.5 策略五：文档 ID 暂允许延迟绑定，避免为 P0 过早重构全文档表
当前系统没有独立的 Document 表，文档主身份仍强依赖 docstore/ref_doc。

因此本轮允许：
1. Folder 与 Asset 先用 `source_path / relative_path` 建立稳定锚点；
2. `source_doc_id` 可在导入当下为空，后续通过 path → ref_doc 关系补齐；
3. 对外接口层优先保证 `kb_id + path + locator` 可追溯；
4. 后续如果补建正式 Document 表，再把 `source_doc_id` 固化。

这个决策是为了在不推翻当前索引架构的前提下，把 Folder / Asset 先跑通。

---

## 6. 方案设计

## 6.1 Folder 最小模型

### 6.1.1 设计目标
在不引入完整数据库表的前提下，让知识库内的目录树具有稳定对象语义。

### 6.1.2 建议存储
新增按 KB 拆分的 folder registry：
- `storage/kb_folders/<kb_id>.json`

原因：
1. 与 `storage/kb_assets/<kb_id>.json` 的资产边界表达一致；
2. 比单一全局 `storage/folder_registry.json` 更符合知识库组织模型；
3. 未来从逻辑对象演进到命名空间隔离时更容易迁移。

### 6.1.3 Folder 最小字段
- `folder_id`
- `kb_id`
- `parent_folder_id`
- `name`
- `path`（知识库内相对路径，如 `design/specs`）
- `depth`
- `source_root`（可选，记录本次目录导入根）
- `status`：`active / orphaned`
- `created_at`
- `updated_at`

### 6.1.4 实现简化原则
本轮不要求 folder registry 成为“唯一事实源”，而是：
- 由导入路径自动同步；
- 可由文档列表反向校验；
- 主要服务于展示、路径归类和后续扩展。

---

## 6.2 Document 与 Folder 的绑定方式

### 6.2.1 当前阶段建议新增的文档语义字段
在 `list_docs()` 输出及节点 metadata 中补：
- `relative_path`
- `folder_path`
- `source_root`（可选）

### 6.2.2 为什么先加 path 语义而不是先建完整 Document 表
因为当前系统里最稳定的现成锚点就是：
- `kb_id`
- `file_path`
- `file_name`

本轮先把“目录语义”附着到这组锚点上，后续再演进到正式 Document 模型，实施风险更低。

---

## 6.3 目录导入协议设计

### 6.3.1 接口策略
优先扩展既有接口：
- `POST /api/kb/file/import`

新增表单字段：
- `relative_paths`: `list[str]`，与 `files` 一一对应；
- `import_mode`: `preserve_tree | flatten`，默认 `preserve_tree`。

### 6.3.2 向后兼容规则
- 老客户端不传 `relative_paths`：按当前平铺导入逻辑工作；
- 新客户端传 `relative_paths` 且 `import_mode=preserve_tree`：后端按相对路径落盘并生成 Folder；
- 若显式传 `flatten`：路径只保留在回执或 metadata 中，不创建 Folder 层级。

### 6.3.3 前端实现方式
`webapp/src/components/kb/KbUpload.jsx` 增加两种模式：
1. 文件模式（现有行为）；
2. 目录模式（使用 `<input type="file" webkitdirectory>`）。

目录模式中：
- 用浏览器提供的 `webkitRelativePath` 收集相对路径；
- 传给 `importFiles(formData, kbId)`；
- 同步展示“保留目录树导入”的提示。

### 6.3.4 后端落盘规则
如果 `relative_path=design/specs/a.md`：
1. 目标落盘为 `data/<kb_id>/design/specs/a.md`；
2. 自动确保父目录存在；
3. 在文档 metadata / 回执里写入：
   - `relative_path=design/specs/a.md`
   - `folder_path=design/specs`

### 6.3.5 安全要求
必须保证：
- `relative_path` 经过规范化处理；
- 禁止 `..` 越出 `data/<kb_id>/`；
- 禁止绝对路径直接复用；
- 任何异常路径都回退为失败项，不允许静默写出知识库根目录之外。

---

## 6.4 Markdown 资源解析设计

### 6.4.1 本轮只支持的资源类型
- Markdown image 语法：`![alt](path)`
- HTML img 标签：`<img src="path">`

### 6.4.2 解析时机
建议在文件成功落盘后、索引完成后，按单文件执行：
1. 若文件不是 Markdown，跳过；
2. 若是 Markdown，读取文本内容；
3. 解析资源引用；
4. 解析为本地绝对路径；
5. 若文件存在且在 KB 目录内，则登记为 Asset；
6. 将资源关系写入资产注册表。

### 6.4.3 为什么放在索引后而不是索引前
因为当前导入链路已经围绕“逐文件写入 → 索引 → receipt”稳定下来；
本轮如果在索引前插入过多逻辑，容易重新放大导入不稳定性。

### 6.4.4 本轮解析限制
本轮只处理：
- 相对当前 Markdown 文档的本地路径；
- 最终能定位到当前 KB 目录内图片文件的情况。

解析失败的资源：
- 不阻断整篇 Markdown 文档导入；
- 但要体现在资源解析结果或警告字段中。

---

## 6.5 Asset 最小模型

### 6.5.1 建议存储
沿用原 plan 中已确认方向：
- `storage/kb_assets/<kb_id>.json`

### 6.5.2 本轮资产来源
本轮只覆盖两类：
1. 独立图片文件导入；
2. Markdown 内嵌本地图片解析得到的资源。

### 6.5.3 Asset 最小字段
- `asset_id`
- `kb_id`
- `source_doc_id`（可为空）
- `source_doc_path`
- `asset_type`：`image | diagram`
- `asset_role`：`standalone | embedded`
- `title`
- `path`
- `relative_path`
- `mime_type`
- `locator`（Markdown 中可记录原始资源位置、索引序号、alt 文本）
- `status`：`active | missing | orphaned`
- `created_at`
- `updated_at`

### 6.5.4 关键设计判断
本轮资产对象的核心不是“图像理解得多强”，而是：
- 先有对象；
- 先可追溯；
- 先能引用；
- 先不丢关系。

---

## 6.6 资产与 Evidence 的关系

### 6.6.1 本轮契约调整建议
`evidence` 结构新增可选字段：
- `asset_id: str | None`

要求：
- 不破坏现有 evidence 契约；
- 旧前端 / 旧测试不依赖时仍能工作；
- 新前端若拿到 `asset_id`，可优先拉资产预览或展示资产标签。

### 6.6.2 为什么本轮只加可选字段
因为当前主检索单元仍是 Chunk，而不是 Asset 原生召回。
所以本轮先保证“命中某文档中的图片资产时，结果能带上 asset_id 作为补充追溯信息”，而不是强推“资产一定单独召回”。

---

## 7. 任务拆解

## 7.1 Task B1：Folder Registry 最小落地

### 目标
建立按 KB 归档的 Folder 最小注册表，并能根据文档相对路径生成 / 刷新目录节点。

### 主要改动文件
**后端新增文件（建议）**
- `server/folder_registry.py`
- `api/services/folder_service.py`

**后端现有文件**
- `api/services/kb_service.py`
- `api/routers/kb.py`

**测试文件（新增）**
- `tests/api/test_folder_registry.py`
- `tests/api/test_kb_folder_listing.py`

### 任务内容
1. 设计 `storage/kb_folders/<kb_id>.json` 的读写封装；
2. 提供“根据 `relative_path` 自动创建所需 folder 链”的能力；
3. 提供按 KB 列出 folder tree / folder list 的服务；
4. `list_docs()` 结果补 `folder_path` / `relative_path` 字段；
5. 新增最小 `GET /api/kb/folders?kb_id=...` 接口（建议）。

### TDD 顺序
1. 先写 registry 测试；
2. 再写 folder list 接口测试；
3. 再把 `kb_service` / router 接起来。

### DoD
1. 能按 KB 生成独立 folder registry 文件；
2. 文档能带出 `folder_path`；
3. 能按 KB 列出 folder 列表或树；
4. 不会跨 KB 混 folder 数据。

---

## 7.2 Task B2：目录导入 preserving tree

### 目标
让目录导入不再把文件拍平，而是保留源目录树结构与相对路径。

### 主要改动文件
**后端现有文件**
- `api/routers/kb.py`
- `api/services/kb_service.py`
- `server/index.py`

**前端现有文件**
- `webapp/src/components/kb/KbUpload.jsx`
- `webapp/src/api/kb.js`
- `webapp/src/pages/KnowledgePage.jsx`

**测试文件**
- `tests/api/test_kb_directory_storage.py`（扩展）
- `tests/api/test_kb_directory_import_tree.py`（新增）
- `webapp/src/api/kb.test.js`（新增或扩展）

### 任务内容
1. router 支持接收 `relative_paths` 与 `import_mode`；
2. service 按 `relative_path` 安全落盘；
3. 对每个文件写入 `relative_path` / `folder_path`；
4. 自动刷新 folder registry；
5. 前端新增“目录导入”入口与导入提示；
6. 导入回执中回显每项的 `relative_path` / `folder_path`。

### TDD 顺序
1. 先写后端目录落盘测试；
2. 再写 API 参数映射测试；
3. 最后补前端上传参数测试与页面提示。

### DoD
1. 目录导入能保留相对路径；
2. 同名文件在不同子目录下不会冲突；
3. 文档列表可按 `folder_path` 感知层级；
4. 旧文件上传模式不被破坏。

---

## 7.3 Task B3：Markdown 内嵌图片解析

### 目标
让 Markdown 内嵌本地图片从“普通文本里的路径字符串”升级为“可登记的资产引用关系”。

### 主要改动文件
**后端新增文件（建议）**
- `server/markdown_asset_extractor.py`
- `api/services/asset_service.py`

**后端现有文件**
- `api/services/kb_service.py`
- `api/routers/kb.py`

**测试文件（新增）**
- `tests/api/test_markdown_asset_extraction.py`

### 任务内容
1. 解析 Markdown image / HTML img 语法；
2. 按 Markdown 文件所在目录解析相对路径；
3. 校验目标资源在 KB 目录内；
4. 生成 embedded asset 记录；
5. 对缺失资源记录 warning / missing 状态，不阻断文档导入。

### TDD 顺序
1. 先写 Markdown 提取器纯单元测试；
2. 再写导入后资产登记集成测试；
3. 最后接入导入链路。

### DoD
1. Markdown 中的本地图片能被识别；
2. 能解析 `./` / `../` 相对路径；
3. 成功解析到的图片可登记为 embedded asset；
4. 解析失败不导致整篇 Markdown 导入失败。

---

## 7.4 Task B4：Asset Registry 与最小预览

### 目标
把独立图片与 Markdown embedded asset 统一纳入资产注册表，并可列出 / 预览。

### 主要改动文件
**后端新增文件（建议）**
- `server/asset_registry.py`
- `api/schemas/asset.py`
- `api/services/asset_service.py`

**后端现有文件**
- `api/routers/kb.py`
- `api/services/kb_service.py`

**前端新增文件（建议）**
- `webapp/src/api/assets.js`
- `webapp/src/components/kb/KbAssetList.jsx`

**前端现有文件**
- `webapp/src/pages/KnowledgePage.jsx`

**测试文件**
- `tests/api/test_asset_registry.py`
- `tests/api/test_image_asset_import.py`

### 任务内容
1. 建立资产注册表存取；
2. 独立图片导入时登记为 `standalone asset`；
3. Markdown 内嵌图片登记为 `embedded asset`；
4. 新增资产列表接口；
5. 新增最小资产预览接口，返回基础信息：
   - `asset_id`
   - `title`
   - `path`
   - `mime_type`
   - `source_doc_path/source_doc_id`
   - `locator`

### TDD 顺序
1. 先写 registry；
2. 再写独立图片导入；
3. 再写资产预览；
4. 最后补前端资产 tab。

### DoD
1. 独立图片导入后可在资产列表中出现；
2. Markdown 解析出的 embedded asset 也可列出；
3. 资产至少能返回基础预览数据；
4. 资产按 KB 分文件存储，不跨库泄露。

---

## 7.5 Task B5：Evidence 补充 asset_id 与前端展示

### 目标
让资产对象能进入回答结果的追溯链路，而不是永远躲在文档后面。

### 主要改动文件
**后端现有文件**
- `api/services/chat_service.py`
- `api/services/evidence_service.py`
- `api/schemas/__init__.py`

**前端现有文件**
- `webapp/src/api/chat.js`
- `webapp/src/pages/AgentPage.jsx`
- `webapp/src/components/kb/KbEvidencePreview.jsx`

**测试文件**
- `tests/api/test_chat_evidence_contract.py`（扩展）
- `webapp/src/api/chat.test.js`（扩展）

### 任务内容
1. Evidence schema 新增可选 `asset_id`；
2. 若当前命中的 Chunk / 文档与某个资产存在明确关系，则尝试补充 `asset_id`；
3. 前端 evidence 展示中可显示“来自资产 / 图片 / 流程图”的标记；
4. 不破坏既有 `doc_id + preview_locator` 主路径。

### TDD 顺序
1. 先补 schema / mapping 测试；
2. 再补前端兼容测试；
3. 最后接入 UI 展示。

### DoD
1. Evidence 契约向后兼容；
2. 可选返回 `asset_id`；
3. 前端不会因没有 `asset_id` 而报错；
4. 有 `asset_id` 时能显示补充信息。

---

## 8. 建议的开发顺序

### 8.1 推荐执行顺序
1. **B1 Folder Registry 最小落地**
2. **B2 目录导入 preserving tree**
3. **B3 Markdown 内嵌图片解析**
4. **B4 Asset Registry 与最小预览**
5. **B5 Evidence 补充 asset_id**

### 8.2 为什么不能先做 B4 再做 B2
如果目录导入还没有 `relative_path / folder_path`，Markdown 资源解析会非常脆，因为：
- 相对路径基准不稳定；
- 同名资源容易冲突；
- Embedded asset 无法稳定落回原层级。

因此必须先把目录语义立起来。

---

## 9. 测试设计要求

## 9.1 本轮新增测试建议
### 后端
- `tests/api/test_folder_registry.py`
- `tests/api/test_kb_folder_listing.py`
- `tests/api/test_kb_directory_import_tree.py`
- `tests/api/test_markdown_asset_extraction.py`
- `tests/api/test_asset_registry.py`
- `tests/api/test_image_asset_import.py`

### 前端
- `webapp/src/api/kb.test.js`
- `webapp/src/api/chat.test.js`（扩展）

## 9.2 必测场景
1. 目录导入后保留相对路径；
2. 不同子目录下同名文件不冲突；
3. Markdown 中 `./` / `../` 图片路径能解析；
4. 越界路径被拒绝；
5. 缺失图片只记 warning，不拖垮导入；
6. 资产按 KB 隔离存储；
7. Evidence 兼容无 `asset_id` 和有 `asset_id` 两种情形。

---

## 10. 验证命令

### 10.1 后端验证
```powershell
python -m pytest \
  tests/api/test_folder_registry.py \
  tests/api/test_kb_folder_listing.py \
  tests/api/test_kb_directory_storage.py \
  tests/api/test_kb_directory_import_tree.py \
  tests/api/test_markdown_asset_extraction.py \
  tests/api/test_asset_registry.py \
  tests/api/test_image_asset_import.py \
  tests/api/test_chat_evidence_contract.py -q
```

### 10.2 前端验证
```powershell
node --test webapp/src/api/kb.test.js webapp/src/api/chat.test.js
npm --prefix webapp run build
```

### 10.3 结合现有主链路的回归验证
```powershell
python -m pytest \
  tests/api/test_chat_scope_contract.py \
  tests/api/test_kb_preview_route.py \
  tests/api/test_m2_multi_kb.py \
  tests/api/test_index_manager_coverage.py \
  tests/api/test_kb_directory_storage.py -q
```

---

## 11. 预期结果

本轮做完后，系统应从：
- 只有平铺文件；
- 不理解目录结构；
- 看不见 Markdown 资源关系；
- 图片只是文件路径；

升级为：
- 知识库内部有最小 Folder 组织语义；
- 目录导入能保留树结构；
- Markdown 本地图片能登记为 embedded asset；
- 独立图片与 embedded asset 都能进入资产列表；
- Evidence 可以补充 asset 追溯信息；
- 后续 Agent / UI / 检索增强有稳定对象锚点可接。

---

## 12. 风险与待确认点

### 12.1 文档 ID 延迟绑定风险
本轮允许 `source_doc_id` 延迟补齐，这降低了实现复杂度，但也意味着：
- 部分资产在早期阶段更依赖 `source_doc_path` 而不是 `source_doc_id`。

这是可接受的阶段性折中，但 FRD 后续实现时必须保持一致口径。

### 12.2 Markdown 资源解析范围必须收窄
若一开始就试图支持全部 Markdown 方言与所有资源类型，复杂度会迅速失控。必须坚持“只做本地相对图片资源”这条最稳路径。

### 12.3 Folder 先做导入驱动，而不是人工维护
这会让第一版可用，但也意味着：
- 手工整理 folder tree 的能力暂时不足；
- 未来若要补手工操作，需以本轮 folder registry 为基础扩展，而不是推翻。

---

## 13. 结论
本轮不是“给知识库加个文件夹按钮”这么简单，而是在把这个项目真正从“平铺文件问答”推进成“有组织层、有资源关系、有资产对象”的知识底座。

对于你最关心的层级问题，这份实施方案的答案很明确：
1. **知识库内部应该有文件夹；**
2. **文件夹先作为导入驱动的组织对象落地；**
3. **目录导入必须保留树结构；**
4. **Markdown 的本地图片必须尽快纳入最小资产闭环；**
5. **Asset 要先成为对象，再逐步增强理解能力。**

建议下一步按本方案继续：
- 先补测试；
- 再做 Folder / 目录导入；
- 再做 Markdown 资源解析；
- 最后把资产挂入 evidence 与前端展示。
