# List Railway projects/services for KLIPORA account analysis.
# Run from repo root: .\scripts\list_railway_services.ps1
# Requires Railway CLI (npm i -g @railway/cli or scoop install railway) and: railway login

$ErrorActionPreference = "Continue"
Write-Host "=== Railway account analysis for KLIPORA ===" -ForegroundColor Cyan
Write-Host ""

# Try Railway CLI
$railway = Get-Command railway -ErrorAction SilentlyContinue
if (-not $railway) {
    Write-Host "Railway CLI not found. Install: npm i -g @railway/cli  or  scoop install railway" -ForegroundColor Yellow
    Write-Host "Then run: railway login" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Alternatively, open https://railway.app/dashboard and note:" -ForegroundColor White
    Write-Host "  - Each PROJECT name" -ForegroundColor White
    Write-Host "  - Each SERVICE inside it (e.g. web, n8n, render)" -ForegroundColor White
    Write-Host "  - Public URL per service (Settings -> Networking)" -ForegroundColor White
    Write-Host ""
    Write-Host "See RAILWAY_ACCOUNT_ANALYSIS.md for how to use them in KLIPORA." -ForegroundColor White
    exit 0
}

Write-Host "Using Railway CLI..." -ForegroundColor Green
railway whoami 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Run: railway login" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "--- Projects (railway list) ---" -ForegroundColor Cyan
railway list 2>$null

Write-Host ""
Write-Host "--- Current project status (railway status) ---" -ForegroundColor Cyan
railway status 2>$null

Write-Host ""
Write-Host "--- Services in linked project (railway service status --all) ---" -ForegroundColor Cyan
railway service status --all 2>$null

Write-Host ""
Write-Host "To see public URLs: Railway Dashboard -> Project -> Service -> Settings -> Networking." -ForegroundColor White
Write-Host "Map them using RAILWAY_ACCOUNT_ANALYSIS.md." -ForegroundColor White
