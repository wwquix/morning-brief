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

Write-Log "Morning brief planner start"

$envPath = Join-Path $PSScriptRoot ".env"

if (Test-Path $envPath) {
    Get-Content $envPath -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()

        if ($line -eq "" -or $line.StartsWith("#")) {
            return
        }

        if ($line -match "^\s*([^=]+)\s*=\s*(.*)\s*$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"').Trim("'")
            Set-Item -Path "Env:$name" -Value $value
        }
    }

    Write-Log ".env loaded"
} else {
    Write-Log ".env not found"
}

Write-Log "Telegram token present: $([bool]$env:TELEGRAM_BOT_TOKEN)"
Write-Log "Telegram chat id present: $([bool]$env:TELEGRAM_CHAT_ID)"
Write-Log "Notion token present: $([bool]$env:NOTION_TOKEN)"

$pythonPath = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$appPath = Join-Path $PSScriptRoot "planner_app.py"

if (!(Test-Path $pythonPath)) {
    Write-Log "ERROR: Python not found at $pythonPath"
    exit 1
}

if (!(Test-Path $appPath)) {
    Write-Log "ERROR: planner_app.py not found at $appPath"
    exit 1
}

& $pythonPath $appPath 2>&1 | ForEach-Object {
    Add-Content -Path $logPath -Value $_ -Encoding UTF8
    Write-Host $_
}

$exitCode = $LASTEXITCODE

Write-Log "Morning brief planner finished with code $exitCode"

exit $exitCode
