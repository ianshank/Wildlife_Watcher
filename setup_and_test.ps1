$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Creating Python virtual environment..."
    python -m venv .venv
}

$venvPython = ".\.venv\Scripts\python.exe"

Write-Host "Installing development dependencies..."
& $venvPython -m pip install -r requirements-dev.txt

Write-Host "Running repo quality gate..."
& $venvPython .agents/harness/orchestrator.py quality

Write-Host "Done!"