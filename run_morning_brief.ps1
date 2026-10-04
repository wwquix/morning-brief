param([switch]$LocalOnly)

$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$logDir = Join-Path $PSScriptRoot "logs"
$logPath = Join-Path $logDir "morning-brief.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-Log {
    param([string]$Message)
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logPath -Value "$stamp $Message" -Encoding UTF8
}

Write-Log "Morning brief start"

# app.py loads .env; existing process variables take precedence.

$pythonPath = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$appPath = Join-Path $PSScriptRoot "app.py"

if (!(Test-Path $pythonPath)) {
    Write-Log "ERROR: Python not found at $pythonPath"
    exit 1
}

if (!(Test-Path $appPath)) {
    Write-Log "ERROR: app.py not found at $appPath"
    exit 1
}

$appArguments = @($appPath)
if ($LocalOnly) { $appArguments += "--local-only" }

& $pythonPath @appArguments 2>&1 | ForEach-Object {
    Add-Content -Path $logPath -Value $_ -Encoding UTF8
}

$exitCode = $LASTEXITCODE

Write-Log "Morning brief finished with code $exitCode"

exit $exitCode
