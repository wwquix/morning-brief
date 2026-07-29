param(
    [ValidatePattern("^([01]\d|2[0-3]):[0-5]\d$")]
    [string]$Time = "07:00"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $projectRoot "run_morning_brief.ps1"

if (!(Test-Path $runner)) {
    throw "Не найден $runner"
}

$parts = $Time.Split(":")
$trigger = New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours([int]$parts[0]).AddMinutes([int]$parts[1]))
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`""
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask `
    -TaskName "Morning Brief" `
    -Description "Ежедневно создаёт Morning Brief, синхронизирует Notion и отправляет Telegram." `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Force | Out-Null

Write-Host "Задача Morning Brief установлена. Время запуска: $Time"
