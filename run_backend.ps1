Set-Location "$PSScriptRoot"
if (-not (Test-Path "backend\.venv\Scripts\python.exe")) { Write-Host "Run .\setup_backend.ps1 first"; exit 1 }
if (-not $env:JWT_SECRET) { Write-Host "JWT_SECRET is not set: sign-ins will be lost whenever the server restarts." }
if (-not $env:DATABASE_URL) { Write-Host "DATABASE_URL is not set: using the local SQLite file backend\invoices.db." }
if (-not $env:ADMIN_USERNAME) { Write-Host "First run? Set ADMIN_USERNAME and ADMIN_PASSWORD (8+ characters) so a staff account can be created." }
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
