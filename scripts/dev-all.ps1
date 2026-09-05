# ThinkRAG / NorthAgent 桌面联调统一入口
# - 先委托 start_dev.ps1 统一管理 FastAPI API + React(Vite)
# - 再单独拉起/停止 Electron desktop，避免复制旧启动链路
# - 所有运行态 PID 与日志统一落到仓库 logs/ 与 .dev-runtime/

param(
  [switch]$InstallDeps,
  [ValidateSet('runtime', 'full')]
  [string]$InstallProfile = 'runtime',
  [switch]$Stop,
  [Nullable[int]]$BackendPort = $null,
  [Nullable[int]]$FrontendPort = $null
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot
$START_DEV_SCRIPT = Join-Path $ROOT 'start_dev.ps1'
$LOG_DIR = Join-Path $ROOT 'logs'
$RUNTIME_DIR = Join-Path $ROOT '.dev-runtime'
$DESKTOP_DIR = Join-Path $ROOT 'desktop'
$DESKTOP_NODE_MODULES = Join-Path $DESKTOP_DIR 'node_modules'
$DEV_RUNTIME_HELPERS = Join-Path $PSScriptRoot 'dev-runtime-helpers.ps1'
if (-not (Test-Path $DEV_RUNTIME_HELPERS)) {
  throw "未找到开发启动共享 helper：$DEV_RUNTIME_HELPERS"
}
. $DEV_RUNTIME_HELPERS

$BackendPort = Resolve-BackendPort $BackendPort
$FrontendPort = Resolve-FrontendPort $FrontendPort
$API_BASE_URL = Resolve-ApiBaseUrl '' $BackendPort
$FRONTEND_URL = Resolve-FrontendUrl $FrontendPort

$DESKTOP_PID_FILE = Join-Path $RUNTIME_DIR (Get-DualPortScopedFileName 'desktop' $BackendPort $FrontendPort (Get-DefaultBackendPort) (Get-DefaultFrontendPort) '.pid')
$DESKTOP_OUT_LOG = Join-Path $LOG_DIR (Get-DualPortScopedFileName 'desktop_out' $BackendPort $FrontendPort (Get-DefaultBackendPort) (Get-DefaultFrontendPort) '.log')
$DESKTOP_ERR_LOG = Join-Path $LOG_DIR (Get-DualPortScopedFileName 'desktop_err' $BackendPort $FrontendPort (Get-DefaultBackendPort) (Get-DefaultFrontendPort) '.log')
$HEADLESS_DESKTOP_ENTRY = Join-Path $DESKTOP_DIR 'scripts\headless-runtime.js'
$ELECTRON_CLI = Join-Path $DESKTOP_NODE_MODULES 'electron\cli.js'

function Stop-RepoDesktopProcesses() {
  $processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $commandLine = [string]$_.CommandLine
    if (-not $commandLine) {
      return $false
    }
    $commandLine -like "*$ROOT*desktop*" -and (
      $commandLine -like "*electron*" -or
      $commandLine -like "*npm*" -or
      $commandLine -like "*node*"
    )
  }

  foreach ($process in $processes) {
    $pidValue = [int]$process.ProcessId
    if ($pidValue -le 0 -or $pidValue -eq $PID) {
      continue
    }
    Write-Host "Stopping stale desktop process (PID=$pidValue)..." -ForegroundColor Yellow
    Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
  }
}

if (-not (Test-Path $START_DEV_SCRIPT)) {
  throw "未找到统一开发启动脚本：$START_DEV_SCRIPT"
}

New-Item -ItemType Directory -Path $LOG_DIR -Force -ErrorAction SilentlyContinue | Out-Null
New-Item -ItemType Directory -Path $RUNTIME_DIR -Force -ErrorAction SilentlyContinue | Out-Null

$NPM_CMD = Resolve-CommandPath @('npm.cmd', 'npm') 'npm'
$NODE_CMD = Resolve-CommandPath @('node.exe', 'node') 'node'
$PYTHON_CMD = Resolve-PreferredPythonCommand
$REQUIREMENTS_PATH = Resolve-RequirementsPath $ROOT $InstallProfile

if ($InstallDeps) {
  Write-Host "[ThinkRAG] Installing root/webapp/desktop dependencies (profile=$InstallProfile)..." -ForegroundColor Cyan
  & $PYTHON_CMD -m pip install -r $REQUIREMENTS_PATH
  Push-Location (Join-Path $ROOT 'webapp')
  & $NPM_CMD install
  Pop-Location
  Push-Location $DESKTOP_DIR
  & $NPM_CMD install
  Pop-Location
}

if ($Stop) {
  Write-Host '[ThinkRAG] Stopping API + web via start_dev.ps1 ...' -ForegroundColor Yellow
  & $START_DEV_SCRIPT -Stop -BackendPort $BackendPort -FrontendPort $FrontendPort
  Stop-ManagedProcess $DESKTOP_PID_FILE 'desktop'
  Stop-RepoDesktopProcesses
  Write-Host '[ThinkRAG] Desktop workflow stopped.' -ForegroundColor Green
  return
}

Write-Host '[ThinkRAG] Starting API + web via start_dev.ps1 ...' -ForegroundColor Cyan
& $START_DEV_SCRIPT -BackendPort $BackendPort -FrontendPort $FrontendPort
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

Stop-ManagedProcess $DESKTOP_PID_FILE 'desktop'
Stop-RepoDesktopProcesses
Start-Sleep -Seconds 1

Write-Host "[ThinkRAG] Starting desktop shell bound to $FRONTEND_URL ..." -ForegroundColor Cyan
Set-DesktopRuntimeEnvironment -BackendPort $BackendPort -ApiBaseUrl $API_BASE_URL -FrontendPort $FrontendPort -FrontendUrl $FRONTEND_URL -PythonCommand $PYTHON_CMD
Normalize-StartProcessEnvironment
try {
  $desktopProcess = Start-DesktopProcess -NodeCommand $NODE_CMD -NpmCommand $NPM_CMD -DesktopDir $DESKTOP_DIR -HeadlessDesktopEntry $HEADLESS_DESKTOP_ENTRY -ElectronCli $ELECTRON_CLI -StdoutLog $DESKTOP_OUT_LOG -StderrLog $DESKTOP_ERR_LOG
} catch {
  Write-Host '[ThinkRAG] Desktop launch failed, showing recent logs...' -ForegroundColor Red
  Write-LogTail -Path $DESKTOP_OUT_LOG -Label 'desktop stdout'
  Write-LogTail -Path $DESKTOP_ERR_LOG -Label 'desktop stderr'
  throw
} finally {
  Clear-DesktopRuntimeEnvironment
}
Set-Content -LiteralPath $DESKTOP_PID_FILE -Value $desktopProcess.Id -Encoding ascii

Write-Host "    Desktop PID: $($desktopProcess.Id)" -ForegroundColor Green
Write-Host "    Desktop log: $DESKTOP_OUT_LOG" -ForegroundColor Green
Write-Host "    Web URL: $FRONTEND_URL" -ForegroundColor Green
Write-Host "    API URL: $API_BASE_URL" -ForegroundColor Green
Write-Host ''
Write-Host "Stop all: powershell -File $PSCommandPath -Stop -BackendPort $BackendPort -FrontendPort $FrontendPort" -ForegroundColor Yellow
