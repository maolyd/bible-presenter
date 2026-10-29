# One-time setup for running Bible Presenter from the source code.
# Run in PowerShell from the project folder:   .\scripts\setup_dev.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "Creating the virtual environment in .venv ..." -ForegroundColor Cyan
if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3.12 -m venv .venv          # the Python launcher picks Python 3.12 specifically
} else {
    python -m venv .venv
}
if ($LASTEXITCODE -ne 0) { throw "Could not create the virtual environment. Is Python 3.12 installed? See docs\INSTALL_WINDOWS.md" }

Write-Host "Installing the required packages (this can take a few minutes) ..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Package installation failed. Check your internet connection and try again." }

Write-Host ""
Write-Host "Done. Start the program with:  .\scripts\run.ps1" -ForegroundColor Green
