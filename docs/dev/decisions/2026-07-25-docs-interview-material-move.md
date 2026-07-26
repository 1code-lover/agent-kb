# 2026-07-25 docs 面试材料归类记录

## 1. 背景
经过前几轮 docs 根目录治理后，`docs/` 根目录只剩两个入口：
1. `docs/project.md`
2. `docs/ThinkRAG_面试问答.md`

其中 `ThinkRAG_面试问答.md` 属于表达 / 面试材料，不应继续停留在根目录。为保持目录语义稳定，本轮将其迁入 `docs/interview/`。

---

## 2. 本次动作
1. 迁移文件：
   - 从：`docs/ThinkRAG_面试问答.md`
   - 到：`docs/interview/ThinkRAG_面试问答.md`
2. 迁移前备份到：
   - `temp/ai_delete_backups/20260725_082449/docs-interview-material-move/`
3. 备份目录内保留：
   - 原文件副本
   - `manifest.txt`
   - 文件 SHA1：`5B326971DB7DDEB741D085D9B06A80D9A99FFB68`

---

## 3. 同步更新的文档
为避免“文件已移动，但索引和设计文档仍指向旧路径”的二次混乱，本轮同步更新了：
1. `docs/guide/DOCS_INDEX.md`
2. `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-rtm.md`
3. `docs/dev/decisions/2026-07-24-docs-desktop-canonical-cleanup.md`
4. `docs/dev/decisions/2026-07-24-docs-root-cleanup.md`
5. `docs/dev/decisions/2026-07-24-docs-root-legacy-archive.md`

---

## 4. 当前结论
本轮之后：
- `docs/interview/` 成为 ThinkRAG 表达 / 面试材料的分类目录；
- `docs/` 根目录仅保留 `docs/project.md` 作为项目级入口；
- 根目录去重、旧主线归档、桌面公共文档 canonical 收敛、面试材料归类四步治理链路已经收口。

这意味着后续如果再新增表达材料，应优先进入 `docs/interview/`，而不是重新散落回 `docs/` 根目录。

---

## 5. 风险与边界
1. 本轮只做路径归类，不改写 `ThinkRAG_面试问答.md` 正文内容。
2. 本轮不处理 `docs/project.md`；它仍保留为项目总览入口。
3. 本轮不清理 `docs/interview/ThinkRAG_面试全集_合并版.md` 与本文件之间的内容关系；若后续需要合并、去重或重新命名，应单独立项。
