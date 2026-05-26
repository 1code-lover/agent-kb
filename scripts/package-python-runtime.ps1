Param(
  [string]$OutputDir = "desktop/resources/python"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root $OutputDir

python -m pip install pyinstaller
if (!(Test-Path $target)) {
  New-Item -ItemType Directory -Path $target | Out-Null
}

pyinstaller `
  --onefile `
  --name thinkrag-api `
  --distpath $target `
  "$root\run_api.py"
