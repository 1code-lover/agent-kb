# ThinkRAG / NorthAgent 统一启动入口
# 当前主线：FastAPI API + React(Vite) Web
# 用法：
#   powershell -File .\start_all.ps1
#   powershell -File .\start_all.ps1 -BackendPort 18095 -FrontendPort 5176
#   powershell -File .\start_all.ps1 -Stop

param(
    [switch]$Stop,
    [Nullable[int]]$BackendPort = $null,
    [Nullable[int]]$FrontendPort = $null
)

$ROOT = Split-Path -Parent $PSCommandPath
$DEV_RUNTIME_HELPERS = Join-Path $ROOT 'scripts\dev-runtime-helpers.ps1'
if (-not (Test-Path $DEV_RUNTIME_HELPERS)) {
    throw "未找到开发启动共享 helper：$DEV_RUNTIME_HELPERS"
}
. $DEV_RUNTIME_HELPERS

$BackendPort = Resolve-BackendPort $BackendPort
$FrontendPort = Resolve-FrontendPort $FrontendPort
$DEV_SCRIPT = Join-Path $ROOT 'start_dev.ps1'

if (-not (Test-Path $DEV_SCRIPT)) {
    throw "未找到开发启动脚本：$DEV_SCRIPT"
}

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  ThinkRAG / NorthAgent 本地启动" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "主链路：FastAPI + React(Vite)" -ForegroundColor Green
Write-Host "仓库根目录：$ROOT" -ForegroundColor Green
Write-Host "后端端口：$BackendPort" -ForegroundColor Green
Write-Host "前端端口：$FrontendPort" -ForegroundColor Green
Write-Host ""

if ($Stop) {
    & $DEV_SCRIPT -Stop -BackendPort $BackendPort -FrontendPort $FrontendPort
    exit $LASTEXITCODE
}

Write-Host "即将调用 start_dev.ps1 拉起前后端。" -ForegroundColor Yellow
Write-Host "如果只需要停止服务，请执行：powershell -File .\start_all.ps1 -Stop" -ForegroundColor Yellow
Write-Host ""

& $DEV_SCRIPT -BackendPort $BackendPort -FrontendPort $FrontendPort
exit $LASTEXITCODE
