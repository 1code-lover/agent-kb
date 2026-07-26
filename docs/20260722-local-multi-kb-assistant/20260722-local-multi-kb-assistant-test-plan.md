# 本地多知识库知识助手平台 v0.1 测试方案（Stage 2 配套）

## 1. 文档信息
- 文档版本：v0.1
- 文档状态：基于实施方案 `20260722-local-multi-kb-assistant-plan.md`（修订版）首版测试方案
- 创建日期：2026-07-23
- 对应实施方案：`20260722-local-multi-kb-assistant-plan.md`
- 对应目录：`docs/20260722-local-multi-kb-assistant/`
- 当前阶段：Stage 2 配套测试方案，**不包含测试执行结果**（执行结果另出测试报告）

## 2. 文档目的
本文档只回答三类问题：
1. 每个 Task 的 DoD 要用哪些具体测试用例验证；
2. 每个用例的前置条件、输入、期望结果分别是什么；
3. 涉及“收紧旧断言”的用例，旧断言现在到底是什么、要改成什么。

本文档不重复 plan.md 已经写清楚的任务目标、改动文件、实施策略，只做 DoD → 测试用例的展开。

## 3. 测试基线核实（写用例前的现状核对）
在展开用例前，先核实一批 plan.md 中引用到的现有代码/测试的真实内容，避免测试用例建立在猜测之上。

### 3.1 现有断言现状（P0-1 收紧对象）
`tests/api/test_m2_multi_kb.py` 中以下 4 个用例的**当前实现**：

1. `test_kb_id_filter_pass_through_empty`（第83-89行）：`KBIdFilter(kb_ids=[])`，断言 `postprocess_nodes` 返回长度为1（不过滤）。
2. `test_kb_id_filter_pass_through_none`（第91-97行）：`KBIdFilter(kb_ids=None)`，断言同上。
3. `test_query_without_kb_ids`（第342-356行）：mock `build_query_engine`，`QueryRequest(question="test")` 不传 `kb_ids`，断言 `mock_build.assert_called_once_with(kb_ids=None)`——**只断言调用参数，不断言返回值**。
4. `test_list_docs_without_kb_id_returns_all`（第196-217行）：mock docstore 含2个文档（1个无 `kb_id`，1个 `kb_id="my-kb"`），调用 `list_docs()` 无参，断言 `len(docs) == 2`。

**关键判断**：前3个用例断言的都是"未声明范围时不过滤/放行"的行为，与"默认拒绝"决策直接冲突，必须改。第4个用例（`list_docs`）验证的是**管理侧列出全部文档**的行为，不是问答检索范围——`list_docs()` 是知识库管理场景（比如"查看所有文档，不限KB"），不属于 FR-04 单库问答闭环，**不在本次默认拒绝收紧范围内**，保持现状。这一点 plan.md 7.1节列出这4个用例时没有区分，本测试方案在 4.1.4 节明确排除它。

### 3.2 现有底层实现现状
- `server/kb_filter.py:27-43` `KBIdFilter._postprocess_nodes`：`if not self._kb_ids: return nodes`，空/None 时无条件放行。
- `server/retriever.py:33-43` `build_kb_metadata_filters`：`if not kb_ids: return None`，空/None 时不设过滤条件。
- `api/services/chat_service.py:29-45` `query()`：直接 `runtime_state.build_query_engine(kb_ids=request.kb_ids)`，中间**没有任何校验/拒绝逻辑**——这是 P0-1 需要新增的部分，当前完全不存在。
- `api/schemas/__init__.py:10-18` `QueryRequest`：`kb_ids: list[str] | None = None`，无 scope 相关字段（`requested_scope_type` 等 6.1 节字段目前都不存在）。
- `api/schemas/__init__.py:180-188` `EvidenceItem`：已有 `id/title/source/page/score/excerpt/receipt_id/kb_id` 7个字段，缺 `doc_id`、`preview_locator`。
- `api/services/agent_tools.py:29-44` `normalize_evidence()`：已存在，字段命名与 `chat_service._normalize_sources()` 不同（`file`/`text` vs `title,source`/`excerpt`）。
- `api/routers/kb.py` 全文确认**不存在** `/api/kb/preview` 路由。
- 以下 plan.md 中标注"新增"的文件**确认目前均不存在**：`api/services/query_scope.py`、`tests/api/test_chat_scope_contract.py`、`tests/api/test_chat_evidence_contract.py`、`tests/api/test_kb_preview_route.py`、`tests/api/test_asset_registry.py`、`tests/api/test_image_asset_import.py`、`tests/api/test_agent_kb_scope_contract.py`。

### 3.3 现有回归基线覆盖范围
以下文件均存在，测试范围概括如下（P0 阶段作为回归基线，不重写）：
- `tests/api/test_kb_registry.py`：KB 元数据 CRUD、重复 kb_id 报错、持久化。
- `tests/api/test_kb_routes.py`：`/api/kb` 路由 CRUD 与错误码（404/409/422）。
- `tests/api/test_kb_directory_storage.py`：按 KB 目录化存储、导入失败回滚、跨 KB 不冲突。
- `tests/api/test_kb_docs_isolation.py`：`list_docs`/`delete_docs` 按 kb_id 隔离、legacy 文档归属 default。
- `tests/api/test_retriever_stale_vectors.py`：陈旧向量容错、`build_kb_metadata_filters` 正确传参给子检索器。

## 4. Task 级测试用例展开

---

## 4.1 P0-1：范围控制共享核心 + Chat 接入

对应 DoD（plan.md 7.1）：单库成功 / 未授权拒绝 / echo 生效 / chat 不绕开核心 / 旧放行行为移除。

### 4.1.1 新增：`tests/api/test_chat_scope_contract.py`

| 用例 | 前置条件 | 输入 | 期望结果 |
|---|---|---|---|
| `test_single_kb_scope_succeeds` | KB `kb-a` 已创建且 active，已导入至少1篇文档 | `POST /api/chat/query`，`kb_ids=["kb-a"]`，`question="..."` | 200；返回体含 `effective_scope_type=="single_kb"`、`effective_kb_ids==["kb-a"]`、`is_default_deny_applied==False` |
| `test_response_echoes_effective_scope` | 同上 | 同上 | 返回体中 scope echo 字段（`requested_scope_type`/`requested_kb_ids`/`effective_scope_type`/`effective_kb_ids`/`isolation_level`）齐全，`isolation_level=="logical_filter_only"` |
| `test_unspecified_scope_is_rejected` | 无 | `POST /api/chat/query`，不传 `kb_ids`（或传 `kb_ids=None`） | 4xx（建议 422，具体状态码由实现决定但必须 ∈ [400,422]，不能是 200）；错误信息指明需显式声明单库范围 |
| `test_empty_kb_ids_is_rejected` | 无 | `kb_ids=[]` | 同上，4xx，不等同于"查全部" |
| `test_multi_kb_scope_rejected_on_mainline` | KB `kb-a`、`kb-b` 均存在 | `kb_ids=["kb-a","kb-b"]` | 4xx；错误信息指明 P0 主线不支持多库，需拆分为单库请求 |
| `test_nonexistent_kb_rejected` | 无 | `kb_ids=["kb-not-exist"]` | 4xx（建议映射为 404 或 400，与 `KBNotFoundError` 现有映射方式对齐，参考 `test_kb_routes.py` 中 404 用例） |
| `test_inactive_kb_rejected` | KB `kb-c` 存在但状态非 active（需先确认 KB 是否有 active/inactive 状态字段，若当前 registry 无此字段，此用例先标记 `xfail` 并在实现阶段一并补 registry 字段） | `kb_ids=["kb-c"]` | 4xx |

### 4.1.2 收紧：`tests/api/test_m2_multi_kb.py`

| 用例 | 现有断言 | 改为 |
|---|---|---|
| `test_kb_id_filter_pass_through_empty` | `kb_ids=[]` → 返回全部节点（长度1） | 保留 `KBIdFilter` 本身单元行为不变（这是通用过滤器组件，不是 chat 层策略）——**不在此文件改**，改为在 `test_chat_scope_contract.py` 层面拦截。若 plan.md 原意是要求过滤器本身也拒绝，需先明确 `KBIdFilter` 是否会被复用于"允许查全部"的其他合法场景（如 P1 跨库/知识库管理场景），若会被复用则不能在过滤器层写死拒绝，只能在 chat 入口层拒绝。**本轮已决议保留此用例不改**，决议见 §6。 |
| `test_kb_id_filter_pass_through_none` | 同上 | 同上，决议见 §6 |
| `test_query_without_kb_ids` | `mock_build.assert_called_once_with(kb_ids=None)`，且 `query()` 正常返回 | 改为：`query(req, record_history=False)` 应抛出异常（或返回前触发拒绝），`mock_build`（即 `build_query_engine`）**不应被调用**。新断言：`mock_build.assert_not_called()`，并断言抛出的异常类型/消息指明"scope 未声明" |
| `test_list_docs_without_kb_id_returns_all` | `list_docs()` 无参返回全部2个文档 | **不改**。理由见 §3.1：这是管理侧列全部文档场景，与 chat 问答范围契约无关 |

### 4.1.3 P0-1 验证命令
```powershell
python -m pytest tests/api/test_chat_scope_contract.py tests/api/test_m2_multi_kb.py -q
```

### 4.1.4 §3.1/4.1.2 排除说明
`test_list_docs_without_kb_id_returns_all` 从"需收紧清单"中排除，与 plan.md 7.1 节 TDD 顺序第2步的清单不完全一致——这是本测试方案基于代码现状核实后的修正，已在本轮同步回 plan.md，决议见 §6。

---

## 4.2 P0-2：证据结构统一化 + Preview Contract 落地

对应 DoD：统一 normalize / mapping；`sources`+`evidence` 并存；`/api/kb/preview` 返回结构化对象；前端可展示并预览；三个字段去留说清楚。

### 4.2.1 新增：`tests/api/test_chat_evidence_contract.py`

| 用例 | 前置条件 | 输入 | 期望结果 |
|---|---|---|---|
| `test_query_response_contains_evidence_field` | KB 含文档，单库问答已能命中至少1条 source | `POST /api/chat/query`，`kb_ids=["kb-a"]` | 返回体同时含 `sources`（兼容）与 `evidence`（正式）两个字段 |
| `test_evidence_item_has_required_fields` | 同上 | 同上 | `evidence` 列表中每项含 `id/title/source/page/score/excerpt/kb_id/receipt_id/doc_id/preview_locator` 十个字段（`doc_id`/`preview_locator` 允许为 `None`，但字段必须存在） |
| `test_sources_and_evidence_field_mapping_consistent` | 同上 | 同上 | 对同一条命中记录，`sources[i].file == evidence[i].title == evidence[i].source`、`sources[i].text == evidence[i].excerpt`、`sources[i].page == evidence[i].page`、`sources[i].kb_id == evidence[i].kb_id` |
| `test_chat_evidence_receipt_id_nullable` | 直接 chat 场景（非 agent/tool 调用） | 同上 | `evidence[i].receipt_id` 可为 `None`，不因为空值报错 |
| `test_agent_evidence_receipt_id_required` | 通过 agent/tool 路径调用（`run_kb_search` 或等价入口） | 触发一次 agent 工具调用 | 返回 evidence 中 `receipt_id` 非空，且与 `append_receipt` 生成的 `receipt["id"]` 一致 |

### 4.2.2 新增：`tests/api/test_kb_preview_route.py`

| 用例 | 前置条件 | 输入 | 期望结果 |
|---|---|---|---|
| `test_preview_by_doc_id_returns_text_excerpt` | KB `kb-a` 含已导入文档 `doc-1` | `POST /api/kb/preview`，`{"kb_id":"kb-a","doc_id":"doc-1"}` | 200；返回体含 `title/kb_id/doc_id/excerpt/locator/preview_type` |
| `test_preview_by_evidence_id_returns_text_excerpt` | 已有一次问答产生 `evidence_id`（若当前 evidence 无独立 id 概念，等价用 `id` 字段如 `"ev-1"`） | `POST /api/kb/preview`，`{"kb_id":"kb-a","evidence_id":"ev-1"}` | 200；同上字段齐全 |
| `test_preview_requires_doc_id_or_evidence_id` | 无 | `{"kb_id":"kb-a"}`（两者都不传） | 4xx |
| `test_preview_rejects_nonexistent_doc` | KB `kb-a` 存在 | `{"kb_id":"kb-a","doc_id":"doc-not-exist"}` | 4xx（建议404） |
| `test_preview_locator_expresses_page_when_available` | 文档为 PDF，命中片段有页码 | 同上 preview 请求 | `locator` 包含页级信息（不要求具体字段名，但需能定位到页） |

### 4.2.3 前端：`webapp/src/api/chat.test.js`（P0-2 部分，见 §4.4 分工）
本 Task 只负责新增/修改与 evidence/preview API 封装相关的用例：

| 用例 | 期望结果 |
|---|---|
| `queryChat 返回体解析出 evidence 字段` | `webapp/src/api/chat.js` 的 `queryChat()` 调用后，调用方能拿到 `result.evidence`（不要求转换，只要求透传不丢字段） |
| 新增 `webapp/src/api/evidence.js` 的 `previewEvidence()`/`previewDoc()` 单元测试 | 正确拼装 `POST /api/kb/preview` 请求体并透传响应 |

### 4.2.4 P0-2 验证命令
```powershell
python -m pytest tests/api/test_chat_evidence_contract.py tests/api/test_kb_preview_route.py -q
node --test webapp/src/domain/agentExperience.test.js webapp/src/api/chat.test.js
npm --prefix webapp run build
```

---

## 4.3 P0-3：资产对象最小闭环（收窄版）

对应 DoD：独立图片导入登记为 asset；可列出；可返回基础预览信息；可被 evidence 引用；不做 Markdown 抽取也可成立。

### 4.3.1 新增：`tests/api/test_asset_registry.py`

| 用例 | 前置条件 | 输入 | 期望结果 |
|---|---|---|---|
| `test_register_asset_creates_entry_in_kb_registry_file` | KB `kb-a` 存在 | 调用资产注册函数，传入 `asset_type="image"`、`path=...` | `storage/kb_assets/kb-a.json` 中出现对应 `asset_id` 记录，字段含 `asset_id/kb_id/source_doc_id/asset_type/title/path/mime_type/locator/status` |
| `test_list_assets_by_kb_id` | `kb-a` 已注册2个资产，`kb-b` 已注册1个资产 | 列出 `kb-a` 的资产 | 只返回 `kb-a` 的2条，不跨库 |
| `test_asset_registry_file_isolated_per_kb` | 同上 | 检查文件系统 | `storage/kb_assets/kb-a.json` 与 `kb-b.json` 分别独立存在，互不包含对方数据 |

### 4.3.2 新增：`tests/api/test_image_asset_import.py`

| 用例 | 前置条件 | 输入 | 期望结果 |
|---|---|---|---|
| `test_import_standalone_image_registers_asset` | KB `kb-a` 存在 | 导入一张独立 `png` 文件到 `kb-a` | 导入成功后能在资产列表中查到该图片对应的 asset object（而非仅作为普通 document） |
| `test_asset_can_be_referenced_by_evidence` | 已导入图片资产、已有一次相关问答命中该资产 | 触发一次能命中该资产的问答 | 返回 evidence/sources 中出现引用该 `asset_id`（或等价可追溯字段）的条目 |
| `test_asset_preview_returns_basic_info` | 同上 | 调用资产预览（可复用 `/api/kb/preview` 或独立资产预览接口，取决于 P0-2/P0-3 实现顺序） | 返回至少含 `title/path/mime_type` |

### 4.3.3 P0-3 验证命令
```powershell
python -m pytest tests/api/test_asset_registry.py tests/api/test_image_asset_import.py -q
npm --prefix webapp run build
```

### 4.3.4 明确不测的范围（对齐 plan.md P0 可选/P1）
Markdown 内嵌图片抽取、PDF 图像区域抽取、流程图语义增强——本阶段不写用例，若实现时顺手做了 Markdown 抽取，用例放入 `test_markdown_asset_extraction.py`（plan.md 已预留文件名），且失败不阻塞 P0-3 DoD 判定。

---

## 4.4 P0-4：前端主线收敛到 KnowledgePage / AgentPage

对应 DoD：用户理解上只有一个主"知识库页"；显式选库规则一致；旧页面孤儿路由兼容保留；新能力只落主线。

### 4.4.1 `webapp/src/domain/kbSelection.test.js`（既有文件，检查/补充）
| 用例 | 期望结果 |
|---|---|
| `requireKbTarget(undefined/null/"")` | 抛出明确错误，不静默放行 |
| `reconcileKbSelection` 在选中 KB 被删除后 | 回退到 `EMPTY_KB_SELECTION`，不停留在已失效的 kb_id 上 |

### 4.4.2 `webapp/src/domain/agentExperience.test.js`（既有文件，检查/补充）
| 用例 | 期望结果 |
|---|---|
| `buildChatPayload({experience:"knowledge", selectedKbId: undefined})` | 不应生成一个"不传 kb_ids"的合法 payload；应在前端侧就拦截或返回校验失败标记，与后端"默认拒绝"策略呼应，避免用户点了问答但请求必然被后端 4xx |
| `buildChatPayload({experience:"knowledge", selectedKbId:"kb-a"})` | payload 中 `kb_ids=["kb-a"]` |

### 4.4.3 `webapp/src/api/kb.test.js`（既有文件，检查/补充）
| 用例 | 期望结果 |
|---|---|
| `listDocs()` 不传 kb_id | 前端侧 `requireKbTarget` 直接抛错，不发请求（现状已如此，需确认测试存在，若不存在需补） |

### 4.4.4 `webapp/src/api/chat.test.js` 任务分工说明（对齐 plan.md 遗留问题）
plan.md 中 P0-2 和 P0-4 都涉及此文件，本测试方案明确切分：
- **P0-2 负责**：evidence/preview 相关请求-响应结构的用例（见 §4.2.3）。
- **P0-4 负责**：`queryChat()` 调用时 `kb_ids` 缺失/非法情况下的前端拦截行为用例（本节）。
两者互不重叠，合并进同一文件时按此归属拆分 `describe` 块。

| 用例（P0-4 归属） | 期望结果 |
|---|---|
| `queryChat` 在未选中 KB 时不发起请求 | 抛出前端校验错误，不产生网络调用 |

### 4.4.5 孤儿路由回归（降级优先级，非阻断 DoD）
`KbManagePage.jsx`/`KbFilePage.jsx`/`KbWebPage.jsx` 三页：
- 仅做人工冒烟：确认路由仍可直接 URL 访问、页面不报错、不允许拒绝弹窗信息误导用户以为是主线功能。
- **不要求**为这三页新增或维护自动化测试用例；现有测试若已覆盖可保留，不新增。

### 4.4.6 P0-4 验证命令
```powershell
node --test webapp/src/domain/kbSelection.test.js webapp/src/domain/agentExperience.test.js webapp/src/api/kb.test.js webapp/src/api/chat.test.js
npm --prefix webapp run build
```

---

## 4.5 P0-5：Agent 接入共享范围核心

对应 DoD：Agent 不再自定义第二套 scope contract；receipt/evidence 回显 scope；共享核心同时服务 chat 与 agent。

### 4.5.1 新增：`tests/api/test_agent_kb_scope_contract.py`

| 用例 | 前置条件 | 输入 | 期望结果 |
|---|---|---|---|
| `test_agent_tool_call_without_scope_is_denied` | 无 | 触发 `KbSearchTool`（或等价工具）调用，不声明 kb_ids | 被拒绝（异常或错误 receipt），不返回全量结果 |
| `test_agent_tool_call_with_single_kb_scope_succeeds` | KB `kb-a` 存在且有数据 | 工具调用声明 `kb_ids=["kb-a"]` | 成功；receipt/evidence 中回显 `request_scope`/`effective_scope`/`kb_id` |
| `test_agent_uses_shared_query_scope_module` | 无（静态检查） | 检查 `api/services/agent_tools.py` 的实现是否 import/调用 `api/services/query_scope.py` 中的函数，而非自行实现平行逻辑 | import 关系存在（可用 `inspect`/源码字符串检查，或直接 mock `query_scope` 模块函数并断言被调用） |
| `test_agent_receipt_echoes_scope_fields` | 同上成功场景 | 检查 `append_receipt` 写入的 receipt 内容 | receipt 中含 scope 相关字段，不是只有 tool 名和时间戳 |

### 4.5.2 P0-5 验证命令
```powershell
python -m pytest tests/api/test_agent_kb_scope_contract.py -q
```

---

## 4.6 P0-6：遗留入口与旧方案归档策略

对应 DoD：新文档成为唯一正式基线；旧入口不再承接新主能力；节奏无歧义。

本 Task 不产生新的自动化测试用例（性质是文档/流程治理，不是可断言的代码行为），改用检查清单：

### 4.6.1 人工检查清单
1. `docs/20260722-local-multi-kb-assistant/` 下 PRD/FRD/RTM/plan/test-plan 均为最新版本，无内部矛盾（本次核实已确认 plan.md 无矛盾，见开头）。
2. 旧主线文档（`agent_v1_prd.md` 等）已迁入 `docs/archive/root-legacy-20260724/`，且未被新代码引用。
3. `app.py`/`frontend/*.py`（Streamlit）未新增任何本次 P0-1~P0-5 的新功能代码。
4. `KbManagePage.jsx`/`KbFilePage.jsx`/`KbWebPage.jsx` 未新增功能代码，仅允许缺陷修复级改动。

---

## 5. 阶段性回归执行顺序

### 5.1 后端回归全集（P0 完成后统一执行）
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

### 5.2 前端回归全集
```powershell
node --test \
  webapp/src/domain/kbSelection.test.js \
  webapp/src/domain/agentExperience.test.js \
  webapp/src/api/kb.test.js \
  webapp/src/api/chat.test.js

npm --prefix webapp run build
```

### 5.3 人工冒烟清单（与 plan.md 9.3 一致，补充断言粒度）
1. 创建两个 KB（`kb-a`、`kb-b`）。
2. 分别导入不同 md / pdf / 图片到两个 KB。
3. 在 `KnowledgePage` 中显式切换 KB，确认文档列表 / 资产列表不串库（对应 `test_kb_docs_isolation.py` 的手工验证）。
4. 在 `AgentPage` 选择"知识库问答"但**不选 KB**直接提问 → 确认前端拦截或后端明确拒绝，不出现"静默查了全部知识库"的结果。
5. 选中 `kb-a` 提问 → 验证回答结果中的 scope（`single_kb`/`kb-a`）/ evidence / kb_id 回显正确。
6. 验证 preview 接口可打开最小文本预览。
7. 验证独立图片导入后可在资产列表中查到，且能被证据引用。
8. 访问旧 KB 页面路由（如 `/kb-manage`），确认页面仍可访问但无新功能、无导航入口。

## 6. 本轮决议（已同步回 plan.md / 可直接作为编码前提）

1. **`KBIdFilter` 在 P0 不下沉默认拒绝策略**：chat 入口层（`chat_service.query` / `query_scope.py`）负责“未声明范围 = 默认拒绝”；`KBIdFilter` 仍保留通用过滤器语义，即空 `kb_ids` 时可不过滤。因此 `test_kb_id_filter_pass_through_empty` / `_none` 暂不作为 P0-1 强制改写对象。
2. **`test_list_docs_without_kb_id_returns_all` 不在本次收紧范围内**：这是 KB 管理侧“列全部文档”场景，不属于 chat 问答范围契约；已要求同步回 plan.md，避免上游/下游文档不一致。
3. **KB active/inactive 字段已存在，可保留在 P0-1 测试范围内**：`server/kb_registry.py` 创建 KB 时已写入 `status: "active"`，且 `api/services/kb_service.py::_ensure_kb_active()` 已有可用性校验逻辑，因此 `test_inactive_kb_rejected` 不需要下放到 P1。
4. **`evidence_id` 在 P0 复用 `EvidenceItem.id`**：P0 不再引入第二套独立 evidence 标识体系；如果实现上仅靠 `evidence_id` 难以稳定解析预览，前端主线优先走 `doc_id + preview_locator`，但契约语义上两者不是两套对象。

## 7. 下一步建议
测试方案确认后，下一步是进入 Stage 3 编码，严格按 plan.md §8 顺序（P0-1 → P0-2 → P0-3 → P0-4 → P0-5 → P0-6），每个 Task 按本文档 §4 对应小节的 TDD 顺序（先写测试，再改实现）推进；每个 Task 完成后执行对应小节 §4.x.末尾的验证命令，全部 Task 完成后执行 §5 的回归全集与人工冒烟清单，再产出测试报告。


