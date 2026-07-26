# 本地多知识库知识助手平台导入与嵌入对象模型设计说明

## 1. 文档定位
- 文档类型：补充设计说明 / 专项 Spec
- 所属目录：`docs/20260722-local-multi-kb-assistant/`
- 对应主 Spec：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec.md`
- 对应实施方案：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-plan-ingestion-hardening.md`
- 对应文件夹模型 Spec：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec-folder-model.md`
- 对应图片 OCR Spec：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec-image-ocr.md`
- 目标：把“文件如何导入、对象如何落模、嵌入链路如何承接、回执与诊断如何表达”作为一条完整底座链路讲清楚。

---

## 2. 结论先行

### 2.1 一句话结论
**这个项目最需要先做稳的，不是更炫的 RAG 能力，而是把“导入成功了什么、失败了什么、哪些对象真正入索引了”讲成一条可追踪、可回放、可诊断的对象链路。**

### 2.2 本文坚持的五个判断
1. **导入链路首先产生知识对象，其次才产生嵌入结果。**
2. **Document / Asset / Chunk / EmbeddingRecord 不能混成一个概念。**
3. **OCR、切块、向量化都是派生步骤，不是主对象本身。**
4. **回执和诊断必须是一等契约，不是日志附属品。**
5. **KB 范围必须先成立，导入与嵌入才能继续向下执行。**

### 2.3 这个专项文档解决什么问题
它重点回答四件事：
- 文件进来后，系统里到底会生成哪些对象；
- 哪些对象是用户可感知的，哪些只是系统内部派生结果；
- 嵌入为什么经常“看起来成功、实际上不可追踪”；
- 后续图片、Folder、Agent 接入怎么复用同一条对象链路。

---

## 3. 设计目标与边界

### 3.1 设计目标
本轮导入对象模型设计，至少要满足：
1. 能覆盖 Markdown、PDF、纯文本、独立图片等主流导入来源；
2. 能把目录导入、单文件导入、Markdown 内嵌资源纳入同一对象模型；
3. 能把导入结果、OCR、切块、嵌入、索引写入拆成可诊断步骤；
4. 能给前端、问答、证据、删除、重导入提供稳定对象锚点；
5. 不和未来独立存储、物理隔离、更多模态扩展冲突。

### 3.2 本文不解决的事情
本专项 Spec 暂不展开：
- 更复杂的多模态理解与图像语义解析；
- 更换向量库或重写检索框架；
- 多用户组织级权限系统；
- 高级工作流编排与 Agent 执行策略。

---

## 4. 推荐的对象层级

### 4.1 端到端对象链路
```text
KnowledgeBase
└─ Folder（可选）
   └─ Document / Asset
      └─ Derived Text
         └─ Chunk
            └─ EmbeddingRecord

另有横切对象：
- IngestionJob
- IngestionReceipt
- Diagnostics
- Evidence
```

### 4.2 用户可感知对象 vs 系统派生对象

#### 用户可感知对象
- **KnowledgeBase**：范围边界与归属边界；
- **Folder**：组织层；
- **Document**：来源文档；
- **Asset**：图片、附件、页面内资源等知识资产；
- **Evidence**：问答时展示给用户的证据包装对象。

#### 系统派生对象
- **Derived Text**：OCR 文本、资源文本化结果、结构化抽取文本；
- **Chunk**：检索与召回单元；
- **EmbeddingRecord**：向量化结果与状态；
- **Diagnostics**：导入链路上的错误、警告、跳过原因。

### 4.3 一个重要原则
**用户看到的是来源对象，系统检索的是派生对象。**
也就是说：
- 用户删除的是 Document / Asset；
- 系统索引的是 Chunk / Embedding；
- 回答命中后必须能回指到 Document / Asset；
- 不能让派生对象反客为主，变成唯一可见对象。

---

## 5. 核心对象定义

### 5.1 IngestionJob
IngestionJob 是一次导入执行任务的顶层对象，用于表达“这一批资料被如何处理”。

建议最小字段：
- `job_id`
- `kb_id`
- `trigger_type`（目录导入 / 单文件导入 / 重导入等）
- `source_type`（local_dir / local_file / url 等）
- `status`
- `started_at`
- `finished_at`
- `summary`

### 5.2 Document
Document 是来源文档对象，是用户最重要的“原始知识载体”。

建议最小字段：
- `doc_id`
- `kb_id`
- `folder_path`（可为空）
- `source_rel_path`
- `title`
- `mime_type`
- `ingestion_job_id`
- `ingestion_receipt_id`
- `status`
- `created_at`
- `updated_at`

### 5.3 Asset
Asset 是文档内部或独立存在的知识资产，当前优先覆盖图片与扫描件。

建议最小字段：
- `asset_id`
- `kb_id`
- `doc_id`（独立图片可为空或指向虚拟宿主）
- `folder_path`
- `source_rel_path`
- `asset_type`（image / attachment / page_image 等）
- `mime_type`
- `preview_locator`
- `ingestion_job_id`
- `status`

### 5.4 Derived Text
Derived Text 表示从原始对象派生出的可文本化结果，它是 OCR / 提取 / 转写后的中间语义层。

建议字段：
- `derived_text_id`
- `kb_id`
- `source_object_type`（document / asset）
- `source_object_id`
- `derived_type`（ocr_text / extracted_text / normalized_markdown_text 等）
- `text`
- `quality_signal`
- `diagnostics`

### 5.5 Chunk
Chunk 是当前主检索与召回单元。

建议字段：
- `chunk_id`
- `kb_id`
- `doc_id`
- `asset_id`（可为空）
- `derived_text_id`（可为空）
- `chunk_index`
- `text`
- `metadata`
- `status`

### 5.6 EmbeddingRecord
EmbeddingRecord 用于表达某个 Chunk 的向量化与写库状态。

建议字段：
- `embedding_id`
- `chunk_id`
- `kb_id`
- `model_name`
- `vector_dim`
- `embedding_status`
- `index_write_status`
- `error_message`
- `updated_at`

### 5.7 IngestionReceipt
Receipt 是这次设计里非常关键的对象：它不是日志，而是对外契约。

它至少应该回答：
- 成功登记了哪些 Document / Asset；
- 哪些对象形成了 Derived Text；
- 哪些 Chunk 成功入索引；
- 哪些步骤失败、跳过或质量不足；
- 用户现在能预览什么、能检索什么、还缺什么。

建议最小字段：
- `receipt_id`
- `job_id`
- `kb_id`
- `requested_source`
- `documents`
- `assets`
- `derived_texts`
- `chunks`
- `diagnostics`
- `summary`
- `created_at`

---

## 6. 标准导入阶段划分

### 6.1 推荐拆成六个阶段
1. **范围确认**：先校验 `kb_id`、范围状态、是否允许导入。
2. **来源登记**：识别目录、文件、Markdown 资源、图片等来源对象。
3. **主对象落模**：创建 Document / Asset。
4. **文本派生**：正文抽取、Markdown 清洗、PDF OCR 回退、图片 OCR。
5. **检索派生**：切 Chunk、做 Embedding、写索引。
6. **回执生成**：形成 Receipt + Diagnostics + Summary。

### 6.2 为什么必须分阶段
如果不分阶段，就会出现三类典型问题：
- “文件导入了，但到底有没有入索引不清楚”；
- “嵌入报错了，但前端只看到一个模糊失败”；
- “删除和重导入时，不知道该撤销哪些派生对象”。

### 6.3 当前建议的状态表达
每一层对象都不应只用一个粗暴的 success / failed。
更建议表达为：
- `registered`
- `parsed`
- `derived`
- `chunked`
- `embedded`
- `indexed`
- `skipped`
- `failed`

这样才能准确回答“到底失败在第几层”。

---

## 7. 典型来源的落模规则

### 7.1 Markdown 文件
推荐落模：
- Markdown 本体创建为 Document；
- 正文文本转为 Derived Text 或直接进入 Chunk 前步骤；
- 内嵌图片创建为 Asset；
- 资产 OCR 成功后形成独立 Derived Text；
- 所有派生对象都保留宿主 Document 与路径信息。

### 7.2 PDF 文件
推荐落模：
- PDF 本体是 Document；
- 文字层抽取优先；
- 文字层质量差时走 OCR 回退；
- 页内图片或截图可按能力抽取为 Asset；
- 文本结果最终统一进入 Chunk / Embedding 主链路。

### 7.3 独立图片文件
推荐落模：
- 图片本体直接创建为 Asset；
- 若需要，也可挂接到一个轻量 Document 语义下，但不强制；
- OCR 成功则生成 Derived Text；
- 命中时 Evidence 必须能打开原图，而不是只给 OCR 文本。

### 7.4 目录导入
推荐落模：
- 先明确 `kb_id`；
- 保留 `folder_path` 和 `source_rel_path`；
- 目录结构映射为 Folder 语义；
- 同一批次由一个 IngestionJob 统领；
- 回执按文件粒度与对象粒度双重回显。

---

## 8. 回执与诊断契约

### 8.1 回执必须回答的五个问题
1. **导入了什么？**
2. **哪些对象只是登记成功，哪些已经可检索？**
3. **哪些对象 OCR / 解析失败？**
4. **失败后是否仍可预览原对象？**
5. **用户接下来该怎么修复或重试？**

### 8.2 建议的诊断维度
Diagnostics 至少覆盖：
- `severity`（info / warning / error）
- `stage`（register / parse / derive / chunk / embed / index）
- `object_type`（document / asset / chunk）
- `object_id`
- `code`
- `message`
- `repair_hint`

### 8.3 为什么 receipt_id 应继续保留
`receipt_id` 很重要，因为它能连接：
- 导入页；
- 问答证据；
- 错误追踪；
- 删除 / 重导入；
- 后续 Agent 工具调用结果。

它不应该被视为一次性调试字段，而应是稳定契约的一部分。

---

## 9. 与问答、证据、预览的关系

### 9.1 问答检索命中的其实是派生对象
当前主检索通常命中的是 Chunk，而不是 Document 原件。
但回答输出不能只回一个 chunk 文本，必须能补足：
- 来自哪个 KB；
- 来自哪个 Folder；
- 来自哪个 Document / Asset；
- 是否来自 OCR / 图片派生文本；
- 对应哪个 receipt_id / preview_locator。

### 9.2 证据对象的建议回指链路
推荐回指顺序：
`Evidence -> Chunk -> Derived Text -> Document / Asset -> Preview`

这样做的好处是：
- 问答层不直接依赖底层索引细节；
- 前端能稳定展示来源；
- 删除或重导入时能精确失效相关证据。

---

## 10. 删除、重导入与一致性

### 10.1 删除不能只删向量
如果用户删除一个 Document / Asset，系统需要同步处理：
- 主对象可见性；
- Derived Text；
- Chunk；
- EmbeddingRecord；
- Receipt / Diagnostics 的关联状态。

否则就会出现“前端看不到，检索仍命中”的脏数据问题。

### 10.2 重导入不能变成黑盒覆盖
重导入时应尽量保留：
- 原始来源路径；
- 原对象标识或可追踪映射；
- 新旧 Receipt 的关联；
- 哪些对象是替换、哪些是新增、哪些是删除。

### 10.3 为什么这对你们当前很重要
因为现在你们遇到的很多“导入嵌入问题”，本质不是模型效果问题，而是对象边界和状态边界不清：
- 不知道失败点在哪；
- 不知道哪些对象已经落库；
- 不知道问题出在解析、OCR、切块还是索引写入；
- 不知道后续删除 / 重导入会不会留下脏数据。

---

## 11. 与 Folder、图片 OCR、Agent 的协同关系

### 11.1 与 Folder 模型的关系
- Folder 提供组织路径；
- Ingestion 对象模型负责把来源落成对象链路；
- 两者结合后，才能形成稳定的 `kb -> folder -> document / asset -> chunk` 表达。

### 11.2 与图片 OCR 的关系
- 图片 OCR 不是单独系统，而是导入对象模型中的一个派生步骤；
- 图片本体始终先是 Asset；
- OCR 只是让 Asset 衍生出可检索文本；
- 命中后仍需回指 Asset 原图。

### 11.3 与 Agent 接入的关系
未来如果对外开放导入或查询工具，Agent 至少要能拿到：
- 明确声明的 `kb_id`；
- 返回的 `receipt_id`；
- 对象粒度的导入结果；
- 不成功阶段的诊断信息。

否则 Agent 只能得到“好像成功了”的模糊反馈，不具备可执行性。

---

## 12. P0 / P1 最值得先落的事情

### 12.1 P0 最小闭环
建议先确保：
1. 每次导入都有 IngestionJob 与 Receipt；
2. Document / Asset 有稳定主对象语义；
3. Chunk 与 Embedding 状态可诊断；
4. Receipt 能表达“已登记 / 已入索引 / 已失败 / 可预览”；
5. 问答 Evidence 能回显 `kb_id + folder_path + doc_id/asset_id + receipt_id`。

### 12.2 P1 增强方向
再往后可以增强：
- 更完整的 Folder 对象落模；
- 更细粒度的删除 / 重导入策略；
- 资产独立检索与更强预览；
- 更完整的 OCR / caption / 结构化文本派生；
- 跨库聚合与更强对象对比能力。

---

## 13. 最终建议

对这个项目来说，导入与嵌入底座最重要的不是“多快做出更多索引”，而是“把对象链路说明白”。

所以更推荐你们坚持下面这条顺序：

1. **先把 KnowledgeBase / Folder / Document / Asset / Chunk 的对象边界讲清楚；**
2. **再把 OCR、切块、嵌入、索引写入定义成派生步骤；**
3. **再把 Receipt / Diagnostics 做成正式契约；**
4. **最后再去优化更多模态、更多 Agent、更多自动化能力。**

这样做的收益是：
- 当前导入问题更容易定位；
- 前端状态更容易解释；
- 删除与重导入更不容易出脏数据；
- 后续物理隔离、图片增强、Agent 接入也都更容易接上同一底座。
