Set-Location "$PSScriptRoot\backend"
if (-not (Test-Path ".venv")) { py -3.11 -m venv .venv }
$python = ".\.venv\Scripts\python.exe"
& $python -m pip --version > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    & $python -m ensurepip --upgrade
}
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
Write-Host "Backend dependencies installed."
