# 2026-07-24 docs 根目录清理决定记录

## 1. 背景

仓库级文档规范已经明确：
1. 具体需求的成套文档应进入 `docs/YYYYMMDD-topic/`；
2. 通用说明文档应进入 `docs/guide/`、`docs/spec/`、`docs/dev/`、`docs/test/` 等公共分类目录；
3. 历史材料应进入 `docs/archive/`。

但当前 `docs/` 根目录仍残留一批散落文件，存在以下问题：
1. 与子目录中的 canonical 版本重复；
2. 新旧主线文档并列，容易造成叙事摇摆；
3. 协作者和 AI 助手很难快速判断“哪份才是当前正式入口”。

本次清理遵循“先低风险、再分批治理”的原则。

> 补充说明：本文只记录第一批“重复副本去重”动作；第二批“旧主线原件迁入 archive”见 `docs/dev/decisions/2026-07-24-docs-root-legacy-archive.md`。

---

## 2. 本次处理原则

### 2.1 本次只处理低风险项
本轮只清理同时满足以下条件的根目录文件：
1. 已存在明确的 canonical 版本；
2. 根目录文件与 canonical 版本内容完全一致；
3. 删除根目录副本不会改变文档语义，只是消除重复入口。

### 2.2 本次暂不处理的对象
以下对象本轮不直接移动或删除：
1. 与 archive / 子目录存在差异的旧主线文件；
2. 尚未明确唯一 canonical 版本的公共文档；
3. 项目级入口文档。

---

## 3. 已执行清理

### 3.1 已从 docs 根目录移除的重复文件
以下文件已从 `docs/` 根目录移除，并保留其规范归宿中的 canonical 版本：

1. `docs/agent_kb_design.md`
   - 保留：`docs/archive/agent_kb_design.md`
2. `docs/code_commenting_requirement.md`
   - 保留：`docs/dev/standards/code_commenting_requirement.md`
3. `docs/Code_of_Conduct.md`
   - 保留：`docs/guide/Code_of_Conduct.md`
4. `docs/desktop_api_contract.md`
   - 保留：`docs/spec/desktop_api_contract.md`
5. `docs/desktop_regression_checklist.md`
   - 保留：`docs/test/desktop_regression_checklist.md`
6. `docs/HowToDownloadModels.md`
   - 保留：`docs/guide/HowToDownloadModels.md`
7. `docs/HowToUsePythonVirtualEnv.md`
   - 保留：`docs/guide/HowToUsePythonVirtualEnv.md`

### 3.2 备份策略
为确保可恢复性，本次清理前已将被移除文件备份到：

`temp/ai_delete_backups/20260724_201313/docs-root-cleanup/`

备份目录内包含：
1. 原文件副本；
2. `manifest.txt`，记录移除路径、保留路径和 SHA1 校验值。

---

## 4. 暂不处理但应后续治理的文件

### 4.1 旧主线文档（应归档退出根目录）
以下文件不应继续长期停留在 `docs/` 根目录，但由于与 archive 版本存在差异，本轮不做直接删除：

1. `docs/agent_v1_prd.md`
2. `docs/agent_v1_frd.md`
3. `docs/agent_v1_rtm.md`
4. `docs/agent_v1_execution_plan.md`
5. `docs/agent_v1_dev_readiness_checklist.md`
6. `docs/knowledge_agent_product_plan.md`

建议后续动作：
1. 确认哪一份是最终保留的历史版本；
2. 补充“已归档 / 已被替代”说明；
3. 统一迁入 `docs/archive/` 后，再从根目录移除。

### 4.2 存在多个版本的公共文档（需先选 canonical）
以下文件已有更合适的公共目录归宿，但根目录与子目录版本并非完全一致：

1. `docs/desktop_project_design.md`
   - 候选 canonical：`docs/spec/desktop_project_design.md`
2. `docs/desktop_runbook.md`
   - 候选 canonical：`docs/guide/desktop_runbook.md`

建议后续动作：
1. 对比两份差异；
2. 选定唯一 canonical 版本；
3. 合并差异后移除根目录副本。

### 4.3 需要重新归类的文档
1. `docs/ThinkRAG_面试问答.md`
   - 建议归入：`docs/interview/` 或 `docs/archive/`。

### 4.4 建议保留在根目录的项目级入口
1. `docs/project.md`
   - 当前定位是“项目总览 / 协作者入口文档”，允许继续保留在根目录。

---

## 5. 后续治理建议

### 5.1 根目录目标状态
`docs/` 根目录应尽量只保留：
1. 少量项目级入口文档；
2. 明确的分类目录；
3. 按需求组织的日期主题目录。

### 5.2 后续治理顺序
建议后续按如下顺序处理：
1. 先处理旧主线文档归档；
2. 再处理 `desktop_project_design.md` / `desktop_runbook.md` 的 canonical 合并；
3. 最后把 `ThinkRAG_面试问答.md` 迁入合适目录。

---

## 6. 本次结论

本次并未做大规模文档迁移，只完成了“明确重复、可校验、可回退”的根目录清理，目的是：
1. 降低 `docs/` 根目录噪音；
2. 保持风险最小；
3. 为后续更大范围的文档治理建立方法和边界。

## 7. 后续状态更新（2026-07-25）
- 原 `docs/ThinkRAG_面试问答.md` 已迁入 `docs/interview/ThinkRAG_面试问答.md`。
- 当前 `docs/` 根目录仅保留 `docs/project.md` 作为项目级入口。
- 迁移动作与备份记录见 `docs/dev/decisions/2026-07-25-docs-interview-material-move.md`。
