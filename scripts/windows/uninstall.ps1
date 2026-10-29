# Removes Bible Presenter (installed by "Install Bible Presenter.bat").
# Started from Start menu > Bible Presenter > Uninstall Bible Presenter.
$ErrorActionPreference = "Stop"
$Target = Join-Path $env:LOCALAPPDATA "Programs\BiblePresenter"
$Data = Join-Path $env:LOCALAPPDATA "BiblePresenter"

# This script lives inside the folder it deletes: run a copy from the TEMP folder instead.
if ($PSScriptRoot -like "$Target*") {
    $copy = Join-Path $env:TEMP "uninstall-bible-presenter.ps1"
    Copy-Item $PSCommandPath $copy -Force
    Start-Process powershell.exe -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$copy`""
    exit 0
}

Write-Host "Uninstall Bible Presenter" -ForegroundColor Cyan
$answer = Read-Host "Remove Bible Presenter from this computer? (y/n)"
if ($answer -notmatch "^[yY]") { exit 0 }

Get-Process pythonw, python -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like "$Target*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path ([Environment]::GetFolderPath("Desktop")) "Bible Presenter.lnk")
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path ([Environment]::GetFolderPath("Programs")) "Bible Presenter")
if (Test-Path $Target) { Remove-Item -Recurse -Force $Target }
Write-Host "The program was removed."

$answer = Read-Host "Also delete your Bible library, favourites and settings? (y/n)"
if ($answer -match "^[yY]" -and (Test-Path $Data)) {
    Remove-Item -Recurse -Force $Data
    Write-Host "Library and settings deleted."
} else {
    Write-Host "Your library and settings were kept in $Data (used again if you reinstall)."
}
Write-Host "Python itself was not removed (Windows Settings > Apps if you want to remove it)."
Read-Host "Press Enter to close this window"
