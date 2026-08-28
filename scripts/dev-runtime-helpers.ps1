# 本地开发启动共享 helper
# - 收口后端 dev env、React(Vite) 启动 fallback、桌面 runtime 环境变量注入、headless 检测
# - 供 start_dev.ps1 / start_api.ps1 / start_frontend.ps1 / scripts/dev-all.ps1 / scripts/desktop-dev.ps1 复用

function Normalize-StartProcessEnvironment() {
  $pathValue = $env:Path
  if (-not $pathValue) {
    $pathValue = $env:PATH
  }
  if ($pathValue) {
    [System.Environment]::SetEnvironmentVariable('Path', $pathValue, 'Process')
  }
  [System.Environment]::SetEnvironmentVariable('PATH', $null, 'Process')
  Remove-Item Env:PATH -ErrorAction SilentlyContinue
}

function Resolve-CommandPath([string[]]$Candidates, [string]$Label) {
  foreach ($candidate in $Candidates) {
    $command = Get-Command $candidate -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command -and $command.Source) {
      return $command.Source
    }
  }
  throw "未找到 $Label，可执行候选：$($Candidates -join ', ')"
}

function Resolve-PreferredPythonCommand() {
  if ($env:KB_PYTHON) {
    return $env:KB_PYTHON
  }
  if ($env:NORTHAGENT_PYTHON) {
    return $env:NORTHAGENT_PYTHON
  }
  if ($env:THINKRAG_PYTHON) {
    return $env:THINKRAG_PYTHON
  }
  if ($env:FOXGLOVE_PYTHON) {
    return $env:FOXGLOVE_PYTHON
  }
  return Resolve-CommandPath @('python.exe', 'python', 'py.exe', 'py') 'python'
}

function Resolve-RequirementsPath([string]$RepoRoot, [string]$Profile) {
  switch ($Profile) {
    'runtime' {
      return Join-Path $RepoRoot 'requirements-runtime.txt'
    }
    'full' {
      return Join-Path $RepoRoot 'requirements.txt'
    }
    default {
      throw "不支持的依赖安装口径：$Profile"
    }
  }
}

function Get-DefaultBackendPort() {
  return 18080
}

function Get-DefaultFrontendPort() {
  return 5173
}

function Resolve-BackendPort([Nullable[int]]$BackendPort) {
  if ($null -ne $BackendPort) {
    return [int]$BackendPort
  }
  return Get-DefaultBackendPort
}

function Resolve-FrontendPort([Nullable[int]]$FrontendPort) {
  if ($null -ne $FrontendPort) {
    return [int]$FrontendPort
  }
  return Get-DefaultFrontendPort
}

function Get-PortScopedFileName([string]$BaseName, [int]$Port, [int]$DefaultPort, [string]$Extension) {
  if ($Port -eq $DefaultPort) {
    return "${BaseName}${Extension}"
  }
  return "${BaseName}-${Port}${Extension}"
}

function Get-DualPortScopedFileName([string]$BaseName, [int]$PrimaryPort, [int]$SecondaryPort, [int]$DefaultPrimaryPort, [int]$DefaultSecondaryPort, [string]$Extension) {
  if ($PrimaryPort -eq $DefaultPrimaryPort -and $SecondaryPort -eq $DefaultSecondaryPort) {
    return "${BaseName}${Extension}"
  }
  return "${BaseName}-${PrimaryPort}-${SecondaryPort}${Extension}"
}

function Normalize-LocalClientUrl([string]$Value) {
  $raw = if ($null -eq $Value) { '' } else { $Value.Trim() }
  if (-not $raw) {
    return ''
  }

  $trimmed = $raw.TrimEnd('/')
  $uri = $null
  if ([Uri]::TryCreate($trimmed, [UriKind]::Absolute, [ref]$uri) -and $uri) {
    if ($uri.Host -eq '0.0.0.0') {
      $builder = [UriBuilder]::new($uri)
      $builder.Host = '127.0.0.1'
      return $builder.Uri.ToString().TrimEnd('/')
    }
    return $uri.ToString().TrimEnd('/')
  }

  return $trimmed
}

function Resolve-ApiBaseUrl([string]$ExplicitApiBaseUrl, [int]$BackendPort) {
  if ([string]::IsNullOrWhiteSpace($ExplicitApiBaseUrl)) {
    return "http://127.0.0.1:$BackendPort"
  }

  $normalizedApiBaseUrl = Normalize-LocalClientUrl $ExplicitApiBaseUrl
  $uri = $null
  if (-not ([Uri]::TryCreate($normalizedApiBaseUrl, [UriKind]::Absolute, [ref]$uri) -and $uri)) {
    throw "显式 API Base 无效，必须是绝对 http(s) URL：$($ExplicitApiBaseUrl)"
  }
  if ($uri.Scheme -notin @('http', 'https')) {
    throw "显式 API Base 无效，必须是绝对 http(s) URL：$($ExplicitApiBaseUrl)"
  }

  return $normalizedApiBaseUrl
}

function Resolve-ApiPortFromBaseUrl([string]$ApiBaseUrl, [int]$FallbackPort) {
  $normalized = Normalize-LocalClientUrl $ApiBaseUrl
  if (-not $normalized) {
    return $FallbackPort
  }

  $uri = $null
  if (-not ([Uri]::TryCreate($normalized, [UriKind]::Absolute, [ref]$uri) -and $uri)) {
    return $FallbackPort
  }
  if ($uri.Scheme -notin @('http', 'https')) {
    return $FallbackPort
  }

  if ($uri.IsDefaultPort) {
    if ($uri.Scheme -eq 'https') {
      return 443
    }
    if ($uri.Scheme -eq 'http') {
      return 80
    }
    return $FallbackPort
  }

  return [int]$uri.Port
}

function Resolve-ExtraDevOrigins([string]$ExplicitExtraDevOrigins, [int]$FrontendPort) {
  if ([string]::IsNullOrWhiteSpace($ExplicitExtraDevOrigins)) {
    return "http://127.0.0.1:$FrontendPort,http://localhost:$FrontendPort"
  }

  $origins = @(
    ($ExplicitExtraDevOrigins -split ',') |
      ForEach-Object { $_.Trim() } |
      Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
  )
  return ($origins -join ',')
}

function Resolve-FrontendUrl([int]$FrontendPort) {
  return Normalize-LocalClientUrl "http://127.0.0.1:$FrontendPort"
}

function Get-ManagedPid([string]$PidFile) {
  if (-not (Test-Path $PidFile)) {
    return $null
  }
  $rawContent = Get-Content $PidFile -Raw -ErrorAction SilentlyContinue
  if ($null -eq $rawContent) {
    return $null
  }
  $raw = $rawContent.Trim()
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


function Set-BackendDevEnvironment(
  [string]$RepoRoot,
  [int]$BackendPort,
  [string]$ApiBaseUrl,
  [string]$ExtraDevOrigins,
  [string]$Reload = '0'
) {
  $env:PYTHONPATH = $RepoRoot
  $env:KB_API_RELOAD = $Reload
  $env:KB_API_PORT = "$BackendPort"
  $env:NORTHAGENT_API_PORT = "$BackendPort"
  $env:THINKRAG_API_PORT = "$BackendPort"
  $env:FOXGLOVE_API_PORT = "$BackendPort"
  $env:KB_API_BASE_URL = $ApiBaseUrl
  $env:NORTHAGENT_API_BASE_URL = $ApiBaseUrl
  $env:THINKRAG_API_BASE_URL = $ApiBaseUrl
  $env:FOXGLOVE_API_BASE_URL = $ApiBaseUrl
  $env:KB_EXTRA_DEV_ORIGINS = $ExtraDevOrigins
  $env:NORTHAGENT_EXTRA_DEV_ORIGINS = $ExtraDevOrigins
  $env:THINKRAG_EXTRA_DEV_ORIGINS = $ExtraDevOrigins
  $env:FOXGLOVE_EXTRA_DEV_ORIGINS = $ExtraDevOrigins
}

function Clear-BackendDevEnvironment() {
  Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
  Remove-Item Env:KB_API_RELOAD -ErrorAction SilentlyContinue
  Remove-Item Env:KB_API_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:NORTHAGENT_API_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:THINKRAG_API_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:FOXGLOVE_API_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:KB_API_BASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:NORTHAGENT_API_BASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:THINKRAG_API_BASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:FOXGLOVE_API_BASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:KB_EXTRA_DEV_ORIGINS -ErrorAction SilentlyContinue
  Remove-Item Env:NORTHAGENT_EXTRA_DEV_ORIGINS -ErrorAction SilentlyContinue
  Remove-Item Env:THINKRAG_EXTRA_DEV_ORIGINS -ErrorAction SilentlyContinue
  Remove-Item Env:FOXGLOVE_EXTRA_DEV_ORIGINS -ErrorAction SilentlyContinue
}

function Set-WebDevEnvironment([string]$ApiBaseUrl, [int]$FrontendPort, [string]$ListenHost = '127.0.0.1') {
  $env:VITE_API_BASE_URL = $ApiBaseUrl
  $env:KB_WEBAPP_HOST = $ListenHost
  $env:KB_WEBAPP_PORT = "$FrontendPort"
}

function Clear-WebDevEnvironment() {
  Remove-Item Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:KB_WEBAPP_HOST -ErrorAction SilentlyContinue
  Remove-Item Env:KB_WEBAPP_PORT -ErrorAction SilentlyContinue
}

function Write-LogTail([string]$Path, [string]$Label, [int]$TailLines = 40) {
  if (-not (Test-Path $Path)) {
    Write-Host "    $Label log not found: $Path" -ForegroundColor DarkYellow
    return
  }

  Write-Host "    --- $Label log tail ($TailLines lines) ---" -ForegroundColor Yellow
  Get-Content -LiteralPath $Path -Tail $TailLines -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "      $_"
  }
}

function Start-WebProcess(
  [string]$NodeCommand,
  [string]$NpmCommand,
  [string]$WebappDir,
  [string]$DevServerEntry,
  [string]$ViteCli,
  [string]$StdoutLog,
  [string]$StderrLog,
  [int]$FrontendPort,
  [string]$ListenHost = '127.0.0.1'
) {
  $frontendArgs = @('--host', $ListenHost, '--port', "$FrontendPort")
  if (Test-Path $DevServerEntry) {
    $webappEntryArgs = @($DevServerEntry) + $frontendArgs
    return Start-Process -FilePath $NodeCommand -ArgumentList $webappEntryArgs -WorkingDirectory $WebappDir -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -WindowStyle Hidden -PassThru
  }

  if (Test-Path $ViteCli) {
    $viteCliArgs = @($ViteCli) + $frontendArgs
    return Start-Process -FilePath $NodeCommand -ArgumentList $viteCliArgs -WorkingDirectory $WebappDir -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -WindowStyle Hidden -PassThru
  }

  $npmFrontendArgs = @('run', 'dev', '--') + $frontendArgs
  return Start-Process -FilePath $NpmCommand -ArgumentList $npmFrontendArgs -WorkingDirectory $WebappDir -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -WindowStyle Hidden -PassThru
}

function Set-DesktopRuntimeEnvironment(
  [int]$BackendPort,
  [string]$ApiBaseUrl,
  [int]$FrontendPort,
  [string]$FrontendUrl,
  [string]$PythonCommand
) {
  $env:KB_API_PORT = "$BackendPort"
  $env:KB_API_BASE_URL = $ApiBaseUrl
  $env:NORTHAGENT_API_PORT = "$BackendPort"
  $env:NORTHAGENT_API_BASE_URL = $ApiBaseUrl
  $env:THINKRAG_API_PORT = "$BackendPort"
  $env:FOXGLOVE_API_PORT = "$BackendPort"
  $env:THINKRAG_API_BASE_URL = $ApiBaseUrl
  $env:FOXGLOVE_API_BASE_URL = $ApiBaseUrl
  $env:KB_WEB_URL = $FrontendUrl
  $env:NORTHAGENT_WEB_URL = $FrontendUrl
  $env:THINKRAG_WEB_URL = $FrontendUrl
  $env:FOXGLOVE_WEB_URL = $FrontendUrl
  $env:KB_WEB_PORT = "$FrontendPort"
  $env:NORTHAGENT_WEB_PORT = "$FrontendPort"
  $env:THINKRAG_WEB_PORT = "$FrontendPort"
  $env:FOXGLOVE_WEB_PORT = "$FrontendPort"
  $env:KB_PYTHON = $PythonCommand
  $env:NORTHAGENT_PYTHON = $PythonCommand
  $env:THINKRAG_PYTHON = $PythonCommand
  $env:FOXGLOVE_PYTHON = $PythonCommand
}

function Clear-DesktopRuntimeEnvironment() {
  Remove-Item Env:KB_API_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:NORTHAGENT_API_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:THINKRAG_API_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:FOXGLOVE_API_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:KB_API_BASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:NORTHAGENT_API_BASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:THINKRAG_API_BASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:FOXGLOVE_API_BASE_URL -ErrorAction SilentlyContinue
  Remove-Item Env:KB_WEB_URL -ErrorAction SilentlyContinue
  Remove-Item Env:NORTHAGENT_WEB_URL -ErrorAction SilentlyContinue
  Remove-Item Env:THINKRAG_WEB_URL -ErrorAction SilentlyContinue
  Remove-Item Env:FOXGLOVE_WEB_URL -ErrorAction SilentlyContinue
  Remove-Item Env:KB_WEB_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:NORTHAGENT_WEB_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:THINKRAG_WEB_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:FOXGLOVE_WEB_PORT -ErrorAction SilentlyContinue
  Remove-Item Env:KB_PYTHON -ErrorAction SilentlyContinue
  Remove-Item Env:NORTHAGENT_PYTHON -ErrorAction SilentlyContinue
  Remove-Item Env:THINKRAG_PYTHON -ErrorAction SilentlyContinue
  Remove-Item Env:FOXGLOVE_PYTHON -ErrorAction SilentlyContinue
}

function Test-DesktopHeadlessRequested() {
  foreach ($key in @('KB_DESKTOP_HEADLESS', 'NORTHAGENT_DESKTOP_HEADLESS', 'THINKRAG_DESKTOP_HEADLESS', 'FOXGLOVE_DESKTOP_HEADLESS')) {
    $raw = [string](Get-Item -Path ("Env:$key") -ErrorAction SilentlyContinue).Value
    if (-not $raw) {
      continue
    }
    switch ($raw.Trim().ToLowerInvariant()) {
      '1' { return $true }
      'true' { return $true }
      'yes' { return $true }
      'on' { return $true }
    }
  }
  return $false
}

function Start-DesktopProcess(
  [string]$NodeCommand,
  [string]$NpmCommand,
  [string]$DesktopDir,
  [string]$HeadlessDesktopEntry,
  [string]$ElectronCli,
  [string]$StdoutLog,
  [string]$StderrLog
) {
  if ((Test-DesktopHeadlessRequested) -and (Test-Path $HeadlessDesktopEntry)) {
    return Start-Process -FilePath $NodeCommand -ArgumentList @($HeadlessDesktopEntry) -WorkingDirectory $DesktopDir -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -WindowStyle Hidden -PassThru
  }

  if (Test-Path $ElectronCli) {
    return Start-Process -FilePath $NodeCommand -ArgumentList @($ElectronCli, '.') -WorkingDirectory $DesktopDir -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -WindowStyle Hidden -PassThru
  }

  return Start-Process -FilePath $NpmCommand -ArgumentList @('run', 'dev') -WorkingDirectory $DesktopDir -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -WindowStyle Hidden -PassThru
}
