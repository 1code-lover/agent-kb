# ThinkRAG 开发模式一键启动
# 前后台后台启动 + 热重载 + 日志文件

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

# 启动后端
Write-Host "[1] Starting backend (--reload)..." -ForegroundColor Cyan
$bl = "$LOG_DIR\backend.log"
$env:PYTHONPATH = $ROOT
Start-Process -FilePath "python" -ArgumentList "-m uvicorn api.app:app --host 127.0.0.1 --port 18080 --reload" -WorkingDirectory $ROOT -RedirectStandardOutput "$LOG_DIR\backend_out.log" -RedirectStandardError "$LOG_DIR\backend_err.log" -WindowStyle Hidden
Start-Sleep -Seconds 2
Write-Host "    log: $bl" -ForegroundColor Green

# 启动前端
Write-Host "[2] Starting frontend (HMR)..." -ForegroundColor Cyan
$fl = "$LOG_DIR\frontend.log"
Start-Process -FilePath "npm" -ArgumentList "run dev" -WorkingDirectory "$ROOT\webapp" -RedirectStandardOutput "$LOG_DIR\frontend_out.log" -RedirectStandardError "$LOG_DIR\frontend_err.log" -WindowStyle Hidden
Start-Sleep -Seconds 2
Write-Host "    log: $fl" -ForegroundColor Green

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
Write-Host "Watch logs (run in another terminal):" -ForegroundColor Yellow
Write-Host "  Get-Content ""$LOG_DIR\backend_out.log"" -Tail 30 -Wait" -ForegroundColor White
Write-Host "  Get-Content ""$LOG_DIR\frontend_out.log"" -Tail 30 -Wait" -ForegroundColor White
Write-Host ""
Write-Host "Stop services: powershell -File $($MyInvocation.MyCommand.Path) -Stop" -ForegroundColor Yellow
