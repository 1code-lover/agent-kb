# 本地多知识库知识助手平台图片 OCR 最小闭环增量设计（Spec）

## 1. 文档信息
- 文档版本：v0.1
- 文档状态：P0 增量设计，作为现有多知识库主线的补充 Spec
- 创建日期：2026-07-24
- 所属目录：`docs/20260722-local-multi-kb-assistant/`
- 关联主 Spec：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec.md`
- 关联 PRD：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-prd.md`
- 关联 FRD：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-frd.md`
- 关联主 Plan：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-plan.md`
- 文档定位：**不是重写产品定位，而是在现有“资产对象”方向上，补齐“图片入库 + OCR 提取 + OCR 文本入索引 + 回答回指原图”的最小闭环设计。**

---

## 2. 背景与问题定义

### 2.1 当前真实现状
当前代码已经做到了“图片资产化”的一部分，但还没有正式做到“图片 OCR 知识化”。

目前已存在的能力：
1. 独立图片文件导入后，可以登记为 `standalone asset`；
2. Markdown 内嵌图片可以被抽取并登记为 `embedded asset`；
3. 资产可被列出、预览、被回答证据引用；
4. PDF 阅读链路具备“文字层优先 + OCR 回退”能力。

当前尚未正式具备的能力：
1. 独立图片文件统一走 OCR 提取；
2. 图片 OCR 结果作为派生文本节点进入索引；
3. 检索结果明确区分“正文命中”与“图片 OCR 命中”；
4. 回答结果稳定回指到原始图片资产，而不只是返回松散文本片段。

### 2.2 当前问题
如果停留在“图片只做资产登记”，则用户只能：
1. 看见图片；
2. 预览图片；
3. 在回答中被动看到图片引用。

但用户还不能稳定做到：
1. 通过问题命中图片中的文字内容；
2. 把截图、扫描件、图中文字纳入知识检索；
3. 在回答里看到“这段内容来自哪张图”。

### 2.3 本文档要解决的最小问题
本文档只解决一个非常收敛的问题：

> **让图片先成为“可入库的资产对象”，再让其中可提取的文字成为“可检索的派生文本”，并在回答时能回到原图。**

这不是多模态全量方案，而是图片知识化的 P0 最小闭环。

---

## 3. 设计目标与非目标

### 3.1 P0 目标
P0 只交付以下 5 件事：
1. 独立图片文件导入后可稳定登记为资产；
2. 支持的图片类型可执行 OCR；
3. OCR 文本可切块并进入现有索引链路；
4. 问答可命中图片 OCR 文本；
5. 命中后回答可回指原图预览，而不是只返回裸文本。

### 3.2 In Scope
本轮纳入范围：
1. 独立图片文件 OCR；
2. 与图片 OCR 对应的派生文本节点模型；
3. 导入回执中的 OCR 诊断字段；
4. 检索 / 证据返回中对图片 OCR 来源的显式标识；
5. 与 KB 范围控制一致的隔离要求。

### 3.3 Out of Scope
本轮明确不做：
1. 流程图结构语义理解；
2. caption / 图像描述生成；
3. 视觉 embedding / 图搜图；
4. UI 截图语义理解；
5. 手写体高可靠识别承诺；
6. PDF 图像区域级细粒度抽取；
7. 复杂多模态 rerank。

### 3.4 产品承诺边界
P0 对用户承诺的是：
- **可读文字进入知识库**；
- **原图仍可预览与引用**；
- **OCR 失败不阻断图片入库**。

P0 不承诺的是：
- 理解图片整体语义；
- 理解流程图中的箭头逻辑；
- 对手写、低清、强噪声图像提供稳定高精度识别。

---

## 4. 核心设计决策

### 4.1 图片本体与图片文本必须分层
本轮坚持以下分层：
1. **图片本体 = Asset Object**；
2. **图片 OCR 结果 = Derived Text Node**；
3. **问答命中主要发生在 OCR 文本节点上**；
4. **证据展示与预览回到图片资产本体。**

这样做的好处：
1. 不把二进制图片直接硬塞进文本知识模型；
2. 不破坏现有证据与预览链路；
3. 后续如要加入 caption / vision embedding，仍有稳定挂载点。

### 4.2 OCR 失败不等于导入失败
本轮必须坚持：
1. 图片文件只要成功落盘并登记为 asset，就不应因为 OCR 失败而整体导入失败；
2. OCR 失败、OCR 无文本、OCR 跳过，统一通过 diagnostics 向上表达；
3. 前端应能区分“图片已入库但尚未形成可检索文本”和“图片 OCR 成功并已入索引”。

### 4.3 P0 不新增复杂图片理解链路
P0 只引入一个新的处理动作：
- `image -> OCR -> text nodes -> index`

P0 不引入：
- `image -> caption -> summary -> rerank`
- `image -> visual embedding -> multimodal retrieval`
- `image -> structure graph -> reasoning`

### 4.4 保持现有返回状态尽量稳定
为降低前后端联动成本，P0 优先保持现有文件级 `status` 语义不大改：
1. `indexed`：图片 OCR 产出可索引文本并成功入索引；
2. `empty`：图片已作为 asset 入库，但未产出可索引文本；
3. `failed`：文件导入链路本身失败，连 asset 登记都未完成或无法保证一致性。

P0 不强行新增 `asset_only` 等新状态码；若后续用户体验需要，再在 P1 讨论。

---

## 5. 支持范围

### 5.1 建议优先支持的图片类型
P0 优先支持：
1. `.png`
2. `.jpg`
3. `.jpeg`
4. `.webp`
5. `.bmp`
6. 如当前 OCR 依赖链允许，可评估 `.tiff`

### 5.2 优先支持的内容类型
P0 优先面向：
1. 扫描页图片；
2. 文档截图；
3. 表格截图；
4. 含较多印刷体文字的流程图 / 架构图；
5. 其他“以可读文字为主”的图片。

### 5.3 暂不重点优化的内容类型
P0 不作为优化重点：
1. 纯装饰图；
2. logo；
3. 极小图标；
4. 纯照片类图片；
5. 复杂手写白板图。

---

## 6. 对象模型

### 6.1 Asset Object（沿用现有方向，补充 OCR 语义）
图片本体继续作为 `asset object` 管理，核心字段保持：
- `asset_id`
- `kb_id`
- `source_doc_id`
- `source_doc_relative_path`
- `asset_type`
- `asset_role`
- `title`
- `path`
- `relative_path`
- `mime_type`
- `locator`
- `status`

本轮不要求把 OCR 文本塞进 asset registry 本体中，以免 registry 膨胀和职责混乱。

### 6.2 OCR Derived Text Node
图片 OCR 的索引单元作为派生文本节点存在，而不是独立用户可见主对象。

建议 OCR 节点 metadata 至少包含：
- `kb_id`
- `asset_id`
- `source_type = image_ocr`
- `file_path`
- `relative_path`
- `file_name`
- `mime_type`
- `source_doc_id`（若图片来自宿主文档则可选）
- `source_doc_relative_path`（若存在）
- `ocr_engine`
- `ocr_confidence`（若 OCR 引擎可提供则可选）

### 6.3 Evidence 引用关系
当回答命中图片 OCR 节点时，Evidence 至少应能还原：
- 命中的文字片段；
- 来自哪个 `asset_id`；
- 是否存在宿主文档；
- 如何打开图片预览；
- 来源类型是 `image_ocr`，不是普通正文 chunk。

---

## 7. 导入与处理链路

### 7.1 最小处理流水线
建议把图片导入拆成以下阶段：

1. **落盘 / 复制到 KB 目录**
   - 与现有文件导入一致，先保证文件进入 KB 目录边界。
2. **资产登记**
   - 先登记 `asset object`，确保图片至少可被列出与预览。
3. **OCR 提取**
   - 对支持格式尝试 OCR。
4. **文本归一化**
   - 清洗 OCR 结果中的空白、重复换行、极端噪声片段。
5. **切块与索引**
   - 只有存在有效文本时才生成节点并入索引。
6. **回执汇总**
   - 返回文件级状态、OCR 状态、诊断信息。

### 7.2 为什么先登记 asset 再做 OCR
顺序必须是：
- **asset first，OCR second**。

原因：
1. OCR 失败时，图片仍然应该是库内资产；
2. 证据预览依赖图片本体，而不是 OCR 成败；
3. 这样才符合“图片是对象，OCR 是派生能力”的设计原则。

### 7.3 OCR 成功判定
建议以“是否产出可索引文字”为主判定标准：
1. OCR 文本为空或只有极少噪声字符，不入索引；
2. OCR 文本通过最小质量门槛后，才生成文本节点；
3. 若 OCR 引擎返回置信度，可作为辅助诊断字段，但不作为唯一准入门槛。

### 7.4 与现有 PDF OCR 的关系
本轮设计与现有 `pdf_ocr.py` 不冲突，但也不等同：
1. 现有 PDF OCR 是“PDF reader 的 fallback”；
2. 本轮要补的是“独立图片文件的 OCR 入口”；
3. 两者后续可复用同一 OCR 基础能力，但当前应在职责上区分清楚。

---

## 8. 导入结果与诊断契约

### 8.1 文件级 status 语义
本轮建议保持：
1. `indexed`：asset 已登记，OCR 成功且有文本入索引；
2. `empty`：asset 已登记，但 OCR 未产出可索引文本；
3. `failed`：文件导入整体失败。

### 8.2 建议新增 diagnostics 字段
在现有 diagnostics 基础上，建议补充：
- `ocr_attempted: bool`
- `ocr_status: success | no_text | skipped | failed`
- `ocr_text_length: int`
- `ocr_error: str | null`
- `indexed_from_ocr: bool`
- `asset_registered: bool`

### 8.3 诊断语义示例
#### 情况 A：图片成功 OCR 并入索引
- `status = indexed`
- `asset_registered = true`
- `ocr_attempted = true`
- `ocr_status = success`
- `indexed_from_ocr = true`

#### 情况 B：图片已入库但 OCR 无文本
- `status = empty`
- `asset_registered = true`
- `ocr_attempted = true`
- `ocr_status = no_text`
- `indexed_from_ocr = false`

#### 情况 C：图片已入库但 OCR 执行失败
- `status = empty`
- `asset_registered = true`
- `ocr_attempted = true`
- `ocr_status = failed`
- `ocr_error` 填写失败原因

#### 情况 D：图片格式不在 OCR 支持范围
- `status = empty`
- `asset_registered = true`
- `ocr_attempted = false`
- `ocr_status = skipped`

---

## 9. 检索与回答契约

### 9.1 检索层要求
当命中图片 OCR 节点时，系统必须能区分：
1. 这是正文 chunk 还是图片 OCR chunk；
2. 对应哪个 `asset_id`；
3. 应该回到哪个预览入口。

### 9.2 建议的来源标记
建议在检索结果与标准化 evidence 中显式保留：
- `source_type = image_ocr`
- `asset_id`
- `doc_id`（可选）
- `preview_locator`
- `excerpt`

### 9.3 回答层最小要求
问答结果中只要引用了图片 OCR 证据，就应该满足：
1. 文本摘录可见；
2. 图片预览入口可用；
3. 用户能知道“这是图片 OCR，不是正文原文”。

---

## 10. 兼容性与迁移策略

### 10.1 与当前资产化能力兼容
本轮设计建立在当前 asset registry / asset preview / evidence preview 能力之上，不推翻现有资产对象模型。

### 10.2 与当前索引链路兼容
本轮优先复用现有文本切块与索引链路，只新增一个来源类型：
- `image_ocr`

而不是为图片 OCR 重新建设另一套独立索引系统。

### 10.3 与前端兼容
前端优先复用现有：
1. 导入结果展示；
2. 证据面板；
3. 资产预览面板。

本轮主要新增的是：
1. OCR 状态展示；
2. “图片已入库但未形成文本”与“图片已形成可检索文本”的差异提示。

---

## 11. 建议改动范围

### 11.1 后端建议关注文件
- `api/services/kb_service.py`
- `api/services/asset_service.py`
- `api/services/evidence_service.py`
- `server/index.py`
- `server/readers/` 下图片 OCR 相关能力入口（新增或复用）
- `api/schemas/__init__.py`

### 11.2 测试建议关注文件
- `tests/api/test_image_asset_import.py`
- `tests/api/test_chat_evidence_contract.py`
- `tests/api/test_m2_multi_kb.py`（如问答范围需要回归）
- 新增：独立图片 OCR 导入 / 检索 / 引证测试

### 11.3 前端建议关注文件
- `webapp/src/pages/KnowledgePage.jsx`
- `webapp/src/domain/importSummary.js`
- `webapp/src/components/kb/KbEvidencePreview.jsx`
- `webapp/src/components/agent/AgentEvidencePanel.jsx`

---

## 12. 测试要点

### 12.1 正常路径
1. 导入一张含清晰文字的独立图片；
2. 图片被登记为 asset；
3. OCR 成功；
4. OCR 文本入索引；
5. 问答能命中该文本；
6. 回答证据可打开原图。

### 12.2 异常路径
1. 图片可入库但 OCR 无文本；
2. OCR 执行失败但 asset 仍可预览；
3. OCR 不支持的图片格式被跳过；
4. 同一 KB 与跨 KB 的查询隔离仍然成立。

### 12.3 回归重点
1. 不能破坏已有 standalone / embedded asset 列表与预览；
2. 不能把所有图片一律误判为 `indexed`；
3. 不能因为 OCR 失败导致导入整批回滚；
4. 不能让图片 OCR 命中绕过 KB 范围控制。

---

## 13. 风险与取舍

### 13.1 最大风险
最大的风险不是 OCR 能不能跑，而是“把图片 OCR 做成一条不清不楚的半文本链路”，导致：
1. 图片本体与 OCR 文本混淆；
2. 前端无法解释导入结果；
3. 回答命中后无法回到原图；
4. 后面加 caption / 多模态时再次返工。

### 13.2 本轮取舍
本轮明确选择：
1. 先做图片资产 + OCR 文本派生；
2. 不做复杂多模态；
3. 保持 `status` 尽量稳定，优先在 diagnostics 扩展语义；
4. 先把最小闭环跑通，再讨论图片理解深度。

---

## 14. 结论

这份增量 Spec 的核心判断是：

> **图片在 P0 阶段应先是“资产对象”，再通过 OCR 派生出“可检索文本”；问答命中的主要是 OCR 文本，但用户看到和打开的应始终是原图资产。**

这样做有 3 个直接收益：
1. 当前代码可以在已有资产化基础上自然演进；
2. 用户立刻获得“图片可搜、可问、可回看原图”的真实价值；
3. 后续要接 caption、流程图理解、视觉 embedding 时，不需要推翻当前对象边界。