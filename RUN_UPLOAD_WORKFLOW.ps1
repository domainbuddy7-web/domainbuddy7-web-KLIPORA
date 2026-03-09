# Double-click or run in PowerShell to upload WF-ASSEMBLE to n8n.
# Copies KEY=value.env to .env then runs the upload.
Set-Location $PSScriptRoot
if (Test-Path "KEY=value.env") { Copy-Item "KEY=value.env" ".env" -Force }
$env:PYTHONPATH = $PSScriptRoot
python scripts/upload_wf_assemble.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nIf you see 401 Unauthorized: check N8N_API_KEY in .env (n8n -> Settings -> API)."
    pause
}
