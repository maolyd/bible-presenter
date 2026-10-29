@echo off
rem Double-click this file to install Bible Presenter for your Windows user account.
rem It runs scripts\windows\install.ps1 (the -ExecutionPolicy Bypass applies to this one script only).
title Install Bible Presenter
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\install.ps1"
