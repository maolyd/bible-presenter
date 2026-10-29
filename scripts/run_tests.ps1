# Run the automated tests. Results are printed and saved to test-results.txt
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)
& .\.venv\Scripts\python.exe -m pytest -v 2>&1 | Tee-Object -FilePath test-results.txt
