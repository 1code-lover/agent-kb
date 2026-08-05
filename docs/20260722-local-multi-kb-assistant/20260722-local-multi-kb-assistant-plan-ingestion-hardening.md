# 本地多知识库知识助手平台导入与嵌入稳定性加固实施方案（Stage 2A）

## 1. 文档目的
本文档是 `20260722-local-multi-kb-assistant` 需求在 Stage 2 基线之外追加的一份“导入与嵌入稳定性加固实施方案”。

它不替代既有 `20260722-local-multi-kb-assistant-plan.md`，而是回答当前已经暴露出来的一个更紧迫问题：**在继续推进 P0-3 资产对象最小闭环之前，如何先把导入、索引写入、删除、重导入这一条 ingestion / embedding 底座链路加固到足够可控。**

本文档重点回答四个问题：
1. 目前“导入文件 / 嵌入 / 删除”具体脆在哪里；
2. 这轮稳定性加固先修哪些点、不修哪些点；
3. 每个任务改哪些文件、先写哪些测试；
4. 用什么命令验证，什么结果算通过。

> 说明：本轮属于 Stage 2A 补充实施计划，优先级位于“直接进入 P0-3 资产对象最小闭环”之前。

## 2. 输入基线
本实施方案以下列文档为正式输入：
- `20260722-local-multi-kb-assistant-prd.md`
- `20260722-local-multi-kb-assistant-frd.md`
- `20260722-local-multi-kb-assistant-rtm.md`
- `20260722-local-multi-kb-assistant-plan.md`
- `20260722-local-multi-kb-assistant-test-plan.md`
- `20260722-local-multi-kb-assistant-spec.md`
- 根目录 `评审建议.txt`

其中，`spec.md` 已新增如下关键判断，本实施方案必须与其保持一致：
1. KnowledgeBase 是边界对象；
2. Folder 是组织对象，不是边界对象；
3. Document / Asset / Chunk / Embedding / Job 必须分层建模；
4. 删除、重导入、重建索引是三件不同的事；
5. 当前共享单索引现实必须被诚实表达，不能假装已经物理隔离。

## 3. 当前代码现实（作为加固约束）

### 3.1 已核实的导入链路现状
1. `api/services/kb_service.py::import_files()` 当前先把上传文件写入 `data/{kb_id}/`，再调用 `runtime_state.get_index_manager().load_files(...)`。
2. `server/index.py::load_files(...)` 当前负责读取文件、切分、生成节点，并在节点 metadata 上补 `kb_id` 与 `file_path`。
3. 当前文件导入返回值仍偏“动作结果”，主要是：
   - `files`
   - `indexed_chunks`
   - `kb_id`
4. 当前 URL 导入 `import_urls(...)` 与本地文件导入的计数策略相近，也按输入数量增量更新 `doc_count`。
5. 当前删除链路使用 `IndexManager.delete_ref_doc(...)`，底层仍依赖 LlamaIndex 原生删除逻辑。

### 3.2 已暴露的稳定性问题
已确认或高度可疑的问题包括：
1. **删除脏引用会炸：**
   - 历史脏数据下，`ref_doc_info.node_ids` 可能包含已经不在 `index_struct.nodes_dict` 中的陈旧 node_id；
   - 原生 `delete_ref_doc` 在这种情况下可能直接抛 `KeyError`，导致整次删除失败。
2. **导入成功数与真实入库结果可能不一致：**
   - 当前 `import_files()` 用 `len(uploaded_files)` 累加 `doc_count`；
   - 但 `manager.load_files()` 可能返回空节点列表，甚至某些文件未真正形成可检索内容；
   - 这会造成“文件落盘了，但没有真实索引内容”时 `doc_count` 仍被加一。
3. **URL 导入存在同类计数漂移风险：**
   - 当前 `import_urls()` 用 `len(urls)` 累加 `doc_count`；
   - 若后续出现抓取空内容、部分失败、零节点生成，计数仍可能虚高。
4. **导入结果可观测性不足：**
   - 当前响应缺少 per-file / per-url 状态；
   - 用户只能看到“传上去了”和“总 chunk 数”，无法区分哪一项失败、哪一项为空、哪一项部分成功。
5. **批量导入隔离不够：**
   - 当前 `import_files()` 在一批文件写完后统一调用 `load_files(file_paths, ...)`；
   - 一旦某个文件拖累整批，失败粒度过粗，回滚和追踪都不清楚。

### 3.3 当前实现与产品目标之间的真实落差
这轮需要正视的不是“还能不能继续做功能”，而是下面这条现实：

> 如果当前 ingestion 底座仍然允许“假成功、计数漂移、删除易炸、失败难追踪”，那么后面继续做 P0-3 资产对象、Markdown 图片抽取、Agent 接入，都会把不稳定性放大。

因此，本轮优先级不是“多做一个产品点”，而是“先把地基补平”。

### 3.4 2026-07-28 最新运行核实结果（真实现状同步）
基于当前工作区代码拉起的干净后端实例（`run_api.py`，验证端口 `18123`）已完成一次真实导入核实，结论如下：

1. **Markdown 导入主链路可用**：文件保存、解析、切分、嵌入、索引写入均已走通，导入项状态可达 `indexed`。
2. **独立图片导入并非“完全没做”**：图片文件能落盘、资产能注册、OCR 逻辑会被触发；当前失败主因是运行环境缺少 `paddleocr`（以及配套 `paddlepaddle`），因此结果为 `empty/ocr_failed`，而不是没有图片导入能力。
3. **PDF 导入当前被运行时依赖阻断**：导入链路会进入 PDF reader，但当前环境缺少 `PyMuPDF (fitz)`，因此返回 `failed`；这说明问题首先是依赖就绪性，而不是产品流程不存在。
4. **Markdown 内嵌图片抽取链路已有雏形**：Markdown 本体可以索引成功，内嵌图片能被抽取为 embedded asset 并注册；若同一图片又被独立上传，当前还能识别 `shadowed_by_embedded_asset`，说明宿主文档—资产关系与去重逻辑已经部分存在。
5. **`display_summary` 结构已真实返回，但后端中文 copy 受损**：导入回执中的 `display_summary`、`headline`、`next_actions` 等字段已经通了前后端链路，但 `api/services/kb_service.py` 中部分中文文案写坏成 `????`，当前属于可用性/可读性问题，而不是结构缺失。
6. **依赖健康信息仍不够完整**：`/api/health` 已能看见 OCR warmup 因缺少 `paddleocr` 而失败，但 PDF/图片导入所需依赖并没有统一能力视图，用户仍要在导入失败后才知道具体缺什么。

这次核实带来的关键修正是：**当前“导入有很多问题”的真实含义，主要是运行时依赖缺失、导入可观测性不足和回执文案质量不达标，而不是基础导入/资产抽取链路完全不存在。** 因此后续优先级应回到“把基础链路拉通并验证问答质量”，而不是先扩展深度图像理解。现阶段图片策略仍维持：**先支持 OCR 提取 + 图片资产入库，不展开高级视觉语义理解。**

## 4. 本轮目标与非目标

### 4.1 本轮目标
本轮只做下面五类稳定性加固：
1. 删除链路面对历史脏引用时不再轻易炸掉；
2. 导入计数与真实成功结果对齐，消除显著的 `doc_count` 漂移；
3. 导入结果从“总量成功”升级为“最小可追踪的逐项结果”；
4. 补齐导入 / 删除 / 重导入相关回归测试，为后续 P0-3 和多模态扩展清路。
5. 为下一阶段“文档导入 → 检索 → 问答”基础链路验证提供稳定、可重复的输入前提。

### 4.2 本轮明确不做
本轮不做：
1. 物理隔离 / 独立命名空间；
2. 完整 Asset 对象模型落地；
3. Markdown 内嵌图片抽取；
4. OCR 质量优化与流程图语义理解；
5. 深度图像语义理解、流程图结构化理解或视觉问答；
6. 全量引入 IngestionJob 持久化存储；
7. 把所有导入接口一次性改成全新协议；
8. 全面开放 Agent 写路径。

### 4.3 与 P0-3 的关系
当前主计划中的 P0-3 是“资产对象最小闭环（收窄版）”，不是“导入链路稳定性修复”。

本轮实施结论如下：
1. 本轮加固视为 **P0-2.5 / Stage 2A**；
2. 完成本轮后，再进入 P0-3；
3. 如果本轮执行中发现 ingestion 底座问题比预期更大，可继续扩展为独立稳定性阶段，但不能边做资产对象边放任导入链路继续积累脏状态。

## 5. 实施总策略

### 5.1 策略一：先补一致性，再补能力
优先修：
- 删除时的历史脏数据兼容；
- 导入返回与计数的一致性；
- per-file / per-url 可见性。

暂不做：
- 大规模重构 reader 体系；
- 一次性引入完整任务表、状态机、后台队列。

### 5.2 策略二：先让失败可见，再讨论更复杂补偿
本轮优先把失败显式化，而不是先做“自动修复一切”。

体现为：
1. 单个输入项是否成功，要能在响应里看见；
2. 空内容 / 零节点 / 抓取失败要能被区分；
3. 先做到“知道哪里坏”，再做更复杂的批量补偿机制。

### 5.3 策略三：优先按输入项隔离，接受局部吞吐折中
当前 `import_files()` 批量写入后统一 `load_files()` 的策略对吞吐友好，但对稳定性与回执不友好。

本轮建议：
- 文件导入改为**按文件逐个处理并累计结果**；
- URL 导入改为**按 URL 逐个处理或至少逐项形成结果**；
- 接受小规模吞吐下降，换取更清晰的失败边界和更可控的计数更新。

### 5.4 策略四：兼容旧返回结构，但追加正式结果字段
本轮不强推一次性 breaking change。

建议：
1. 保留旧字段：`files`、`indexed_chunks`、`kb_id`；
2. 追加新字段，例如：
   - `receipt_id`
   - `import_summary`
   - `file_results` / `url_results`
   - `failed_count` / `success_count`
3. 前端与后续接口优先消费新字段，旧字段作为兼容层保留。

## 6. 关键契约冻结（编码前必须定死）

### 6.1 文件导入结果最小契约（本轮冻结）
建议 `import_files()` 最小返回结构扩充为：
- `kb_id`
- `receipt_id`
- `indexed_chunks`
- `success_count`
- `failed_count`
- `file_results`

其中 `file_results[*]` 最小字段建议为：
- `name`
- `path`
- `kb_id`
- `status`：`indexed` / `empty` / `failed`
- `indexed_chunks`
- `message`

冻结规则：
1. `indexed` 代表该文件已产生节点并进入索引；
2. `empty` 代表该文件成功落盘，但未产生可索引内容；
3. `failed` 代表该文件导入过程中发生异常，且不应计入 `doc_count`。

### 6.2 URL 导入结果最小契约（本轮冻结）
建议 `import_urls()` 最小返回结构扩充为：
- `kb_id`
- `receipt_id`
- `indexed_chunks`
- `success_count`
- `failed_count`
- `url_results`

其中 `url_results[*]` 最小字段建议为：
- `url`
- `status`：`indexed` / `empty` / `failed`
- `indexed_chunks`
- `message`

### 6.3 doc_count 更新规则（本轮冻结）
本轮冻结如下规则：
1. `doc_count` 只能按**真实成功导入的输入项数**更新；
2. `empty` 与 `failed` 都不能增加 `doc_count`；
3. 单批导入中允许部分成功、部分失败；
4. 不能再使用“输入项数量”近似代表“成功入库数量”。

### 6.4 删除链路兼容规则（本轮冻结）
1. 删除前必须允许对陈旧 node 引用做清理；
2. 对不存在于 `index_struct.nodes_dict` 中的 node_id，应视为历史脏引用，而不是直接让底层异常中断请求；
3. 清理行为应被测试覆盖；
4. 本轮只做“陈旧引用兜底”，不把 delete_ref_doc 全量重写成新删除框架。

## 7. 任务拆解（TDD 顺序）

### 7.1 任务 H1：删除链路历史脏引用兜底

#### 7.1.1 目标
修复 `IndexManager.delete_ref_doc()` 在历史脏数据场景下可能因陈旧 node_id 抛 `KeyError` 的问题。

#### 7.1.2 涉及文件
- `server/index.py`
- `tests/api/test_index_manager_coverage.py`

#### 7.1.3 先写失败测试
新增 / 收紧测试：
1. `ref_doc_info.node_ids` 中既有有效节点也有陈旧节点时，删除应成功完成；
2. 所有节点都有效时，不应误删；
3. 清理后仍应调用原有 `index.delete_ref_doc(...)` 与 `storage_context.persist()`。

#### 7.1.4 实现要求
1. 在调用底层删除前，先读取 `docstore.get_ref_doc_info(ref_doc_id)`；
2. 若发现 `node_id` 已不在 `index.index_struct.nodes_dict` 中，则先从 docstore 关联信息中移除；
3. 不改变正常路径的删除行为；
4. 中文注释与函数说明必须清晰说明“为什么要在这里兜底”。

#### 7.1.5 DoD
- `tests/api/test_index_manager_coverage.py` 相关新增用例通过；
- 删除行为对正常场景无回归；
- 代码注释说明清楚历史脏数据来源与处理目的。

### 7.2 任务 H2：修复文件导入“假成功”与 doc_count 漂移

#### 7.2.1 目标
让 `kb_service.import_files()` 的统计口径与真实成功结果对齐，不再把“成功落盘”误当成“成功入库”。

#### 7.2.2 涉及文件
- `api/services/kb_service.py`
- `api/routers/kb.py`（如需补充响应字段说明）
- `tests/api/test_kb_directory_storage.py`
- `tests/api/test_m2_multi_kb.py`（如已有 import 响应契约测试需同步）

#### 7.2.3 先写失败测试
至少补以下测试：
1. 当 `manager.load_files(...)` 返回空列表时：
   - `doc_count` 不增加；
   - 响应中该文件状态为 `empty`；
   - 不应伪装为完全成功。
2. 批量导入时，一部分文件成功、一部分文件失败：
   - `success_count` / `failed_count` 正确；
   - `doc_count` 只增加成功项数量；
   - 失败文件应保留明确错误消息。
3. 单文件失败时：
   - 本地落盘文件被清理；
   - `doc_count` 不增加；
   - 返回结构中有失败项状态。

#### 7.2.4 实现要求
1. 文件导入从“整批统一 load_files”调整为“逐文件导入、逐文件收集结果”；
2. 每个文件独立记录：
   - 路径
   - 产生节点数
   - 状态
   - 错误消息
3. 只对 `indexed` 状态的文件做 `doc_count` 累加；
4. 保留旧字段 `files` 作为兼容输出，但新增正式字段 `file_results` 与统计字段；
5. 若整批无任何成功项，不得返回看似正常的“成功导入”。

#### 7.2.5 DoD
- 文件导入可以区分 `indexed` / `empty` / `failed`；
- `doc_count` 与真实成功导入数一致；
- 旧调用方在保留字段存在的前提下不被无谓打断；
- 测试覆盖空节点、部分失败、单文件失败场景。

### 7.3 任务 H3：修复 URL 导入统计口径与逐项回执

#### 7.3.1 目标
让 `import_urls()` 不再用 `len(urls)` 近似表示成功导入数，并形成最小逐项结果回执。

#### 7.3.2 涉及文件
- `api/services/kb_service.py`
- `tests/api/test_kb_directory_storage.py`
- `tests/api/test_m2_multi_kb.py`（若涉及 schema / response 契约）

#### 7.3.3 先写失败测试
至少补以下测试：
1. 单 URL 返回零节点时，不增加 `doc_count`，该项状态为 `empty`；
2. 多 URL 部分成功时，只按成功项增加 `doc_count`；
3. URL 抓取异常时，该项状态为 `failed`，不影响其他成功项计数。

#### 7.3.4 实现要求
1. URL 导入同样形成 `url_results`；
2. 更新 `doc_count` 的依据改为真实成功项数量；
3. 尽量与文件导入使用相同的状态枚举与统计字段；
4. 本轮不要求把文件导入与 URL 导入彻底抽象为统一任务框架，但输出语义应尽量一致。

#### 7.3.5 DoD
- URL 导入不再存在显著的 doc_count 漂移；
- 响应可以定位具体失败项；
- 新老测试均通过。

### 7.4 任务 H4：补齐删除 / 导入 / 重导入回归防线

#### 7.4.1 目标
围绕本轮修复点建立一组回归测试，确保后续做 P0-3 资产对象时不把地基再踩坏。

#### 7.4.2 涉及文件
- `tests/api/test_kb_directory_storage.py`
- `tests/api/test_index_manager_coverage.py`
- `tests/api/test_m2_multi_kb.py`
- 如有必要新增：`tests/api/test_ingestion_hardening.py`

#### 7.4.3 重点覆盖场景
1. 删除历史脏引用；
2. 文件导入空内容；
3. 文件导入部分失败；
4. URL 导入部分失败；
5. 同一 KB 下重复导入与 doc_count 更新；
6. 删除后再次导入不出现异常漂移。

#### 7.4.4 DoD
- 相关测试归类清晰，不与 Chat / Evidence 主链路测试相互污染；
- 新增断言真正验证契约，而不是只验证“没有报错”；
- 后续 P0-3 可以直接复用本轮回归集。

## 8. 建议实现顺序
严格按以下顺序执行：
1. **H1**：先落删除脏引用兜底；
2. **H2**：再改文件导入统计与逐项回执；
3. **H3**：同步 URL 导入统计口径；
4. **H4**：补齐回归测试并统一整理。

原因：
- H1 当前已有明确本地修复方向与测试草稿，是最小、最确定的 bugfix；
- H2 / H3 属于导入返回语义与计数逻辑的收紧，需建立在删除链路不会轻易炸掉的前提上；
- H4 最后收口，避免测试结构边写边散。

## 9. 验证命令与预期结果

### 9.1 H1 最小验证
```powershell
python -m pytest tests/api/test_index_manager_coverage.py -q
```
预期：
- 相关新增用例通过；
- 总体用例通过，无删除链路回归。

### 9.2 H2 / H3 核心验证
```powershell
python -m pytest tests/api/test_kb_directory_storage.py tests/api/test_m2_multi_kb.py -q
```
预期：
- 导入与删除相关测试通过；
- `doc_count` 相关断言全部对齐新口径；
- 无“空内容也记成功”的旧断言残留。

### 9.3 本轮总回归
```powershell
python -m pytest tests/api/test_index_manager_coverage.py tests/api/test_kb_directory_storage.py tests/api/test_m2_multi_kb.py tests/api/test_chat_scope_contract.py tests/api/test_chat_evidence_contract.py tests/api/test_kb_preview_route.py -q
```
预期：
- 全部通过；
- 不因导入链路收紧而破坏已完成的 Chat scope / evidence / preview 主链路。

## 10. 风险与权衡

### 10.1 吞吐下降风险
按文件 / 按 URL 逐项处理会降低一部分批量导入吞吐，但当前阶段这是可接受权衡。优先级应是：
1. 结果可解释；
2. 计数正确；
3. 失败边界清楚；
4. 再谈吞吐优化。

### 10.2 响应字段扩张风险
追加 `file_results` / `url_results` 会使响应变大，但这是必要成本。当前旧字段可保留，避免不必要的前端大改。

### 10.3 与未来 IngestionJob 的关系
本轮只做“最小 receipt / 逐项结果”，不直接上完整持久化任务模型。后续若要做 `IngestionJob`，本轮的状态枚举与回执字段应尽量可迁移，不要未来重命名两次。

### 10.4 与导入 scope 收紧的边界
当前 `api/routers/kb.py` 与 `api/schemas/__init__.py` 里仍有 `kb_id="default"` 的 legacy 默认值。本轮重点是稳定性，不强行把所有导入接口同步改成“未声明即拒绝”。

但要明确：
- 这是**暂不扩面**，不是认可 legacy default 为最终正确方案；
- 若后续继续做导入契约统一，应以 `spec.md` 中“显式 KnowledgeBase 归属”为目标态。

## 11. 验收标准
本轮完成后，应满足以下验收标准：
1. 删除历史脏引用时不再因陈旧 node_id 直接失败；
2. 文件导入和 URL 导入都能区分 `indexed` / `empty` / `failed`；
3. `doc_count` 只反映真实成功入库项，不再按输入数近似；
4. 导入响应至少能回答“哪一项成功、哪一项失败、失败原因是什么”；
5. 本轮修改不会破坏已落地的 Chat scope / evidence / preview 主线；
6. 完成本轮后，P0-3 资产对象最小闭环可以在更稳定的 ingestion 底座上继续推进。

## 12. 本文结论
当前“导入文件嵌入方面问题很多”的核心，并不是缺一个新页面或新按钮，而是 ingestion 底座里已经出现了：
- 删除脏引用易炸；
- 导入结果假成功；
- 计数与真实入库结果不一致；
- 批量导入失败不可见。

同时，2026-07-28 的真实运行核实也说明：
- Markdown 导入主链路已经可用；
- 图片资产抽取/注册已具雏形，但 OCR 受运行时依赖阻断；
- PDF 导入当前首先受 `fitz` 缺失阻断；
- 问题更多集中在依赖就绪性、可观测性和回执质量，而不是“什么都没有”。

因此，本轮实施方案明确建议：
1. 先把这条稳定性链路补平；
2. 同步修复导入回执 copy 与依赖可见性，让当前能力可被真实使用；
3. 再把优先级收敛到“文档导入 → 检索 → 问答”的基础链路验证与问答测试集构造；
4. 让后续多模态、目录层级、Agent 化能力建立在一个至少“结果可信、失败可见、计数正确、删除可控、问答可验证”的底座之上。

## 13. 基于最新运行核实的下一阶段建议
在 H1~H4 稳定性加固之外，下一阶段建议按下面顺序推进：
1. **先修可用性问题**：修复 `api/services/kb_service.py` 中 `display_summary` 的中文文案损坏，避免导入回执虽然有结构但不可读。
2. **补依赖就绪性可见性**：至少把 `fitz`、`paddleocr`、`paddlepaddle` 的可用状态纳入统一的导入能力视图或健康输出，避免用户只能在失败后反推环境问题。
3. **拉通基础链路**：围绕单库场景验证 Markdown/PDF/图片（OCR）导入、索引、检索、问答整条主线，不在此阶段扩面做高级图像理解。
4. **尽快构造问答测试集**：以稳定 Markdown 文档为首批基线，优先建设单库问答评测集；每条样本至少包含 `kb_id`、`source_doc`、`question`、`expected_keypoints`、`expected_evidence`、`must_not_contain`。
5. **把准确性验证前置**：P0/P1 阶段不以“能返回答案”作为通过标准，而要检查 scope 正确、证据来源正确、关键事实覆盖率达标。

## 14. 2026-07-28 implementation sync

Part of the `Section 13` next-step list is now completed:

1. The `display_summary` usability issue is fixed in `api/services/kb_service.py`, so import receipts are readable again.
2. Dependency readiness visibility is fixed in `/api/health`, which now exposes `import_capabilities` for `fitz / paddleocr / paddlepaddle / Pillow`.
3. Single-kb QA smoke groundwork has started with:
   - `tests/fixtures/rag_quality/single_kb_smoke_cases.json`
   - `tests/api/test_chat_single_kb_qa_smoke.py`

This means the focus can keep moving forward:
- import failures are now more explainable than before;
- the next priority is answer quality and evidence quality after import succeeds;
- the P0 image policy remains frozen: OCR extraction + image asset registration first, no deep visual reasoning yet.

## 15. 2026-07-28 implementation sync: ingestion QA baseline linkage

The ingestion-hardening track has now been connected to a larger QA baseline instead of only an import smoke check:

1. A semi-real Markdown fixture set exists in `tests/fixtures/rag_quality/semireal_markdown/`.
2. Semi-real QA has been extended beyond Markdown into:
   - `tests/api/test_chat_pdf_semireal.py`
   - `tests/api/test_chat_image_ocr_semireal.py`
3. Reader-layer regressions are covered by:
   - `tests/readers/test_image_ocr.py`
   - `tests/readers/test_pdf_ocr.py`
4. Shared QA metric calculation now lives in `tests/api/chat_qa_metrics.py`.

Current combined regression command:
`python -m pytest tests/api/test_chat_qa_metrics.py tests/api/test_chat_markdown_qa_semireal.py tests/api/test_chat_single_kb_qa_smoke.py tests/api/test_chat_pdf_semireal.py tests/api/test_chat_image_ocr_semireal.py tests/api/test_chat_scope_contract.py tests/api/test_chat_evidence_contract.py tests/api/test_health_route.py tests/api/test_image_asset_import.py tests/api/test_kb_directory_storage.py tests/test_rag_quality_fixtures.py tests/readers/test_image_ocr.py tests/readers/test_pdf_ocr.py -q`

Current verified result: **124 passed, 1 skipped, 2 warnings**.

What this means for ingestion hardening:
1. The project is no longer checking only "can files import without crashing".
2. It is now checking whether imported Markdown / PDF / OCR text can later be queried, cited, previewed, and evaluated with explicit quality metrics.
3. The current hardening story therefore covers import, storage, query, evidence, preview, parser diagnostics, and QA metric governance together.

Boundary reminder:
- This is still not the final PDF/OCR answer-quality benchmark.
- It is the parser-and-ingestion quality floor that should stay green before we expand modality-specific evaluation further.


## 16. 2026-07-28 implementation sync: deletion safety and copy repair

本轮又完成了两个小而硬的 ingestion 加固项：

1. `server/index.py` 中的 `delete_ref_doc()` 已增加针对陈旧 `node_id` 引用的回归测试覆盖。
2. 导入主链路核心文件中被写坏的中文 docstring / 注释已修复，涉及：
   - `server/readers/image_ocr.py`
   - `api/services/kb_service.py`
   - `api/services/asset_service.py`

新增回归覆盖：
- `tests/api/test_index_manager_coverage.py`
  - 先清理 stale node 引用，再委托原生 delete flow
  - 无 stale 引用时不误删正常 node

已验证命令：
`python -m pytest tests/api/test_index_manager_coverage.py tests/readers/test_image_ocr.py tests/api/test_image_asset_import.py tests/api/test_health_route.py -q`

已验证结果：**44 passed, 2 warnings**。

这意味着：
1. ingestion 基线不只是“更可观测”，也对一类已知历史删除故障更安全了。
2. 核心导入 / OCR 文件已恢复可读性，便于后续 FRD-to-code 追踪、代码评审和前后端契约维护。
3. 下一阶段的优先级仍然不变：继续收紧“真实导入 -> 检索 -> QA 验证”这条主线，而不是过早扩展到更深的多模态推理。

## 17. 2026-07-29 implementation sync: preserve_tree nested reimport regressions

本轮补齐了目录导入 `preserve_tree` 模式下的 nested relative_path 回归基线，重点不是新增功能，而是把“目录层级下的重导入/删除/retry”也纳入 ingestion hardening 的保护范围。

已新增 / 收紧的回归点：
1. `tests/api/test_kb_directory_import_tree.py`
   - `test_import_files_preserve_tree_reimport_nested_path_replaces_existing_doc`
   - `test_import_files_preserve_tree_failed_reimport_restores_previous_bytes`
   - `test_delete_docs_by_nested_path_allows_preserve_tree_reimport`
2. 失败重导入用例已收紧断言顺序：先验证“失败后仍保留旧文件字节与旧 ref_doc”，再验证 retry 成功后生成新的 ref_doc。

本轮验证命令：
- `python -m pytest tests/api/test_kb_directory_import_tree.py -q`
  - 结果：**7 passed, 2 warnings**
- `python -m pytest tests/api/test_kb_directory_import_tree.py tests/api/test_kb_directory_storage.py tests/api/test_index_manager_coverage.py -q`
  - 结果：**69 passed, 2 warnings**
- `python -m pytest tests/api/test_chat_evidence_contract.py tests/api/test_health_route.py tests/api/test_kb_directory_import_tree.py tests/api/test_kb_directory_storage.py tests/api/test_index_manager_coverage.py -q`
  - 结果：**84 passed, 2 warnings**

这意味着：
1. ingest hardening 现在不只覆盖“单文件平铺导入”，也覆盖“保留目录结构导入”下的 nested path 替换与恢复。
2. 当前基础链路已经能更可信地支撑下一步的中文 PDF / 图片 OCR / 混合目录批量导入回归扩展。
3. 下一阶段仍然应优先补真实导入和问答质量验证，而不是过早扩展到更深的图像理解或多 Agent 联动。



## 18. 2026-07-31 implementation sync: empty-markdown import normalization

本轮在继续清扫导入链路时，确认并修复了一个真实的空文档导入缺陷：空白 Markdown 文件在 live 服务里原本会返回 `failed`，错误为 `'NoneType' object is not iterable`，而不是按设计返回 `empty`。

根因已定位到 `server/ingestion.py`：
1. `AdvancedIngestionPipeline.run()` 的自定义诊断路径里，当 transform 对空文档返回 `None` 时，会直接把 `None` 传给 cache 写入；
2. cache 层随后按可迭代节点集合处理，触发 `TypeError`；
3. `server/index.py` 中“空节点时不 insert”的保护虽然已存在，但在这个报错点之前还来不及生效。

本轮已落实的修复：
1. `server/ingestion.py`
   - 新增 `_normalize_transformed_nodes()`；
   - transform 命中 cache miss / no-cache 分支时，统一把 `None` 归一化为 `[]` 后再写 cache 或进入后续阶段。
2. `tests/api/test_ingestion_pipeline.py`
   - 新增直接回归：transform 返回 `None` 时，断言 cache 写入 `[]`、流程不崩溃、诊断计数为 0。
3. `tests/api/test_index_manager_coverage.py`
   - 先前补齐的 manager 层空结果保护继续保持通过，说明 pipeline 修复与上层 guard 没有互相打架。

本轮验证：
- 定向回归命令：
  - `python -X utf8 -m pytest tests/api/test_ingestion_pipeline.py tests/api/test_index_manager_coverage.py tests/api/test_kb_directory_storage.py -q`
  - 结果：**82 passed**
- 运行时直连验证：
  - `docs/20260722-local-multi-kb-assistant/artifacts/runtime/20260731-empty-markdown-runtime.json`
  - 结果：`node_count = 0`、`empty_document_count = 1`
- fresh live HTTP 验证：
  - `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18086-empty-file.json`
  - 结果：文件状态为 `empty`，`empty_count = 1`，`failed_count = 0`，且 KB 文档列表为空。

这意味着：
1. ingestion hardening 现在不只覆盖“有内容时能索引”，也覆盖“无可索引内容时要稳定返回 empty 而不是崩溃”；
2. 空文档这类边界输入已经从 live 缺陷变成了有测试、有 runtime 证据、有 HTTP 证据的回归基线；
3. 下一步仍应回到主线目标：继续扩展导入后问答准确性评测，而不是把注意力转向更深的图像理解承诺。


## 19. 2026-07-31 implementation sync: reject unsupported binary uploads early

本轮在继续清扫导入链路时，又确认了一个真实边界问题：`application/octet-stream` 的 `.bin` 文件此前会落入通用 loader 路径，并被误记为“导入成功 + 已入索引”，这与当前产品范围不一致。

根因：
1. `api/services/kb_service.py` 之前虽然已经能识别 `file_kind = binary`，但并没有在导入入口拒绝；
2. 文件仍会被落盘并进入 `manager.load_files(...)`；
3. 通用读取链路会把原始字节当作可处理内容，最终导致“未知二进制内容被误判为知识导入成功”。

本轮已落实的修复：
1. `api/services/kb_service.py`
   - 新增 `_is_rejected_file_kind()`；
   - 对 `file_kind = binary` 在落盘前直接返回 `failed`；
   - 新增 `_build_unsupported_file_type_message()`，统一输出用户可读错误；
   - 稳定透出 `failure_category = unsupported_file_type`，并确保该场景不触发 runtime/model/index-manager。
2. `tests/api/test_kb_directory_storage.py`
   - 新增 `test_import_files_rejects_binary_upload_before_runtime`；
   - 明确断言：`status = failed`、`path is None`、`file_retained_on_disk = false`、`failure_category = unsupported_file_type`，且 `ensure_models_ready / get_index_manager / load_files` 都不应被调用。

本轮验证命令：
- `python -X utf8 -m pytest tests/api/test_kb_directory_storage.py tests/api/test_image_asset_import.py tests/api/test_ingestion_pipeline.py tests/api/test_index_manager_coverage.py -q`
  - 结果：**96 passed**

本轮运行时证据：
- `docs/20260722-local-multi-kb-assistant/artifacts/runtime/20260731-binary-upload-rejected-runtime.json`
  - 结果：`success_count = 0`、`failed_count = 1`、`indexed_chunks = 0`，且 `file_save_ms = 0`、`primary_index_ms = 0`、`files_on_disk = []`。

这意味着：
1. 导入链路现在不再把未知二进制内容误报为“成功入库”；
2. 当前产品范围与实现边界更加一致：首阶段仍聚焦 Markdown / PDF / 文本 / 图片 OCR 与资产入库，不承诺任意二进制理解；
3. 下一步仍应继续沿主线补真实导入缺陷和问答评测，而不是把范围扩大到未定义格式。


## 20. 2026-07-31 implementation sync: reject `.bin` even when MIME is missing

???????????????????????????????????????? `.bin`?? `content_type` ??????????? `unknown`???????????????

???
1. `_detect_file_kind()` ????? MIME ????????????? `unknown`?
2. ??? `.bin` ??? `content_type` ??????????? binary ?????
3. ?????????????????????????? MIME??????????????

?????????
1. `api/services/kb_service.py`
   - ?? `_detect_file_kind()`????????????????????????? `binary` ????? MIME ???
   - ??????????? `unknown`???????? README ?????????????
   - ?? early-reject ???? diagnostics ??????????????????? `file_kind = unknown`?
2. `tests/api/test_kb_directory_storage.py`
   - ?? `test_import_files_rejects_binary_suffix_without_content_type_before_runtime`?
   - ??????????? runtime??????? `file_kind = binary`?`failure_category = unsupported_file_type`?

???????
- `python -X utf8 -m pytest tests/api/test_kb_directory_storage.py tests/api/test_image_asset_import.py tests/api/test_ingestion_pipeline.py tests/api/test_index_manager_coverage.py -q`
  - ???**98 passed**
- `python -X utf8 -m pytest tests/api/test_chat_single_kb_qa_smoke.py tests/test_rag_quality_eval_dataset_v5.py -q`
  - ???**13 passed**

????????
- `docs/20260722-local-multi-kb-assistant/artifacts/runtime/20260731-binary-suffix-no-content-type-rejected-runtime.json`
  - ???`success_count = 0`?`failed_count = 1`?`indexed_chunks = 0`?? `files_on_disk = []`?

?????
1. ?????????????????????? octet-stream??????????? MIME???????
2. ????????????????? `eval_v5` ?????????????
3. ?????????????????????????????????????????????????

## 21. 2026-07-31 implementation sync: reject extensionless binary payloads without MIME

Another follow-up probe found one more real import bypass after the earlier `.bin` tightening: a file like `README` with `content_type = ""` and raw binary bytes could still pass through as `unknown` and be misreported as a successful import.

Root cause:
1. the earlier hardening used suffix and MIME only, so extensionless payloads still had no strong signal;
2. without suffix and without MIME, the payload stayed `unknown` and still reached the generic import path;
3. this meant obvious binary bytes could still be written and indexed under an extensionless filename.

What was implemented:
1. `api/services/kb_service.py`
   - added a narrow content-sniffing fallback that only runs when both suffix and MIME are missing;
   - classifies extensionless UTF-8 / UTF-16-like text as `text`, so legitimate README-style text files are not over-rejected;
   - classifies clearly binary extensionless payloads as `binary`, so they are rejected before persistence and indexing;
   - carries the inferred `file_kind` into final diagnostics via `file_kind_override`.
2. `tests/api/test_kb_directory_storage.py`
   - added `test_import_files_rejects_extensionless_binary_without_content_type_before_runtime`;
   - added `test_import_files_allows_extensionless_utf8_text_without_content_type` as the non-regression guard.

Verification commands:
- `python -X utf8 -m pytest tests/api/test_kb_directory_storage.py tests/api/test_image_asset_import.py tests/api/test_ingestion_pipeline.py tests/api/test_index_manager_coverage.py -q`
  - result: **100 passed**
- `python -X utf8 -m pytest tests/api/test_chat_single_kb_qa_smoke.py tests/test_rag_quality_eval_dataset_v5.py -q`
  - result: **13 passed**

Runtime evidence:
- `docs/20260722-local-multi-kb-assistant/artifacts/runtime/20260731-extensionless-binary-no-content-type-rejected-runtime.json`
  - result: `success_count = 0`, `failed_count = 1`, `indexed_chunks = 0`, `files_on_disk = []`, and runtime/model/index-manager all stay uncalled.

This means:
1. unsupported extensionless binary payloads are now rejected as early as the explicit `.bin` variants;
2. the hardening stays narrow enough to preserve suffix-less UTF-8 text import;
3. the current product scope remains honest: Markdown / PDF / text / image-OCR import is in, arbitrary binary ingestion is out.


## 22. 2026-07-31 implementation sync: recognize extensionless supported PDF/image payloads without MIME

A new follow-up probe showed that the earlier extensionless-content hardening was still incomplete: supported files already inside product scope could still miss the right import branch when both suffix and MIME were absent.

Observed gap:
1. `manual` + `content_type = ""` + PDF header (`%PDF-...`) could still avoid the dedicated PDF classification and later lose `file_kind` precision in diagnostics.
2. `diagram` + `content_type = ""` + PNG signature could still avoid the image/OCR branch.
3. This was no longer a question of rejecting unsupported binary bytes; it was a question of correctly recognizing supported PDF/image inputs that arrive without filename hints.

What was implemented:
1. `api/services/kb_service.py`
   - added `_detect_file_kind_from_content_signature()` before the generic text/binary sniffing fallback;
   - recognizes supported signature patterns for PDF, PNG, JPEG, GIF, BMP, and WEBP when suffix and MIME are both missing;
   - keeps the inferred `file_kind` through failed-result branches as well, so a dependency-missing PDF still reports `file_kind = pdf` instead of degrading to `unknown`.
2. `tests/api/test_kb_directory_storage.py`
   - added `test_import_files_detects_extensionless_pdf_without_content_type_as_pdf`;
   - added `test_import_files_detects_extensionless_png_without_content_type_as_image`;
   - repaired the affected Chinese docstrings/assertions so the contract is now checked against real semantics.

Verification commands:
- `python -X utf8 -m pytest tests/api/test_kb_directory_storage.py -k "extensionless_pdf_without_content_type or extensionless_png_without_content_type or extensionless_binary_without_content_type or extensionless_utf8_text_without_content_type" -q`
  - result: **4 passed**
- `python -X utf8 -m pytest tests/api/test_kb_directory_storage.py tests/api/test_image_asset_import.py tests/api/test_ingestion_pipeline.py tests/api/test_index_manager_coverage.py -q`
  - result: **102 passed**
- `python -X utf8 -m pytest tests/api/test_chat_single_kb_qa_smoke.py tests/test_rag_quality_eval_dataset_v5.py -q`
  - result: **13 passed**
- `python -X utf8 scripts/verify_stage3_artifacts.py`
  - result: **ok=True** (`manifest_count = 9`, `submit_scope_count = 9`)

This means:
1. extensionless-but-supported PDF/image files now enter the correct product path even without filename or MIME hints;
2. the hardening remains layered and narrow: supported signatures are promoted, unsupported extensionless binary bytes are still rejected by Section 21;
3. the current product statement stays honest: we support Markdown / PDF / text / image-OCR import, not arbitrary unknown binary ingestion.


## 23. 2026-07-31 implementation sync: align standalone image OCR with extensionless supported-image detection

A live follow-up probe showed a remaining gap after Section 22: extensionless PNG payloads were already recognized as `file_kind = image`, but the standalone OCR executor still gated on suffix/MIME only. In practice this meant the import path could classify a file as image and still end with `ocr_skipped`.

What was implemented:
1. `server/readers/image_ocr.py`
   - added `_has_supported_image_signature()` to sniff PNG/JPEG/BMP/WEBP headers directly from the saved file when suffix and MIME are both missing;
   - added `_is_supported_image_input()` so OCR eligibility now accepts either explicit suffix/MIME or a supported image signature;
   - kept the scope intentionally narrow: unsupported text/binary payloads still return `skipped`, so this is not a broad "try OCR on anything" change.
2. `tests/readers/test_image_ocr.py`
   - added `test_extract_image_ocr_result_supports_extensionless_png_without_content_type`;
3. `tests/api/test_kb_directory_storage.py`
   - added `test_import_files_runs_ocr_for_extensionless_png_without_content_type` to cover the import-to-OCR chain instead of only the low-level reader.

Verification commands:
- `python -X utf8 -m pytest tests/readers/test_image_ocr.py -q`
  - result: **16 passed**
- `python -X utf8 -m pytest tests/api/test_kb_directory_storage.py -q`
  - result: **50 passed**
- `python -X utf8 -m pytest tests/readers/test_image_ocr.py tests/api/test_kb_directory_storage.py tests/api/test_image_asset_import.py tests/api/test_ingestion_pipeline.py tests/api/test_index_manager_coverage.py -q`
  - result: **119 passed**
- live HTTP probe artifact: `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18088-extensionless-image-empty-mime.json`
  - observed result: extensionless PNG + empty MIME now reports `ocr_attempted = true`, `ocr_status = no_text`, `ocr_skipped_count = 0`, `asset_registered = true`.

This means:
1. extensionless supported images no longer stop at the wrong `ocr_skipped` branch merely because suffix and MIME are absent;
2. the import classifier and the OCR executor now use consistent support rules for the currently promised image scope;
3. blank images are now reported honestly as `no_text`, which is the correct product behavior for OCR-only image support.


## 24. 2026-07-31 implementation sync: accept extensionless supported files behind generic octet-stream MIME

A follow-up probe after Sections 22 and 23 showed another realistic client-side import gap: some extensionless uploads do not arrive with an empty MIME at all. Instead, they arrive as the generic fallback `application/octet-stream`. Under the previous logic, that generic MIME still blocked content sniffing, so supported payloads could fall back to `binary` even though their bytes were clearly text/image/PDF.

What was implemented:
1. `api/services/kb_service.py`
   - added `_CONTENT_SNIFF_FALLBACK_MIME_TYPES` so extensionless files with generic fallback MIME can reuse the existing signature/text/binary sniffing path;
   - keeps the scope narrow: files with explicit unsupported suffixes are still rejected by suffix, and obvious binary bytes remain `binary`.
2. `server/readers/image_ocr.py`
   - added `_SIGNATURE_SNIFF_FALLBACK_IMAGE_MIME_TYPES` so extensionless supported images with generic MIME can still enter OCR by signature;
   - still requires a supported image signature, so non-image octet-stream payloads do not start OCR.
3. `tests/readers/test_image_ocr.py`
   - added `test_extract_image_ocr_result_supports_extensionless_png_with_octet_stream_content_type`;
4. `tests/api/test_kb_directory_storage.py`
   - added `test_import_files_rejects_extensionless_binary_with_octet_stream_before_runtime`;
   - added `test_import_files_allows_extensionless_utf8_text_with_octet_stream`;
   - added `test_import_files_detects_extensionless_pdf_with_octet_stream_as_pdf`;
   - added `test_import_files_runs_ocr_for_extensionless_png_with_octet_stream`.

Verification commands:
- `python -X utf8 -m pytest tests/readers/test_image_ocr.py -k "extensionless_png_without_content_type or extensionless_png_with_octet_stream_content_type" -q`
  - result: **2 passed**
- `python -X utf8 -m pytest tests/api/test_kb_directory_storage.py -k "extensionless_binary_with_octet_stream or extensionless_utf8_text_with_octet_stream or extensionless_pdf_with_octet_stream or extensionless_png_with_octet_stream" -q`
  - result: **4 passed**
- `python -X utf8 -m pytest tests/readers/test_image_ocr.py tests/api/test_kb_directory_storage.py tests/api/test_image_asset_import.py tests/api/test_ingestion_pipeline.py tests/api/test_index_manager_coverage.py -q`
  - result: **124 passed**
- `python -X utf8 -m pytest tests/api/test_chat_image_ocr_semireal.py tests/api/test_chat_mixed_batch_semireal.py tests/api/test_chat_single_kb_qa_smoke.py -q`
  - result: **22 passed**
- live artifact: `docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/20260731-live-18089-extensionless-octet-fallback-import.json`
  - observed result: extensionless `README` + `application/octet-stream` imports as `text`, extensionless `diagram` + `application/octet-stream` enters OCR as `image/no_text`, and extensionless `BLOB` still fails as unsupported binary.

This means:
1. the import chain now better matches real upload-client behavior instead of only the ideal empty-MIME case;
2. supported extensionless content can recover into the right path even behind a generic binary MIME;
3. the guardrail remains intact: generic MIME is not treated as ?allow everything?, because clear binary payloads are still rejected.
