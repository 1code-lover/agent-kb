# 本地多知识库知识助手 Knowledge Workspace 实施方案

## 1. 文档目的

本文是 `Knowledge Workspace` 前端改造的实施方案，目标是把前面的页面专项 Spec 落到可直接编码的任务级拆解，明确：

1. 改哪些文件；
2. 先写哪些测试；
3. 每个 Task 的 DoD 是什么；
4. 哪些能力属于 P0，哪些留到 P1。

---

## 2. 输入基线

本实施方案基于以下文档：

- `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-prd.md`
- `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-frd.md`
- `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec.md`
- `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec-frontend-ia.md`
- `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec-knowledge-workspace.md`
- `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-plan-folder-assets.md`

已确认的前提：

1. KnowledgeBase 是一级边界对象；
2. Folder 是组织对象，不是边界对象；
3. 当前 `KnowledgePage` 是知识管理主入口；
4. 当前前端已具备显式 KB 选择、按 KB 导入、按 KB 拉文档能力；
5. 本轮目的是先把 `KnowledgePage` 从 tab 拼盘重构成 Workspace 骨架，而不是一次做完整 Folder / Asset 产品化。

---

## 3. 当前代码现实（实施约束）

### 3.1 已核实现状

当前关键文件如下：

- `webapp/src/pages/KnowledgePage.jsx`
- `webapp/src/components/kb/KbSidebar.jsx`
- `webapp/src/components/kb/KbDocumentList.jsx`
- `webapp/src/components/kb/KbUpload.jsx`
- `webapp/src/components/kb/KbWebImport.jsx`
- `webapp/src/components/kb/KbContext.jsx`

当前现实：

1. 页面状态主轴仍是 `tab = docs / upload / web`。
2. `KbDocumentList` 直接承担整个对象区。
3. `KbUpload` 与 `KbWebImport` 是页面一级 tab，而不是动作面板。
4. 还没有 Asset 视图、Receipt 视图、Detail Panel。
5. 还没有 Folder Tree。

### 3.2 这意味着什么

这意味着本轮最重要的不是加更多业务细节，而是先做**页面骨架重构**：

- 先把状态模型改对；
- 再把页面区域拆对；
- 再逐步接入对象视图。

如果状态和组件边界不先理顺，后续 Folder / Asset / Receipt 只会继续堆在旧 tab 结构上。

---

## 4. 本轮目标与非目标

### 4.1 本轮目标

本轮 P0 目标限定为 6 项：

1. 把 `KnowledgePage` 从单一 tab 状态改成 `viewMode + actionMode` 双状态模型；
2. 抽出 Workspace Header；
3. 抽出 Workspace Filter Bar；
4. 抽出 Object Explorer 容器并接入现有 `KbDocumentList`；
5. 把 `KbUpload` / `KbWebImport` 改成动作面板而不是一级 tab；
6. 补一个最小 Detail Panel / Receipt Summary 闭环。

### 4.2 本轮明确不做

1. 完整 Folder Tree；
2. 完整 Asset 列表产品化；
3. 完整 Receipt 列表产品化；
4. 复杂拖拽布局；
5. 复杂预览器；
6. 跨页深链跳转打磨。

---

## 5. 总体实施策略

### 5.1 策略一：先重构骨架，再接对象类型

本轮不应先写 `KbAssetList` 或 Folder Tree，而应先让页面具备一个稳定骨架：

- Header
- Filter Bar
- Explorer
- Action Panel
- Detail Panel

### 5.2 策略二：优先复用现有组件

现有组件能复用的尽量复用：

- `KbSidebar`
- `KbDocumentList`
- `KbUpload`
- `KbWebImport`

这样可以降低改造风险，并减少“文档改得很理想、代码却要推倒”的落差。

### 5.3 策略三：先把接口与状态抽象出来，再补数据源

本轮先定义稳定的视图模式和动作模式：

- `viewMode`: `all / documents / assets / recent_imports / failed_items`
- `actionMode`: `none / upload / directory_import / web_import`

即便某些模式当前先回退到占位空态，也优于继续把结构绑死在 tab 上。

### 5.4 策略四：详情区先做最小可见层

Detail Panel 本轮不追求功能做满，只要先能展示：

- 当前 KB 摘要
- 最近一次导入摘要
- 当前选中文档基础信息

就已经足够支撑后续渐进增强。

---

## 6. 文件改动建议

### 6.1 现有文件

建议改动：

- `webapp/src/pages/KnowledgePage.jsx`
- `webapp/src/components/kb/KbDocumentList.jsx`
- `webapp/src/components/kb/KbUpload.jsx`
- `webapp/src/components/kb/KbWebImport.jsx`

### 6.2 建议新增文件

建议新增：

- `webapp/src/components/kb/KbWorkspaceHeader.jsx`
- `webapp/src/components/kb/KbWorkspaceFilterBar.jsx`
- `webapp/src/components/kb/KbObjectExplorer.jsx`
- `webapp/src/components/kb/KbDetailPanel.jsx`

可选占位新增：

- `webapp/src/components/kb/KbReceiptSummary.jsx`
- `webapp/src/components/kb/KbEmptyState.jsx`

### 6.3 测试文件建议

建议新增或扩充：

- `webapp/src/pages/__tests__/knowledge-page.test.jsx`
- `webapp/src/components/kb/__tests__/kb-workspace-filter-bar.test.jsx`
- `webapp/src/components/kb/__tests__/kb-object-explorer.test.jsx`
- `webapp/src/components/kb/__tests__/kb-detail-panel.test.jsx`

如果当前测试目录结构与建议不一致，以仓库已有风格为准，但测试意图应保持一致。

---

## 7. 任务拆解

## 7.1 Task KW-1：页面状态模型重构

### 目标

把 `KnowledgePage` 从 `tab` 单状态改为：

- `viewMode`
- `actionMode`
- `notice / receiptSummary`
- `selectedObject`（最小可先支持 document）

### 主要改动文件

- `webapp/src/pages/KnowledgePage.jsx`

### 任务内容

1. 删除页面对 `docs / upload / web` tab 的强绑定；
2. 引入 `viewMode` 与 `actionMode`；
3. 导入成功后默认回到 `documents` 或 `all` 视图；
4. 保留现有导入通知，但升级为可供 Detail Panel 使用的摘要状态。

### TDD 顺序

1. 先写页面测试，验证默认状态与切换逻辑；
2. 再写实现；
3. 最后补导入成功后状态回切测试。

### DoD

1. 页面内部不再依赖旧 `tab` 作为主状态；
2. 导入动作与对象视图已经可以独立切换；
3. 页面行为不破坏现有显式 KB 选择契约。

---

## 7.2 Task KW-2：Workspace Header / Filter Bar 抽取

### 目标

把页面头部和视图切换从 `KnowledgePage.jsx` 中抽出，形成稳定的可复用结构。

### 主要改动文件

- `webapp/src/pages/KnowledgePage.jsx`
- `webapp/src/components/kb/KbWorkspaceHeader.jsx`
- `webapp/src/components/kb/KbWorkspaceFilterBar.jsx`

### 任务内容

1. 头部显示当前 KB 名称、ID、根目录摘要；
2. 头部放主动作：导入文件 / 导入目录 / 导入网页 / 当前 KB 提问；
3. Filter Bar 提供最小视图切换：`documents / recent_imports`；
4. 为 `assets / failed_items` 预留状态入口，可先灰态或空态。

### TDD 顺序

1. 先写 Header 渲染测试；
2. 再写 Filter Bar 模式切换测试；
3. 再实现组件与回调；
4. 最后补禁用状态测试（未选 KB）。

### DoD

1. Header 与 Filter Bar 已从页面容器中解耦；
2. 页面有清晰 CTA，不再只能靠顶部 tab 导航；
3. 未选中 KB 时，Header / Filter Bar 呈现正确禁用或空态。

---

## 7.3 Task KW-3：Object Explorer 容器化

### 目标

引入 `KbObjectExplorer` 作为对象工作区壳层，先接入文档列表，再为后续资产 / 回执视图预留插槽。

### 主要改动文件

- `webapp/src/pages/KnowledgePage.jsx`
- `webapp/src/components/kb/KbObjectExplorer.jsx`
- `webapp/src/components/kb/KbDocumentList.jsx`

### 任务内容

1. 新增 `KbObjectExplorer` 容器；
2. 当 `viewMode = documents` 时，内部渲染 `KbDocumentList`；
3. 当 `viewMode = recent_imports` 或其他未实现视图时，返回规范空态；
4. 为对象选择回调预留接口，如 `onSelectObject`。

### TDD 顺序

1. 先写 Explorer 视图切换测试；
2. 再写 DocumentList 接入测试；
3. 再实现 Explorer；
4. 最后补空态测试。

### DoD

1. `KbDocumentList` 不再被页面直接硬编码渲染；
2. Explorer 已成为统一对象区入口；
3. 未来可增量接 Asset / Receipt，而无需再改页面主骨架。

---

## 7.4 Task KW-4：导入组件改为动作面板

### 目标

把 `KbUpload` 与 `KbWebImport` 从一级页面 tab 调整为受 `actionMode` 控制的动作面板。

### 主要改动文件

- `webapp/src/pages/KnowledgePage.jsx`
- `webapp/src/components/kb/KbUpload.jsx`
- `webapp/src/components/kb/KbWebImport.jsx`

### 任务内容

1. 页面点击 CTA 后打开对应动作面板；
2. 上传 / 网页导入成功后关闭动作面板；
3. 成功后触发 Explorer 刷新；
4. 继续保留当前“必须先选择 KB”的限制；
5. 为目录导入预留 `directory_import` 面板状态。

### TDD 顺序

1. 先写动作面板打开 / 关闭测试；
2. 再写上传成功后回切对象视图测试；
3. 再实现组件编排；
4. 最后补异常路径测试。

### DoD

1. 页面已不再依赖 upload / web tab；
2. 导入路径与对象浏览路径形成同页闭环；
3. 导入失败时错误信息仍可见，且不会把页面状态卡死。

---

## 7.5 Task KW-5：最小 Detail Panel / Receipt Summary

### 目标

引入最小详情区，让页面具备“选中对象 -> 看摘要”的基础能力。

### 主要改动文件

- `webapp/src/pages/KnowledgePage.jsx`
- `webapp/src/components/kb/KbDetailPanel.jsx`
- 可选：`webapp/src/components/kb/KbReceiptSummary.jsx`

### 任务内容

1. 当未选中对象时，右侧显示当前 KB 说明或最近一次导入摘要；
2. 当选中文档时，显示最小文档信息：名称、类型、路径、KB；
3. 导入成功后，Detail Panel 可显示最近一次回执摘要；
4. 为后续资产详情 / OCR 摘要 / 预览入口预留区域。

### TDD 顺序

1. 先写未选对象空态测试；
2. 再写选中文档摘要测试；
3. 再写导入成功后回执摘要测试；
4. 最后实现 Detail Panel。

### DoD

1. 页面已有稳定详情区概念；
2. 导入与浏览都能把信息沉淀到右侧摘要层；
3. 后续接 Asset / Receipt / Preview 时不需要重新拆页面。

---

## 8. 测试设计要求

### 8.1 本轮前端必测场景

1. 未选 KB 时页面空态正确；
2. 选中 KB 后可切换对象视图；
3. 点击 CTA 可打开对应动作面板；
4. 上传成功后自动关闭动作面板并刷新主区；
5. 网页导入成功后自动回到对象视图；
6. Explorer 未实现视图返回稳定空态而不是崩溃；
7. Detail Panel 能响应对象选择与回执摘要。

### 8.2 回归重点

1. KB 显式选择契约不能被破坏；
2. 现有 `KbUpload`、`KbWebImport` 的目标 KB 绑定不能丢；
3. 现有 `KbDocumentList` 的查询 / 删除 / 搜索能力不能被重构破坏。

---

## 9. 验证命令（建议）

### 9.1 前端单测

根据仓库实际测试命令执行，建议至少覆盖：

- `KnowledgePage` 页面测试
- 新增组件测试
- 与现有 KB 组件相关的回归测试

### 9.2 手动验证清单

1. 进入 `/knowledge`，未选 KB 时显示正确空态；
2. 选择 KB 后，Header、Filter Bar、Explorer 正常显示；
3. 点击“导入文件”可展开上传面板；
4. 上传成功后返回对象视图并提示成功；
5. 点击“导入网页”可展开网页导入面板；
6. 导入成功后能看到主区刷新；
7. 选中文档时右侧摘要正确。

---

## 10. 风险与注意事项

### 10.1 不要在第一轮就试图做完整三栏高保真布局

第一轮最重要的是状态与组件边界正确，而不是视觉细节做满。

### 10.2 不要让未实现模式直接报错

`assets`、`failed_items`、`recent_imports` 若暂时未接完整数据，必须返回明确空态或占位态。

### 10.3 不要把旧组件强行塞进新结构而不抽状态

如果只是把原 tab 内容搬位置，但仍保留旧状态模型，那么这轮改造价值会大幅下降。

---

## 11. 结论

这份实施方案的核心思想是：

1. 先把 `KnowledgePage` 的页面骨架改对；
2. 再把状态模型改对；
3. 再把现有文档列表和导入组件装进新的 Workspace 壳层；
4. 最后逐步扩展到 Folder / Asset / Receipt。

如果按这个顺序执行，下一轮编码就不会陷入“边写 Folder 边返工页面结构”的重复劳动。