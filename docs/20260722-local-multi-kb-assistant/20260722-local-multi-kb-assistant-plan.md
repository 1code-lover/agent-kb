# 本地多知识库知识助手平台 v0.2 实施方案（Stage 2，修订版）

## 1. 文档目的
本文档是 `20260722-local-multi-kb-assistant` 需求的 Stage 2 实施方案，用于把已确认的 PRD / FRD / RTM 落到可执行开发计划。

本文档只回答四类问题：
1. P0 先做什么；
2. 每个任务改哪些文件；
3. 先写哪些测试、再写哪些实现；
4. 用什么命令验证、什么结果算通过。

> 说明：本阶段**不开始编码**，也**不物理删除旧方案文档/旧入口**；先把实现边界、任务顺序、测试口径和遗留处理策略写清楚。

## 2. 输入基线
本实施方案以下列文档为唯一正式输入基线：
- `20260722-local-multi-kb-assistant-prd.md`
- `20260722-local-multi-kb-assistant-frd.md`
- `20260722-local-multi-kb-assistant-rtm.md`
- 根目录 `评审建议.txt`（本次修订必须逐项落实）

## 3. 当前代码现实（作为实施约束，不作为宣传口径）

### 3.1 已核实现状
1. 当前“多知识库”本质仍是**共享单一索引 + metadata["kb_id"] 过滤**：
   - 全局共享：`storage/docstore.json`、`storage/index_store.json`、`storage/default__vector_store.json`、`storage/image__vector_store.json`
   - 检索边界依赖：`server/kb_filter.py` 与 `server/retriever.py`
2. 当前主线前端已经明显偏向：
   - Electron + FastAPI + React/Vite
   - `webapp/src/pages/KnowledgePage.jsx` + `webapp/src/components/kb/*` 是更接近未来主线的信息架构
3. Agent 运行时当前是**自研 plan-executor + tool registry**，并非 MCP-first。
4. 根目录仍存在 Streamlit 旧入口（`app.py`、`frontend/*.py`），但不应再承接新主能力。
5. 当前仓库已有**与本需求无关**的在途改动，后续编码时必须避免误覆盖：
   - `server/index.py`
   - `tests/api/test_index_manager_coverage.py`
   - `docs/archive/20260722-codebase-scan/`

### 3.2 本阶段必须坚持的诚实边界
1. P0 只能交付“**契约优先、范围显式、结果回显、默认拒绝**”的范围控制能力。
2. P0 **不能**把现状包装成“强隔离的多知识库服务”。
3. P0 **不做**物理隔离；物理隔离保留到后续架构升级阶段。
4. P0 **不开放**任意第三方 Agent 的广域知识访问能力；只做未来接口契约与内部调用约束的准备。

## 4. 本阶段目标与非目标

### 4.1 P0 目标（本阶段要落的最小闭环）
围绕以下六项形成可实施、可验证、可演进的底座：
1. 知识库对象成立；
2. 本地导入 / 解析闭环成立；
3. 资产对象最小闭环成立；
4. 单库问答闭环成立；
5. 证据输出与预览入口成立；
6. 范围控制契约成立。

### 4.2 本阶段明确不做
1. 物理隔离 / 独立命名空间；
2. 跨库比较 / 跨库综合回答主能力；
3. 多用户组织权限系统；
4. 对外标准协议层（MCP/OpenAPI 风格平台化开放）的完整落地；
5. PDF 图像区域级结构化抽取与流程图理解的深度能力；
6. Streamlit 旧入口上的新功能继续建设。

## 5. 实施总策略

### 5.1 策略一：Contract First，不先追求底层“大重构”
P0 先把“请求范围怎么声明、服务端怎么校验、结果怎么回显、UI 怎么显式展示”做实；
不在本阶段直接把共享索引重写成物理隔离架构。

### 5.2 策略二：Scope Core 先行，再分别接 Chat / Agent
范围控制必须先抽成**共享核心层**，而不是让 chat 和 agent 各写一套：
- 核心层：scope model / normalize / validate / effective scope echo
- 接入层：chat 接共享核心；agent 也接共享核心

**实施结论：**
- `api/services/query_scope.py` 目前不存在，P0 需要**新建**为共享核心文件，而不是“升级既有文件”；
- P0-1 负责“共享核心 + chat 接入”；
- P0-5 只负责“agent 接入共享核心 + receipt/evidence 回显”。

### 5.3 策略三：Evidence First，不把回答做成黑箱
问答结果必须输出统一证据结构；前端主线必须能看到证据、范围、来源和预览入口。

### 5.4 策略四：Asset First，但必须收窄到可交付 P0
P0 的“资产一等对象”只做**最小可验证闭环**，并明确拆层：
- **P0 必做：**独立图片文件导入后登记为 asset object；可列出、可预览基础信息、可被证据引用
- **P0 可选：**Markdown 内嵌图片抽取
- **P1 再做：**Markdown 图片抽取稳定化、PDF 图像区域抽取、流程图语义增强

### 5.5 策略五：主线前端收敛，不继续分叉叙事
所有新主能力优先落在：
- `webapp/src/pages/KnowledgePage.jsx`
- `webapp/src/pages/AgentPage.jsx`
- `webapp/src/components/kb/*`

旧页面与旧入口仅做兼容、转发或保守保留，不再作为主线承载。

### 5.6 策略六：兼容策略显式化
P0 采用“**新 contract 正式化，旧字段兼容保留**”策略：
1. `kb_ids` 在 P0 阶段仅作为**旧入参字段兼容**保留；**不再保留**“不传 / 传空 = 查全库”的旧行为；
2. 主线前端 contract 应向“single scope object / single selected KB”收敛；
3. `sources` 在 P0 保留兼容；`evidence` 作为正式主字段；
4. `receipt_id` 在 evidence contract 中保留：直接 chat 可为空，agent / tool 回执场景需显式填写；
5. 任何 legacy 行为都不能压过“未声明范围 = 默认拒绝”的新主线 contract。

### 5.7 策略七：遗留入口执行纪律
从本阶段开始，新增主能力必须遵守以下规则：
1. **禁止**新增主能力只落在 Streamlit 旧入口；
2. **禁止**新增主能力只落在 `KbManagePage` / `KbFilePage` / `KbWebPage`；
3. 新能力必须优先落在 React/Electron/FastAPI 主线；
4. 旧入口只允许：兼容展示、跳转、保守维护、缺陷修复，不承接新的产品主叙事。

## 6. 关键契约冻结（编码前必须定死）

### 6.1 范围控制核心契约
P0 范围控制采用共享核心模型，最小字段建议如下：
- `requested_scope_type`：`unspecified` / `single_kb` / `multi_kb`
- `requested_kb_ids`
- `effective_scope_type`
- `effective_kb_ids`
- `is_default_deny_applied`
- `isolation_level`：固定回显 `logical_filter_only`

**P0 冻结规则：**
1. P0 主线只接受 `single_kb`；
2. `unspecified`（未声明或空数组）与 `multi_kb` 都必须显式拒绝；
3. 这是有意为之的收紧：旧的“`kb_ids` 不传 = 放行到全量检索”行为不再保留。

### 6.2 证据预览最小契约（P0 冻结）
为避免前后端各做各的，P0 先冻结 preview contract：

**接口路径**
- `POST /api/kb/preview`

**最小入参**
- `kb_id`
- `doc_id` 或 `evidence_id`（至少一项）

**标识规则（P0 冻结）**
1. `evidence_id` 在 P0 直接复用 `EvidenceItem.id`；
2. P0 不新引入第二套独立 evidence 持久化标识体系；
3. 若实现上无法稳定仅靠 `evidence_id` 解析预览，前端主线应优先走 `doc_id + preview_locator`。

**最小出参**
- `title`
- `kb_id`
- `doc_id`
- `excerpt`
- `locator`
- `preview_type`

**P0 约束**
1. 前端**不得**绕过 API 直接把裸 `file_path` 当成预览协议；
2. `preview_locator` 在 P0 至少要能表达：
   - 文档级定位（doc_id）
   - 页级定位（若有 page）
   - 片段级定位（excerpt 起点或等价字段，可简化）
3. P0 允许先做“文本摘录预览”，不要求富文档预览器。

### 6.3 资产注册表暂定持久化方案
为避免后续编码时对象落盘位置摇摆，P0 暂定采用：
- `storage/kb_assets/<kb_id>.json`

原因：
1. 比单一 `storage/assets_registry.json` 更贴近知识库边界；
2. 有利于未来向更强隔离演进；
3. 不要求现在就完成物理隔离，但能先把对象归档口径统一。

## 7. 实施里程碑与任务拆解

---

## 7.1 Task P0-1：范围控制共享核心 + Chat 接入

### 目标
把“单库问答”从“前端传一个 `kb_ids` 约定”升级成“**服务端可验证、可拒绝、可回显**”的正式契约，并明确沉淀为共享 scope 核心。

### 任务内容
1. **新建** `api/services/query_scope.py` 作为共享核心：
   - normalize
   - validate
   - effective scope echo
   - default deny policy
2. 保留现有 `QueryRequest.kb_ids` 作为 legacy 入参字段兼容，但**不保留旧行为兼容**：
   - `None`
   - `[]`
   - 缺失 scope 声明
   以上情况都不再代表“查全部”，而是显式拒绝；这是本次 P0 有意引入的 breaking change。
3. 在 chat 侧明确区分三种情况：
   - 未声明范围：拒绝并要求显式声明单库范围
   - 声明单库：single_kb mode
   - 声明多库：P0 主线默认拒绝或不暴露给主线 UI
4. 同步收紧 chat/runtime 入口与 scope 归一化路径，确保 chat 请求在触达 `server/retriever.py` 前已完成 default-deny；
5. `server/kb_filter.py` / `KBIdFilter` 在 P0 暂保留“空 `kb_ids` = 不过滤”的通用过滤器语义，不把 chat 的默认拒绝策略直接下沉到底层过滤器；
6. 响应里新增 scope echo：
   - 请求范围
   - 生效范围
   - 隔离级别（`logical_filter_only`）
7. 对异常输入给出明确错误：
   - knowledge mode 未选 KB
   - 多 KB 请求被主线拒绝
   - KB 不存在 / 非 active

### 主要改动文件
**后端现有文件**
- `api/schemas/__init__.py`
- `api/routers/chat.py`
- `api/services/chat_service.py`
- `api/runtime.py`
- `server/engine.py`
- `server/retriever.py`
- `server/kb_filter.py`

**后端新增文件（建议）**
- `api/services/query_scope.py`

**测试文件**
- `tests/api/test_m2_multi_kb.py`（补充 / 收紧现有断言）
- `tests/api/test_chat_scope_contract.py`（新增）

### TDD 顺序
1. 先写 `tests/api/test_chat_scope_contract.py`：
   - 单库范围请求成功
   - 响应回显 effective scope
   - 未声明范围时返回明确拒绝
   - 多 KB 请求在 P0 主线被拒绝
   - KB 不存在 / inactive 映射为明确错误
2. 复核 `tests/api/test_m2_multi_kb.py` 的旧断言并按职责分层处理：
   - `test_query_without_kb_ids`：**必须收紧**为“拒绝并且 `build_query_engine` 不应被调用”；
   - `test_kb_id_filter_pass_through_empty` / `test_kb_id_filter_pass_through_none`：P0 暂**不作为强制改写对象**，因为 `KBIdFilter` 作为通用过滤器仍可保留空 `kb_ids` 不过滤语义；
   - `test_list_docs_without_kb_id_returns_all`：**不在本次收紧范围内**，这是 KB 管理侧“列全部文档”场景，不属于 chat 问答范围契约。
3. 再写 `query_scope.py` 的纯函数与服务层实现；
4. 最后接到 router / runtime / retriever。

### DoD
1. 单库 scope 请求成功；
2. 未授权/无效 scope 被拒绝；
3. response echo 生效；
4. chat 侧不再绕开共享 scope 核心；
5. 旧的“无 scope = 全量放行”行为在 chat 主线被明确移除，并在文档与测试中同步体现；
6. KB 管理侧 `list_docs()` 无参列全部文档行为不受本次 P0-1 收紧影响。

### 验证命令
```powershell
python -m pytest tests/api/test_chat_scope_contract.py tests/api/test_m2_multi_kb.py -q
```

### 预期结果
1. 单库请求通过；
2. 未声明范围与多库请求不会被主线静默放行；
3. 返回结果能明确告诉前端“本次回答到底在哪个 KB 范围内执行”；
4. 文档和代码表述都不再暗示“已具备强隔离”。

---
## 7.2 Task P0-2：证据结构统一化 + Preview Contract 落地

### 目标
把当前 `sources` 的松散返回，升级成前后端共识的证据对象，并在 P0 冻结最小 preview contract。

### 当前代码切入点
1. `api/services/chat_service.py` 目前已能从 `source_nodes` 生成 `sources`
2. `api/schemas/__init__.py` 已存在 `EvidenceItem`，当前已包含 7 个核心字段与 `kb_id` / `receipt_id`
3. P0 新增字段实际只缺：`doc_id`、`preview_locator`
4. `api/services/agent_tools.py` 已有 `normalize_evidence()`，但与 chat 侧 `_normalize_sources()` 命名不一致
5. `webapp/src/pages/AgentPage.jsx` 已能展示 `sources`

### 任务内容
1. 统一 evidence normalize，不只做“抽公共函数”，还要明确旧字段到新字段的迁移映射：
   - `sources.file -> evidence.title`
   - `sources.file -> evidence.source`
   - `sources.text -> evidence.excerpt`
   - `sources.page -> evidence.page`
   - `sources.score -> evidence.score`
   - `sources.kb_id -> evidence.kb_id`
   - 若 metadata 可得，再补 `doc_id` 与 `preview_locator`
2. 在 `/api/chat/query` 返回中保留 `sources` 兼容字段，同时正式增加 `evidence` 字段；
3. 明确 `receipt_id` 去留：
   - 直接 chat 场景允许为 `null`
   - agent / tool receipt 场景必须回填真实 `receipt_id`
   - 不允许因为 chat 暂时无 receipt 就删掉该字段
4. 证据字段至少包含：
   - `id`
   - `title`
   - `source`
   - `page`
   - `score`
   - `excerpt`
   - `kb_id`
   - `receipt_id`
   - `doc_id`（若可获得）
   - `preview_locator`
5. 增加 `POST /api/kb/preview`：
   - 先支持文本 excerpt 预览
   - 严禁前端把裸 `file_path` 作为预览协议
   - 统一返回结构化 preview object

### 主要改动文件
**后端现有文件**
- `api/schemas/__init__.py`
- `api/services/chat_service.py`
- `api/services/agent_tools.py`
- `api/routers/kb.py`
- `api/services/kb_service.py`

**后端新增文件（建议）**
- `api/services/evidence_service.py`

**前端现有文件**
- `webapp/src/api/chat.js`
- `webapp/src/pages/AgentPage.jsx`

**前端新增文件（建议）**
- `webapp/src/api/evidence.js`
- `webapp/src/components/kb/KbEvidencePreview.jsx`
- `webapp/src/api/chat.test.js`

**测试文件**
- `tests/api/test_chat_evidence_contract.py`（新增）
- `tests/api/test_kb_preview_route.py`（新增）

### TDD 顺序
1. 先写后端 contract test：
   - `evidence` 字段存在
   - 单条 evidence 字段完整
   - `sources` 与 `evidence` 在核心字段上保持映射一致
   - chat 场景 `receipt_id` 可为空
   - agent 场景 `receipt_id` 被正确保留
2. 再写 preview route test；
3. 再改前端展示与预览组件。

### DoD
1. chat 与 agent 使用统一 evidence normalize / mapping 规则；
2. `/api/chat/query` 同时返回 `sources`（兼容）和 `evidence`（正式）；
3. `/api/kb/preview` 返回结构化 preview object；
4. 前端可展示 evidence 列表并打开最小预览；
5. `receipt_id`、`doc_id`、`preview_locator` 的去留在契约中说清楚，不留隐式字段漂移。

### 验证命令
```powershell
python -m pytest tests/api/test_chat_evidence_contract.py tests/api/test_kb_preview_route.py -q
node --test webapp/src/domain/agentExperience.test.js webapp/src/api/chat.test.js
npm --prefix webapp run build
```

### 预期结果
1. 回答结果不再只有松散 `sources`；
2. UI 可稳定展示证据项；
3. chat / agent 对同一证据对象的字段含义保持一致；
4. 后续做文档 / 资产预览时不需要再次推翻返回结构。

---
## 7.3 Task P0-3：资产对象最小闭环（收窄版）

### 目标
把“图片 / 流程图 / 截图 / 扫描页”从“附件或路径字符串”升级成**最小一等对象**，但严格控制 P0 只交付一条最稳闭环。

### P0 范围定义（必须诚实）
**P0 必做：**
1. 作为独立文件导入的图片（png/jpg/jpeg/webp 等）登记为 asset object；
2. 资产可列出；
3. 资产可返回基础预览信息；
4. 资产可被 evidence / 回答结果直接引用。

**P0 可选：**
1. Markdown 内嵌图片抽取。

**P1 再做：**
1. Markdown 图片抽取稳定化；
2. PDF 图像区域抽取；
3. 流程图语义增强；
4. 更复杂的多模态资产理解。

### 任务内容
1. 设计最小资产对象模型：
   - `asset_id`
   - `kb_id`
   - `source_doc_id`
   - `asset_type`
   - `title`
   - `path`
   - `mime_type`
   - `locator`
   - `status`
2. 设计按 KB 归档的资产注册表：`storage/kb_assets/<kb_id>.json`
3. 在导入链路中优先补最小识别：
   - 独立图片文件导入时直接登记为 asset object
   - Markdown 内嵌图片抽取只作为 P0 可选项，不绑死上线门槛
4. 为资产提供：
   - 列表查询
   - 预览基础数据
   - 被证据引用的能力

### 主要改动文件
**后端现有文件**
- `server/index.py`
- `api/services/kb_service.py`
- `api/routers/kb.py`

**后端新增文件（建议）**
- `api/schemas/asset.py`
- `api/services/asset_service.py`
- `server/asset_registry.py`

**前端现有文件**
- `webapp/src/pages/KnowledgePage.jsx`

**前端新增文件（建议）**
- `webapp/src/api/assets.js`
- `webapp/src/components/kb/KbAssetList.jsx`

**测试文件**
- `tests/api/test_asset_registry.py`（新增）
- `tests/api/test_image_asset_import.py`（新增）
- `tests/api/test_markdown_asset_extraction.py`（新增，可选任务对应）

### TDD 顺序
1. 先写资产 registry / schema test；
2. 再写独立图片文件导入登记 test；
3. 再挂入导入链路；
4. 最后做 KnowledgePage 资产 tab；
5. 若还有余量，再补 Markdown 内嵌图片抽取 test 与实现。

### DoD
1. 独立图片文件导入后可登记为 asset object；
2. 资产可在资产列表中独立出现；
3. 资产可返回基础预览信息；
4. 回答结果或 evidence 可引用资产对象；
5. 即使不做 Markdown 图片抽取，P0 也可成立。

### 验证命令
```powershell
python -m pytest tests/api/test_asset_registry.py tests/api/test_image_asset_import.py -q
npm --prefix webapp run build
```

### 预期结果
1. 资产不再只是“文档路径上的附属物”；
2. 至少独立图片文件能被独立列出；
3. 回答结果未来可以直接引用 asset object，而不是只能引用宿主文档。

---

## 7.4 Task P0-4：前端主线收敛到 KnowledgePage / AgentPage

### 目标
把前端主线收敛为“知识库管理页 + 问答工作台”两大入口，避免多套 KB 页面继续分叉。

### 当前判断
更适合作为主线的页面是：
- `webapp/src/pages/KnowledgePage.jsx`
- `webapp/src/pages/AgentPage.jsx`

不应再作为未来主线承载的页面是：
- `webapp/src/pages/KbManagePage.jsx`
- `webapp/src/pages/KbFilePage.jsx`
- `webapp/src/pages/KbWebPage.jsx`

补充现实：
- `webapp/src/App.jsx` 仍保留 `/kb-file`、`/kb-web`、`/kb-manage` 路由；
- `webapp/src/components/ShellLayout.jsx` 已移除这些入口导航；
- 因而三页现状更准确地说是“**孤儿路由**”，而不是仍在主导航中并行存在。

### 已拍板的遗留页面策略
采用**方案 B：保留现有孤儿路由兼容，但停更且不恢复导航入口，不承接新主能力**。

原因：
1. 比立即全量重定向更稳妥；
2. 不会立刻打断已有使用习惯或测试脚本；
3. 符合“先收敛叙事，再统一清理”的节奏。

### 任务内容
1. `KnowledgePage` 新增资产 tab 与预览入口；
2. `AgentPage` 明确展示当前问答范围、证据列表、预览入口；
3. 旧 KB 页面仅做兼容保留，不再新增主能力；
4. 保证“显式选库”成为所有导入 / 删除 / 单库问答动作的共同前置条件。

### 主要改动文件
- `webapp/src/App.jsx`
- `webapp/src/pages/KnowledgePage.jsx`
- `webapp/src/pages/AgentPage.jsx`
- `webapp/src/components/ShellLayout.jsx`
- `webapp/src/components/kb/KbContext.jsx`
- `webapp/src/components/kb/KbSidebar.jsx`
- `webapp/src/components/kb/KbDocumentList.jsx`
- `webapp/src/components/kb/KbUpload.jsx`
- `webapp/src/components/kb/KbWebImport.jsx`
- `webapp/src/domain/agentExperience.js`
- `webapp/src/domain/kbSelection.js`

### 测试文件
- `webapp/src/domain/agentExperience.test.js`
- `webapp/src/domain/kbSelection.test.js`
- `webapp/src/api/kb.test.js`
- `webapp/src/api/chat.test.js`

### TDD 顺序
1. 先补 domain / api 纯函数测试；
2. 再做 UI 收敛；
3. 对旧三页仅保留轻量回归与人工冒烟，不再给予与主线同级的回归优先级；
4. 最后执行 build 与人工冒烟。

### DoD
1. 用户理解上只有一个主“知识库页”；
2. 显式选库规则在导入、问答、证据展示上保持一致；
3. 旧页面仍可访问，但仅以孤儿路由形式兼容保留，不承接新主能力；
4. 新能力全部落在主线页面。

### 验证命令
```powershell
node --test webapp/src/domain/kbSelection.test.js webapp/src/domain/agentExperience.test.js webapp/src/api/kb.test.js webapp/src/api/chat.test.js
npm --prefix webapp run build
```

### 预期结果
1. 用户理解上只有一个主“知识库页”；
2. 显式选库规则在导入、问答、证据展示上保持一致；
3. 旧页面不再制造新的信息架构分叉。

---

## 7.5 Task P0-5：Agent 接入共享范围核心

### 目标
不在 P0 直接开放平台化接口，但先把内部 Agent 调用知识库的范围契约接到共享 scope core 上，为后续 MCP / 标准工具接口共存预留稳定对象层。

### 任务内容
1. Agent 侧复用 `query_scope.py` 共享核心；
2. 默认 deny：未显式声明 scope 时，不应被包装成“受限访问已成立”；
3. tool receipt / evidence 中回显：
   - request scope
   - effective scope
   - kb_id
4. 保持与未来 MCP 共存，而不是预设替换当前 runtime。

### 主要改动文件
- `api/schemas/tool_schemas.py`
- `api/services/agent_tools.py`
- `api/services/agent_runtime.py`
- `api/routers/agent.py`
- `api/schemas/__init__.py`
- `api/services/query_scope.py`

### 测试文件
- `tests/api/test_agent_kb_scope_contract.py`（新增）

### TDD 顺序
1. 先写 contract test；
2. 再统一 tool 层 evidence / scope；
3. 再补 runtime 回执字段。

### DoD
1. Agent 不再自定义第二套 scope contract；
2. Agent receipt / evidence 可回显 request scope 与 effective scope；
3. 共享 scope core 同时服务 chat 与 agent。

### 验证命令
```powershell
python -m pytest tests/api/test_agent_kb_scope_contract.py -q
```

### 预期结果
1. 未来外部接入前，内部 Agent 已经遵守显式范围契约；
2. 后续加 MCP 时，替换的是接口包装层，不是知识对象层和范围控制层。

---

## 7.6 Task P0-6：遗留入口与旧方案归档策略

### 目标
避免“新方案写了一套、旧入口继续长另一套”的叙事摇摆。

### 当前处理原则
1. `docs/20260722-local-multi-kb-assistant/` 下文档是**当前唯一正式基线**；
2. 根目录旧产品文档、旧设计文档**暂不物理删除**；
3. Streamlit 旧入口暂不删除，但不再承接新主能力；
4. React/Electron/FastAPI 是主线。

### 本阶段动作
1. 旧文档：先标记 superseded / archive 候选；
2. 旧页面：先停止新增主能力；
3. 真正删除动作延后到：
   - 新主线稳定；
   - README / 入口引用清理完成；
   - 没有依赖后再删。

### 本阶段不执行的动作
1. 不直接删根目录旧 PRD / FRD / RTM；
2. 不直接删 `frontend/*.py` 与 `app.py`；
3. 不在本轮把所有旧页面一键移除。

### DoD
1. 新文档成为唯一正式基线；
2. 旧入口不再承接新主能力；
3. 团队对“先停更、后归档、再删除”的节奏无歧义。

## 8. 推荐实施顺序（严格按依赖）
1. **P0-1 范围控制共享核心 + Chat 接入**
2. **P0-2 证据结构统一化 + Preview Contract 落地**
3. **P0-3 资产对象最小闭环（收窄版）**
4. **P0-4 前端主线收敛**
5. **P0-5 Agent 接入共享范围核心**
6. **P0-6 遗留入口与旧方案归档策略**

说明：
- P0-1 和 P0-2 是前置，因为前端是否能正确展示范围和证据，取决于后端 contract；
- P0-3 在对象层成立后，P0-4 才能稳定展示资产 tab；
- P0-5 依赖前面 contract 稳定后再接；
- P0-6 是收尾，不抢在主能力前面做清理。

## 9. 阶段性测试计划（实施阶段必须执行）

### 9.1 后端回归最小集
```powershell
python -m pytest \
  tests/api/test_kb_registry.py \
  tests/api/test_kb_routes.py \
  tests/api/test_kb_directory_storage.py \
  tests/api/test_kb_docs_isolation.py \
  tests/api/test_m2_multi_kb.py \
  tests/api/test_retriever_stale_vectors.py \
  tests/api/test_chat_scope_contract.py \
  tests/api/test_chat_evidence_contract.py \
  tests/api/test_kb_preview_route.py \
  tests/api/test_asset_registry.py \
  tests/api/test_image_asset_import.py \
  tests/api/test_agent_kb_scope_contract.py \
  -q
```

### 9.2 前端回归最小集
```powershell
node --test \
  webapp/src/domain/kbSelection.test.js \
  webapp/src/domain/agentExperience.test.js \
  webapp/src/api/kb.test.js \
  webapp/src/api/chat.test.js

npm --prefix webapp run build
```

### 9.3 人工冒烟清单
1. 创建两个 KB；
2. 分别导入不同 md / pdf / 图片；
3. 在 `KnowledgePage` 中显式切换 KB；
4. 验证文档列表 / 资产列表不串库；
5. 在 `AgentPage` 选择“知识库问答”并提问；
6. 验证回答结果中的 scope / evidence / kb_id 回显正确；
7. 验证 preview 接口可打开最小文本预览；
8. 验证旧页面不再承载新能力或已明确停更。

## 10. 风险与控制点

### 10.1 最大真实风险
**共享单索引 + filter 失效 = 跨库泄露风险。**

### 10.2 P0 接受该风险的前提
1. 本地单机；
2. 单用户主导；
3. 不宣传为强隔离服务；
4. 主线默认单库问答；
5. 结果必须回显范围；
6. 未显式授权时默认拒绝。

### 10.3 本阶段不能犯的错
1. 把 P0 的逻辑隔离写成“已支持安全多租户”；
2. 为了赶 UI 进度，继续放任未声明范围放行或 multi-kb 行为混入主线；
3. 把资产对象又做回“附件字段”；
4. 在遗留 Streamlit 上继续补主功能，造成双主线；
5. 在 preview 协议上让前后端各写一套；
6. 误修改本需求之外的在途文件。

## 11. 对“原来那套是不是可以删掉或者覆盖掉”的明确结论

### 11.1 可以覆盖的
1. **当前需求目录下的同名正式文档**可以继续覆盖迭代；
2. Stage 2 的正式实施方案应继续写在本目录下，而不是另起一套 `-v2`、`-final`、`-new`。

### 11.2 现在不建议直接删除的
1. 根目录历史产品文档；
2. Streamlit 旧入口；
3. 老的 KB 页面实现。

### 11.3 推荐动作
1. **新文档作为唯一正式基线继续演进**；
2. **旧文档先标记 superseded / archive 候选**；
3. **旧代码先停更，不立即物理删除**；
4. 等 Stage 3/4 稳定后，再统一做归档或删除清理。

## 12. 进入编码前的准入门槛
只有以下条件同时满足，才进入 Stage 3 编码：
1. 本实施方案审核通过；
2. 明确 P0 接受“contract-first but logical-only”风险前提；
3. 确认 Task P0-1 ~ P0-6 的顺序不再调整；
4. 确认 preview contract 冻结；
5. 确认旧页面策略采用“保留现有孤儿路由兼容，但停更且不恢复导航入口”；
6. 测试文件命名与新增 API 路径命名通过审核。

---

## 13. 下一步建议
截至 2026-07-28，本需求的 `test-plan` 已形成，且基于当前代码完成了一轮真实运行核实：Markdown 导入可用、图片资产/OCR 链路已有雏形但受 `paddleocr` 阻断、PDF 导入受 `fitz` 阻断。

因此，下一步建议不再停留在“继续写文档”，而是转入下面这条主线：
1. **同步修复基础可用性问题**：导入回执中文 copy、依赖可见性、失败原因稳定输出；
2. **拉通基础链路**：围绕单库场景验证“文档导入 → 索引 → 检索 → 问答 → 证据预览”；
3. **尽快构造问答测试集**：优先用稳定 Markdown 文档建设单库问答评测样本，再逐步接入 PDF / 图片（OCR）；
4. **在测试报告里显式回答准确性问题**：不是只报接口通过数，而是报 scope 正确、证据正确、关键事实覆盖是否达标。

换句话说，接下来最重要的不是继续扩展功能点，而是先把“导入和问答到底好不好用、准不准确”做成可验证事实。

## 14. 2026-07-28 progress sync: single-kb QA smoke baseline

### 14.1 What is completed
1. Import usability improvements already landed:
   - `api/services/kb_service.py` now returns readable `display_summary` copy;
   - `api/routers/health.py` now exposes `import_capabilities` for `fitz / paddleocr / paddlepaddle / Pillow`.
2. Structured QA smoke cases have been added at `tests/fixtures/rag_quality/single_kb_smoke_cases.json`.
3. Executable regression coverage has been added at `tests/api/test_chat_single_kb_qa_smoke.py`.

### 14.2 What this smoke baseline validates
1. Scope echo correctness for `requested_*`, `effective_*`, and `is_default_deny_applied`.
2. Answer coverage against `expected_keypoints`.
3. Negative guardrails via `must_not_contain`.
4. Evidence hit checks against `expected_evidence`.

### 14.3 Current boundary
1. This is a deterministic baseline built with a mocked query engine.
2. It proves that the dataset structure, scope assertions, answer assertions, and evidence assertions are executable.
3. It is not yet the final answer-quality conclusion for real model runs.

### 14.4 Next track
1. Move from mocked QA to a more realistic Markdown import -> index -> query smoke flow.
2. Record per-case evidence hit and keypoint coverage in the test report.
3. Extend the same baseline to PDF and image OCR after dependency readiness is stable.

## 15. 2026-07-28 progress sync: expanded QA baseline

### 15.1 What is newly landed
1. The QA baseline is no longer Markdown-only; it now includes four executable QA suites:
   - `tests/api/test_chat_single_kb_qa_smoke.py`
   - `tests/api/test_chat_markdown_qa_semireal.py`
   - `tests/api/test_chat_pdf_semireal.py`
   - `tests/api/test_chat_image_ocr_semireal.py`
2. A shared metric helper now exists at `tests/api/chat_qa_metrics.py`.
3. Reader-layer diagnostics remain covered by:
   - `tests/readers/test_image_ocr.py`
   - `tests/readers/test_pdf_ocr.py`
4. The execution-source document is `20260722-local-multi-kb-assistant-test-report.md`.

### 15.2 What this expanded baseline now validates
1. `Markdown / PDF text-layer / image OCR import -> KB storage -> single-kb query -> evidence -> preview` is executable.
2. Chat query still enforces single-kb scope echo and default-deny assumptions from the contract tests.
3. Returned `sources/evidence` carry usable `doc_id` and `preview_locator`.
4. QA is now metricized instead of reporting only a green test count.
5. Reader-layer parser behavior has an explicit regression floor before we move further into richer ingestion work.

### 15.3 Current command and result
Executed command:
`python -m pytest tests/api/test_chat_qa_metrics.py tests/api/test_chat_markdown_qa_semireal.py tests/api/test_chat_single_kb_qa_smoke.py tests/api/test_chat_pdf_semireal.py tests/api/test_chat_image_ocr_semireal.py tests/api/test_chat_scope_contract.py tests/api/test_chat_evidence_contract.py tests/api/test_health_route.py tests/api/test_image_asset_import.py tests/api/test_kb_directory_storage.py tests/test_rag_quality_fixtures.py tests/readers/test_image_ocr.py tests/readers/test_pdf_ocr.py -q`

Current verified result: **124 passed, 1 skipped, 2 warnings**.

### 15.4 Metricized QA scope
1. The QA layer now reports `pass_rate`, `scope_pass_rate`, `average_keypoint_coverage`, `evidence_hit_rate`, `preview_resolvable_rate`, `source_count_match_rate`, and `forbidden-term clean rate`.
2. The current QA case pool contains 23 cases across smoke, Markdown semi-real, PDF semi-real, and image OCR semi-real.
3. This means the testing story no longer stops at "did it run"; it now measures whether imported knowledge is answerable, evidence-backed, previewable, and refusal-safe.

### 15.5 Coverage snapshot note
1. A targeted coverage snapshot is now part of the QA baseline execution, using `--cov=api/services --cov=api/routers --cov=server/readers`.
2. The aggregate snapshot is currently **62%**, but that number is not yet a standalone gate because those directories still contain unrelated modules.
3. The execution-source report records core-file coverage for `query_scope.py`, `chat_service.py`, `kb_service.py`, `asset_service.py`, `evidence_service.py`, `health.py`, `image_ocr.py`, and `pdf_ocr.py`.

### 15.6 Boundary note
1. This is still a deterministic semi-real baseline, not a final real-model benchmark.
2. The baseline proves the base chain is runnable, measurable, and reviewable.
3. It does not yet prove final retrieval quality, final answer quality under real LLM orchestration, or storage-level KB isolation.
