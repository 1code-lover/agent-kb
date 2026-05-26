Param(
  [switch]$InstallDeps
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if ($InstallDeps) {
  python -m pip install -r "$root\requirements.txt"
  Push-Location "$root\webapp"
  npm install
  npm run build
  Pop-Location

  Push-Location "$root\desktop"
  npm install
  Pop-Location
}

Push-Location "$root\desktop"
npm run build
Pop-Location
