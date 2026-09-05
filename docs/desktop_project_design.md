# ThinkRAG 桌面化项目设计文档（兼容跳转说明）

## 当前状态

该文件仅保留为**根目录兼容跳转页**，避免历史链接、旧索引或旧材料继续把它当作当前桌面设计正文。

- **当前唯一设计文档**：`docs/spec/desktop_project_design.md`
- **当前主线**：FastAPI + React（Vite）+ Electron
- **当前 source of truth**：桌面壳 / 前端 / Python API / RAG 核心分层设计，以及运行手册与发布链路边界，均以 `docs/spec/desktop_project_design.md` 为准

## 关键设计摘要

如果你只是快速确认当前桌面主线的设计边界，可以先看以下摘要：

1. **运行与发布边界**
   - 本地 desktop build helper：`scripts/build-desktop.ps1` / `scripts/build-desktop.sh`
   - 默认 runtime 依赖：`requirements-runtime.txt`
   - API-only PyInstaller 兼容 helper：`scripts/package-python-runtime.ps1`
2. **正式 macOS 发布链路**
   - 本地包验证：`build:mac` + `verify:package`
   - 正式发布：`release:preflight` + `release:mac`
3. **运行时基线**
   - 当前 gate 关注 `llama-index-core==0.11.19`
   - 不再把顶层 `llama_index` metapackage 当成默认 runtime baseline
4. **关联文档入口**
   - 运行手册：`docs/guide/desktop_runbook.md`
   - 回归清单：`docs/test/desktop_regression_checklist.md`

## 应该查看哪里

如果你要看完整架构、模块职责、接口边界、发布说明与后续演进，请直接查看：

- `docs/spec/desktop_project_design.md`

## 为什么还保留这个文件

1. 历史评审记录、外部链接和旧目录索引可能仍然引用 `docs/desktop_project_design.md`
2. 直接删除会让这些引用失效，并继续制造“是不是缺了一份设计文档”的噪音
3. 因此这里故意收口成兼容跳转页，而不是继续复制一份会再次漂移的正文

## 明确边界

- 不要再把本文件视为当前设计正文
- 不要在这里维护完整架构说明
- 如果桌面设计、发布链路或运行边界发生变化，只更新 `docs/spec/desktop_project_design.md`
