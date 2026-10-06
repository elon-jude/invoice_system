param(
    [switch]$Reload,
    [switch]$UsePostgres,
    [int]$Port = 8001
)

Set-Location "$PSScriptRoot"
if (-not (Test-Path "backend\.venv\Scripts\python.exe")) { Write-Host "Run .\setup_backend.ps1 first"; exit 1 }
if (-not $env:JWT_SECRET) { Write-Host "JWT_SECRET is not set: sign-ins will be lost whenever the server restarts." }
if ($UsePostgres) {
    if (-not $env:DATABASE_URL) {
        Write-Host "DATABASE_URL must be set when using -UsePostgres."
        exit 1
    }
} else {
    if ($env:DATABASE_URL) { Write-Host "Using local SQLite. Pass -UsePostgres to use DATABASE_URL." }
    Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    Write-Host "Using the local SQLite file backend\invoices.db."
}
if (-not $env:ADMIN_USERNAME) { Write-Host "First run? Set ADMIN_USERNAME and ADMIN_PASSWORD (8+ characters) so a staff account can be created." }
$uvicornArgs = @("-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "$Port")
if ($Reload) {
    $uvicornArgs += "--reload"
}

& .\backend\.venv\Scripts\python.exe @uvicornArgs
