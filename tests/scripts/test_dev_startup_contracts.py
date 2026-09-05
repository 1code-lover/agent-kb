from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")




def _run_powershell_file(relative_path: str, *args: str) -> subprocess.CompletedProcess[str]:
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(REPO_ROOT / relative_path),
        *args,
    ]
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )

def test_dev_runtime_helper_centralizes_shared_startup_contracts() -> None:
    content = _read("scripts/dev-runtime-helpers.ps1")

    assert "function Normalize-StartProcessEnvironment()" in content
    assert "function Get-DefaultBackendPort()" in content
    assert "function Get-DefaultFrontendPort()" in content
    assert "function Resolve-BackendPort([Nullable[int]]$BackendPort)" in content
    assert "function Resolve-FrontendPort([Nullable[int]]$FrontendPort)" in content
    assert "function Get-PortScopedFileName([string]$BaseName, [int]$Port, [int]$DefaultPort, [string]$Extension)" in content
    assert "function Get-DualPortScopedFileName([string]$BaseName, [int]$PrimaryPort, [int]$SecondaryPort, [int]$DefaultPrimaryPort, [int]$DefaultSecondaryPort, [string]$Extension)" in content
    assert "function Set-BackendDevEnvironment(" in content
    assert "function Clear-BackendDevEnvironment()" in content
    assert "function Resolve-ExtraDevOrigins([string]$ExplicitExtraDevOrigins, [int]$FrontendPort)" in content
    assert "function Resolve-FrontendUrl([int]$FrontendPort)" in content
    assert "function Set-WebDevEnvironment([string]$ApiBaseUrl, [int]$FrontendPort, [string]$ListenHost = '127.0.0.1')" in content
    assert "[string]$Host = '127.0.0.1'" not in content
    assert "function Clear-WebDevEnvironment()" in content
    assert "function Start-WebProcess(" in content
    assert "function Set-DesktopRuntimeEnvironment(" in content
    assert "function Clear-DesktopRuntimeEnvironment()" in content
    assert "function Test-DesktopHeadlessRequested()" in content
    assert "function Start-DesktopProcess(" in content
    assert "Start-Process -FilePath $NodeCommand -ArgumentList $webappEntryArgs" in content
    assert "Start-Process -FilePath $NodeCommand -ArgumentList @($ElectronCli, '.')" in content
def test_startup_scripts_do_not_use_legacy_absolute_paths() -> None:
    old_markers = [
        r"C:\Users\ethan1.zhao\Downloads",
        "agent-kb-main",
        "github-agent-kb",
    ]

    for relative_path in ("start_all.ps1", "start_dev.ps1", "scripts/dev-all.ps1"):
        content = _read(relative_path)
        for marker in old_markers:
            assert marker not in content, f"{relative_path} still references legacy path marker: {marker}"


def test_start_all_delegates_to_start_dev() -> None:
    content = _read("start_all.ps1")

    assert "start_dev.ps1" in content
    assert "& $DEV_SCRIPT" in content
    assert "$DEV_RUNTIME_HELPERS = Join-Path $ROOT 'scripts\\dev-runtime-helpers.ps1'" in content
    assert "$BackendPort = Resolve-BackendPort $BackendPort" in content
    assert "$FrontendPort = Resolve-FrontendPort $FrontendPort" in content
    assert "-Stop -BackendPort $BackendPort -FrontendPort $FrontendPort" in content


def test_start_dev_exports_backend_contract_and_log_redirection() -> None:
    content = _read("start_dev.ps1")
    helper_content = _read("scripts/dev-runtime-helpers.ps1")

    assert "$BACKEND_PORT = Resolve-BackendPort $BackendPort" in content
    assert "$FRONTEND_PORT = Resolve-FrontendPort $FrontendPort" in content
    assert "Get-PortScopedFileName 'backend' $BACKEND_PORT (Get-DefaultBackendPort) '.pid'" in content
    assert "Get-PortScopedFileName 'frontend' $FRONTEND_PORT (Get-DefaultFrontendPort) '.pid'" in content
    assert "Get-PortScopedFileName 'backend_out' $BACKEND_PORT (Get-DefaultBackendPort) '.log'" in content
    assert "Get-PortScopedFileName 'frontend_out' $FRONTEND_PORT (Get-DefaultFrontendPort) '.log'" in content
    assert "$FRONTEND_API_BASE_URL = Resolve-ApiBaseUrl '' $BACKEND_PORT" in content
    assert "$FRONTEND_DEV_ORIGINS = Resolve-ExtraDevOrigins '' $FRONTEND_PORT" in content
    assert "Set-BackendDevEnvironment -RepoRoot $ROOT -BackendPort $BACKEND_PORT -ApiBaseUrl $FRONTEND_API_BASE_URL -ExtraDevOrigins $FRONTEND_DEV_ORIGINS" in content
    assert "try {" in content
    assert "} finally {" in content
    assert "Clear-BackendDevEnvironment" in content
    assert "-RedirectStandardOutput $BACKEND_OUT_LOG" in content
    assert "-RedirectStandardError $BACKEND_ERR_LOG" in content
    assert "Set-Content -LiteralPath $BACKEND_PID_FILE -Value $backendProcess.Id -Encoding ascii" in content
    assert "Set-Content -LiteralPath $FRONTEND_PID_FILE -Value $frontendProcess.Id -Encoding ascii" in content
    assert "function Repair-NpmStagedPackage([string]$PackageRelativePath)" in content
    assert "function Get-StagedPackageLeafName([string]$StageDirectoryName)" in content
    assert "function Repair-StagedPackagesInParentDir([string]$ParentDir, [string]$PackagePrefix = '')" in content
    assert "function Repair-WebappDevRuntime()" in content
    assert "'esbuild'" in content
    assert "'rollup'" in content
    assert "'@esbuild\\win32-x64'" in content
    assert "'@rollup\\rollup-win32-x64-msvc'" in content
    assert "$recoveredPackages += Repair-StagedPackagesInParentDir $WEBAPP_NODE_MODULES" in content
    assert "$recoveredPackages += Repair-StagedPackagesInParentDir $scopeDir.FullName $scopeDir.Name" in content
    assert "Sort-Object -Unique" in content
    assert "Repair-WebappDevRuntime" in content
    assert "$DEV_RUNTIME_HELPERS = Join-Path $ROOT 'scripts\\dev-runtime-helpers.ps1'" in content
    assert ". $DEV_RUNTIME_HELPERS" in content
    assert "$PYTHON_CMD = Resolve-PreferredPythonCommand" in content
    assert "$NODE_CMD = Resolve-CommandPath @('node.exe', 'node') 'node'" in content
    assert "$NPM_CMD = Resolve-CommandPath @('npm.cmd', 'npm') 'npm'" in content
    assert "$VITE_CLI = Join-Path $WEBAPP_NODE_MODULES 'vite\\bin\\vite.js'" in content
    assert "$WEBAPP_DEV_SERVER_ENTRY = Join-Path $WEBAPP_DIR 'scripts\\dev-server.mjs'" in content
    assert "Stop-ManagedProcess $BACKEND_PID_FILE 'backend'" in content
    assert "Stop-ManagedProcess $FRONTEND_PID_FILE 'frontend'" in content
    assert "Set-WebDevEnvironment -ApiBaseUrl $FRONTEND_API_BASE_URL -FrontendPort $FRONTEND_PORT" in content
    assert "$frontendProcess = Start-WebProcess -NodeCommand $NODE_CMD -NpmCommand $NPM_CMD -WebappDir $WEBAPP_DIR -DevServerEntry $WEBAPP_DEV_SERVER_ENTRY -ViteCli $VITE_CLI -StdoutLog $FRONTEND_OUT_LOG -StderrLog $FRONTEND_ERR_LOG -FrontendPort $FRONTEND_PORT" in content
    assert "Clear-WebDevEnvironment" in content
    assert "Write-LogTail -Path $BACKEND_OUT_LOG -Label 'backend stdout'" in content
    assert "Write-LogTail -Path $BACKEND_ERR_LOG -Label 'backend stderr'" in content
    assert "Normalize-StartProcessEnvironment" in content

    assert "function Get-ManagedPid([string]$PidFile)" in helper_content
    assert "$rawContent = Get-Content $PidFile -Raw -ErrorAction SilentlyContinue" in helper_content
    assert "if ($null -eq $rawContent)" in helper_content
    assert "function Set-BackendDevEnvironment(" in helper_content
    assert "function Write-LogTail([string]$Path, [string]$Label, [int]$TailLines = 40)" in helper_content
    assert '$env:KB_API_PORT = "$BackendPort"' in helper_content
    assert '$env:KB_API_BASE_URL = $ApiBaseUrl' in helper_content
    assert '$env:KB_EXTRA_DEV_ORIGINS = $ExtraDevOrigins' in helper_content
    assert "function Clear-BackendDevEnvironment()" in helper_content
    assert "Remove-Item Env:KB_API_RELOAD -ErrorAction SilentlyContinue" in helper_content
    assert "function Stop-ManagedProcess([string]$PidFile, [string]$Label)" in helper_content

def test_dev_all_reuses_start_dev_and_manages_desktop_process() -> None:
    content = _read("scripts/dev-all.ps1")
    helper_content = _read("scripts/dev-runtime-helpers.ps1")

    assert "$START_DEV_SCRIPT = Join-Path $ROOT 'start_dev.ps1'" in content
    assert "$BackendPort = Resolve-BackendPort $BackendPort" in content
    assert "$FrontendPort = Resolve-FrontendPort $FrontendPort" in content
    assert "$DESKTOP_DIR = Join-Path $ROOT 'desktop'" in content
    assert "$DESKTOP_NODE_MODULES = Join-Path $DESKTOP_DIR 'node_modules'" in content
    assert "$HEADLESS_DESKTOP_ENTRY = Join-Path $DESKTOP_DIR 'scripts\\headless-runtime.js'" in content
    assert "$ELECTRON_CLI = Join-Path $DESKTOP_NODE_MODULES 'electron\\cli.js'" in content
    assert "& $START_DEV_SCRIPT -BackendPort $BackendPort -FrontendPort $FrontendPort" in content
    assert "& $START_DEV_SCRIPT -Stop -BackendPort $BackendPort -FrontendPort $FrontendPort" in content
    assert "Get-DualPortScopedFileName 'desktop' $BackendPort $FrontendPort (Get-DefaultBackendPort) (Get-DefaultFrontendPort) '.pid'" in content
    assert "Get-DualPortScopedFileName 'desktop_out' $BackendPort $FrontendPort (Get-DefaultBackendPort) (Get-DefaultFrontendPort) '.log'" in content
    assert "Stop-ManagedProcess $DESKTOP_PID_FILE 'desktop'" in content
    assert "$DEV_RUNTIME_HELPERS = Join-Path $PSScriptRoot 'dev-runtime-helpers.ps1'" in content
    assert ". $DEV_RUNTIME_HELPERS" in content
    assert "$PYTHON_CMD = Resolve-PreferredPythonCommand" in content
    assert "$API_BASE_URL = Resolve-ApiBaseUrl '' $BackendPort" in content
    assert "$FRONTEND_URL = Resolve-FrontendUrl $FrontendPort" in content
    assert "Set-DesktopRuntimeEnvironment -BackendPort $BackendPort -ApiBaseUrl $API_BASE_URL -FrontendPort $FrontendPort -FrontendUrl $FRONTEND_URL -PythonCommand $PYTHON_CMD" in content
    assert "Normalize-StartProcessEnvironment" in content
    assert "$desktopProcess = Start-DesktopProcess -NodeCommand $NODE_CMD -NpmCommand $NPM_CMD -DesktopDir $DESKTOP_DIR -HeadlessDesktopEntry $HEADLESS_DESKTOP_ENTRY -ElectronCli $ELECTRON_CLI -StdoutLog $DESKTOP_OUT_LOG -StderrLog $DESKTOP_ERR_LOG" in content
    assert "Write-LogTail -Path $DESKTOP_OUT_LOG -Label 'desktop stdout'" in content
    assert "Write-LogTail -Path $DESKTOP_ERR_LOG -Label 'desktop stderr'" in content
    assert "Clear-DesktopRuntimeEnvironment" in content
    assert "Set-Content -LiteralPath $DESKTOP_PID_FILE -Value $desktopProcess.Id -Encoding ascii" in content

    assert "function Stop-ManagedProcess([string]$PidFile, [string]$Label)" in helper_content
    assert "function Start-DesktopProcess(" in helper_content

def test_dev_all_supports_install_and_stop_contracts() -> None:
    content = _read("scripts/dev-all.ps1")
    helper_content = _read("scripts/dev-runtime-helpers.ps1")

    assert "[switch]$InstallDeps" in content
    assert "[switch]$Stop" in content
    assert "[string]$InstallProfile = 'runtime'" in content
    assert "$REQUIREMENTS_PATH = Resolve-RequirementsPath $ROOT $InstallProfile" in content
    assert "profile=$InstallProfile" in content
    assert "$DESKTOP_OUT_LOG = Join-Path $LOG_DIR" in content
    assert "Stop all: powershell -File $PSCommandPath -Stop" in content

    assert "function Resolve-RequirementsPath([string]$RepoRoot, [string]$Profile)" in helper_content
    assert "requirements-runtime.txt" in helper_content
    assert "requirements.txt" in helper_content

def test_start_api_and_start_frontend_are_explicit_compatibility_wrappers() -> None:
    helper_content = _read("scripts/dev-runtime-helpers.ps1")

    api_content = _read("start_api.ps1")
    assert "不是当前主入口" in api_content
    assert "start_all.ps1" in api_content
    assert "start_dev.ps1" in api_content
    assert "[Nullable[int]]$BackendPort = $null" in api_content
    assert "[Nullable[int]]$FrontendPort = $null" in api_content
    assert "[string]$ExtraDevOrigins = ''" in api_content
    assert "Resolve-ExtraDevOrigins([string]$ExplicitExtraDevOrigins, [int]$FrontendPort)" not in api_content
    assert "$BackendPort = Resolve-BackendPort $BackendPort" in api_content
    assert "$FrontendPort = Resolve-FrontendPort $FrontendPort" in api_content
    assert "$API_BASE_URL = Resolve-ApiBaseUrl '' $BackendPort" in api_content
    assert "$FRONTEND_DEV_ORIGINS = Resolve-ExtraDevOrigins $ExtraDevOrigins $FrontendPort" in api_content
    assert "$DEV_RUNTIME_HELPERS = Join-Path $ROOT 'scripts\\dev-runtime-helpers.ps1'" in api_content
    assert ". $DEV_RUNTIME_HELPERS" in api_content
    assert "$PYTHON_CMD = Resolve-PreferredPythonCommand" in api_content
    assert "Set-BackendDevEnvironment -RepoRoot $ROOT -BackendPort $BackendPort -ApiBaseUrl $API_BASE_URL -ExtraDevOrigins $FRONTEND_DEV_ORIGINS" in api_content
    assert "try {" in api_content
    assert "& $PYTHON_CMD (Join-Path $ROOT 'run_api.py')" in api_content
    assert "} finally {" in api_content
    assert "Clear-BackendDevEnvironment" in api_content
    assert 'python "$PSScriptRoot/run_api.py"' not in api_content

    frontend_content = _read("start_frontend.ps1")
    assert "不是当前主入口" in frontend_content
    assert "start_all.ps1" in frontend_content
    assert "start_dev.ps1" in frontend_content
    assert "[Nullable[int]]$BackendPort = $null" in frontend_content
    assert "[Nullable[int]]$FrontendPort = $null" in frontend_content
    assert "[string]$ApiBaseUrl = ''" in frontend_content
    assert "Normalize-LocalClientUrl([string]$Value)" not in frontend_content
    assert "Resolve-ApiBaseUrl([string]$ExplicitApiBaseUrl, [int]$BackendPort)" not in frontend_content
    assert "$BackendPort = Resolve-BackendPort $BackendPort" in frontend_content
    assert "$FrontendPort = Resolve-FrontendPort $FrontendPort" in frontend_content
    assert "Resolve-ApiBaseUrl $ApiBaseUrl $BackendPort" in frontend_content
    assert "如需指向非默认后端地址，可直接传 -ApiBaseUrl。" in frontend_content
    assert "$WEBAPP_DEV_SERVER_ENTRY = Join-Path $WEBAPP_DIR 'scripts\\dev-server.mjs'" in frontend_content
    assert "$VITE_CLI = Join-Path $WEBAPP_NODE_MODULES 'vite\\bin\\vite.js'" in frontend_content
    assert "$DEV_RUNTIME_HELPERS = Join-Path $ROOT 'scripts\\dev-runtime-helpers.ps1'" in frontend_content
    assert ". $DEV_RUNTIME_HELPERS" in frontend_content
    assert "$NODE_CMD = Resolve-CommandPath @('node.exe', 'node') 'node'" in frontend_content
    assert "$NPM_CMD = Resolve-CommandPath @('npm.cmd', 'npm') 'npm'" in frontend_content
    assert "Set-WebDevEnvironment -ApiBaseUrl $API_BASE_URL -FrontendPort $FrontendPort" in frontend_content
    assert "Clear-WebDevEnvironment" in frontend_content
    assert "if (Test-Path $WEBAPP_DEV_SERVER_ENTRY)" in frontend_content
    assert "& $NODE_CMD $WEBAPP_DEV_SERVER_ENTRY @frontendArgs" in frontend_content
    assert "elseif (Test-Path $VITE_CLI)" in frontend_content
    assert "& $NODE_CMD $VITE_CLI @frontendArgs" in frontend_content
    assert "& $NPM_CMD run dev -- @frontendArgs" in frontend_content
    assert 'Set-Location "$PSScriptRoot/webapp"' not in frontend_content

    assert "function Resolve-CommandPath([string[]]$Candidates, [string]$Label)" in helper_content
    assert "function Resolve-PreferredPythonCommand" in helper_content
    assert "function Normalize-LocalClientUrl([string]$Value)" in helper_content
    assert "function Resolve-ApiBaseUrl([string]$ExplicitApiBaseUrl, [int]$BackendPort)" in helper_content
    assert "function Resolve-ExtraDevOrigins([string]$ExplicitExtraDevOrigins, [int]$FrontendPort)" in helper_content
    assert "function Resolve-FrontendUrl([int]$FrontendPort)" in helper_content
    assert "[string]::IsNullOrWhiteSpace($ExplicitApiBaseUrl)" in helper_content
    assert "$normalizedApiBaseUrl = Normalize-LocalClientUrl $ExplicitApiBaseUrl" in helper_content
    assert "显式 API Base 无效，必须是绝对 http(s) URL：$($ExplicitApiBaseUrl)" in helper_content
    assert "$uri.Scheme -notin @('http', 'https')" in helper_content
    assert "[string]::IsNullOrWhiteSpace($ExplicitExtraDevOrigins)" in helper_content
    assert "$uri.Host -eq '0.0.0.0'" in helper_content

def test_desktop_build_scripts_default_to_runtime_profile_and_allow_full_profile() -> None:
    helper_content = _read("scripts/dev-runtime-helpers.ps1")

    for relative_path in ("scripts/build-desktop.ps1", "scripts/desktop-dev.ps1"):
        content = _read(relative_path)
        assert "[switch]$InstallDeps" in content
        assert "[string]$InstallProfile = 'runtime'" in content
        assert "Resolve-RequirementsPath" in content

    assert "function Resolve-RequirementsPath([string]$RepoRoot, [string]$Profile)" in helper_content
    assert "requirements-runtime.txt" in helper_content
    assert "requirements.txt" in helper_content

def test_build_desktop_scripts_respect_kb_python_contract() -> None:
    helper_content = _read("scripts/dev-runtime-helpers.ps1")
    ps_content = _read("scripts/build-desktop.ps1")
    sh_content = _read("scripts/build-desktop.sh")

    assert "$PYTHON_CMD = Resolve-PreferredPythonCommand" in ps_content
    assert "& $PYTHON_CMD -m pip install -r $requirementsPath" in ps_content
    assert "if ($env:KB_PYTHON)" in helper_content
    assert "if ($env:NORTHAGENT_PYTHON)" in helper_content
    assert "if ($env:THINKRAG_PYTHON)" in helper_content
    assert "if ($env:FOXGLOVE_PYTHON)" in helper_content
    assert "Resolve-CommandPath @('python.exe', 'python', 'py.exe', 'py') 'python'" in helper_content
    assert '${KB_PYTHON:-}' in sh_content
    assert '${CONDA_PREFIX:-}' in sh_content
    assert '${VIRTUAL_ENV:-}' in sh_content
    assert "/opt/miniconda3/envs/agent-kb/bin/python" not in sh_content
    assert '"$PYTHON_CMD" -m pip install -r "$REQUIREMENTS_FILE"' in sh_content

def test_package_python_runtime_uses_kb_python_contract() -> None:
    helper_content = _read("scripts/dev-runtime-helpers.ps1")
    content = _read("scripts/package-python-runtime.ps1")

    assert "$PYTHON_CMD = Resolve-PreferredPythonCommand" in content
    assert "Resolve-CommandPath @('python.exe', 'python', 'py.exe', 'py') 'python'" in helper_content
    assert "& $PYTHON_CMD -m pip install pyinstaller" in content
    assert "& $PYTHON_CMD -m PyInstaller" in content

def test_build_and_package_helpers_document_release_boundary() -> None:
    for relative_path in ("scripts/build-desktop.ps1", "scripts/build-desktop.sh"):
        content = _read(relative_path)
        assert "local desktop build helper" in content
        assert "KB_PYTHON" in content
        assert "release:mac" in content
        assert "webapp/dist" in content

    package_content = _read("scripts/package-python-runtime.ps1")
    assert "PyInstaller" in package_content
    assert "API-only" in package_content
    assert "Electron desktop release lane" in package_content


def test_python_override_precedence_prefers_kb_then_northagent_before_legacy_aliases() -> None:
    helper_content = _read("scripts/dev-runtime-helpers.ps1")
    expected_ps_order = (
        "if ($env:KB_PYTHON)",
        "if ($env:NORTHAGENT_PYTHON)",
        "if ($env:THINKRAG_PYTHON)",
        "if ($env:FOXGLOVE_PYTHON)",
    )
    positions = [helper_content.index(fragment) for fragment in expected_ps_order]
    assert positions == sorted(positions)

    for relative_path in (
        "start_dev.ps1",
        "scripts/dev-all.ps1",
        "scripts/desktop-dev.ps1",
        "scripts/build-desktop.ps1",
        "scripts/package-python-runtime.ps1",
        "start_api.ps1",
    ):
        content = _read(relative_path)
        assert "Resolve-PreferredPythonCommand" in content, f"{relative_path} should reuse the shared Python override resolver"

    sh_content = _read("scripts/build-desktop.sh")
    expected_sh_order = (
        '${KB_PYTHON:-}',
        '${NORTHAGENT_PYTHON:-}',
        '${THINKRAG_PYTHON:-}',
        '${FOXGLOVE_PYTHON:-}',
    )
    positions = [sh_content.index(fragment) for fragment in expected_sh_order]
    assert positions == sorted(positions)

def test_desktop_dev_supports_port_contracts_for_web_and_electron() -> None:
    content = _read("scripts/desktop-dev.ps1")

    assert "[switch]$Stop" in content
    assert "[Nullable[int]]$BackendPort = $null" in content
    assert "[Nullable[int]]$FrontendPort = $null" in content
    assert "[string]$ApiBaseUrl = ''" in content
    assert "Get-DualPortScopedFileName 'desktop-web' $BackendPort $FrontendPort (Get-DefaultBackendPort) (Get-DefaultFrontendPort) '.pid'" in content
    assert "Get-DualPortScopedFileName 'desktop-shell' $BackendPort $FrontendPort (Get-DefaultBackendPort) (Get-DefaultFrontendPort) '.pid'" in content
    assert "Get-DualPortScopedFileName 'desktop_web_out' $BackendPort $FrontendPort (Get-DefaultBackendPort) (Get-DefaultFrontendPort) '.log'" in content
    assert "Get-DualPortScopedFileName 'desktop_shell_out' $BackendPort $FrontendPort (Get-DefaultBackendPort) (Get-DefaultFrontendPort) '.log'" in content
    assert "$DEV_RUNTIME_HELPERS = Join-Path $PSScriptRoot 'dev-runtime-helpers.ps1'" in content
    assert ". $DEV_RUNTIME_HELPERS" in content
    assert "$BackendPort = Resolve-BackendPort $BackendPort" in content
    assert "$FrontendPort = Resolve-FrontendPort $FrontendPort" in content
    assert "$API_BASE_URL = Resolve-ApiBaseUrl $ApiBaseUrl $BackendPort" in content
    assert "$BACKEND_RUNTIME_PORT = Resolve-ApiPortFromBaseUrl $API_BASE_URL $BackendPort" in content
    assert "$FRONTEND_URL = Resolve-FrontendUrl $FrontendPort" in content
    assert "Set-WebDevEnvironment -ApiBaseUrl $API_BASE_URL -FrontendPort $FrontendPort" in content
    assert "try {" in content
    assert "$webProcess = Start-WebProcess -NodeCommand $NODE_CMD -NpmCommand $NPM_CMD -WebappDir $WEBAPP_DIR -DevServerEntry $WEBAPP_DEV_SERVER_ENTRY -ViteCli $VITE_CLI -StdoutLog $WEB_OUT_LOG -StderrLog $WEB_ERR_LOG -FrontendPort $FrontendPort" in content
    assert "} finally {" in content
    assert "Clear-WebDevEnvironment" in content
    assert "Set-Content -LiteralPath $WEB_PID_FILE -Value $webProcess.Id -Encoding ascii" in content
    assert "Set-DesktopRuntimeEnvironment -BackendPort $BACKEND_RUNTIME_PORT -ApiBaseUrl $API_BASE_URL -FrontendPort $FrontendPort -FrontendUrl $FRONTEND_URL -PythonCommand $PYTHON_CMD" in content
    assert "$desktopProcess = Start-DesktopProcess -NodeCommand $NODE_CMD -NpmCommand $NPM_CMD -DesktopDir $DESKTOP_DIR -HeadlessDesktopEntry $HEADLESS_DESKTOP_ENTRY -ElectronCli $ELECTRON_CLI -StdoutLog $DESKTOP_OUT_LOG -StderrLog $DESKTOP_ERR_LOG" in content
    assert "Clear-DesktopRuntimeEnvironment" in content
    assert "Set-Content -LiteralPath $DESKTOP_PID_FILE -Value $desktopProcess.Id -Encoding ascii" in content
    assert "Stop-ManagedProcess $DESKTOP_PID_FILE 'desktop helper shell'" in content
    assert "Stop-ManagedProcess $WEB_PID_FILE 'desktop helper web'" in content
    assert "compatibility helper" in content
    assert "Using explicit API base $API_BASE_URL" in content
    assert "Stop helper: powershell -File $PSCommandPath -Stop -BackendPort $BackendPort -FrontendPort $FrontendPort" in content

    helper_index = content.index(". $DEV_RUNTIME_HELPERS")
    api_base_index = content.index("$API_BASE_URL = Resolve-ApiBaseUrl $ApiBaseUrl $BackendPort")
    frontend_url_index = content.index("$FRONTEND_URL = Resolve-FrontendUrl $FrontendPort")
    assert helper_index < api_base_index
    assert helper_index < frontend_url_index
def test_build_desktop_shell_script_supports_runtime_and_full_profiles() -> None:
    content = _read("scripts/build-desktop.sh")

    assert 'INSTALL_PROFILE="runtime"' in content
    assert "--install-profile" in content
    assert 'REQUIREMENTS_FILE="$ROOT/requirements-runtime.txt"' in content
    assert 'REQUIREMENTS_FILE="$ROOT/requirements.txt"' in content
    assert "unsupported install profile:" in content



def test_desktop_docs_explain_explicit_remote_api_no_local_fallback() -> None:
    runbook = _read("docs/desktop_runbook.md")
    quick_guide = _read("docs/guide/desktop_runbook.md")
    contract = _read("docs/spec/desktop_api_contract.md")

    assert "不会自动回退到本地 `run_api.py`" in runbook
    assert "不会自动回退到本地 `run_api.py`" in quick_guide
    assert "must **not** silently auto-start or fall back to a local `run_api.py` process" in contract
    assert "explicit remote API boot failure" in contract


def test_headless_desktop_runtime_runner_reuses_bootstrap_contracts() -> None:
    content = _read("desktop/scripts/headless-runtime.js")

    assert "bootDesktopApp" in content
    assert "resolveDevProjectRoot" in content
    assert "ensurePythonApi" in content
    assert "resolveRendererEntry" in content
    assert "resolveDesktopHeadless" in content
    assert '"renderer_resolved"' in content
    assert '"renderer_loaded"' in content
    assert "KB_RUNTIME_ROOT" not in content
    assert "process.exitCode = 1" in content

@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell startup contract is Windows-specific")
def test_start_frontend_rejects_invalid_explicit_api_base_before_launch() -> None:
    result = _run_powershell_file("start_frontend.ps1", "-ApiBaseUrl", "/api")

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert "http(s) URL" in combined_output
    assert "/api" in combined_output


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell startup contract is Windows-specific")
def test_desktop_dev_rejects_invalid_explicit_api_base_before_launch() -> None:
    result = _run_powershell_file("scripts/desktop-dev.ps1", "-ApiBaseUrl", "/api")

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert "http(s) URL" in combined_output
    assert "/api" in combined_output

