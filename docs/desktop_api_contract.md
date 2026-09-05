# ThinkRAG Desktop API Contract（兼容跳转说明）

## 当前状态

该文件仅保留为**根目录兼容跳转页**，避免历史链接或旧索引继续把它当作当前契约正文。

- **当前唯一主契约文档**：`docs/spec/desktop_api_contract.md`
- **当前主产品路径**：FastAPI + React (Vite) + Electron
- **旧 Streamlit 路径状态**：`app.py` + `frontend/*.py` 仅保留为 legacy compatibility shim，且必须显式设置 `KB_ALLOW_LEGACY_STREAMLIT=1` 才允许进入

## 应该查看哪里

如果你要确认当前桌面 / Web / API 契约，请直接查看：

- `docs/spec/desktop_api_contract.md`

该文档才是当前 source of truth，包含：

1. React / Electron QA Workspace 与 Knowledge Base Workspace 的 API 映射
2. Agent Runtime Workspace 与 Open Readonly API 合同
3. Runtime URL / port / preload bridge 的统一解析规则
4. `start_all.ps1` / `start_dev.ps1` 作为默认本地启动入口的说明

## 为什么还保留这个文件

1. 历史文档、旧索引或外部链接可能仍然引用 `docs/desktop_api_contract.md`
2. 直接删除会让这些引用失效，并继续制造“是不是少了一份主合同文档”的噪音
3. 因此这里故意收口成兼容跳转页，而不是继续复制一份会漂移的正文

## 明确边界

- 不要再把本文件视为当前 API contract 正文
- 不要在这里维护页面到接口的逐项映射
- 不要在这里恢复“当前仍以 Streamlit 页面为主入口”的叙事
- 如果主契约发生变化，只更新 `docs/spec/desktop_api_contract.md`
