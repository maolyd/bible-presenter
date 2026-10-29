# Installs Bible Presenter for the current Windows user. No administrator rights needed.
# Started by double-clicking "Install Bible Presenter.bat" in the project folder.
#
# What it does:
#   1. Finds Python 3.10-3.13, or downloads Python 3.12 from python.org and installs it for this user.
#   2. Copies the program to %LOCALAPPDATA%\Programs\BiblePresenter.
#   3. Downloads the program's components (PySide6, about 200 MB) into a private folder there.
#   4. Creates "Bible Presenter" shortcuts on the Desktop and in the Start menu, and an uninstaller.
# Running it again updates an existing installation. Your Bibles and settings are kept.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"      # makes downloads much faster in Windows PowerShell

$Source = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Target = Join-Path $env:LOCALAPPDATA "Programs\BiblePresenter"
$PythonVersion = "3.12.10"
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"

function Step($message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}

function Stop-WithError($message) {
    Write-Host ""
    Write-Host "Installation stopped:" -ForegroundColor Red
    Write-Host $message -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to close this window"
    exit 1
}

function Find-Python {
    # Per-user and all-users installs from python.org
    foreach ($v in "312", "313", "311", "310") {
        foreach ($dir in (Join-Path $env:LOCALAPPDATA "Programs\Python\Python$v"), (Join-Path $env:ProgramFiles "Python$v")) {
            $exe = Join-Path $dir "python.exe"
            if (Test-Path $exe) { return $exe }
        }
    }
    # The "py" launcher knows about other installs. It writes to stderr when a version is
    # missing, which must not count as an error here.
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $previous = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            foreach ($v in "3.12", "3.13", "3.11", "3.10") {
                $exe = & py "-$v" -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $exe) { return ($exe | Select-Object -First 1).Trim() }
            }
        } finally {
            $ErrorActionPreference = $previous
        }
    }
    return $null
}

try {
    Write-Host "Bible Presenter installer" -ForegroundColor Green
    Write-Host "Installing to: $Target"

    if (-not (Test-Path (Join-Path $Source "main.py"))) {
        Stop-WithError "This installer must stay inside the bible-presentation-app folder (next to main.py). Unzip the whole folder first, then run it again."
    }

    # ---------------------------------------------------------------- 1. Python
    Step "Looking for Python"
    $python = Find-Python
    if ($python) {
        Write-Host "Found $python"
    } else {
        Step "Downloading Python $PythonVersion from python.org (about 25 MB)"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $installer = Join-Path $env:TEMP "python-$PythonVersion-amd64.exe"
        try {
            Invoke-WebRequest -Uri $PythonUrl -OutFile $installer -UseBasicParsing
        } catch {
            Stop-WithError "Could not download Python. Check the internet connection and run the installer again.`n$($_.Exception.Message)"
        }
        Step "Installing Python for your user account (about 1 minute)"
        $pyArgs = @("/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=0", "Include_test=0", "Include_doc=0")
        $process = Start-Process -FilePath $installer -ArgumentList $pyArgs -Wait -PassThru
        if ($process.ExitCode -ne 0) {
            Stop-WithError "The Python installer reported error code $($process.ExitCode). Install Python 3.12 from https://www.python.org/downloads/windows/ yourself, then run this installer again."
        }
        $python = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
        if (-not (Test-Path $python)) { Stop-WithError "Python was installed but could not be found at $python." }
        Write-Host "Python installed."
    }

    # ---------------------------------------------------------------- 2. Program files
    Step "Copying Bible Presenter"
    New-Item -ItemType Directory -Force -Path $Target | Out-Null
    if ((Resolve-Path $Source).Path -ne (Resolve-Path $Target).Path) {
        foreach ($item in "app", "web", "data", "docs", "scripts") {
            $old = Join-Path $Target $item
            if (Test-Path $old) { Remove-Item -Recurse -Force $old }     # remove files from an older version
            Copy-Item -Path (Join-Path $Source $item) -Destination $Target -Recurse -Force
        }
        foreach ($item in "main.py", "requirements.txt", "README.md", "LICENSES.md") {
            Copy-Item -Path (Join-Path $Source $item) -Destination $Target -Force
        }
    }

    # ---------------------------------------------------------------- 3. Components
    $venv = Join-Path $Target ".venv"
    $venvPython = Join-Path $venv "Scripts\python.exe"
    $venvPythonW = Join-Path $venv "Scripts\pythonw.exe"
    if (-not (Test-Path $venvPython)) {
        Step "Preparing a private Python environment"
        & $python -m venv $venv
        if ($LASTEXITCODE -ne 0) { Stop-WithError "Could not create the Python environment in $venv." }
    }
    Step "Downloading the program components (about 200 MB the first time - this takes a few minutes)"
    & $venvPython -m pip install --disable-pip-version-check --upgrade -r (Join-Path $Target "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "Downloading the components failed. Check the internet connection and run the installer again."
    }

    # ---------------------------------------------------------------- 4. Shortcuts
    Step "Creating shortcuts"
    $shell = New-Object -ComObject WScript.Shell
    $icon = Join-Path $Target "app\resources\bible-presenter.ico"
    $startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "Bible Presenter"
    New-Item -ItemType Directory -Force -Path $startMenu | Out-Null

    $places = @(
        (Join-Path ([Environment]::GetFolderPath("Desktop")) "Bible Presenter.lnk"),
        (Join-Path $startMenu "Bible Presenter.lnk")
    )
    foreach ($path in $places) {
        $link = $shell.CreateShortcut($path)
        $link.TargetPath = $venvPythonW                      # pythonw = no black console window
        $link.Arguments = '"' + (Join-Path $Target "main.py") + '"'
        $link.WorkingDirectory = $Target
        $link.IconLocation = $icon
        $link.Description = "Bible Presenter - English / Francais Bible display for OBS"
        $link.Save()
    }
    $uninstall = $shell.CreateShortcut((Join-Path $startMenu "Uninstall Bible Presenter.lnk"))
    $uninstall.TargetPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $uninstall.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $Target "scripts\windows\uninstall.ps1") + '"'
    $uninstall.WorkingDirectory = $env:TEMP
    $uninstall.Save()

    Step "Done!"
    Write-Host "Bible Presenter is installed. Start it any time with the 'Bible Presenter' icon on your Desktop"
    Write-Host "or in the Start menu. Starting it now..."
    Start-Process -FilePath $venvPythonW -ArgumentList ('"' + (Join-Path $Target "main.py") + '"') -WorkingDirectory $Target
    Write-Host ""
    Write-Host "You can delete the downloaded zip and folder now; the program lives in $Target." -ForegroundColor Green
    Read-Host "Press Enter to close this window"
} catch {
    Stop-WithError $_.Exception.Message
}
