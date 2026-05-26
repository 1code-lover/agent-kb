Param(
  [switch]$InstallDeps
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if ($InstallDeps) {
  python -m pip install -r "$root\requirements.txt"
  Push-Location "$root\webapp"
  npm install
  Pop-Location
  Push-Location "$root\desktop"
  npm install
  Pop-Location
}

Write-Host "[ThinkRAG] Starting API server..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$root`"; python run_api.py"

Start-Sleep -Seconds 2

Write-Host "[ThinkRAG] Starting webapp..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$root\webapp`"; npm run dev"

Start-Sleep -Seconds 2

Write-Host "[ThinkRAG] Starting desktop shell..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$root\desktop`"; `$env:THINKRAG_WEB_URL='http://127.0.0.1:5173'; npm run dev"

Write-Host "[ThinkRAG] All services started."
