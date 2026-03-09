# KLIPORA Telegram Mission Console — run from repo root
# Run: .\run_telegram_bot.ps1
# Keys are loaded from KEY=value.env (or .env) in this folder.

$root = $PSScriptRoot
Set-Location $root
$env:PYTHONPATH = $root

# Load KEY=value.env and .env (both if present; .env overrides so either file can define MISSION_CONTROL_URL)
foreach ($envName in @("KEY=value.env", ".env")) {
    $envFile = Join-Path $root $envName
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            $line = $_.Trim()
            if ($line -and -not $line.StartsWith("#") -and $line -match "^(.+?)=(.+)$") {
                [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim().Trim('"').Trim("'"), "Process")
            }
        }
    }
}

# Clear webhook so this bot can use long polling (in case n8n set a webhook)
python scripts/reset_telegram_webhook.py 2>$null

python -m Command_Center.telegram_command_center
