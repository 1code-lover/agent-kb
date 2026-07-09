# ThinkRAG 开发模式一键启动
# 后端日志 1MB 自动轮转 + 时间戳，前端日志输出到文件

param([switch]$Stop)

$ROOT = "C:\Users\ethan1.zhao\Downloads\agent-kb-main\github-agent-kb"
$LOG_DIR = "$ROOT\logs"
New-Item -ItemType Directory -Path $LOG_DIR -Force -ErrorAction SilentlyContinue | Out-Null

# 停止模式
if ($Stop) {
    Write-Host "Stopping services..." -ForegroundColor Yellow
    @(18080, 5173) | ForEach-Object {
        Get-NetTCPConnection -LocalPort $_ -ErrorAction SilentlyContinue | ForEach-Object {
            try { Stop-Process -Id $_.OwningProcess -Force } catch {}
        }
    }
    Write-Host "Stopped." -ForegroundColor Green; return
}

Write-Host "=== ThinkRAG Dev Mode ===" -ForegroundColor Cyan

# 清理旧端口
@(18080, 5173) | ForEach-Object {
    Get-NetTCPConnection -LocalPort $_ -ErrorAction SilentlyContinue | ForEach-Object {
        try { Stop-Process -Id $_.OwningProcess -Force } catch {}
    }
}
Start-Sleep -Seconds 1

# 启动后端（日志 1MB 轮转 + 时间戳，由 run_api.py 内置处理）
Write-Host "[1] Starting backend (--reload)..." -ForegroundColor Cyan
$env:PYTHONPATH = $ROOT
$env:UVICORN_LOG_CONFIG = "1"  # 仅标记
Start-Process -FilePath "python" -ArgumentList "run_api.py" -WorkingDirectory $ROOT -WindowStyle Hidden
Start-Sleep -Seconds 4
Write-Host "    logs: $LOG_DIR\backend.log / access.log (1MB auto-rotate)" -ForegroundColor Green

# 启动前端（Vite 日志）
Write-Host "[2] Starting frontend (HMR)..." -ForegroundColor Cyan
$fl = "$LOG_DIR\frontend.log"
Start-Process -FilePath "npm" -ArgumentList "run dev" -WorkingDirectory "$ROOT\webapp" -RedirectStandardOutput "$LOG_DIR\frontend_out.log" -RedirectStandardError "$LOG_DIR\frontend_err.log" -WindowStyle Hidden
Start-Sleep -Seconds 2
Write-Host "    log: $LOG_DIR\frontend_out.log" -ForegroundColor Green

# 验证后端
Start-Sleep -Seconds 3
try {
    $r = Invoke-RestMethod -Uri http://127.0.0.1:18080/api/health -UseBasicParsing -ErrorAction Stop
    if ($r.code -eq 0) { Write-Host "Backend OK" -ForegroundColor Green }
} catch { Write-Host "Backend not ready" -ForegroundColor Red }

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "  Backend:  http://127.0.0.1:18080" -ForegroundColor Green
Write-Host "  API docs: http://127.0.0.1:18080/docs" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Log files (1MB auto-rotate, 5 backups):" -ForegroundColor Green
Write-Host "  $LOG_DIR\backend.log / backend.log.1~5" -ForegroundColor White
Write-Host "  $LOG_DIR\access.log  / access.log.1~5" -ForegroundColor White
Write-Host ""
Write-Host "Watch live (new terminal):" -ForegroundColor Yellow
Write-Host "  Get-Content $LOG_DIR\backend.log -Tail 20 -Wait" -ForegroundColor White
Write-Host "  Get-Content $LOG_DIR\frontend_out.log -Tail 20 -Wait" -ForegroundColor White
Write-Host ""
Write-Host "Stop: powershell -File $PSCommandPath -Stop" -ForegroundColor Yellow
