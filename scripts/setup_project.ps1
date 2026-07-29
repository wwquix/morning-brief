param(
    [switch]$SkipNpmInstall,
    [switch]$InstallSchedule,
    [ValidatePattern("^([01]\d|2[0-3]):[0-5]\d$")]
    [string]$ScheduleTime = "07:00"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

Write-Host "1/5 Проверяю Python..."
$pythonCommand = Get-Command py -ErrorAction SilentlyContinue
if ($pythonCommand) {
    $pythonLauncher = "py"
    $pythonArgs = @("-3")
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (!$pythonCommand) {
        throw "Python 3 не найден. Установи Python 3.11+ и повтори запуск."
    }
    $pythonLauncher = "python"
    $pythonArgs = @()
}

if (!(Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "2/5 Создаю виртуальное окружение..."
    & $pythonLauncher @pythonArgs -m venv .venv
}

Write-Host "3/5 Устанавливаю Python-зависимости..."
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

if (!(Test-Path ".env") -and (Test-Path ".env.planner.example")) {
    Copy-Item ".env.planner.example" ".env"
    Write-Host "Создан .env. Вставь в него существующие Telegram-переменные и NOTION_TOKEN."
}

Write-Host "4/5 Собираю frontend..."
if (!(Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm не найден. Установи Node.js 20+ и повтори запуск."
}
Push-Location frontend
try {
    if (!$SkipNpmInstall -or !(Test-Path "node_modules")) {
        npm install
    }
    npm run build
} finally {
    Pop-Location
}

Write-Host "5/5 Проверяю конфигурацию..."
& ".\.venv\Scripts\python.exe" scripts\check_setup.py

if ($InstallSchedule) {
    & "$PSScriptRoot\install_windows_task.ps1" -Time $ScheduleTime
}

Write-Host ""
Write-Host "Базовая установка завершена."
Write-Host "Для Notion: добавь NOTION_TOKEN в .env, затем запусти:"
Write-Host ".\.venv\Scripts\python.exe scripts\setup_notion.py"
Write-Host "Для тестового запуска:"
Write-Host ".\.venv\Scripts\python.exe planner_app.py"
