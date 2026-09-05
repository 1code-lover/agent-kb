# ThinkRAG / NorthAgent 后端兼容入口
# 注意：这不是当前主入口。完整本地启动请使用 start_all.ps1 或 start_dev.ps1。
# 仅用于只拉起 FastAPI 后端的窄用途场景（接口调试、脚本联调、手工诊断）。

param(
    [Nullable[int]]$BackendPort = $null,
    [Nullable[int]]$FrontendPort = $null,
    [string]$ExtraDevOrigins = ''
)

$ROOT = Split-Path -Parent $PSCommandPath
$DEV_RUNTIME_HELPERS = Join-Path $ROOT 'scripts\dev-runtime-helpers.ps1'
if (-not (Test-Path $DEV_RUNTIME_HELPERS)) {
    throw "未找到开发启动共享 helper：$DEV_RUNTIME_HELPERS"
}
. $DEV_RUNTIME_HELPERS

$BackendPort = Resolve-BackendPort $BackendPort
$FrontendPort = Resolve-FrontendPort $FrontendPort
$API_BASE_URL = Resolve-ApiBaseUrl '' $BackendPort
$FRONTEND_DEV_ORIGINS = Resolve-ExtraDevOrigins $ExtraDevOrigins $FrontendPort

$PYTHON_CMD = Resolve-PreferredPythonCommand

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  ThinkRAG / NorthAgent API Only" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "兼容脚本：只启动 FastAPI 后端，不拉起前端。" -ForegroundColor Yellow
Write-Host "完整前后端联调请使用：powershell -File .\start_all.ps1" -ForegroundColor Yellow
Write-Host "或：powershell -File .\start_dev.ps1" -ForegroundColor Yellow
Write-Host "后端端口：$BackendPort" -ForegroundColor Green
Write-Host "前端端口（调试来源默认值）：$FrontendPort" -ForegroundColor Green
Write-Host "API Base：$API_BASE_URL" -ForegroundColor Green
Write-Host "额外调试来源：$FRONTEND_DEV_ORIGINS" -ForegroundColor Green
Write-Host "Python：$PYTHON_CMD" -ForegroundColor Green

Set-BackendDevEnvironment -RepoRoot $ROOT -BackendPort $BackendPort -ApiBaseUrl $API_BASE_URL -ExtraDevOrigins $FRONTEND_DEV_ORIGINS

try {
    & $PYTHON_CMD (Join-Path $ROOT 'run_api.py')
    $exitCode = $LASTEXITCODE
} finally {
    Clear-BackendDevEnvironment
}

exit $exitCode
