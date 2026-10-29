# Build the portable Windows program:  dist\BiblePresenter\BiblePresenter.exe
# Run in PowerShell from the project folder:   .\scripts\build_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path .\.venv\Scripts\python.exe)) { throw "Run .\scripts\setup_dev.ps1 first." }

Write-Host "Running the automated tests first ..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed - not building. Fix the failures (or ask for help) first." }

Write-Host "Building with PyInstaller (a few minutes) ..." -ForegroundColor Cyan
if (Test-Path .\build) { Remove-Item -Recurse -Force .\build }
if (Test-Path .\dist\BiblePresenter) { Remove-Item -Recurse -Force .\dist\BiblePresenter }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean BiblePresenter.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$zip = ".\dist\BiblePresenter-portable.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path .\dist\BiblePresenter -DestinationPath $zip
Write-Host ""
Write-Host "Built:  dist\BiblePresenter\BiblePresenter.exe" -ForegroundColor Green
Write-Host "Zip to copy to other computers:  $zip" -ForegroundColor Green
