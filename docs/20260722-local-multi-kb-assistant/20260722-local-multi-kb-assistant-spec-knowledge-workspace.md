# 本地多知识库知识助手 Knowledge Workspace 页面专项 Spec

## 1. 文档信息
- 文档版本：v0.1
- 文档状态：可直接指导前端编码拆分
- 创建日期：2026-07-25
- 所属目录：`docs/20260722-local-multi-kb-assistant/`
- 关联主 Spec：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec.md`
- 关联前端 IA 专项：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec-frontend-ia.md`
- 关联文件夹模型专项：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec-folder-model.md`
- 关联导入对象模型专项：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec-ingestion-object-model.md`
- 关联实施方案：`docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-plan-folder-assets.md`

---

## 2. 一句话结论

`KnowledgePage` 不应继续只是“文档列表 + 上传 tab + 网页导入 tab”的功能拼盘，而应演进为一个围绕 **KnowledgeBase 内对象管理** 的统一工作区（Workspace）。

---

## 3. 本文要解决的问题

本文聚焦 4 件事：

1. 把 `KnowledgePage` 的页面层级写清楚；
2. 把页面内部推荐区域、组件边界、状态边界写清楚；
3. 把现有组件如何迁移到新结构写清楚；
4. 把 P0 先做什么、P1 再做什么拆到能直接开工的粒度。

---

## 4. 当前页面现实

### 4.1 当前代码现状

根据当前代码核实，`KnowledgePage` 由以下结构组成：

- 左侧：`KbSidebar`
- 右侧 Header：显示当前知识库名称、ID、数据目录
- 右侧主内容：
  - `文档列表`
  - `文件上传`
  - `网页导入`

对应文件：

- `webapp/src/pages/KnowledgePage.jsx`
- `webapp/src/components/kb/KbSidebar.jsx`
- `webapp/src/components/kb/KbDocumentList.jsx`
- `webapp/src/components/kb/KbUpload.jsx`
- `webapp/src/components/kb/KbWebImport.jsx`

### 4.2 当前结构的问题

当前结构虽然满足“先选 KB 再操作”的基本契约，但从产品和编码两端看，都存在不足：

1. 页面以 tab 承载动作，而不是以对象承载内容。
2. 文档、资产、目录、回执、失败项没有统一工作区表达。
3. 上传与浏览割裂，导入之后不能自然回到对象视图。
4. 页面内没有稳定的“详情区 / 预览区 / 回执区”。
5. 如果后续继续加 Folder、Asset、Receipt，很容易把 tab 越堆越多。

所以这份专项 Spec 的核心目标，就是把 `KnowledgePage` 从“平铺功能页”升级为“对象工作区页面”。

---

## 5. 页面定位

### 5.1 页面职责

`KnowledgePage` 的职责应明确为：

1. 选择当前 `KnowledgeBase`
2. 在当前 KB 内浏览与组织知识对象
3. 执行导入动作
4. 查看导入结果与诊断
5. 从知识对象进入后续问答消费链路

### 5.2 页面不负责什么

`KnowledgePage` 不负责：

1. 承担跨 KB 问答主流程（这属于 `AgentPage`）
2. 承担复杂多模态理解工作台
3. 承担 Folder 级权限管理
4. 承担完整外部 Agent 授权编排

这样才能保证页面边界稳定，不会因为后续能力扩展而不断失焦。

---

## 6. 推荐页面结构

### 6.1 顶层布局

推荐采用 **左侧 KB 导航 + 中央 Workspace + 右侧详情区** 的三段式布局。

`KnowledgePage`
- Left Rail：KnowledgeBase 导航
- Center Workspace：对象浏览 / 导入 / 回执主区
- Right Detail Panel：对象详情 / 预览 / 回执摘要

P0 阶段即便暂时不把右侧详情区做成常驻，也应在组件与状态设计上给它留位置。

### 6.2 Left Rail：KnowledgeBase 导航

这一层基本沿用现有 `KbSidebar`，职责保持不变：

- KB 列表
- 新建 KB
- 重命名 KB
- 删除 KB
- 显示 active / inactive
- 切换当前 KB

建议补充但不必立即实现的增强点：

- 当前 KB 的对象数 / 最近更新时间摘要
- 当前 KB 是否有失败导入提示

### 6.3 Center Workspace：知识对象工作区

中央区域应从“tab 平铺动作”演进为“工作区”。推荐结构如下：

1. **Workspace Header**
   - 当前 KB 名称
   - KB 标识与根目录信息
   - 主要 CTA：导入文件 / 导入目录 / 导入网页 / 去当前 KB 提问

2. **Workspace Filter Bar**
   - 视图切换：全部对象 / 文档 / 资产 / 最近导入 / 失败项
   - 搜索框
   - 排序 / 筛选

3. **Workspace Main Panel**
   - 列表视图或树 + 列表混合视图
   - 支持批量选择、删除、查看详情

4. **Workspace Action Area**
   - 在需要时展开上传区、网页导入区、目录导入区
   - 不建议长期作为平级 tab 常驻在最上层

### 6.4 Right Detail Panel：详情与预览区

右侧详情区建议承担以下职责：

- 当前选中 Document / Asset 的基础信息
- Preview 入口
- OCR / 派生文本摘要
- 导入回执摘要
- 跳转到 Ask / Agent 的入口

P0 若来不及做常驻右栏，也可以先用 Drawer / SideSheet / Expandable Panel 替代，但概念上它应是稳定对象，而不是临时 modal。

---

## 7. 页面内对象层次

### 7.1 用户可见对象

在 `KnowledgePage` 中，建议直接向用户暴露的对象层次是：

- `KnowledgeBase`
- `Folder`
- `Document`
- `Asset`
- `Ingestion Receipt`

### 7.2 不建议直接做成主浏览对象的内部对象

以下对象不建议在 P0 做成一等浏览层：

- Chunk
- Embedding record
- OCR 派生中间节点
- 检索内部 metadata 节点

这些对象更适合放在详情区或诊断区中间接呈现，而不是让用户主界面直接面向它们。

### 7.3 Folder 的前端定位

Folder 在这个页面里应该表现为：

- 目录树 / 面包屑 / 路径过滤条件
- 默认服务于“浏览和组织”
- 不参与 KB 作用域选择
- 不参与权限边界判断

这条原则必须在 UI 里持续保持，否则后面很容易把 Folder 做成另一个假的 KB 层。

---

## 8. 推荐页面模块拆分

下面的模块拆分，目标是让当前页面可以渐进式重构，而不是推倒重写。

### 8.1 页面级容器

建议保留：

- `webapp/src/pages/KnowledgePage.jsx`

建议职责：

- 挂载 `KbProvider`
- 管理页面级视图状态
- 编排左中右三区
- 编排导入成功后的刷新与回执展示

### 8.2 建议保留并继续使用的现有组件

1. `KbSidebar.jsx`
2. `KbUpload.jsx`
3. `KbWebImport.jsx`
4. `KbDocumentList.jsx`

但这些组件的定位建议调整：

- `KbUpload`：从“页面 tab”降级为“工作区动作面板”
- `KbWebImport`：从“页面 tab”降级为“工作区动作面板”
- `KbDocumentList`：从“整个内容区”升级为“对象列表的一种视图”

### 8.3 建议新增组件

#### A. `KbWorkspaceHeader.jsx`
职责：
- 显示当前 KB 标题
- 显示 KB 摘要信息
- 放主要操作入口（导入、问答）

#### B. `KbWorkspaceFilterBar.jsx`
职责：
- 视图切换
- 搜索
- 过滤 / 排序
- 展示当前过滤上下文

#### C. `KbObjectExplorer.jsx`
职责：
- 统一承载对象列表区
- 根据当前模式显示文档列表、资产列表、最近导入、失败项
- 后续可接 Folder Tree + 列表混合模式

#### D. `KbDetailPanel.jsx`
职责：
- 展示当前选中对象详情
- 承载最小预览入口
- 显示回执摘要与派生对象摘要

#### E. `KbReceiptList.jsx`
职责：
- 展示最近导入记录
- 支持查看成功 / 失败 / 部分成功
- 支持跳转回对象列表

#### F. `KbAssetList.jsx`
职责：
- 展示 Asset 视图
- 与文档视图并列，而不是只藏在文档详情里

### 8.4 推荐组件关系

推荐的组件关系可以先按下面理解：

`KnowledgePage`
- `KbSidebar`
- `KbWorkspaceHeader`
- `KbWorkspaceFilterBar`
- `KbObjectExplorer`
  - `KbDocumentList`
  - `KbAssetList`
  - `KbReceiptList`
- `KbUpload`
- `KbWebImport`
- `KbDetailPanel`

这里的关键不是一次把所有组件都写出来，而是先把“谁是容器、谁是视图、谁是动作面板”分清楚。

---

## 9. 页面状态设计

### 9.1 页面级状态

`KnowledgePage` 至少需要稳定表达以下页面级状态：

1. **未选择 KB**
2. **KB 已选择但暂无对象**
3. **正在加载对象列表**
4. **导入进行中**
5. **导入完成并有回执**
6. **对象已选中，详情区展开**
7. **筛选中 / 搜索中**

### 9.2 视图模式状态

建议定义最小视图模式枚举，例如：

- `all`
- `documents`
- `assets`
- `recent_imports`
- `failed_items`

这样后面无论用 tab、segmented control 还是 side filter，本质都是同一状态，不会把逻辑绑死在某一种 UI 皮肤上。

### 9.3 动作面板状态

建议把导入动作也抽成独立状态，而不是继续靠最顶层 tab：

- `none`
- `upload`
- `directory_import`
- `web_import`

这样在编码时可以更自然地实现：

- 在对象列表上方展开导入面板
- 导入成功后自动回到对象视图，并展示回执摘要

---

## 10. 关键交互建议

### 10.1 导入文件

推荐交互：

1. 用户先选中 KB
2. 点击“导入文件”
3. 展开 `KbUpload`
4. 选择文件后执行导入
5. 导入结束后自动收起导入面板
6. 刷新对象列表
7. 展示一条可点击的回执摘要

### 10.2 导入目录

即便当前目录导入尚未编码完成，页面结构也应预留入口：

1. 在 Workspace Header 放“导入目录”入口
2. 动作状态切到 `directory_import`
3. 后续实现时直接接 preserving tree 上传协议

这能避免后续为了目录导入再重做页面结构。

### 10.3 浏览对象

推荐顺序：

1. 先筛选对象视图
2. 再查看列表
3. 点击对象后在右侧详情区展示摘要
4. 若对象有关联资产或 OCR 信息，在详情区显式展示

### 10.4 查看导入结果

导入结果不应只是一句 toast，而应至少具备：

- 成功数
- 失败数
- 对应 KB
- 时间
- 可点开看明细

因此回执列表值得成为独立视图，而不是挂在上传组件里的瞬时提示。

### 10.5 去当前 KB 提问

页面建议提供一个稳定动作：

- “在当前知识库中提问”

它的作用是把 `KnowledgePage` 与 `AgentPage` 打通，避免管理和使用两条主线割裂。

---

## 11. 与现有 API / 状态的映射建议

### 11.1 可直接复用的现有能力

当前已有能力已经足够支撑 P0 第一轮重构：

- `KbContext`：KB 选择和刷新
- `listDocs(selectedKbId)`：按 KB 拉文档
- `deleteDocs(...)`：文档删除
- `importFiles(...)`：文件导入
- `importWeb(...)`：网页导入

### 11.2 需要为后续页面结构预留的能力

后续页面结构需要新增或逐步补齐的能力包括：

- Folder 列表 / 树读取接口
- Asset 列表接口
- Receipt / 导入记录接口
- 对象详情读取接口
- 从 Knowledge 对象跳转到 Ask 页的参数约定

但这些都不阻碍先把页面骨架搭起来。

---

## 12. P0 直接编码顺序建议

### 12.1 第一步：收拢页面状态

先在 `KnowledgePage.jsx` 中把状态从“tab = docs/upload/web”收拢为更稳定的两个维度：

1. `viewMode`
2. `actionMode`

这是后续整个页面可扩展的前提。

### 12.2 第二步：抽出 Workspace Header / Filter Bar

先把页面头部与主要操作抽出来，不要一上来就写 Folder Tree。先把页面骨架立住。

### 12.3 第三步：把 `KbDocumentList` 包进 `KbObjectExplorer`

先实现“对象工作区”的壳，再决定内部逐步接入哪些对象类型。

### 12.4 第四步：把导入组件改成动作面板

把 `KbUpload` 和 `KbWebImport` 从页面 tab 变成受 `actionMode` 控制的动作区。

### 12.5 第五步：补右侧详情区最小闭环

先实现最轻量的：

- 文档基础信息
- 资产基础信息
- 最近一次导入摘要

不用一开始就把完整预览与跳转都做满。

---

## 13. P1 / P2 扩展建议

### 13.1 P1

P1 推荐重点：

1. Folder Tree
2. Asset 列表
3. Receipt 视图
4. 失败项视图
5. 从对象详情跳转到 Ask / Agent

### 13.2 P2

P2 再考虑：

1. 更丰富的对象详情页
2. 目录面包屑与批量移动
3. 更完整的图片 / PDF 预览
4. 更强的跨页对象定位与深链

---

## 14. 当前编码阶段最重要的约束

1. 不要继续往 `KnowledgePage` 顶部叠加新的 tab。
2. 不要把 Folder 误做成作用域选择器。
3. 不要把 Asset 继续长期隐藏在文档附属信息里。
4. 不要让导入反馈只停留在 toast 或一句提示文案。
5. 不要在页面里保留任何“未选 KB 也可操作”的兼容路径。

---

## 15. 总结

这份页面专项 Spec 的目的，不是把视觉稿画满，而是把 `KnowledgePage` 的编码方向一次性校正：

- 从“tab 平铺功能页”转向“Knowledge Workspace”
- 从“只有文档列表”转向“Document / Asset / Receipt 并列对象视图”
- 从“上传完就结束”转向“导入 -> 回执 -> 对象浏览”的完整闭环

因此，如果下一步准备开始编码，最推荐的落地顺序不是“先把 Folder Tree 做炫”，而是：

1. 先重构页面骨架；
2. 再重构状态模型；
3. 再补对象视图；
4. 最后逐步接 Folder / Asset / Receipt。
