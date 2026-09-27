Set-Location "$PSScriptRoot"
if (-not (Test-Path "backend\.venv\Scripts\python.exe")) { Write-Host "Run .\setup_backend.ps1 first"; exit 1 }
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
