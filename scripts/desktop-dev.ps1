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

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$root\webapp`"; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$root\desktop`"; npm run dev"
