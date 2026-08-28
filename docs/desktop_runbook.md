# ThinkRAG Desktop Runbook（兼容跳转说明）

## 当前状态

该文件仅保留为**根目录兼容跳转页**，避免历史链接、旧索引或旧 audit 材料继续把它当作当前桌面运行手册正文。

- **当前唯一运行手册**：`docs/guide/desktop_runbook.md`
- **当前主线**：FastAPI + React（Vite）+ Electron
- **默认本地入口**：`start_all.ps1` / `scripts/dev-all.ps1`
- **legacy Streamlit 状态**：`app.py` + `frontend/` 仍保留为 legacy 兼容 shim，必须显式设置 `KB_ALLOW_LEGACY_STREAMLIT=1`

## 快速契约摘要

如果你只是想快速确认“当前桌面主线怎么跑”，至少记住下面几条：

1. **联调优先入口**
   - API + Web：`powershell -File .\start_all.ps1`
   - API + Web + Desktop：`powershell -File .\scripts\dev-all.ps1`
   - 仅 Web + Desktop 兼容 helper：`powershell -File .\scripts\desktop-dev.ps1`
   - 停止兼容 helper：`powershell -File .\scripts\desktop-dev.ps1 -Stop`
2. **端口与 API Base 契约**
   - FastAPI fallback：`18080`
   - Vite fallback：`5173`
   - 优先遵循 `KB_API_BASE_URL` / `KB_API_PORT` / `VITE_API_BASE_URL`
   - 如果显式把 `KB_API_BASE_URL` 配成远端非 loopback 地址，Electron 只探活该远端 API，不会自动回退到本地 `run_api.py`
   - `-BackendPort` / `-FrontendPort` 会沿统一契约透传
   - 如果传入 `-BackendPort 18095 -FrontendPort 5176`，就应按覆盖后的地址理解联调结果
3. **依赖基线**
   - 默认 runtime profile：`requirements-runtime.txt`
   - 当前显式锁定：`httpx==0.27.2`
   - 如果 pytest / TestClient 报 `Client.__init__() got an unexpected keyword argument 'app'`，先回到该 runtime profile
4. **Docker smoke 建议**
   - 优先：`python scripts/docker_smoke.py --install-profile smoke --app-runtime-mode api`
   - helper 默认让 Docker 自动分配 loopback host port，再用 `docker port` 回查映射
   - `docker run -p 18080:18080` 只是固定端口手工复现实例，不是唯一有效口径

## 应该查看哪里

如果你要看当前完整运行说明、端口覆盖、安装 profile、桌面 helper、Docker smoke 或 legacy 边界，请直接查看：

- `docs/guide/desktop_runbook.md`

该文档才是当前 source of truth。

## 为什么还保留这个文件

1. 历史文档、旧索引和部分审计材料仍可能引用 `docs/desktop_runbook.md`
2. 直接删除会让这些引用失效，并继续制造“是不是缺一份运行手册正文”的噪音
3. 因此这里故意收口成兼容跳转页，而不是继续保留一份会再次漂移的正文副本

## 明确边界

- 不要再把本文件视为当前 runbook 正文
- 不要在这里维护完整启动步骤或长篇联调说明
- 如运行契约发生变化，只更新 `docs/guide/desktop_runbook.md`
