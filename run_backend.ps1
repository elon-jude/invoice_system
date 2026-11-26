param(
    [switch]$Reload,
    [switch]$UsePostgres,
    [switch]$NoAuth,
    [switch]$Sandbox,
    [switch]$ResetSandbox,
    [int]$Port = 8001
)

Set-Location "$PSScriptRoot"
$env:APP_ENV = "development"
if (-not (Test-Path "backend\.venv\Scripts\python.exe")) { Write-Host "Run .\setup_backend.ps1 first"; exit 1 }
if ($Sandbox) {
    $env:AUTH_DISABLED = "1"
    $sandboxDb = Join-Path $PSScriptRoot "backend\sandbox.db"
    if ($ResetSandbox) {
        Remove-Item $sandboxDb -ErrorAction SilentlyContinue
        Remove-Item "$sandboxDb-shm" -ErrorAction SilentlyContinue
        Remove-Item "$sandboxDb-wal" -ErrorAction SilentlyContinue
    }
    $env:WASHKING_DB_PATH = $sandboxDb
    Write-Host "SANDBOX: authentication disabled and database: backend\sandbox.db"
}
if ($NoAuth) {
    $env:AUTH_DISABLED = "1"
    Write-Host "AUTH IS DISABLED (-NoAuth): no login needed. Development only."
}
if (-not $env:JWT_SECRET) { Write-Host "JWT_SECRET is not set: sign-ins will be lost whenever the server restarts." }
if ($UsePostgres) {
    if (-not $env:DATABASE_URL) {
        Write-Host "DATABASE_URL must be set when using -UsePostgres."
        exit 1
    }
} else {
    if ($env:DATABASE_URL) { Write-Host "Using local SQLite for a local test database. Pass -UsePostgres to use DATABASE_URL." }
    Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    if ($Sandbox) {
        Write-Host "Using the isolated SQLite sandbox database backend\sandbox.db."
    } else {
        Write-Host "Using the local SQLite file backend\invoices.db."
    }
}
if (-not $env:ADMIN_USERNAME) { Write-Host "First run? Set ADMIN_USERNAME and ADMIN_PASSWORD (8+ characters) so an administrator account can be created." }
$uvicornArgs = @("-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "$Port")
if ($Reload) {
    $uvicornArgs += "--reload"
}

& .\backend\.venv\Scripts\python.exe @uvicornArgs
