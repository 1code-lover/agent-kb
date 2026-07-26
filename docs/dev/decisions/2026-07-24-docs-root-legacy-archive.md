# 2026-07-24 docs 根目录旧主线原件归档记录

## 1. 背景
第一批 `docs/` 根目录清理已经完成了“完全重复副本”的低风险去重，但 `agent_v1 / knowledge_agent` 系列旧主线文档仍停留在根目录，会继续制造两个问题：
1. 根目录同时存在“当前正式基线”和“旧主线原件”，协作者容易误把历史文档当现行入口；
2. 新文档虽然已经在 `docs/20260722-local-multi-kb-assistant/` 形成正式基线，但根目录保留旧主线原件，会削弱目录结构本身传递出的产品叙事。

因此，本轮进一步执行“迁出根目录、保留历史原件”的第二批治理。

---

## 2. 本次动作

### 2.1 新建历史原件快照目录
新建目录：`docs/archive/root-legacy-20260724/`

定位：
1. 保存从 `docs/` 根目录迁出的历史原件；
2. 不覆盖已有的 `docs/archive/superseded-20260722-local-multi-kb-assistant/` 整理归档版本；
3. 让 `docs/` 根目录只保留少量项目级 / 过渡级入口。

### 2.2 迁出的文件
本次从 `docs/` 根目录迁出以下文件：
1. `agent_v1_prd.md`
2. `agent_v1_frd.md`
3. `agent_v1_rtm.md`
4. `agent_v1_execution_plan.md`
5. `agent_v1_dev_readiness_checklist.md`
6. `knowledge_agent_product_plan.md`

### 2.3 同步修正的文档口径
为避免“文件已迁出，但文档还写着在根目录”的叙事错位，本轮同步更新：
1. `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-test-plan.md`
2. `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-rtm.md`
3. `docs/guide/DOCS_INDEX.md`
4. `docs/archive/superseded-20260722-local-multi-kb-assistant/README.md`

---

## 3. 备份与可回退性
在迁移前，已将根目录原文件备份到：

`temp/ai_delete_backups/20260724_201950/docs-root-legacy-archive/`

备份目录内包含：
1. 原文件副本；
2. `manifest.txt`；
3. 每个文件的 SHA1 记录。

因此，本轮迁移具备可回退性，不属于不可逆删除。

---

## 4. 本次不做的事
1. 不合并 `root-legacy` 与 `superseded` 两套 archive；
2. 不立即删除 archive 中的历史版本；
3. 不在本轮处理 `desktop_project_design.md`、`desktop_runbook.md`、`ThinkRAG_面试问答.md` 的最终归类；
4. 不改写迁入 `root-legacy` 的历史原件正文，避免混淆“原件快照”与“整理版”。

---

## 5. 当前结论
本轮之后，`docs/` 根目录不再保留 `agent_v1 / knowledge_agent` 旧主线原件；这些资料已经从“根目录入口”降级为“archive 历史材料”。

更准确地说：
- 当前正式基线：`docs/20260722-local-multi-kb-assistant/`
- 历史原件快照：`docs/archive/root-legacy-20260724/`
- 带 superseded 语义的整理归档：`docs/archive/superseded-20260722-local-multi-kb-assistant/`

这使目录结构本身能够更清楚地表达：**什么是当前主线，什么是历史追溯，什么只是整理归档。**
## 6. 后续状态更新（2026-07-25）
- 本文第 4 节提到的 `ThinkRAG_面试问答.md` 已在后续治理中迁入 `docs/interview/ThinkRAG_面试问答.md`。
- 因此当前 `docs/` 根目录不再保留该表达材料文件，只保留 `docs/project.md` 作为项目级入口。
- 详见 `docs/dev/decisions/2026-07-25-docs-interview-material-move.md`。
