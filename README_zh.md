# NorthAgent / ThinkRAG

NorthAgent 是一款本地优先的知识库助手。当前产品主线采用 **FastAPI + React + Electron + LlamaIndex**；仓库名、部分 Python 包名继续保留 `ThinkRAG`，用于兼容已有代码和数据。

## 当前能力

- 多知识库显式选择，未指定范围时默认拒绝问答，避免隐式跨库检索。
- 物理索引隔离：历史 `default` 知识库继续兼容 `storage/`，其他知识库分别持久化到 `storage/kbs/{kb_id}/`，各自拥有独立 docstore、index store 和 vector store 文件。
- 支持文件、Markdown、PDF、图片 OCR、网页导入，并提供导入回执和证据元数据。
- `/api/health` 提供 Embedding 诊断；本地 BGE 缓存缺失时，Knowledge Workspace 可点击“使用 ModelScope 准备缓存”，下载完成后自动重新预热。
- PaddleOCR 结果按几何坐标恢复阅读顺序；扫描 PDF 保留 `[Page N]` 页边界；规则表格可启发式恢复成 Markdown 表格；质量脚本覆盖关键词召回、行顺序和表格单元格召回。
- React Knowledge Workspace、Agent Workspace 与 Electron 桌面壳，桌面产品名为 **NorthAgent**。

## macOS 开发环境

必须优先使用已经验证通过的 conda 环境，不要使用仓库中由 Windows 创建的 `.venv`。

```bash
conda activate agent-kb
# 非交互脚本建议直接使用绝对路径
/opt/miniconda3/envs/agent-kb/bin/python --version
/opt/miniconda3/envs/agent-kb/bin/python -m pip install -r requirements-runtime.txt
# 如需本地 OCR / legacy 扩展 / 更完整依赖，再切到 full profile
/opt/miniconda3/envs/agent-kb/bin/python -m pip install -r requirements.txt
```

项目运行时基线为 Python 3.12，LlamaIndex 依赖口径以 `llama-index-core==0.11.19` 和仓库实际使用到的 integration packages 为中心。`requirements-runtime.txt` 会**刻意避开**顶层 `llama_index` metapackage，因为它会把 OpenAI / LlamaCloud / LlamaParse 一整串默认 API 并不需要的依赖拉进来，导致 Docker 解析明显变慢；`requirements.txt` 则保留更完整的本地 profile，包含 OCR、legacy Streamlit 兼容包以及其他较重依赖。

共享的运行时 / 测试基线现在也显式锁定 `httpx==0.27.2`。这是有意为之：FastAPI 0.104 / Starlette 0.27 的 `TestClient` 与 `httpx 0.28+` 不兼容。如果本地 pytest collection 或 API 测试报出 `Client.__init__() got an unexpected keyword argument 'app'`，请先重装当前 profile（`python -m pip install -r requirements-runtime.txt`），或最小化执行 `python -m pip install httpx==0.27.2`。

## 本地启动

### Windows 统一开发入口

```powershell
powershell -File .\start_all.ps1
powershell -File .\start_all.ps1 -BackendPort 18095 -FrontendPort 5176
powershell -File .\start_all.ps1 -Stop
```

`start_all.ps1` 会委托 `start_dev.ps1`，并把 **FastAPI + React（Vite）** 作为默认开发主线。仓库中的 `app.py` + `frontend/` 仅保留为兼容/阅读旧实现的入口，不再是当前主入口。如果确实需要查看历史 Streamlit UI，请先安装 `requirements.txt`，再设置 `KB_ALLOW_LEGACY_STREAMLIT=1` 后执行 `python -m streamlit run app.py`。

### 通过脚本安装桌面联调依赖

```powershell
powershell -File .\scripts\dev-all.ps1 -InstallDeps
powershell -File .\scripts\dev-all.ps1 -InstallDeps -InstallProfile full
```

脚本默认安装 `requirements-runtime.txt`；只有明确需要更完整本地依赖时才使用 `-InstallProfile full`。

### Docker 运行 / 评测 profile

```bash
docker build -t agent-kb-api --build-arg INSTALL_PROFILE=runtime .
docker run --rm -p 18080:18080 agent-kb-api

docker build -t agent-kb-eval --build-arg INSTALL_PROFILE=eval .
docker run --rm -e APP_RUNTIME_MODE=eval -v "${PWD}:/app" agent-kb-eval
```

`INSTALL_PROFILE` 用来决定镜像里安装哪套依赖（`runtime`、`full`、`dev`、`prod`、`eval`）；`APP_RUNTIME_MODE` 用来决定容器默认启动什么进程（`api`、`prod`、`eval`）。现在 Docker 默认是 `INSTALL_PROFILE=runtime` + API 模式，和本地 FastAPI 开发主线保持一致；需要 semireal 回归镜像时再显式切到 `eval`。`requirements-minimal.txt` 仅保留为本地旧脚本兼容别名，不再作为 Docker install profile。

上面的 `docker run -p 18080:18080` 只是固定端口的手工复现实例。做可重复的 smoke / regression 时，优先使用 `python scripts/docker_smoke.py --install-profile smoke --app-runtime-mode api`：该 helper 默认会让 Docker 自动分配一个 loopback host port，再通过 `docker port` 回查映射，因此不会把 `18080` 误写成当前唯一 source of truth。只有明确需要固定对外端口时，再显式传 `--host-port`。

### macOS / 手动启动 API

```bash
/opt/miniconda3/envs/agent-kb/bin/python run_api.py
```

默认本地 fallback 地址为 `http://127.0.0.1:18080`，健康诊断接口为 `/api/health`。对于客户端探活、诊断脚本和评测 harness，优先使用 `KB_API_BASE_URL`；如果只是本机端口变化，再设置 `KB_API_PORT`。出于兼容考虑，`run_api.py` 本身也会继续读取 `NORTHAGENT_API_PORT` / `THINKRAG_API_PORT` / `FOXGLOVE_API_PORT`。

### Web 前端

```bash
cd webapp
npm install
npm run dev
```

如果前端独立启动且后端端口不是默认 fallback `18080`，请显式设置 `VITE_API_BASE_URL`。浏览器 renderer 不会直接读取 Python/Node 侧的 `KB_API_BASE_URL` 等别名。

### Electron 桌面端

```bash
cd desktop
npm install
NORTHAGENT_PYTHON=/opt/miniconda3/envs/agent-kb/bin/python npm run dev
```

Windows 上如果希望用一条命令把 Electron、web 和 API 绑到同一套端口配置，建议使用 `scripts/dev-all.ps1 -BackendPort <api_port> -FrontendPort <web_port>`。该脚本现在会复用 `start_dev.ps1` 的前后端启动逻辑、在 `.dev-runtime/desktop.pid` 维护桌面进程，并支持 `powershell -File .\scripts\dev-all.ps1 -Stop` 一键停止。

如果你只想启动 Web + Electron，而不顺手拉起 FastAPI，可以使用：

```powershell
powershell -File .\scripts\desktop-dev.ps1
powershell -File .\scripts\desktop-dev.ps1 -BackendPort 18095 -FrontendPort 5176
powershell -File .\scripts\desktop-dev.ps1 -ApiBaseUrl https://api.example.com:18443 -FrontendPort 5176
powershell -File .\scripts\desktop-dev.ps1 -Stop
powershell -File .\scripts\desktop-dev.ps1 -InstallDeps
powershell -File .\scripts\desktop-dev.ps1 -InstallDeps -InstallProfile full
```

`desktop-dev.ps1` 现在也支持 `-BackendPort/-FrontendPort`、`-ApiBaseUrl` 与 `-Stop`，会把 `VITE_API_BASE_URL`、`KB_API_BASE_URL` / `KB_API_PORT`、`KB_WEB_URL` 以及 `NORTHAGENT_*` / `THINKRAG_*` / `FOXGLOVE_*` 兼容别名和桌面端 Python 运行时参数一起对齐到同一套契约，并在 `.dev-runtime/` 与 `logs/` 下维护 helper 专属 PID / 日志文件；如果 FastAPI 已经跑在别处，可以直接传 `-ApiBaseUrl https://api.example.com:18443`，而不必再伪装成本地 `127.0.0.1` 端口。显式 `-ApiBaseUrl` 必须是绝对 `http(s)` URL，非法值会在 helper 启动 Web / Electron 之前直接报错。它仍然只是“后端已在别处启动”场景下的**兼容 helper**，不会帮你拉起 FastAPI。完整主线仍应优先使用 `scripts/dev-all.ps1`。

## Embedding 缓存恢复

当 `/api/health` 返回“本地缓存不存在且运行时禁止远程下载”时，知识库页面会显示恢复按钮。按钮只允许使用白名单中的 `modelscope` 来源，不执行任意 shell 命令，也不要求用户输入密码或密钥。

也可使用 CLI：

```bash
/opt/miniconda3/envs/agent-kb/bin/python scripts/prepare_embedding_model_cache.py \
  --model bge-small-zh-v1.5 --download --provider modelscope
```

## 验证命令

```bash
# 启动脚本 / requirements profile 静态契约
python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_docs_entry_contracts.py tests/test_requirements_profiles.py tests/scripts/test_cleanup_local_artifacts.py -q

# Python 非 slow 全量测试
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"

# Web 单测与生产构建
node --test webapp/src/**/*.test.js
npm run build --prefix webapp

# Electron 测试
cd desktop
node --test src/*.test.js scripts/*.test.js
```

## 打包状态

当前可以进行未签名或 ad-hoc 的本地开发构建验证。桌面打包运行时现在以 `requirements-runtime.txt` 作为依赖基线。正式 macOS 分发仍需要 Apple Developer 证书、签名、公证和安装后回归；这些外部发布门禁当前明确跳过，不能据此宣称正式 macOS 版本已经发布完成。

- 本地桌面构建 helper：`powershell -File .\scripts\build-desktop.ps1 -InstallDeps` 和 `bash ./scripts/build-desktop.sh --install-deps`。它们会优先读取 `KB_PYTHON`，默认使用 `runtime` install profile，只负责准备 `webapp/dist` 和 Electron bundle 供本地验证，不替代正式 release 链路。
- 当前正式 mac 打包 / 发布链路：`cd desktop && npm run build:mac && npm run verify:package` 用于 ad-hoc 本地包验证；`cd desktop && npm run release:preflight && npm run release:mac` 才是要求严格公证的正式链路。`release:mac` 才是已签名 mac 分发的当前 source of truth，因为它会串起 `build:preflight`、严格 `release:preflight`、`verify:package` 和 `verify:mac-release`。
- `scripts/package-python-runtime.ps1` 仅保留为 API-only 的 PyInstaller 兼容 helper，不是当前 Electron 桌面主打包链路。

## 文档

- [项目进度与运行命令](./docs/project.md)

`docs/2026.../` 下的历史账本会刻意保留当时真实执行过的命令、端口和输出路径（其中很多示例写的是 `--api-base http://127.0.0.1:18080`）。应把它们视为证据快照，而不是当前运行时契约的 source of truth。
- [本地多知识库产品文档](./docs/20260722-local-multi-kb-assistant/)

## License

[MIT](./LICENSE)

## 迁移、只读 Agent API 与 OCR/缓存运维

当前本地 API 还提供：

- `GET/POST /api/kb/migration/{status,scan,start,rollback}`：支持无副作用扫描、逐知识库迁移、带校验的备份、仅重试失败项和批次回滚。
- 只读 Agent API：`GET /api/open/v1/me`、`GET /api/open/v1/knowledge-bases`、`POST /api/open/v1/search`、`POST /api/open/v1/answer`。每次请求都必须携带 Bearer 令牌，令牌只允许访问已授权知识库；令牌管理接口仅允许回环地址。
- 令牌管理 CLI：
  ```bash
  /opt/miniconda3/envs/agent-kb/bin/python scripts/manage_access_tokens.py create --name robot --kb finance
  /opt/miniconda3/envs/agent-kb/bin/python scripts/manage_access_tokens.py list
  /opt/miniconda3/envs/agent-kb/bin/python scripts/manage_access_tokens.py revoke TOKEN_ID
  ```
  明文令牌只在 `create` 时返回一次，存储文件只保存 HMAC 摘要。不要把本机管理员密钥注入 renderer 或前端 bundle。
- Embedding 缓存操作：`GET /api/embedding/cache`、`POST /api/embedding/cache/preflight`、`POST /api/embedding/cache/prepare`、`POST /api/embedding/cache/cancel`。磁盘空间预检不足返回 HTTP `507`；下载状态包含阶段、字节数、估算/精确进度和取消状态。
- OCR 扫描基准工具：
  ```bash
  /opt/miniconda3/envs/agent-kb/bin/python scripts/build_ocr_scan_benchmark.py
  /opt/miniconda3/envs/agent-kb/bin/python scripts/eval_ocr_scan_benchmark.py
  ```
  已提交的基准集区分项目自制清晰页面与合成退化样本，是离线确定性基线；真实 PaddleOCR 执行仍属于单独的 slow/runtime 检查。
