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

## 4. 本轮目标与非目标

### 4.1 本轮目标
本轮只做下面四类稳定性加固：
1. 删除链路面对历史脏引用时不再轻易炸掉；
2. 导入计数与真实成功结果对齐，消除显著的 `doc_count` 漂移；
3. 导入结果从“总量成功”升级为“最小可追踪的逐项结果”；
4. 补齐导入 / 删除 / 重导入相关回归测试，为后续 P0-3 和多模态扩展清路。

### 4.2 本轮明确不做
本轮不做：
1. 物理隔离 / 独立命名空间；
2. 完整 Asset 对象模型落地；
3. Markdown 内嵌图片抽取；
4. OCR 质量优化与流程图语义理解；
5. 全量引入 IngestionJob 持久化存储；
6. 把所有导入接口一次性改成全新协议；
7. 全面开放 Agent 写路径。

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

因此，本轮实施方案明确建议：
1. 先把这条稳定性链路补平；
2. 再继续推进 P0-3 资产对象；
3. 让后续多模态、目录层级、Agent 化能力建立在一个至少“结果可信、失败可见、计数正确、删除可控”的底座之上。
