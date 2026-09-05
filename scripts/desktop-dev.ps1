# ThinkRAG / NorthAgent 桌面兼容联调 helper
# - 仅在你已经单独起好 FastAPI 时，辅助启动 Web + Electron
# - 不是主入口；完整 API + Web + Desktop 联调请优先使用 scripts/dev-all.ps1
# - 运行态 PID 与日志统一落到仓库 logs/ 与 .dev-runtime/

Param(
  [switch]$InstallDeps,
  [ValidateSet('runtime', 'full')]
  [string]$InstallProfile = 'runtime',
  [switch]$Stop,
  [Nullable[int]]$BackendPort = $null,
  [Nullable[int]]$FrontendPort = $null,
  [string]$ApiBaseUrl = ''
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot
$LOG_DIR = Join-Path $ROOT 'logs'
$RUNTIME_DIR = Join-Path $ROOT '.dev-runtime'
$WEBAPP_DIR = Join-Path $ROOT 'webapp'
$WEBAPP_NODE_MODULES = Join-Path $WEBAPP_DIR 'node_modules'
$VITE_CLI = Join-Path $WEBAPP_NODE_MODULES 'vite\bin\vite.js'
$WEBAPP_DEV_SERVER_ENTRY = Join-Path $WEBAPP_DIR 'scripts\dev-server.mjs'
$DESKTOP_DIR = Join-Path $ROOT 'desktop'
$DESKTOP_NODE_MODULES = Join-Path $DESKTOP_DIR 'node_modules'
$HEADLESS_DESKTOP_ENTRY = Join-Path $DESKTOP_DIR 'scripts\headless-runtime.js'
$ELECTRON_CLI = Join-Path $DESKTOP_NODE_MODULES 'electron\cli.js'
$DEV_RUNTIME_HELPERS = Join-Path $PSScriptRoot 'dev-runtime-helpers.ps1'
if (-not (Test-Path $DEV_RUNTIME_HELPERS)) {
  throw "未找到开发启动共享 helper：$DEV_RUNTIME_HELPERS"
}
. $DEV_RUNTIME_HELPERS

$BackendPort = Resolve-BackendPort $BackendPort
$FrontendPort = Resolve-FrontendPort $FrontendPort
$API_BASE_URL = Resolve-ApiBaseUrl $ApiBaseUrl $BackendPort
$BACKEND_RUNTIME_PORT = Resolve-ApiPortFromBaseUrl $API_BASE_URL $BackendPort
$FRONTEND_URL = Resolve-FrontendUrl $FrontendPort

$WEB_PID_FILE = Join-Path $RUNTIME_DIR (Get-DualPortScopedFileName 'desktop-web' $BackendPort $FrontendPort (Get-DefaultBackendPort) (Get-DefaultFrontendPort) '.pid')
$DESKTOP_PID_FILE = Join-Path $RUNTIME_DIR (Get-DualPortScopedFileName 'desktop-shell' $BackendPort $FrontendPort (Get-DefaultBackendPort) (Get-DefaultFrontendPort) '.pid')
$WEB_OUT_LOG = Join-Path $LOG_DIR (Get-DualPortScopedFileName 'desktop_web_out' $BackendPort $FrontendPort (Get-DefaultBackendPort) (Get-DefaultFrontendPort) '.log')
$WEB_ERR_LOG = Join-Path $LOG_DIR (Get-DualPortScopedFileName 'desktop_web_err' $BackendPort $FrontendPort (Get-DefaultBackendPort) (Get-DefaultFrontendPort) '.log')
$DESKTOP_OUT_LOG = Join-Path $LOG_DIR (Get-DualPortScopedFileName 'desktop_shell_out' $BackendPort $FrontendPort (Get-DefaultBackendPort) (Get-DefaultFrontendPort) '.log')
$DESKTOP_ERR_LOG = Join-Path $LOG_DIR (Get-DualPortScopedFileName 'desktop_shell_err' $BackendPort $FrontendPort (Get-DefaultBackendPort) (Get-DefaultFrontendPort) '.log')

$NPM_CMD = Resolve-CommandPath @('npm.cmd', 'npm') 'npm'
$NODE_CMD = Resolve-CommandPath @('node.exe', 'node') 'node'
$PYTHON_CMD = Resolve-PreferredPythonCommand

New-Item -ItemType Directory -Path $LOG_DIR -Force -ErrorAction SilentlyContinue | Out-Null
New-Item -ItemType Directory -Path $RUNTIME_DIR -Force -ErrorAction SilentlyContinue | Out-Null

if ($InstallDeps) {
  $requirementsPath = Resolve-RequirementsPath $ROOT $InstallProfile
  & $PYTHON_CMD -m pip install -r $requirementsPath
  Push-Location $WEBAPP_DIR
  & $NPM_CMD install
  Pop-Location
  Push-Location $DESKTOP_DIR
  & $NPM_CMD install
  Pop-Location
}

if ($Stop) {
  Stop-ManagedProcess $DESKTOP_PID_FILE 'desktop helper shell'
  Stop-ManagedProcess $WEB_PID_FILE 'desktop helper web'
  Write-Host '[ThinkRAG] Desktop compatibility helper stopped.' -ForegroundColor Green
  return
}

Write-Host '[ThinkRAG] desktop-dev.ps1 is a compatibility helper; prefer scripts/dev-all.ps1 for the unified API + Web + Desktop path.' -ForegroundColor Yellow
if ([string]::IsNullOrWhiteSpace($ApiBaseUrl)) {
  Write-Host "[ThinkRAG] Assuming FastAPI is already running at $API_BASE_URL ..." -ForegroundColor Yellow
} else {
  Write-Host "[ThinkRAG] Using explicit API base $API_BASE_URL for the compatibility helper path ..." -ForegroundColor Yellow
}

Stop-ManagedProcess $DESKTOP_PID_FILE 'desktop helper shell'
Stop-ManagedProcess $WEB_PID_FILE 'desktop helper web'
Start-Sleep -Seconds 1

Write-Host "[ThinkRAG] Starting Web dev server on $FRONTEND_URL (API base: $API_BASE_URL) ..." -ForegroundColor Cyan
Set-WebDevEnvironment -ApiBaseUrl $API_BASE_URL -FrontendPort $FrontendPort
Normalize-StartProcessEnvironment
try {
  $webProcess = Start-WebProcess -NodeCommand $NODE_CMD -NpmCommand $NPM_CMD -WebappDir $WEBAPP_DIR -DevServerEntry $WEBAPP_DEV_SERVER_ENTRY -ViteCli $VITE_CLI -StdoutLog $WEB_OUT_LOG -StderrLog $WEB_ERR_LOG -FrontendPort $FrontendPort
} finally {
  Clear-WebDevEnvironment
}
Set-Content -LiteralPath $WEB_PID_FILE -Value $webProcess.Id -Encoding ascii

Start-Sleep -Seconds 1

Write-Host "[ThinkRAG] Starting Electron desktop bound to $FRONTEND_URL ..." -ForegroundColor Cyan
Set-DesktopRuntimeEnvironment -BackendPort $BACKEND_RUNTIME_PORT -ApiBaseUrl $API_BASE_URL -FrontendPort $FrontendPort -FrontendUrl $FRONTEND_URL -PythonCommand $PYTHON_CMD
Normalize-StartProcessEnvironment
try {
  $desktopProcess = Start-DesktopProcess -NodeCommand $NODE_CMD -NpmCommand $NPM_CMD -DesktopDir $DESKTOP_DIR -HeadlessDesktopEntry $HEADLESS_DESKTOP_ENTRY -ElectronCli $ELECTRON_CLI -StdoutLog $DESKTOP_OUT_LOG -StderrLog $DESKTOP_ERR_LOG
} finally {
  Clear-DesktopRuntimeEnvironment
}
Set-Content -LiteralPath $DESKTOP_PID_FILE -Value $desktopProcess.Id -Encoding ascii

Write-Host "    Web PID: $($webProcess.Id)" -ForegroundColor Green
Write-Host "    Web log: $WEB_OUT_LOG" -ForegroundColor Green
Write-Host "    Desktop PID: $($desktopProcess.Id)" -ForegroundColor Green
Write-Host "    Desktop log: $DESKTOP_OUT_LOG" -ForegroundColor Green
Write-Host "    Web URL: $FRONTEND_URL" -ForegroundColor Green
Write-Host "    API URL: $API_BASE_URL" -ForegroundColor Green
Write-Host ''
Write-Host "Stop helper: powershell -File $PSCommandPath -Stop -BackendPort $BackendPort -FrontendPort $FrontendPort" -ForegroundColor Yellow
if (-not [string]::IsNullOrWhiteSpace($ApiBaseUrl)) {
  Write-Host "Explicit API base: $API_BASE_URL" -ForegroundColor Yellow
}
