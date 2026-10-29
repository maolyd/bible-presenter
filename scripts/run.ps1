# Start Bible Presenter from the source code (after running setup_dev.ps1 once).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path .\.venv\Scripts\python.exe)) { throw "Run .\scripts\setup_dev.ps1 first." }
& .\.venv\Scripts\python.exe main.py
