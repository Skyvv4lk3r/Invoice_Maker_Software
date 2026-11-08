$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $ProjectRoot
try {
    if (-not (Test-Path '.venv\Scripts\python.exe')) {
        & py -3.12 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Creating the Python 3.12 environment failed.' }
    }
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Updating pip failed.' }
    & .\.venv\Scripts\python.exe -m pip install -e '.[desktop,dev,gui-test]'
    if ($LASTEXITCODE -ne 0) { throw 'Installing project dependencies failed.' }
    Write-Host 'Setup complete. Run .\.venv\Scripts\python.exe -m invoice_generator'
} finally {
    Pop-Location
}
