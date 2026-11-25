param(
    [switch]$Reset,
    [switch]$Reload
)

Set-Location "$PSScriptRoot"

if (-not (Test-Path "backend\.venv\Scripts\python.exe")) {
    Write-Host "Setting up the backend environment..."
    & "$PSScriptRoot\setup_backend.ps1"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$env:JWT_SECRET = "washking-local-sandbox-secret-change-for-production"
$staticServer = Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
if (-not $staticServer) {
    Start-Process -FilePath "$PSScriptRoot\backend\.venv\Scripts\python.exe" `
        -ArgumentList "-m", "http.server", "8080", "--bind", "127.0.0.1" `
        -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
    Start-Sleep -Milliseconds 500
}
Write-Host "Sandbox frontend: http://127.0.0.1:8080/index.html?sandbox=1"

if ($Reset) {
    & "$PSScriptRoot\run_backend.ps1" -Sandbox -ResetSandbox -Reload:$Reload -Port 8001
} else {
    & "$PSScriptRoot\run_backend.ps1" -Sandbox -Reload:$Reload -Port 8001
}
