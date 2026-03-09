# Project 2 — Run Telegram bot with Project 2 credentials
# Run from repo root: .\project2\run_bot.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$env:PYTHONPATH = $root

$envFile = Join-Path $PSScriptRoot "KEY=value.env.project2"
if (-not (Test-Path $envFile)) {
    Write-Host "Create project2\KEY=value.env.project2 from KEY=value.env.project2.example and fill in credentials." -ForegroundColor Yellow
    Write-Host "See project2\OPEN_THESE_URLS.md for where to get each value." -ForegroundColor Yellow
    exit 1
}

Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line -match "^(.+?)=(.+)$") {
        $key = $matches[1].Trim()
        $val = $matches[2].Trim().Trim('"').Trim("'")
        [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
    }
}
[System.Environment]::SetEnvironmentVariable("PROJECT_ID", "p2", "Process")

# Optional: load Upstash into env for scripts that read REDIS from env
if ($env:UPSTASH_REDIS_REST_URL) {
    $env:REDIS_URL = $env:UPSTASH_REDIS_REST_URL
}
if ($env:UPSTASH_REDIS_REST_TOKEN) {
    $env:REDIS_TOKEN = $env:UPSTASH_REDIS_REST_TOKEN
}

Write-Host "Starting Project 2 Telegram bot (env loaded from project2\KEY=value.env.project2)..." -ForegroundColor Cyan
python scripts/reset_telegram_webhook.py 2>$null
python -m Command_Center.telegram_command_center
