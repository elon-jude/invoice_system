Set-Location "$PSScriptRoot\backend"
if (-not (Test-Path ".venv")) {
    $pythonLaunch = $null
    foreach ($candidate in @("py -3.11", "py -3.12", "py -3.13", "py -3.14", "py -3.15", "python")) {
        $parts = $candidate.Split(" ")
        $probe = & $parts[0] $parts[1..($parts.Length - 1)] --version 2>$null
        if ($LASTEXITCODE -eq 0) { $pythonLaunch = $candidate; break }
    }
    if (-not $pythonLaunch) { Write-Host "Python 3.11 or newer is required."; exit 1 }
    $parts = $pythonLaunch.Split(" ")
    & $parts[0] $parts[1..($parts.Length - 1)] -m venv .venv
}
$python = ".\.venv\Scripts\python.exe"
& $python -m pip --version > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    & $python -m ensurepip --upgrade
}
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
Write-Host "Backend dependencies installed."
