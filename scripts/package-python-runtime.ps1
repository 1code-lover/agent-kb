# Compatibility helper for packaging the standalone Python API with PyInstaller
# - Prefers KB_PYTHON, then NORTHAGENT/THINKRAG/FOXGLOVE compatibility aliases
# - API-only / experimental packaging path; it does not replace the Electron desktop release lane
Param(
  [string]$OutputDir = "desktop/resources/python"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root $OutputDir

$DEV_RUNTIME_HELPERS = Join-Path $PSScriptRoot 'dev-runtime-helpers.ps1'
if (-not (Test-Path $DEV_RUNTIME_HELPERS)) {
  throw "未找到开发启动共享 helper：$DEV_RUNTIME_HELPERS"
}
. $DEV_RUNTIME_HELPERS

$PYTHON_CMD = Resolve-PreferredPythonCommand

& $PYTHON_CMD -m pip install pyinstaller
if (!(Test-Path $target)) {
  New-Item -ItemType Directory -Path $target | Out-Null
}

& $PYTHON_CMD -m PyInstaller `
  --onefile `
  --name thinkrag-api `
  --distpath $target `
  (Join-Path $root 'run_api.py')
