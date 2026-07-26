# 本地多知识库知识助手平台证据与预览契约设计说明

## 1. 文档定位
- 文档类型：补充设计说明 / 专项 Spec
- 所属目录：`docs/20260722-local-multi-kb-assistant/`
- 对应主 Spec：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec.md`
- 对应实施方案：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-plan.md`
- 对应导入对象模型 Spec：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec-ingestion-object-model.md`
- 对应文件夹模型 Spec：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec-folder-model.md`
- 对应图片 OCR Spec：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec-image-ocr.md`
- 目标：把“回答结果中的证据对象是什么、如何兼容旧 sources、如何稳定打开预览、图片与 OCR 命中如何回指来源”讲成一套正式契约。

---

## 2. 结论先行

### 2.1 一句话结论
**问答系统不能只返回一段答案文本和几条模糊来源字符串；它必须返回结构化 Evidence，并且每条 Evidence 都要能被稳定预览、稳定回指、稳定解释。**

### 2.2 本文坚持的六个判断
1. **`evidence` 是正式契约，`sources` 只是兼容层。**
2. **Evidence 不是 Chunk 本身，而是回答阶段对来源对象的引用包装。**
3. **Preview 不是附件功能，而是 Evidence 能被验证的必要能力。**
4. **`receipt_id` 应保留，它连接导入、问答、Agent 工具与后续追踪。**
5. **`doc_id + preview_locator` 是当前最稳定的预览锚点。**
6. **图片 / OCR 命中最终也要回指到 Document / Asset，而不是只暴露一段派生文本。**

### 2.3 这份文档主要解决什么问题
它重点回答：
- `/api/chat/query` 应该返回什么样的 Evidence；
- 旧 `sources` 字段如何与新 `evidence` 共存；
- `/api/kb/preview` 该如何理解与使用；
- `asset_id`、`doc_id`、`preview_locator`、`evidence_id`、`receipt_id` 各自承担什么职责；
- 为什么这块契约必须先定清楚，前端预览、OCR 资产回指、Agent 回执才会稳。

---

## 3. 现状核实（基于当前代码）

### 3.1 当前已经存在的正式对象
根据当前代码，`EvidenceItem` 已经定义了以下字段：
- `id`
- `title`
- `source`
- `page`
- `score`
- `excerpt`
- `receipt_id`
- `kb_id`
- `doc_id`
- `preview_locator`
- `asset_id`

这说明：P0 需要的核心 Evidence 字段已经基本具备，不是从零开始设计。

### 3.2 当前 chat / agent 已开始共用同一套 evidence 归一化逻辑
当前代码中：
- `api/services/chat_service.py` 已通过 `evidence_service` 统一组装 `sources` 与 `evidence`；
- `normalize_source_nodes()` 负责把节点恢复成兼容型 source；
- `normalize_evidence()` 负责把 source 转成正式 evidence；
- `/api/chat/query` 已同时返回 `sources` 与 `evidence`。

这说明“Evidence First”已经不是纯文档构想，而是正在形成中的正式接口路径。

### 3.3 当前 preview 契约现状
当前代码里：
- `PreviewRequest` 支持 `kb_id`、`doc_id`、`evidence_id`、`preview_locator`；
- `/api/kb/preview` 当前主要按 `doc_id / evidence_id` 返回最小文本预览；
- `PreviewItem` 当前返回：`title`、`kb_id`、`doc_id`、`excerpt`、`locator`、`preview_type`、`evidence_id`；
- `preview_type` 当前是 `text_excerpt` 导向；
- 独立资产预览当前另有 `/api/kb/assets/{asset_id}?kb_id=...` 路由。

### 3.4 当前仍存在的产品级缺口
虽然接口已经起步，但仍有三个需要文档先说清的缺口：
1. **Evidence 与 Preview 的对象语义还没有被单独成文。**
2. **图片 / OCR 命中的预览主路径仍偏文本片段，不是统一的来源对象预览。**
3. **`evidence_id` 当前更像可反解 transport id，不是独立持久化 evidence 实体。**

---

## 4. Evidence 的对象语义

### 4.1 Evidence 是什么
Evidence 是回答结果中的证据引用对象，不等于：
- 原始 Document；
- 原始 Asset；
- 单个 Chunk；
- 单条 OCR 文本节点。

它更准确的定义应该是：
> **Evidence 是回答阶段对底层命中结果做的一层“用户可验证引用包装”。**

所以 Evidence 要同时满足两类需求：
1. **回答可展示**：能把来源、页码、摘录、分数回给用户；
2. **后续可反查**：能打开预览、追踪 receipt、定位到 doc / asset。

### 4.2 Evidence 不应该只是一条字符串来源
如果只返回：
- 文件名；
- 一段来源文本；
- 一个 page 字符串；

会出现两个问题：
1. 前端无法稳定打开原始文档或图片；
2. 用户无法判断这条证据到底来自正文、OCR 还是图片派生文本。

所以 Evidence 一定要从“显示字段”升级成“对象字段”。

---

## 5. 当前推荐的 Evidence 契约

### 5.1 P0 正式字段
当前最推荐的正式字段集合就是现有 `EvidenceItem`：
- `id`
- `title`
- `source`
- `page`
- `score`
- `excerpt`
- `receipt_id`
- `kb_id`
- `doc_id`
- `preview_locator`
- `asset_id`

### 5.2 字段职责解释

#### `id`
- 当前阶段直接作为 `evidence_id` 使用；
- 可以是可反解的引用 id；
- P0 不要求单独引入第二套 evidence 持久化主键体系。

#### `title`
- 面向用户展示的来源标题；
- 通常取文件名或文档标题；
- 应与 preview 打开后的标题保持基本一致。

#### `source`
- 来源显示字段；
- 当前与 `title` 允许相同；
- 未来若区分“显示标题”和“来源路径”，再扩展也不破坏主契约。

#### `page`
- 表示页级或页段级来源信息；
- 对 PDF / OCR 场景尤其重要；
- 当前可为字符串，不急着过早做复杂结构化。

#### `score`
- 表示检索命中分数；
- 是解释性字段，不是用户主心智；
- 前端可以选择弱展示。

#### `excerpt`
- 当前最小可读证据文本；
- 用于回答页内快速浏览；
- 不是完整预览，不应替代 preview 打开动作。

#### `receipt_id`
- 连接导入回执、Agent 工具回执、后续追踪；
- chat 场景可为空；
- agent / tool 路径应尽量回填真实值；
- 不建议删掉。

#### `kb_id`
- 说明证据属于哪个知识库；
- 是范围可见性的最基本字段；
- 任何 preview 或 asset 打开都要受此范围约束。

#### `doc_id`
- 当前最稳定的文档级反查锚点；
- preview 主路径优先依赖它；
- 即使来自 OCR 或资产，也应尽可能回指宿主文档。

#### `preview_locator`
- 用于表达页码、节点、偏移或其他最小定位信息；
- 当前阶段最重要的是“能打开对的位置”，不是一次性设计成极复杂协议；
- 推荐优先覆盖页码和节点定位。

#### `asset_id`
- 用于区分这条证据是否还关联某个图片 / 资产对象；
- 对图片 OCR 命中尤其关键；
- 它让系统知道“这不是纯正文命中，而是可能需要打开图片资产”。

### 5.3 建议的最小 JSON 形态
```json
{
  "id": "ev:base64...",
  "title": "manual.pdf",
  "source": "manual.pdf",
  "page": "15",
  "score": 0.87,
  "excerpt": "关键片段...",
  "receipt_id": null,
  "kb_id": "kb-a",
  "doc_id": "doc-1",
  "preview_locator": {
    "page": "15",
    "node_id": "node-1"
  },
  "asset_id": null
}
```

---

## 6. `sources` 与 `evidence` 的关系

### 6.1 为什么还要保留 `sources`
当前代码与前端仍存在旧兼容路径，因此 P0 不适合暴力删掉 `sources`。
更合理的做法是：
- `sources` 继续保留兼容；
- `evidence` 成为正式字段；
- 新功能、新前端、新 agent 逻辑都优先依赖 `evidence`。

### 6.2 当前推荐映射关系
建议明确以下映射：
- `sources.file -> evidence.title`
- `sources.file -> evidence.source`
- `sources.text -> evidence.excerpt`
- `sources.page -> evidence.page`
- `sources.score -> evidence.score`
- `sources.kb_id -> evidence.kb_id`
- 若 metadata 可恢复，则补 `doc_id / preview_locator / asset_id`

### 6.3 兼容期的产品原则
兼容期内不要让两套字段各说各话。
对同一命中记录，至少应保证：
- `sources[i]` 与 `evidence[i]` 数量一致；
- 核心来源字段语义一致；
- 前端即使还读 `sources`，也不应与 `evidence` 冲突。

---

## 7. Preview 的对象语义

### 7.1 Preview 是什么
Preview 不是“顺便看一下文件”的附属功能，而是 Evidence 的验证动作。

更准确地说：
> **Preview 是把一条 Evidence 重新映射回原始知识对象的最小可验证视图。**

### 7.2 当前 Preview 的最小职责
P0 阶段 Preview 至少要回答：
1. 这条证据来自哪个 KB；
2. 对应哪个 Document；
3. 有没有页码或定位信息；
4. 能给出一段足够核验的 excerpt；
5. 能否从 evidence_id 反解回最小文档定位。

### 7.3 当前 PreviewItem 字段是合理的起点
当前 `PreviewItem`：
- `title`
- `kb_id`
- `doc_id`
- `excerpt`
- `locator`
- `preview_type`
- `evidence_id`

这套字段适合作为 P0 的文本预览起点，但还不能覆盖未来所有图片 / 资产预览场景。

---

## 8. `doc_id + preview_locator` 为什么是当前主路径

### 8.1 这是当前最稳的锚点组合
在当前代码现实下，`doc_id + preview_locator` 的优势是：
- 不依赖额外持久化 evidence 表；
- 能与 docstore 直接配合；
- 能从 chat / agent 结果直接衔接到 preview；
- 能兼容由 `evidence_id` 反解回来的文档定位。

### 8.2 `evidence_id` 当前更像 transport id
当前 `evidence_id` 是可反解、可运输的引用 id，主要用于：
- 在前端点击证据时少传一堆字段；
- 让 `/api/kb/preview` 能恢复出 `doc_id + locator`；
- 在不引入 evidence 持久化表的前提下保持最小闭环。

因此 P0 不应把 `evidence_id` 误解为：
- 稳定持久化的数据库实体 id；
- 可脱离来源对象长期存在的独立对象主键。

### 8.3 为什么这反而是对的
因为你们当前真正需要先做稳的是：
- 能不能打开对的文档；
- 能不能回到对的页；
- 能不能说明这条证据来自哪里；
- 能不能不制造第二套漂浮的对象体系。

---

## 9. 图片、OCR 与资产预览

### 9.1 图片 OCR 命中的正确回指逻辑
当一条证据来自图片 OCR 或资产派生文本时，正确链路不应该停在 OCR 文本上。
应该至少能表达：
- 属于哪个 KB；
- 来自哪个 Document；
- 关联哪个 `asset_id`；
- 若能文本预览，则给出摘录；
- 若用户要看原图，则能打开对应 Asset。

### 9.2 为什么 `asset_id` 不能省
如果图片命中后没有 `asset_id`：
- 系统只能把它伪装成普通正文命中；
- 前端无法稳定打开原图；
- 用户会误以为命中的是正文而不是图片 OCR。

所以 `asset_id` 是图片区分“来源对象类型”的关键字段，而不只是附加信息。

### 9.3 当前产品现实要诚实表达
当前系统现状是：
- `/api/kb/preview` 仍偏文本摘录预览；
- 资产原图预览当前另有 `/api/kb/assets/{asset_id}` 路径；
- 因此“文本证据预览”和“资产原图预览”在 P0 仍是双路径。

这不是问题，但文档必须先明确：
> **P0 阶段允许文本 preview 与资产 preview 并存，但 Evidence 契约必须同时携带能衔接两条路径的字段。**

---

## 10. 对 chat、agent、前端的影响

### 10.1 对 chat 返回体
`/api/chat/query` 推荐长期保持：
- `answer`
- `sources`（兼容）
- `evidence`（正式）
- `scope`（范围回显）

其中真正给前端长期依赖的，应该逐渐切到 `evidence`。

### 10.2 对 agent / tool receipt
Agent 路径应尽量做到：
- 返回正式 evidence；
- 回填真实 `receipt_id`；
- 保留 `kb_id / doc_id / preview_locator / asset_id`；
- 让 agent 工具结果与 chat 结果使用同一套解释模型。

### 10.3 对前端信息架构
前端展示上建议分成两层：
1. **Evidence List**：标题、摘录、页码、来源标识；
2. **Preview Panel**：点击后打开文本片段或资产原图。

也就是说：
- Evidence 解决“列出来”；
- Preview 解决“打开验证”。

---

## 11. P0 / P1 最值得先做的事

### 11.1 P0 先做稳的事情
建议优先保证：
1. `evidence` 字段稳定存在；
2. `sources` 与 `evidence` 映射一致；
3. `receipt_id` 在 chat / agent 场景里的规则写死；
4. `/api/kb/preview` 对 `doc_id / evidence_id` 的行为稳定；
5. 图片 / OCR 命中时 `asset_id` 尽量补齐；
6. 前端先把最小文本预览跑通。

### 11.2 P1 再增强的事情
后续再增强：
- 统一文本 preview 与资产 preview 的入口；
- 更丰富的 `preview_locator` 结构；
- 证据对比、证据分组、跨库证据解释；
- 资产级 preview contract 的正式并轨；
- 是否需要真正持久化的 evidence 实体层。

---

## 12. 最终建议

对这个项目来说，Evidence 与 Preview 不应该被看成“聊天页附属细节”，而应该被看成知识助手是否可信的核心契约。

因此更推荐坚持下面这条顺序：

1. **先把 `evidence` 立为正式字段，`sources` 退为兼容层；**
2. **先把 `doc_id + preview_locator` 做成稳定主路径；**
3. **先保留 `receipt_id`，让 chat / agent / 导入回执能串起来；**
4. **先让图片 / OCR 命中也能回指 `asset_id` 与宿主 Document；**
5. **最后再去考虑更复杂的 evidence 持久化与统一多模态 preview。**

这样做的好处是：
- 问答结果更可信；
- 证据更能被用户验证；
- 图片 / OCR 不会继续沦为黑箱文本；
- Agent 工具与前端展示能共享同一套对象契约。
