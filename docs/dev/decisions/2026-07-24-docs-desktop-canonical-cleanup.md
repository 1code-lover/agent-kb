# 2026-07-24 桌面公共文档 canonical 收敛记录

## 1. 背景
在完成旧主线原件迁出后，`docs/` 根目录还残留两份桌面公共文档副本：
1. `docs/desktop_project_design.md`
2. `docs/desktop_runbook.md`

它们分别与下列分类目录版本几乎一致：
- `docs/spec/desktop_project_design.md`
- `docs/guide/desktop_runbook.md`

实际差异仅体现在链接路径仍指向旧的根目录文档入口，因此继续保留根目录副本没有新的信息价值，只会继续制造“哪个版本才是准的”认知负担。

---

## 2. 核实结果
### 2.1 `desktop_project_design.md`
根目录版与 `docs/spec/desktop_project_design.md` 的正文差异仅有两处：
1. 运行手册链接从 `docs/desktop_runbook.md` 改为 `docs/guide/desktop_runbook.md`
2. 回归清单链接从 `docs/desktop_regression_checklist.md` 改为 `docs/test/desktop_regression_checklist.md`

### 2.2 `desktop_runbook.md`
根目录版与 `docs/guide/desktop_runbook.md` 的正文差异仅有一处：
1. 回归清单链接从 `docs/desktop_regression_checklist.md` 改为 `docs/test/desktop_regression_checklist.md`

结论：`docs/spec/desktop_project_design.md` 与 `docs/guide/desktop_runbook.md` 已可直接视为唯一 canonical 版本。

---

## 3. 本次动作
1. 备份根目录副本到 `temp/ai_delete_backups/20260724_203016/docs-desktop-canonical-cleanup/`
2. 从 `docs/` 根目录删除：
   - `desktop_project_design.md`
   - `desktop_runbook.md`
3. 保留分类目录中的 canonical 版本不变
4. 同步更新：
   - `docs/guide/DOCS_INDEX.md`
   - `docs/20260722-local-multi-kb-assistant/20260722-local-multi-kb-assistant-rtm.md`

---

## 4. 当前结论
本轮之后：
- 桌面整体设计只看 `docs/spec/desktop_project_design.md`
- 桌面运行手册只看 `docs/guide/desktop_runbook.md`

这意味着 `docs/` 根目录进一步收敛为：
1. `docs/project.md`
2. `docs/ThinkRAG_面试问答.md`

也即：根目录只保留项目级总览入口和一个待后续归类的表达材料文件。

补充更新（2026-07-25）：`docs/ThinkRAG_面试问答.md` 已迁入 `docs/interview/ThinkRAG_面试问答.md`，因此当前 `docs/` 根目录只保留 `docs/project.md`。详见 `docs/dev/decisions/2026-07-25-docs-interview-material-move.md`。
