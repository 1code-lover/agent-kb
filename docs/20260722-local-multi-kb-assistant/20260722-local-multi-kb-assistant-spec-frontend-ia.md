# 本地多知识库知识助手前端信息架构专项 Spec

## 1. 文档信息
- 文档版本：v0.1
- 文档状态：前端信息架构专项基线
- 创建日期：2026-07-25
- 所属目录：`docs/20260722-local-multi-kb-assistant/`
- 关联主 Spec：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec.md`
- 关联文件夹模型专项：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec-folder-model.md`
- 关联导入对象模型专项：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec-ingestion-object-model.md`
- 关联证据与预览契约专项：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec-evidence-preview-contract.md`

---

## 2. 一句话结论

前端主心智应收敛为：**先选择 KnowledgeBase，再在 KnowledgeBase 内组织、导入、浏览和消费知识**；不再让用户在多个历史页面之间切换“上传、管理、问答”来拼装完整体验。

---

## 3. 本文要回答的问题

本文重点回答 5 个问题：

1. 这个产品前端到底应该围绕什么对象组织，而不是围绕什么技术动作组织？
2. `KnowledgePage` 与 `AgentPage` 各自应该承担什么角色？
3. KnowledgeBase 内部为什么需要 `Folder -> Document / Asset -> Evidence / Preview` 这一层级？
4. 现有旧路由 `/kb-file`、`/kb-web`、`/kb-manage` 应该如何归宿？
5. P0 / P1 前端演进应该先做什么，后做什么？

---

## 4. 代码核实后的前端现状

### 4.1 当前路由现状

当前前端路由集中在 `webapp/src/App.jsx`，实际可见路由包括：

- `/` -> `AgentPage`
- `/agent` -> `AgentPage`
- `/knowledge` -> `KnowledgePage`
- `/kb-file`
- `/kb-web`
- `/kb-manage`
- 以及 `/settings`、`/models`、`/storage`、`/advanced`

这说明当前项目事实上已经形成了“`AgentPage` + `KnowledgePage`”双主入口，但历史 KB 页面路由仍保留在代码中，属于兼容入口，而不是新的主产品结构。

### 4.2 KnowledgePage 已经具备的能力

基于 `webapp/src/pages/KnowledgePage.jsx`、`KbSidebar.jsx`、`KbDocumentList.jsx`、`KbUpload.jsx`、`KbWebImport.jsx` 的代码核实，当前 `KnowledgePage` 已经具备以下基础能力：

1. 左侧 `KbSidebar` 负责知识库列表、显式选择、新建、改名、删除。
2. `KbContext` 负责全局知识库状态，且只允许选中 `active` 知识库。
3. 右侧主区域已有 3 个标签页：
   - `docs`：文档列表
   - `upload`：文件上传
   - `web`：网页导入
4. 文件上传和网页导入都已经强制绑定 `selectedKbId`，不会默认写入“全部知识库”。
5. 文档列表已经严格按当前所选知识库查询与展示。

这说明产品已经具备“按 KB 显式操作”的前端雏形，但仍停留在**平铺功能页**阶段，而不是**对象化信息架构**阶段。

### 4.3 AgentPage 已经具备的能力

基于 `webapp/src/pages/AgentPage.jsx`、`webapp/src/api/evidence.js`、`KbEvidencePreview.jsx` 的代码核实，当前 `AgentPage` 已经具备：

1. 与 `KnowledgePage` 共用 `KbProvider` / `KbContext`，说明“问答范围”已经与“知识库选择”绑定。
2. 问答返回同时包含 `sources` 与 `evidence`，其中 `evidence` 是正式契约。
3. 点击证据后可走统一 `previewItem()` 预览链路。
4. 前端预览优先级已经统一为：`asset_id > doc_id > evidence_id`。
5. `KbEvidencePreview` 已支持文本证据预览与资产元数据预览两种最小展示形态。

这说明“证据可点击、可预览、可回溯”的基础链路已经存在，但还没有被上升为完整前端 IA 的主结构。

### 4.4 当前前端 IA 的不足

尽管已有基础能力，但目前信息架构仍存在明显缺口：

1. **KnowledgeBase 内部仍是平铺文档列表心智**，还没有 `Folder` 树。
2. **Document 与 Asset 尚未在浏览层被统一表达**，图片、流程图、OCR 派生文本仍缺少产品对象入口。
3. **导入回执 / 诊断结果还没有稳定的产品视图**，成功与失败反馈仍偏临时提示。
4. **Evidence / Preview 更像回答附属物，而不是验证答案可信度的正式动作层。**
5. **旧页面路由仍存在，会干扰用户对主线入口的理解。**

因此，下一阶段前端设计的重点不是继续堆 tab，而是把对象层与使用层梳理出来。

---

## 5. 前端 IA 的核心设计判断

### 5.1 顶层不是“上传 / 管理 / 问答”，而是“管理知识 / 使用知识”

前端顶层应收敛为两条主线：

1. **Knowledge Page**：管理知识对象
2. **Agent / Ask Page**：消费知识对象

这样划分的原因是：

- 上传、网页导入、目录导入、本地拖拽，本质都属于“形成知识对象”的动作，应归入管理侧。
- 提问、证据查看、预览、回答验证，本质都属于“消费知识对象”的动作，应归入问答侧。
- 如果继续以“文件上传页 / 网页导入页 / 问答页”平行并列，会把“动作”误当成“产品对象”。

### 5.2 KnowledgeBase 是前端第一层对象

无论从产品原则还是当前安全边界看，前端都必须坚持：

- 用户先进入一个 `KnowledgeBase`
- 再在这个 KB 内进行导入、浏览、删除、问答
- Evidence / Preview 也必须带着 KB 上下文展开

这和当前“未声明范围默认拒绝”的后端收口是一致的。前端不能再提供任何“默认全库”心智。

### 5.3 Folder 是 KB 内组织层，不是另一个权限层

前端应支持 Folder，但要明确向用户表达：

- Folder 用来组织资料
- Folder 不承担安全边界职责
- Folder 不是 mini-KB
- Folder 不应该替代 KnowledgeBase 选择

也就是说，Folder 是提升可管理性的 UI / 内容层对象，而不是访问控制对象。

### 5.4 Evidence / Preview 必须进入主信息架构，而不是作为小挂件存在

对于知识助手产品，用户真正关心的不只是“模型回答了什么”，而是：

- 这句话来自哪个文档 / 哪个图片 / 哪一页
- 我能不能点开看
- 我能不能回到原对象

所以 Evidence / Preview 在前端里不是附属功能，而是“验证答案”的正式层级。它应成为从回答返回知识对象的桥，而不是一段边缘来源文本。

---

## 6. 推荐的前端信息架构分层

### 6.1 App Level

应用顶层推荐保持以下主导航：

- **Ask / Agent**：面向提问、对话、执行
- **Knowledge**：面向知识对象管理
- **Models / Settings / Storage / Advanced**：系统支撑页

其中：

- `Ask / Agent` 与 `Knowledge` 是业务主线。
- 配置类页面不应与业务主线争夺主导航心智。
- 历史 KB 专页不应继续作为主导航项暴露。

### 6.2 Knowledge Level

进入 `Knowledge` 后，第一层仍然是“知识库列表 / 当前知识库”。推荐结构：

- 左侧：KnowledgeBase 列表
- 右侧：当前 KB 工作区

左侧的主要职责：

- 查看 KB 列表
- 明确 active / inactive 状态
- 新建 / 改名 / 删除 KB
- 切换当前 KB

右侧的主要职责：

- 展示当前 KB 的对象树与导入动作
- 展示当前 KB 的导入回执与诊断
- 作为后续“从管理进入问答”的起点

### 6.3 KB Workspace Level

KnowledgeBase 内部推荐从现有“三 tab 平铺”升级为“对象工作区”。建议的主布局如下：

- **左侧次级导航 / 树区**
  - Folder Tree
  - 过滤器（全部对象 / 文档 / 资产 / 最近导入 / 失败项）
- **中间对象列表区**
  - Document 列表
  - Asset 列表
  - 支持搜索、筛选、排序、批量动作
- **右侧详情区**
  - 对象详情
  - 导入回执摘要
  - 预览 / OCR 摘要 / 派生对象摘要

P0 阶段不必一次把三栏都做满，但 IA 上应先定成这个方向，而不是继续靠 tab 累加功能。

### 6.4 Object Level

KB 内的对象层推荐如下：

`KnowledgeBase -> Folder -> Document / Asset -> Derived Text / Chunk -> Evidence / Preview`

其中前端需要让用户感知到的是：

- `KnowledgeBase`
- `Folder`
- `Document`
- `Asset`
- `Evidence`
- `Preview`

而不需要直接暴露为主浏览对象的是：

- `Chunk`
- embedding record
- 检索内部节点

原因是这些对象是系统内部处理单元，不应污染用户主界面心智。

### 6.5 Answer / Evidence Level

在 `AgentPage` 中，推荐继续沿用“回答 + 证据 + 预览”三段式，但要把关系讲清楚：

- 回答：模型生成层
- Evidence：可验证引用层
- Preview：最小查看层

用户操作链路应是：

`问题 -> 回答 -> 点击 evidence -> 打开 preview -> 回到 document / asset`

这条链路代表“从回答回到知识对象”，是本产品可信度的关键体验。

---

## 7. 推荐页面结构

### 7.1 Knowledge Page 推荐结构

P0 推荐页面结构：

`KnowledgePage`
- KB Sidebar
- KB Header
- Workspace Tabs / Filters
  - 全部对象
  - 文档
  - 资产（可先占位为轻量列表，不必一步做满）
  - 导入
  - 网页导入
  - 最近回执
- Main Panel
  - 列表 / 表格 / 空态
- Detail / Preview Panel（可在 P1 强化）

当前实现中的 `文档列表 / 文件上传 / 网页导入` 三个 tab 可以视为 P0 过渡版，但后续建议演进为：

- **对象浏览视图**
- **导入动作视图**
- **导入结果 / 回执视图**

而不是让“上传 tab”长期与“文档 tab”平级存在。

### 7.2 Agent Page 推荐结构

`AgentPage` 推荐保持双区或三区：

- 左侧 / 上方：问题输入、当前 KB 范围、会话
- 中间：回答流
- 右侧：Evidence 列表与 Preview 面板

当前代码里已经具备 `evidence` 和 `preview` 的基本分区能力，因此后续重点不是发明新面板，而是强化两点：

1. 让证据列表表达“文档 / 资产 / 页码 / 定位”的对象感。
2. 让 Preview 之后能更顺畅地跳转回 Knowledge 侧对象页。

### 7.3 Knowledge 与 Agent 的联动

推荐建立两个明确动作：

1. **从 Knowledge 去 Ask**
   - 在 KB 工作区中，提供“在当前知识库中提问”入口。
2. **从 Ask 回 Knowledge**
   - 在证据或预览中，提供“打开源文档 / 打开源资产 / 在知识库中定位”入口。

这两个动作打通后，产品心智才是一个整体，而不是两个平行页面。

---

## 8. 关键交互流建议

### 8.1 交互流 A：进入并选择知识库

1. 用户进入 `Knowledge` 或 `Ask`
2. 左侧 / 顶部必须明确当前 KnowledgeBase
3. 若未选中 KB，则显示空态并要求显式选择
4. 若 KB 非 active，则不能作为当前工作范围

这条交互流必须与当前后端 default-deny 契约一致。

### 8.2 交互流 B：导入文件或目录

推荐交互：

1. 用户先选定 KB
2. 再选择导入方式：单文件 / 批量文件 / 目录 / URL
3. 导入后返回回执摘要
4. 回执中明确显示：
   - 成功对象数
   - 失败对象数
   - OCR 是否发生
   - 是否生成资产
   - 是否生成派生文本
5. 用户可直接跳到“最近导入对象”或“失败项”

现在的上传成功提示已经是一个起点，但还不够形成产品级导入反馈。

### 8.3 交互流 C：在 KB 内浏览知识对象

推荐顺序：

1. 先看 Folder / 分类过滤
2. 再看 Document / Asset 列表
3. 点开单个对象后看详情、预览、回执摘要
4. 如对象包含图片 OCR 派生文本，应在详情中明确展示“原资产”和“OCR 文本”的关系

### 8.4 交互流 D：问答与证据验证

推荐顺序：

1. 选定 KB
2. 提问
3. 查看回答
4. 查看 Evidence 列表
5. 点击某条 evidence 打开 preview
6. 再决定是否进入完整源对象

这里要强调：**Preview 不是终点，而是验证动作中的中间层。**

### 8.5 交互流 E：图片 / OCR 命中的体验

对于图片、流程图、扫描页等资产，P0 阶段建议做到：

1. 回答命中 OCR 文本时，Evidence 尽量补 `asset_id`
2. Preview 优先打开资产或资产元数据，而不是只展示截断 OCR 文本
3. 若当前只能返回资产元数据，也要明确提示它来自哪个宿主文档、相对路径是什么

这与当前 `previewItem` 的“`asset_id > doc_id > evidence_id`”优先级是一致的，应继续保留。

---

## 9. 旧路由的产品归宿

### 9.1 结论

`/kb-file`、`/kb-web`、`/kb-manage` 可以作为历史兼容路由暂时保留，但不应再作为主导航心智，也不应再成为后续新能力的首发承载页。

### 9.2 原因

原因有三点：

1. 这些页面按“动作类型”分裂，而不是按“知识对象”组织。
2. 它们会削弱 `KnowledgePage` 已经形成的显式 KB 选择心智。
3. 若后续继续在旧页上叠加新能力，会导致 IA 再次分叉。

### 9.3 推荐归宿

- P0：保留兼容路由，但不新增主导航入口。
- P1：将其能力并入 `KnowledgePage`。
- P2：视真实使用情况决定彻底下线或只保留跳转壳。

---

## 10. P0 / P1 前端演进建议

### 10.1 P0：先把主线 IA 收拢

P0 前端优先目标：

1. 明确 `KnowledgePage` 是知识管理主入口。
2. 明确 `AgentPage` 是知识消费主入口。
3. 在 `KnowledgePage` 内引入“对象视图”的表达，而不是长期停留在“上传 tab / 文档 tab”心智。
4. 把导入成功提示升级为最小回执摘要。
5. 把 Evidence / Preview 作为正式交互动作显式表达。

### 10.2 P1：补齐 KB 内对象层

P1 推荐补齐：

1. Folder Tree
2. Asset 列表或 Asset 过滤视图
3. 对象详情抽屉 / 侧板
4. 最近导入 / 失败项 / 诊断视图
5. 从证据跳转回 Knowledge 内源对象

### 10.3 P2：进一步提升统一工作区

P2 再考虑：

1. 更完整的目录导入工作流
2. 更强的图片 / PDF 预览体验
3. 更完整的跨页对象定位
4. 如果 Agent 外部接入成熟，再把“授权范围”和“知识消费工作台”结合得更完整

---

## 11. 对当前编码阶段的直接指导

### 11.1 现在前端最该避免的错误

1. 不要继续新增独立 KB 功能页来承载局部能力。
2. 不要把 Folder 做成另一个权限或作用域选择器。
3. 不要把 Asset 继续当成 Document 的附件细节长期隐藏。
4. 不要把 Evidence 继续当成一段不可点击的来源文本。
5. 不要在前端保留任何“未选择 KB 也能默认查询”的体验。

### 11.2 当前最值得推进的几个前端动作

1. 先在 `KnowledgePage` 中补“对象视图”心智。
2. 再补“导入回执 / 最近导入 / 失败项”可视化。
3. 然后补“Asset 视图”与“Folder 视图”。
4. 最后再做更丰富的预览与跨页面联动。

这个顺序的原因是：对象层和反馈层清楚后，后面的预览、OCR、Agent 联动才不会继续堆在临时交互上。

---

## 12. 总结

当前代码已经证明，这个项目的前端主线其实已经自然收敛到两个页面：

- `KnowledgePage`：显式选择 KB，并完成导入与管理
- `AgentPage`：在显式 KB 范围内提问，并用 Evidence / Preview 验证回答

真正缺的不是更多入口页，而是把这两个页面之间的对象层、证据层、预览层补成一套一致的信息架构。

所以本专项 Spec 的最终结论是：

1. **主导航收敛到 Knowledge + Ask / Agent 双主线。**
2. **KB 内部按 Folder -> Document / Asset -> Evidence / Preview 组织心智。**
3. **旧 KB 专页只保留兼容，不再作为主线 IA。**
4. **P0 优先收拢主线与对象层，P1 再补 Folder / Asset / Receipt 视图。**
