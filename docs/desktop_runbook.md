# ThinkRAG Desktop Runbook

## 1. Local Development

### Prerequisites

- Python 3.10+
- Node.js 18+
- npm

### Install dependencies

```powershell
python -m pip install -r requirements.txt
cd webapp; npm install; cd ..
cd desktop; npm install; cd ..
```

### Start desktop dev mode

```powershell
.\scripts\desktop-dev.ps1
```

或使用一键联调（显式启动 API + Web + Desktop）：

```powershell
.\scripts\dev-all.ps1
```

This starts:

- React dev server at `http://127.0.0.1:5173`
- Electron desktop shell
- Python API is auto-started by Electron (`run_api.py`)

## 2. API Smoke Check

Run:

```powershell
python run_api.py
```

Then check:

```powershell
python -c "import requests;print(requests.get('http://127.0.0.1:18080/api/health',timeout=5).json())"
```

Expected:

- `code` is `0`
- `data.status` is `ok`

## 3. Build Desktop Packages

### Windows

```powershell
.\scripts\build-desktop.ps1 -InstallDeps
```

### macOS/Linux

```bash
chmod +x scripts/build-desktop.sh
./scripts/build-desktop.sh --install-deps
```

`desktop/package.json` 中的 `npm run build` 会按当前平台自动选择目标：

- Windows 主机打包 `--win`
- macOS 主机打包 `--mac`

Build artifacts are generated under `desktop/dist`.

## 4. Package Python Runtime (Optional)

If you need to bundle API as a standalone executable:

```powershell
.\scripts\package-python-runtime.ps1
```

Output path defaults to:

- `desktop/resources/python/thinkrag-api(.exe)`

## 5. Known Notes

- Current query/index pipeline relies on `llama_index` runtime dependencies.
- If local environment has a `pydantic` mismatch, align by reinstalling from `requirements.txt`.
- Keep `streamlit run app.py` as migration fallback until feature parity acceptance.
- Electron 首次打包需要从 GitHub 下载 Electron 二进制；若网络受限，请先配置代理或镜像，再执行 `npm run build`。
- 功能回归清单见 `docs/desktop_regression_checklist.md`，建议每次发布前执行。
