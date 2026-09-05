# ThinkRAG Desktop Runbook

> 当前桌面开发主线已经统一为 **FastAPI + React（Vite）+ Electron**。如果你只记一个入口：联调优先用 `scripts/dev-all.ps1`，纯 API/Web 优先用 `start_all.ps1` / `start_dev.ps1`。
> **当前 source of truth**：本文是桌面运行、联调、依赖与 Docker smoke 的唯一 canonical 说明；`docs/desktop_runbook.md` 仅保留为根目录兼容跳转页。

## 1. 入口选择

| 场景 | 推荐命令 | 说明 |
|---|---|---|
| API + Web | `powershell -File .\start_all.ps1` | Windows 主入口；会委托 `start_dev.ps1` |
| API + Web + Desktop | `powershell -File .\scripts\dev-all.ps1` | 一键联调主入口 |
| 仅 Web + Desktop | `powershell -File .\scripts\desktop-dev.ps1` | 兼容 helper；适合你已经单独起好 FastAPI |
| 停止 API + Web | `powershell -File .\start_all.ps1 -Stop` | 停止 `start_dev.ps1` 管理的进程 |
| 停止 API + Web + Desktop | `powershell -File .\scripts\dev-all.ps1 -Stop` | 同时停止 Electron 与 API/Web |
| 停止仅 Web + Desktop helper | `powershell -File .\scripts\desktop-dev.ps1 -Stop` | 停止 `desktop-dev.ps1` 管理的 Web/Electron |

`dev-all.ps1` 会把 API/Web 启动委托给 `start_dev.ps1`，因此 `-BackendPort/-FrontendPort` 会沿同一条契约传到 FastAPI、Vite 与 Electron。当前 `scripts/dev-runtime-helpers.ps1` 是这条启动契约的共享实现，统一负责 API base fallback、frontend loopback URL、extra dev origins，以及 Web / Electron 的运行态环境变量注入；如果后续继续收口脚本漂移，优先改 helper，而不是让各个 wrapper 再单独复制默认值。

## 2. 默认端口与环境变量契约

| 项目 | 默认 fallback 值 | 覆盖方式 |
|---|---|---|
| FastAPI | `18080` | `-BackendPort` / `KB_API_PORT` |
| React（Vite） | `5173` | `-FrontendPort` |
| 前端 API Base | `http://127.0.0.1:18080` | `VITE_API_BASE_URL` |
| Electron 加载地址 | `http://127.0.0.1:5173` | 由 `dev-all.ps1` / `desktop-dev.ps1` 透传 `KB_WEB_URL`（并兼容 `NORTHAGENT_WEB_URL` / `THINKRAG_WEB_URL` / `FOXGLOVE_WEB_URL`） |

上表里的 `18080` / `5173` 都只是 fallback 默认值，不是唯一有效口径。诊断脚本、API smoke check 与桌面联调都应优先遵循 `KB_API_BASE_URL` / `KB_API_PORT` 契约；前端独立启动且后端不在默认端口时，请显式设置 `VITE_API_BASE_URL`。

如果显式把 `KB_API_BASE_URL` 配成远端非 loopback 地址，Electron 只会探活该远端 API，不会自动回退到本地 `run_api.py`；远端不可达时应直接排查该地址、网络连通性和目标服务状态。

如果做 Docker smoke / regression，优先使用 `python scripts/docker_smoke.py --install-profile smoke --app-runtime-mode api`。该 helper 默认不会抢占宿主机 `18080`，而是让 Docker 自动分配一个 loopback host port，再通过 `docker port` 回查映射；文档里的 `docker run -p 18080:18080` 仅是固定端口手工复现实例。

## 3. 安装依赖

### 推荐：runtime profile

```powershell
python -m pip install -r requirements-runtime.txt
cd webapp; npm install; cd ..
cd desktop; npm install; cd ..
```

`requirements-runtime.txt` 现在会显式锁定 `httpx==0.27.2`。如果本地 API 测试、`fastapi.testclient.TestClient` 或 pytest collection 报出 `Client.__init__() got an unexpected keyword argument 'app'`，基本可以判定是 `httpx 0.28+` 漂移；先重装当前 profile，或最小化执行 `python -m pip install httpx==0.27.2`。

### 如需 full profile

```powershell
python -m pip install -r requirements.txt
```

### 也可直接让脚本代装依赖

```powershell
.\scripts\desktop-dev.ps1 -InstallDeps
.\scripts\dev-all.ps1 -InstallDeps
# 如需 full profile：.\scripts\dev-all.ps1 -InstallDeps -InstallProfile full
```

## 4. 启动方式

### 4.1 API + Web（推荐主入口）

```powershell
powershell -File .\start_all.ps1
powershell -File .\start_all.ps1 -BackendPort 18095 -FrontendPort 5176
```

`start_all.ps1` 会委托 `start_dev.ps1`，并把 **FastAPI + React（Vite）** 作为默认开发主线。

### 4.2 API + Web + Desktop（推荐桌面联调）

```powershell
powershell -File .\scripts\dev-all.ps1
powershell -File .\scripts\dev-all.ps1 -BackendPort 18095 -FrontendPort 5176
```

按默认端口启动时，会得到：

- FastAPI API：`http://127.0.0.1:18080`
- React dev server：`http://127.0.0.1:5173`
- Electron desktop shell：绑定到当前运行中的 Web dev server

如果传入 `-BackendPort 18095 -FrontendPort 5176`，上述地址会同步变成 `http://127.0.0.1:18095` 与 `http://127.0.0.1:5176`。

### 4.3 仅 Web + Desktop

```powershell
powershell -File .\scripts\desktop-dev.ps1
powershell -File .\scripts\desktop-dev.ps1 -BackendPort 18095 -FrontendPort 5176
powershell -File .\scripts\desktop-dev.ps1 -ApiBaseUrl https://api.example.com:18443 -FrontendPort 5176
powershell -File .\scripts\desktop-dev.ps1 -Stop
```

`desktop-dev.ps1` 也支持 `-BackendPort/-FrontendPort`、`-ApiBaseUrl` 与 `-Stop`。脚本会同步注入 `VITE_API_BASE_URL`、`KB_API_BASE_URL` / `KB_API_PORT`、`KB_WEB_URL` / `KB_WEB_PORT`，以及 `NORTHAGENT_*` / `THINKRAG_*` / `FOXGLOVE_*` 兼容别名和桌面端 Python 运行时参数，并把 helper 专属 PID / 日志写到 `.dev-runtime/desktop-web*.pid`、`.dev-runtime/desktop-shell*.pid` 与 `logs/desktop_*`；如果 FastAPI 并不在本机默认端口，而是已经跑在其他地址，可以直接传 `-ApiBaseUrl https://api.example.com:18443`。显式 `-ApiBaseUrl` 必须是绝对 `http(s)` URL，非法值会在 helper 启动 Web / Electron 之前直接报错。但它不会启动 FastAPI，适合你已经单独起好后端的场景。若要走统一主线，请优先使用 `scripts/dev-all.ps1`。

## 5. API Smoke Check

```powershell
python run_api.py
python -c "import os,requests; base=(os.getenv('KB_API_BASE_URL') or f'http://127.0.0.1:{os.getenv("KB_API_PORT", "18080")}').rstrip('/'); print(requests.get(base + '/api/health', timeout=5).json())"
```

期望：

- `code == 0`
- `data.status == ok`

## 6. 打包

### Windows

```powershell
.\scripts\build-desktop.ps1 -InstallDeps
# 如需 full profile：.\scripts\build-desktop.ps1 -InstallDeps -InstallProfile full
```

### macOS / Linux

```bash
chmod +x scripts/build-desktop.sh
./scripts/build-desktop.sh --install-deps
# 如需 full profile：./scripts/build-desktop.sh --install-deps --install-profile full
```

Build artifacts are generated under `desktop/dist`.

## 7. 运行与维护说明

- `app.py` + `frontend/` 仍保留为 legacy 代码路径，但不再是桌面主线运行入口；如果确实要查看旧 Streamlit UI，请先安装 `requirements.txt`，再设置 `KB_ALLOW_LEGACY_STREAMLIT=1` 后执行 `python -m streamlit run app.py`。
- `scripts/dev-all.ps1` 会在 `.dev-runtime/desktop.pid` 维护 Electron 进程；异常退出后可先执行 `powershell -File .\scripts\dev-all.ps1 -Stop` 再重启。
- `scripts/desktop-dev.ps1` 现在也会为兼容 helper 维护独立的 `.dev-runtime/desktop-web*.pid`、`.dev-runtime/desktop-shell*.pid` 和 `logs/desktop_*`；如果只跑 helper，可用 `powershell -File .\scripts\desktop-dev.ps1 -Stop` 回收。
- 如果本地环境出现 `pydantic` 或 LlamaIndex 版本漂移，先重装当前选定 profile（默认 `requirements-runtime.txt`，必要时再切到 `requirements.txt`）。
- Electron 首次打包需要从 GitHub 下载 Electron 二进制；若网络受限，请先配置代理或镜像，再执行打包命令。
- 更完整的项目现状、验证证据与已知问题，请结合 `docs/project.md` 与 `docs/20260821-project-audit-remediation/` 一起阅读。
