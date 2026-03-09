# Project 2 — Initialize p2: Redis keys (run once before first use)
# Run from repo root: .\project2\run_setup_p2.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$env:PYTHONPATH = $root

Write-Host "Initializing Project 2 Redis keys (prefix p2:)..." -ForegroundColor Cyan
python project2/setup_redis_p2.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Done. You can run the P2 bot: .\project2\run_bot.ps1" -ForegroundColor Green
