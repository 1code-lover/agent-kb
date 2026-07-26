# 本地多知识库知识助手 Knowledge Workspace 测试方案

## 1. 文档目的

本文是 `Knowledge Workspace` 前端重构的测试方案，目标是为编码阶段提供统一测试口径，确保页面从“tab 功能页”重构为“Workspace 对象页”后：

1. 不破坏现有知识库选择契约；
2. 不破坏现有导入能力；
3. 能正确支撑新的 `viewMode / actionMode` 状态模型；
4. 为后续 Folder / Asset / Receipt 增强提供稳定回归基线。

---

## 2. 输入基线

本测试方案基于：

- `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-spec-knowledge-workspace.md`
- `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-plan-knowledge-workspace.md`
- 当前前端实现：`KnowledgePage.jsx`、`KbSidebar.jsx`、`KbDocumentList.jsx`、`KbUpload.jsx`、`KbWebImport.jsx`

---

## 3. 测试范围

### 3.1 本轮纳入范围

1. `KnowledgePage` 页面状态重构
2. Workspace Header / Filter Bar
3. Object Explorer 容器
4. Upload / Web Import 动作面板化
5. 最小 Detail Panel / Receipt Summary

### 3.2 本轮排除范围

1. 完整 Folder Tree
2. 完整 Asset 列表
3. 完整 Receipt 列表
4. 复杂拖拽布局
5. 复杂对象预览器

---

## 4. 测试策略

### 4.1 测试层次

本轮采用三层验证：

1. **组件单元测试**：验证 Header、Filter Bar、Explorer、Detail Panel 的渲染与交互
2. **页面集成测试**：验证 `KnowledgePage` 状态切换、导入动作、回切逻辑
3. **手动冒烟测试**：验证与真实 KB 选择、上传行为、列表刷新之间的联动

### 4.2 核心回归目标

本轮最重要的回归目标不是视觉样式，而是下面 4 条：

1. 仍然必须显式选择 KB 才能操作；
2. 导入文件 / 网页导入仍然绑定当前 KB；
3. 文档列表仍然按当前 KB 展示；
4. 新增视图模式与动作模式不会造成页面状态混乱。

---

## 5. 测试对象与建议文件

### 5.1 页面测试

建议测试文件：

- `webapp/src/pages/__tests__/knowledge-page.test.jsx`

### 5.2 组件测试

建议测试文件：

- `webapp/src/components/kb/__tests__/kb-workspace-header.test.jsx`
- `webapp/src/components/kb/__tests__/kb-workspace-filter-bar.test.jsx`
- `webapp/src/components/kb/__tests__/kb-object-explorer.test.jsx`
- `webapp/src/components/kb/__tests__/kb-detail-panel.test.jsx`

### 5.3 现有组件回归测试

必要时扩充或补充：

- `KbDocumentList` 相关测试
- `KbUpload` 相关测试
- `KbWebImport` 相关测试

---

## 6. 逐 Task 测试设计

## 6.1 Task KW-1：页面状态模型重构

### 目标

验证 `KnowledgePage` 已从旧 `tab` 状态切换为 `viewMode + actionMode`，并能保持页面行为稳定。

### 用例表

| 编号 | 场景 | 前置条件 | 输入/动作 | 期望结果 |
|---|---|---|---|---|
| KW-1-01 | 默认进入页面 | 未选 KB | 渲染页面 | 显示未选择 KB 空态；不展示可操作对象区 |
| KW-1-02 | 选择 KB 后初始化 | 已选 active KB | 渲染页面 | 默认进入对象视图，且 actionMode 为 none |
| KW-1-03 | 切换动作面板 | 已选 KB | 点击“导入文件” | actionMode 切换为 upload；主对象视图状态仍保留 |
| KW-1-04 | 导入成功后回切 | 已选 KB，上传成功 mock | 触发导入成功回调 | actionMode 回到 none，viewMode 回到 documents 或约定默认视图 |
| KW-1-05 | 多次切换不串态 | 已选 KB | upload -> web_import -> none | 页面不出现残留错误状态或重复面板 |

### 重点断言

1. 页面主状态不再依赖旧 tab 文案；
2. `viewMode` 与 `actionMode` 相互独立；
3. 导入成功后页面能回到稳定对象视图。

---

## 6.2 Task KW-2：Workspace Header / Filter Bar

### 目标

验证 Header 与 Filter Bar 的显示和交互正确，并且能表达 KB 上下文。

### 用例表

| 编号 | 场景 | 前置条件 | 输入/动作 | 期望结果 |
|---|---|---|---|---|
| KW-2-01 | Header 显示当前 KB | 已选 KB | 渲染组件 | 显示 KB 名称、kb_id、根目录摘要 |
| KW-2-02 | 未选 KB Header 降级 | 未选 KB | 渲染组件 | 显示禁用态或空态提示 |
| KW-2-03 | Filter Bar 切换 documents | 已选 KB | 点击 documents | 回调收到 documents |
| KW-2-04 | Filter Bar 切换 recent_imports | 已选 KB | 点击 recent_imports | 回调收到 recent_imports |
| KW-2-05 | 未实现模式占位 | 已选 KB | 点击 assets / failed_items | 若约定为灰态，则按钮禁用；若约定为占位，则回调后显示稳定空态 |

### 重点断言

1. Header 始终带 KB 上下文；
2. Filter Bar 只负责表达视图，不直接承担数据拉取；
3. 未选 KB 时不能误触发可操作 CTA。

---

## 6.3 Task KW-3：Object Explorer 容器化

### 目标

验证 `KbObjectExplorer` 作为统一对象区壳层的行为稳定。

### 用例表

| 编号 | 场景 | 前置条件 | 输入/动作 | 期望结果 |
|---|---|---|---|---|
| KW-3-01 | documents 视图渲染文档列表 | 已选 KB | viewMode=documents | 渲染 `KbDocumentList` |
| KW-3-02 | 未实现视图空态 | 已选 KB | viewMode=recent_imports | 显示规范空态，不报错 |
| KW-3-03 | Explorer 接收对象选择回调 | 已选 KB，列表可选中 | 点击文档行 | 触发 `onSelectObject` 或等价回调 |
| KW-3-04 | 视图切换后稳定 | 已选 KB | documents -> recent_imports -> documents | 文档列表可正常恢复，不出现脏状态 |

### 重点断言

1. `KbDocumentList` 不再由页面直接硬编码渲染；
2. 未实现视图必须返回稳定占位；
3. Explorer 能成为未来 Asset / Receipt 接入的统一入口。

---

## 6.4 Task KW-4：动作面板化

### 目标

验证 Upload / Web Import 已从一级 tab 迁移为动作面板，并形成“导入 -> 回到对象视图”的同页闭环。

### 用例表

| 编号 | 场景 | 前置条件 | 输入/动作 | 期望结果 |
|---|---|---|---|---|
| KW-4-01 | 打开上传面板 | 已选 KB | 点击导入文件 CTA | 显示 `KbUpload` |
| KW-4-02 | 打开网页导入面板 | 已选 KB | 点击导入网页 CTA | 显示 `KbWebImport` |
| KW-4-03 | 上传成功回切 | 已选 KB，上传成功 mock | 触发成功回调 | 面板关闭；对象视图刷新；成功摘要可见 |
| KW-4-04 | 网页导入成功回切 | 已选 KB，网页导入成功 mock | 触发成功回调 | 面板关闭；对象视图刷新；成功摘要可见 |
| KW-4-05 | 导入失败不锁死页面 | 已选 KB，导入失败 mock | 触发失败 | 错误可见；用户仍可重试或关闭面板 |
| KW-4-06 | 未选 KB 禁止导入 | 未选 KB | 尝试触发导入 | 面板按钮禁用或空态提示，不能执行导入 |

### 重点断言

1. 动作面板和对象视图不是互斥页面，而是同页不同层；
2. 成功后必须自动回切，不再停留在旧 tab 心智；
3. 失败态不应导致页面状态失控。

---

## 6.5 Task KW-5：最小 Detail Panel / Receipt Summary

### 目标

验证页面已经具备稳定的右侧摘要层。

### 用例表

| 编号 | 场景 | 前置条件 | 输入/动作 | 期望结果 |
|---|---|---|---|---|
| KW-5-01 | 未选对象时空态 | 已选 KB，无对象选中 | 渲染 Detail Panel | 显示当前 KB 说明或引导 |
| KW-5-02 | 选中文档时显示摘要 | 已选 KB，文档可选中 | 点击文档 | 显示名称、类型、路径、kb_id |
| KW-5-03 | 导入成功后显示回执摘要 | 已选 KB，导入成功 | 渲染 Detail Panel | 显示最近导入摘要 |
| KW-5-04 | 切换 KB 后摘要刷新 | 已选 A 库后切换 B 库 | 切换 KB | Detail Panel 不残留旧库对象信息 |

### 重点断言

1. 详情区已成为页面稳定结构；
2. 导入摘要与对象摘要都能在这一层沉淀；
3. 切换 KB 时详情区状态正确重置。

---

## 7. 全局回归用例

### 7.1 KB 显式选择契约

| 编号 | 场景 | 期望结果 |
|---|---|---|
| REG-01 | 未选 KB 进入页面 | 不允许导入，不加载对象列表 |
| REG-02 | 选中 inactive KB | 不能作为当前工作目标 |
| REG-03 | 切换 active KB | 主区、详情区、动作区都更新到新 KB |

### 7.2 现有列表能力回归

| 编号 | 场景 | 期望结果 |
|---|---|---|
| REG-04 | 文档搜索 | 仍能按名称过滤 |
| REG-05 | 文档分页 | 仍能翻页 |
| REG-06 | 批量删除 | 仍能删除并刷新列表 |

### 7.3 现有导入能力回归

| 编号 | 场景 | 期望结果 |
|---|---|---|
| REG-07 | 文件上传绑定 KB | 请求仍携带当前 selectedKbId |
| REG-08 | 网页导入绑定 KB | 请求仍携带当前 selectedKbId |
| REG-09 | 成功提示 | 导入后仍能看到成功反馈 |

---

## 8. 手动冒烟测试清单

1. 打开 `/knowledge`，确认未选 KB 时显示空态；
2. 在侧边栏选择一个 active KB；
3. 确认页面显示 Workspace Header、Filter Bar、对象区；
4. 点击“导入文件”，确认上传面板展开；
5. 上传一个文件，确认成功后回到对象视图；
6. 点击“导入网页”，确认网页导入面板展开；
7. 导入完成后确认成功摘要可见；
8. 点击文档列表中的一项，确认右侧摘要区更新；
9. 切换到另一个 KB，确认列表和详情区都切换；
10. 尝试切换到未实现视图，确认显示稳定空态。

---

## 9. 通过标准

本轮测试通过标准：

1. 本测试方案中的 P0 必测用例全部通过；
2. KB 显式选择契约相关回归全部通过；
3. 现有文档列表与导入主链路没有回归；
4. 未实现视图全部返回稳定占位，不出现崩溃或白屏。

---

## 10. 结论

这份测试方案的重点不是验证页面“看起来像不像设计稿”，而是验证这次重构是否真的把 `KnowledgePage` 的结构与状态模型改对了。

只要本方案通过，后续再接 Folder / Asset / Receipt 时，就可以在一个稳定页面骨架上增量开发，而不是反复返工页面主结构。