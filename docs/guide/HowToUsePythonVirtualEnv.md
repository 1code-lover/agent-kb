# Python 虚拟环境与当前主入口使用说明

当前项目主线已经不是直接运行 Streamlit。推荐用虚拟环境 + `requirements-runtime.txt` 拉起 **FastAPI + React（Vite）**；只有在确实需要查看历史 Streamlit UI 时，才切到 full profile 并显式 opt-in。

## 1. 创建虚拟环境

```zsh
python -m venv .venv
```

## 2. 激活虚拟环境

```zsh
# Windows command prompt
.venv\Scripts\activate.bat

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS and Linux
source .venv/bin/activate
```

## 3. 安装当前主线依赖

```zsh
python -m pip install -r requirements-runtime.txt
```

如果你需要本地 OCR、旧 Streamlit 兼容包或其他完整本地扩展，再补装：

```zsh
python -m pip install -r requirements.txt
```

如果本地 API pytest、`fastapi.testclient.TestClient` 或 pytest collection 报出 `Client.__init__() got an unexpected keyword argument 'app'`，优先检查虚拟环境里的 `httpx` 是否漂到了 `0.28+`。当前主线 runtime profile 会显式锁定 `httpx==0.27.2`，建议先重装 `requirements-runtime.txt`，或最小化执行：

```zsh
python -m pip install httpx==0.27.2
```

## 4. 当前推荐启动方式

```powershell
powershell -File .\start_all.ps1
# 或者：powershell -File .\start_dev.ps1
```

如果只想单独启动 API：

```zsh
python run_api.py
```

如果客户端探活、诊断脚本或评测命令需要连接非默认地址，优先设置 `KB_API_BASE_URL`；如果只是本机端口变更，可设置 `KB_API_PORT`。前端独立启动时仍要显式设置 `VITE_API_BASE_URL`，浏览器不会直接读取 `KB_API_BASE_URL`。

## 5. 仅在需要旧 Streamlit UI 时

历史 `app.py` + `frontend/` 只保留为 legacy 入口。若确实需要查看：

```zsh
python -m pip install -r requirements.txt
KB_ALLOW_LEGACY_STREAMLIT=1 python -m streamlit run app.py
```

Windows PowerShell 可写成：

```powershell
$env:KB_ALLOW_LEGACY_STREAMLIT = '1'
python -m streamlit run app.py
```

## 6. 退出虚拟环境

```zsh
deactivate
```
