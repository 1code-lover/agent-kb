# ThinkRAG / NorthAgent 开发启动脚本
# - 默认拉起 FastAPI API（18080）与 React Vite（5173）
# - 统一从仓库根目录推导路径，不再依赖历史绝对路径
# - 允许通过参数覆盖端口，并同步写入前端 API base / 后端 CORS 调试来源

param(
    [switch]$Stop,
    [Nullable[int]]$BackendPort = $null,
    [Nullable[int]]$FrontendPort = $null
)

$ROOT = Split-Path -Parent $PSCommandPath
$LOG_DIR = Join-Path $ROOT 'logs'
$RUNTIME_DIR = Join-Path $ROOT '.dev-runtime'
$WEBAPP_DIR = Join-Path $ROOT 'webapp'
$WEBAPP_NODE_MODULES = Join-Path $WEBAPP_DIR 'node_modules'
$VITE_CLI = Join-Path $WEBAPP_NODE_MODULES 'vite\bin\vite.js'
$WEBAPP_DEV_SERVER_ENTRY = Join-Path $WEBAPP_DIR 'scripts\dev-server.mjs'

$DEV_RUNTIME_HELPERS = Join-Path $ROOT 'scripts\dev-runtime-helpers.ps1'
if (-not (Test-Path $DEV_RUNTIME_HELPERS)) {
    throw "未找到开发启动共享 helper：$DEV_RUNTIME_HELPERS"
}
. $DEV_RUNTIME_HELPERS

$BACKEND_PORT = Resolve-BackendPort $BackendPort
$FRONTEND_PORT = Resolve-FrontendPort $FrontendPort
$BACKEND_PID_FILE = Join-Path $RUNTIME_DIR (Get-PortScopedFileName 'backend' $BACKEND_PORT (Get-DefaultBackendPort) '.pid')
$FRONTEND_PID_FILE = Join-Path $RUNTIME_DIR (Get-PortScopedFileName 'frontend' $FRONTEND_PORT (Get-DefaultFrontendPort) '.pid')
$BACKEND_OUT_LOG = Join-Path $LOG_DIR (Get-PortScopedFileName 'backend_out' $BACKEND_PORT (Get-DefaultBackendPort) '.log')
$BACKEND_ERR_LOG = Join-Path $LOG_DIR (Get-PortScopedFileName 'backend_err' $BACKEND_PORT (Get-DefaultBackendPort) '.log')
$FRONTEND_OUT_LOG = Join-Path $LOG_DIR (Get-PortScopedFileName 'frontend_out' $FRONTEND_PORT (Get-DefaultFrontendPort) '.log')
$FRONTEND_ERR_LOG = Join-Path $LOG_DIR (Get-PortScopedFileName 'frontend_err' $FRONTEND_PORT (Get-DefaultFrontendPort) '.log')

$FRONTEND_API_BASE_URL = Resolve-ApiBaseUrl '' $BACKEND_PORT
$FRONTEND_DEV_ORIGINS = Resolve-ExtraDevOrigins '' $FRONTEND_PORT

function Repair-NpmStagedPackage([string]$PackageRelativePath) {
    $targetDir = Join-Path $WEBAPP_NODE_MODULES $PackageRelativePath
    $targetPackageJson = Join-Path $targetDir 'package.json'
    if (Test-Path $targetPackageJson) {
        return $false
    }

    $parentDir = Split-Path -Parent $targetDir
    $leafName = Split-Path -Leaf $PackageRelativePath
    if (-not (Test-Path $parentDir)) {
        return $false
    }

    $stagedCandidates = @(Get-ChildItem -LiteralPath $parentDir -Force -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq ('.' + $leafName) -or $_.Name -like ('.' + $leafName + '-*') } |
        Where-Object { Test-Path (Join-Path $_.FullName 'package.json') })

    if ($stagedCandidates.Count -ne 1) {
        return $false
    }

    $stagedDir = $stagedCandidates[0].FullName
    New-Item -ItemType Directory -Path $targetDir -Force -ErrorAction SilentlyContinue | Out-Null
    Get-ChildItem -LiteralPath $stagedDir -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $targetDir -Recurse -Force
    }

    return (Test-Path $targetPackageJson)
}

function Get-StagedPackageLeafName([string]$StageDirectoryName) {
    if (-not $StageDirectoryName -or -not $StageDirectoryName.StartsWith('.')) {
        return $null
    }

    $trimmed = $StageDirectoryName.Substring(1)
    if (-not $trimmed) {
        return $null
    }

    if ($trimmed -match '^(.*)-[^-]+$') {
        return $matches[1]
    }

    return $trimmed
}

function Repair-StagedPackagesInParentDir([string]$ParentDir, [string]$PackagePrefix = '') {
    if (-not (Test-Path $ParentDir)) {
        return @()
    }

    $recoveredPackages = @()
    $stagedDirs = @(Get-ChildItem -LiteralPath $ParentDir -Force -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name.StartsWith('.') } |
        Where-Object { Test-Path (Join-Path $_.FullName 'package.json') })

    foreach ($stagedDir in $stagedDirs) {
        $leafName = Get-StagedPackageLeafName $stagedDir.Name
        if (-not $leafName) {
            continue
        }

        $packageRelativePath = if ($PackagePrefix) {
            Join-Path $PackagePrefix $leafName
        } else {
            $leafName
        }

        if (Repair-NpmStagedPackage $packageRelativePath) {
            $recoveredPackages += $packageRelativePath
        }
    }

    return $recoveredPackages
}

function Repair-WebappDevRuntime() {
    if (-not (Test-Path $WEBAPP_NODE_MODULES)) {
        return
    }

    $recoveredPackages = @()
    foreach ($packageRelativePath in @(
        'vite',
        '@vitejs\plugin-react',
        'esbuild',
        'rollup',
        '@esbuild\win32-x64',
        '@rollup\rollup-win32-x64-msvc',
        '@rollup\rollup-win32-x64-gnu'
    )) {
        if (Repair-NpmStagedPackage $packageRelativePath) {
            $recoveredPackages += $packageRelativePath
        }
    }

    $recoveredPackages += Repair-StagedPackagesInParentDir $WEBAPP_NODE_MODULES
    foreach ($scopeDir in @(Get-ChildItem -LiteralPath $WEBAPP_NODE_MODULES -Force -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '@*' })) {
        $recoveredPackages += Repair-StagedPackagesInParentDir $scopeDir.FullName $scopeDir.Name
    }

    $recoveredPackages = @($recoveredPackages | Sort-Object -Unique)
    if ($recoveredPackages.Count -gt 0) {
        Write-Host ("Recovered staged webapp packages: " + ($recoveredPackages -join ', ')) -ForegroundColor Yellow
    }
}

$NPM_CMD = Resolve-CommandPath @('npm.cmd', 'npm') 'npm'
$NODE_CMD = Resolve-CommandPath @('node.exe', 'node') 'node'
$PYTHON_CMD = Resolve-PreferredPythonCommand

New-Item -ItemType Directory -Path $LOG_DIR -Force -ErrorAction SilentlyContinue | Out-Null
New-Item -ItemType Directory -Path $RUNTIME_DIR -Force -ErrorAction SilentlyContinue | Out-Null

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
        $belongsToRepo = $commandLine -like "*$ROOT*" -or $commandLine -like "*run_api.py*" -or $commandLine -like "*vite*"
        if (-not $belongsToRepo) {
            continue
        }
        Write-Host "Stopping stale $Label listener on port $Port (PID=$pidValue)..." -ForegroundColor Yellow
        Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
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
    Write-Host 'Stopping services...' -ForegroundColor Yellow
    Stop-ManagedProcess $BACKEND_PID_FILE 'backend'
    Stop-ManagedProcess $FRONTEND_PID_FILE 'frontend'
    Stop-RepoPortProcess $BACKEND_PORT 'backend'
    Stop-RepoPortProcess $FRONTEND_PORT 'frontend'
    Write-Host 'Stopped.' -ForegroundColor Green
    return
}

Write-Host '=== ThinkRAG / NorthAgent Dev Mode ===' -ForegroundColor Cyan
Write-Host "Repository root: $ROOT" -ForegroundColor Cyan
Write-Host "Backend port: $BACKEND_PORT" -ForegroundColor Cyan
Write-Host "Frontend port: $FRONTEND_PORT" -ForegroundColor Cyan
Stop-ManagedProcess $BACKEND_PID_FILE 'backend'
Stop-ManagedProcess $FRONTEND_PID_FILE 'frontend'
Stop-RepoPortProcess $BACKEND_PORT 'backend'
Stop-RepoPortProcess $FRONTEND_PORT 'frontend'
Start-Sleep -Seconds 1

Write-Host '[1] Starting backend (FastAPI)...' -ForegroundColor Cyan
Normalize-StartProcessEnvironment
$backendArgs = @('run_api.py')
Set-BackendDevEnvironment -RepoRoot $ROOT -BackendPort $BACKEND_PORT -ApiBaseUrl $FRONTEND_API_BASE_URL -ExtraDevOrigins $FRONTEND_DEV_ORIGINS
try {
    $backendProcess = Start-Process -FilePath $PYTHON_CMD -ArgumentList $backendArgs -WorkingDirectory $ROOT -RedirectStandardOutput $BACKEND_OUT_LOG -RedirectStandardError $BACKEND_ERR_LOG -WindowStyle Hidden -PassThru
} finally {
    Clear-BackendDevEnvironment
}
Set-Content -LiteralPath $BACKEND_PID_FILE -Value $backendProcess.Id -Encoding ascii
Write-Host "    PID: $($backendProcess.Id)" -ForegroundColor Green
Write-Host "    logs: $BACKEND_OUT_LOG / $BACKEND_ERR_LOG" -ForegroundColor Green

Write-Host '[2] Starting frontend (React + Vite)...' -ForegroundColor Cyan
Repair-WebappDevRuntime
Normalize-StartProcessEnvironment
Set-WebDevEnvironment -ApiBaseUrl $FRONTEND_API_BASE_URL -FrontendPort $FRONTEND_PORT
try {
    $frontendProcess = Start-WebProcess -NodeCommand $NODE_CMD -NpmCommand $NPM_CMD -WebappDir $WEBAPP_DIR -DevServerEntry $WEBAPP_DEV_SERVER_ENTRY -ViteCli $VITE_CLI -StdoutLog $FRONTEND_OUT_LOG -StderrLog $FRONTEND_ERR_LOG -FrontendPort $FRONTEND_PORT
} finally {
    Clear-WebDevEnvironment
}
Set-Content -LiteralPath $FRONTEND_PID_FILE -Value $frontendProcess.Id -Encoding ascii
Write-Host "    PID: $($frontendProcess.Id)" -ForegroundColor Green
Write-Host "    API base: $FRONTEND_API_BASE_URL" -ForegroundColor Green
Write-Host "    log: $FRONTEND_OUT_LOG" -ForegroundColor Green

$health = Wait-HttpReady -Url "$FRONTEND_API_BASE_URL/api/health" -RetryCount 25 -DelaySeconds 1
if ($health -and $health.code -eq 0) {
    Write-Host 'Backend OK' -ForegroundColor Green
} else {
    Write-Host "Backend not ready, check $BACKEND_OUT_LOG / $BACKEND_ERR_LOG" -ForegroundColor Red
    Write-LogTail -Path $BACKEND_OUT_LOG -Label 'backend stdout'
    Write-LogTail -Path $BACKEND_ERR_LOG -Label 'backend stderr'
}

Write-Host ''
Write-Host '================================' -ForegroundColor Cyan
Write-Host "  Frontend: http://127.0.0.1:$FRONTEND_PORT" -ForegroundColor Green
Write-Host "  Backend:  $FRONTEND_API_BASE_URL" -ForegroundColor Green
Write-Host "  API docs: $FRONTEND_API_BASE_URL/docs" -ForegroundColor Green
Write-Host '================================' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Watch live (new terminal):' -ForegroundColor Yellow
Write-Host "  Get-Content $BACKEND_OUT_LOG -Tail 20 -Wait" -ForegroundColor White
Write-Host "  Get-Content $FRONTEND_OUT_LOG -Tail 20 -Wait" -ForegroundColor White
Write-Host ''
Write-Host "Stop: powershell -File $PSCommandPath -Stop -BackendPort $BACKEND_PORT -FrontendPort $FRONTEND_PORT" -ForegroundColor Yellow
