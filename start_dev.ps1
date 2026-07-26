# ThinkRAG ????????
# - ?????? reload??? uvicorn ????? 18080
# - ?? PID ??????????/????
# - ??????????????????

param(
    [switch]$Stop,
    [int]$BackendPort = 18080,
    [int]$FrontendPort = 5174
)

$ROOT = "C:\Users\ethan1.zhao\Downloads\agent-kb-main\github-agent-kb"
$LOG_DIR = Join-Path $ROOT "logs"
$RUNTIME_DIR = Join-Path $ROOT ".dev-runtime"
$BACKEND_PID_FILE = Join-Path $RUNTIME_DIR "backend.pid"
$FRONTEND_PID_FILE = Join-Path $RUNTIME_DIR "frontend.pid"
$BACKEND_PORT = $BackendPort
$FRONTEND_PORT = $FrontendPort
$FRONTEND_API_BASE_URL = "http://127.0.0.1:$BACKEND_PORT"
$NPM_CMD = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $NPM_CMD) { $NPM_CMD = (Get-Command npm -ErrorAction SilentlyContinue).Source }
$NODE_CMD = (Get-Command node.exe -ErrorAction SilentlyContinue).Source
$NODE_DIR = if ($NODE_CMD) { Split-Path -Parent $NODE_CMD } else { "" }

New-Item -ItemType Directory -Path $LOG_DIR -Force -ErrorAction SilentlyContinue | Out-Null
New-Item -ItemType Directory -Path $RUNTIME_DIR -Force -ErrorAction SilentlyContinue | Out-Null

function Get-ManagedPid([string]$PidFile) {
    if (-not (Test-Path $PidFile)) {
        return $null
    }
    $raw = (Get-Content $PidFile -Raw -ErrorAction SilentlyContinue).Trim()
    if (-not $raw) {
        return $null
    }
    $pidValue = 0
    if (-not [int]::TryParse($raw, [ref]$pidValue)) {
        return $null
    }
    return $pidValue
}

function Remove-StalePidFile([string]$PidFile) {
    if (Test-Path $PidFile) {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    }
}

function Stop-ManagedProcess([string]$PidFile, [string]$Label) {
    $pidValue = Get-ManagedPid $PidFile
    if ($null -eq $pidValue) {
        Remove-StalePidFile $PidFile
        return
    }
    $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if ($process) {
        Write-Host "Stopping $Label (PID=$pidValue)..." -ForegroundColor Yellow
        Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
    }
    Remove-StalePidFile $PidFile
}

function Stop-RepoPortProcess([int]$Port, [string]$Label) {
    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
        Where-Object { $_.State -in @('Listen', 'Established') } |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($pidValue in $connections) {
        if ($pidValue -le 0) {
            continue
        }
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $pidValue" -ErrorAction SilentlyContinue
        if (-not $process) {
            continue
        }
        $commandLine = [string]$process.CommandLine
        $name = [string]$process.Name
        $belongsToRepo = $commandLine -like "*$ROOT*" -or $commandLine -like "*run_api.py*" -or $commandLine -like "*vite*"
        if ($belongsToRepo -or $name -in @('python.exe', 'pythonw.exe', 'node.exe', 'cmd.exe', 'powershell.exe')) {
            Write-Host "Stopping stale $Label listener on port $Port (PID=$pidValue)..." -ForegroundColor Yellow
            Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
        }
    }
}

function Wait-HttpReady([string]$Url, [int]$RetryCount = 20, [int]$DelaySeconds = 1) {
    for ($attempt = 0; $attempt -lt $RetryCount; $attempt++) {
        try {
            $response = Invoke-RestMethod -Uri $Url -UseBasicParsing -ErrorAction Stop
            return $response
        } catch {
            Start-Sleep -Seconds $DelaySeconds
        }
    }
    return $null
}

if ($Stop) {
    Write-Host "Stopping services..." -ForegroundColor Yellow
    Stop-ManagedProcess $BACKEND_PID_FILE "backend"
    Stop-ManagedProcess $FRONTEND_PID_FILE "frontend"
    Stop-RepoPortProcess $BACKEND_PORT "backend"
    Stop-RepoPortProcess $FRONTEND_PORT "frontend"
    Write-Host "Stopped." -ForegroundColor Green
    return
}

Write-Host "=== ThinkRAG Dev Mode ===" -ForegroundColor Cyan
Write-Host "Target backend port: $BACKEND_PORT" -ForegroundColor Cyan
Write-Host "Target frontend port: $FRONTEND_PORT" -ForegroundColor Cyan
Stop-ManagedProcess $BACKEND_PID_FILE "backend"
Stop-ManagedProcess $FRONTEND_PID_FILE "frontend"
Stop-RepoPortProcess $BACKEND_PORT "backend"
Stop-RepoPortProcess $FRONTEND_PORT "frontend"
Start-Sleep -Seconds 1

Write-Host "[1] Starting backend (reload disabled by default)..." -ForegroundColor Cyan
$env:PYTHONPATH = $ROOT
$env:KB_API_RELOAD = "0"
$env:KB_API_PORT = "$BACKEND_PORT"
$env:Path = "C:\Users\ethan1.zhao\AppData\Local\Programs\Python\Python312\;C:\Users\ethan1.zhao\AppData\Local\Programs\Python\Python312\Scripts\;$NODE_DIR;$env:SystemRoot\system32;$env:SystemRoot;$env:SystemRoot\System32\Wbem"
$backendProcess = Start-Process -FilePath "python" -ArgumentList "run_api.py" -WorkingDirectory $ROOT -WindowStyle Hidden -PassThru
Set-Content -LiteralPath $BACKEND_PID_FILE -Value $backendProcess.Id -Encoding utf8
Write-Host "    PID: $($backendProcess.Id)" -ForegroundColor Green
Write-Host "    logs: $LOG_DIR\backend.log / access.log" -ForegroundColor Green

Write-Host "[2] Starting frontend (Vite)..." -ForegroundColor Cyan
if (-not $NPM_CMD) { throw "npm.cmd not found before PATH cleanup" }
$env:VITE_API_BASE_URL = $FRONTEND_API_BASE_URL
$frontendArgs = @('run', 'dev', '--', '--host', '127.0.0.1', '--port', "$FRONTEND_PORT")
$frontendProcess = Start-Process -FilePath $NPM_CMD -ArgumentList $frontendArgs -WorkingDirectory (Join-Path $ROOT 'webapp') -RedirectStandardOutput (Join-Path $LOG_DIR 'frontend_out.log') -RedirectStandardError (Join-Path $LOG_DIR 'frontend_err.log') -WindowStyle Hidden -PassThru
Remove-Item Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue
Set-Content -LiteralPath $FRONTEND_PID_FILE -Value $frontendProcess.Id -Encoding utf8
Write-Host "    PID: $($frontendProcess.Id)" -ForegroundColor Green
Write-Host "    API base: $FRONTEND_API_BASE_URL" -ForegroundColor Green
Write-Host "    log: $LOG_DIR\frontend_out.log" -ForegroundColor Green

$health = Wait-HttpReady -Url "http://127.0.0.1:$BACKEND_PORT/api/health" -RetryCount 25 -DelaySeconds 1
if ($health -and $health.code -eq 0) {
    Write-Host "Backend OK" -ForegroundColor Green
} else {
    Write-Host "Backend not ready, check $LOG_DIR\backend.log" -ForegroundColor Red
}

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "  Frontend: http://127.0.0.1:$FRONTEND_PORT" -ForegroundColor Green
Write-Host "  Backend:  http://127.0.0.1:$BACKEND_PORT" -ForegroundColor Green
Write-Host "  API base: $FRONTEND_API_BASE_URL" -ForegroundColor Green
Write-Host "  API docs: http://127.0.0.1:$BACKEND_PORT/docs" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Watch live (new terminal):" -ForegroundColor Yellow
Write-Host "  Get-Content $LOG_DIR\backend.log -Tail 20 -Wait" -ForegroundColor White
Write-Host "  Get-Content $LOG_DIR\frontend_out.log -Tail 20 -Wait" -ForegroundColor White
Write-Host ""
Write-Host "Stop: powershell -File $PSCommandPath -Stop -BackendPort $BACKEND_PORT -FrontendPort $FRONTEND_PORT" -ForegroundColor Yellow
