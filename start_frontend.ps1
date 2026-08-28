# ThinkRAG / NorthAgent 前端兼容入口
# 注意：这不是当前主入口。完整本地启动请使用 start_all.ps1 或 start_dev.ps1。
# 仅用于只拉起 React(Vite) 前端并手动指向某个后端地址的窄用途场景。
# 该脚本会尽量复用与 start_dev.ps1 相同的 web helper / env contract，减少前端-only 与主链路漂移。

param(
    [Nullable[int]]$BackendPort = $null,
    [Nullable[int]]$FrontendPort = $null,
    [string]$ApiBaseUrl = ''
)

$ROOT = Split-Path -Parent $PSCommandPath
$WEBAPP_DIR = Join-Path $ROOT 'webapp'
$WEBAPP_NODE_MODULES = Join-Path $WEBAPP_DIR 'node_modules'
$WEBAPP_DEV_SERVER_ENTRY = Join-Path $WEBAPP_DIR 'scripts\dev-server.mjs'
$VITE_CLI = Join-Path $WEBAPP_NODE_MODULES 'vite\bin\vite.js'
$DEV_RUNTIME_HELPERS = Join-Path $ROOT 'scripts\dev-runtime-helpers.ps1'
if (-not (Test-Path $DEV_RUNTIME_HELPERS)) {
    throw "未找到开发启动共享 helper：$DEV_RUNTIME_HELPERS"
}
. $DEV_RUNTIME_HELPERS

$BackendPort = Resolve-BackendPort $BackendPort
$FrontendPort = Resolve-FrontendPort $FrontendPort
$API_BASE_URL = Resolve-ApiBaseUrl $ApiBaseUrl $BackendPort

$NPM_CMD = Resolve-CommandPath @('npm.cmd', 'npm') 'npm'
$NODE_CMD = Resolve-CommandPath @('node.exe', 'node') 'node'

Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  ThinkRAG / NorthAgent Frontend Only" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "兼容脚本：只启动 React(Vite) 前端，不拉起后端。" -ForegroundColor Yellow
Write-Host "如需指向非默认后端地址，可直接传 -ApiBaseUrl。" -ForegroundColor Yellow
Write-Host "完整前后端联调请使用：powershell -File .\start_all.ps1" -ForegroundColor Yellow
Write-Host "或：powershell -File .\start_dev.ps1" -ForegroundColor Yellow
Write-Host "前端端口：$FrontendPort" -ForegroundColor Green
Write-Host "后端 API Base：$API_BASE_URL" -ForegroundColor Green
Write-Host "node：$NODE_CMD" -ForegroundColor Green
Write-Host "npm：$NPM_CMD" -ForegroundColor Green

Push-Location $WEBAPP_DIR
try {
    Set-WebDevEnvironment -ApiBaseUrl $API_BASE_URL -FrontendPort $FrontendPort
    $frontendArgs = @('--host', '127.0.0.1', '--port', "$FrontendPort")
    if (Test-Path $WEBAPP_DEV_SERVER_ENTRY) {
        & $NODE_CMD $WEBAPP_DEV_SERVER_ENTRY @frontendArgs
    } elseif (Test-Path $VITE_CLI) {
        & $NODE_CMD $VITE_CLI @frontendArgs
    } else {
        & $NPM_CMD run dev -- @frontendArgs
    }
    $exitCode = $LASTEXITCODE
} finally {
    Clear-WebDevEnvironment
    Pop-Location
}

exit $exitCode
