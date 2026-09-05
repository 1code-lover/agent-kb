# NorthAgent / ThinkRAG local desktop build helper
# - Defaults to the runtime install profile; switch to full only when local OCR / legacy extras are truly needed
# - Prefers KB_PYTHON, then NORTHAGENT/THINKRAG/FOXGLOVE compatibility aliases
# - Only builds webapp/dist + the Electron bundle for local verification; it does not replace desktop/package.json build:preflight / release:mac
Param(
  [switch]$InstallDeps,
  [ValidateSet('runtime', 'full')]
  [string]$InstallProfile = 'runtime'
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$DEV_RUNTIME_HELPERS = Join-Path $PSScriptRoot 'dev-runtime-helpers.ps1'
if (-not (Test-Path $DEV_RUNTIME_HELPERS)) {
  throw "未找到开发启动共享 helper：$DEV_RUNTIME_HELPERS"
}
. $DEV_RUNTIME_HELPERS

$PYTHON_CMD = Resolve-PreferredPythonCommand
$NPM_CMD = Resolve-CommandPath @('npm.cmd', 'npm') 'npm'

if ($InstallDeps) {
  $requirementsPath = Resolve-RequirementsPath $root $InstallProfile
  & $PYTHON_CMD -m pip install -r $requirementsPath
  Push-Location (Join-Path $root 'webapp')
  & $NPM_CMD install
  & $NPM_CMD run build
  Pop-Location

  Push-Location (Join-Path $root 'desktop')
  & $NPM_CMD install
  Pop-Location
}

Push-Location (Join-Path $root 'desktop')
& $NPM_CMD run build
Pop-Location
