# Installing and running Bible Presenter on Windows 10 / 11

This guide assumes you have never built a Python program before. Follow the steps in order.

## Easy install (recommended): double-click

1. Download `bible-presentation-app.zip`. Right-click it → **Extract All…** → **Extract**.
2. Open the extracted `bible-presentation-app` folder and double-click **Install Bible Presenter** (`Install Bible Presenter.bat`).
   * If Windows shows *“Windows protected your PC”*, click **More info → Run anyway**. Windows shows this for any script downloaded from the internet; it is your own file.
3. A blue window shows the progress. It needs the internet for this one time and takes about 5–10 minutes:
   * if Python 3.10–3.13 is not installed, it downloads Python 3.12 from python.org and installs it for your user (no administrator password);
   * it copies the program to `%LOCALAPPDATA%\Programs\BiblePresenter` and downloads its components (about 200 MB);
   * it creates a **Bible Presenter** icon on the Desktop and in the Start menu.
4. The program starts by itself and installs the KJV, Louis Segond 1910 and WEB Bibles automatically (about 15 seconds). Press Enter to close the blue window.

From then on, just double-click **Bible Presenter** on the Desktop. It works offline. You can delete the zip and the extracted folder.

* **Update** to a newer version: extract the new zip and double-click *Install Bible Presenter* again. Your Bibles and settings are kept.
* **Uninstall**: Start menu → *Bible Presenter* → *Uninstall Bible Presenter*.
* If something goes wrong, the blue window says what happened and stays open — send that message for help. If the program closes unexpectedly later, the details are in `%LOCALAPPDATA%\BiblePresenter\bible-presenter.log`.

Next: connect OBS with [OBS_SETUP.md](OBS_SETUP.md).

---

The rest of this guide is the manual way, for developers or if the easy install does not work.

There are two ways to use the program:

* **Method A – run from the source code.** You install Python once, then start the program with one command. Use this first; it is also how you build the `.exe`.
* **Method B – build a portable `.exe`.** After Method A works, you build a folder with `BiblePresenter.exe` that you can copy to the church computer. That computer does not need Python.

> **How to read the commands.** Grey boxes marked **PowerShell** are commands you type (or paste) into Windows PowerShell and confirm with **Enter**. You never type Python code yourself.

---

## Method A – development setup

### Step 1 – Install Python 3.12

1. Open <https://www.python.org/downloads/windows/>.
2. Under **Python 3.12**, click the latest release (for example *Python 3.12.8*), then download **Windows installer (64-bit)**.
   *Use 3.12. It is fully supported by the program's components (PySide6 6.8 and PyInstaller 6.11).*
3. Run the downloaded file.
4. **On the first screen, tick “Add python.exe to PATH”** (bottom of the window). This lets PowerShell find Python.
5. Click **Install Now**. Accept the Windows permission prompt.
6. When it says *Setup was successful*, click **Close**.

Check it worked: open the Start menu, type **PowerShell**, open **Windows PowerShell**, and run:

**PowerShell**
```powershell
py -3.12 --version
```

You should see `Python 3.12.x`. If you see an error, restart the computer and try again. If it still fails, run the installer again, choose **Modify**, and make sure *py launcher* and *Add Python to environment variables* are ticked.

### Step 2 – Install Visual Studio Code (recommended, optional)

Visual Studio Code is a free editor that makes it easier to look at the files and run commands.

1. Download it from <https://code.visualstudio.com/> and install it with the default options.
2. Start it once. If it suggests installing the **Python** extension, accept.

You can also do everything with plain PowerShell and File Explorer.

### Step 3 – Put the project in a folder

1. Unzip the project (the `bible-presentation-app` folder) somewhere easy, for example `C:\BiblePresenter\bible-presentation-app`.
   The folder must contain `main.py`, `requirements.txt` and the folders `app`, `web`, `data`, `docs`, `scripts`, `tests`.
2. In Visual Studio Code: **File → Open Folder…** and choose the `bible-presentation-app` folder.
   Then open a terminal inside VS Code: **Terminal → New Terminal**. This opens PowerShell already in the project folder.

   *Without VS Code:* open PowerShell and move into the folder:

   **PowerShell**
   ```powershell
   cd C:\BiblePresenter\bible-presentation-app
   ```

### Step 4 – Create the virtual environment

A *virtual environment* is a private folder (`.venv`) that holds the program's packages, so they do not interfere with anything else on the computer.

**PowerShell**
```powershell
py -3.12 -m venv .venv
```

This takes a few seconds and creates a `.venv` folder.

### Step 5 – Activate the virtual environment

**PowerShell**
```powershell
.\.venv\Scripts\Activate.ps1
```

When it works, the prompt starts with `(.venv)`.

If you get a red message saying *running scripts is disabled on this system*, Windows is blocking PowerShell scripts. You have two options:

* **Option 1 (common setting, recommended by Microsoft for developers):** allow scripts that you created on this computer, for your Windows account only:

  **PowerShell**
  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
  ```
  Answer `Y`, then run the `Activate.ps1` command again. This still blocks unsigned scripts downloaded from the internet.
* **Option 2 (no setting change):** skip activation. Wherever this guide says `python`, type `.\.venv\Scripts\python.exe` instead.

### Step 6 – Install the required packages

Needs an internet connection (only this once). It downloads PySide6 (the window toolkit, about 200 MB), pytest and PyInstaller.

**PowerShell**
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Wait until you see `Successfully installed ...`. Yellow *WARNING* lines about pip versions can be ignored; red *ERROR* lines mean something went wrong (usually the internet connection — run the command again).

### Step 7 – Run the program

**PowerShell**
```powershell
python main.py
```

The Bible Presenter window opens. The first time, a **Set up your Bible library** window appears.

*Windows Defender Firewall:* the program only listens on `127.0.0.1` (this computer only), so Windows normally does not ask. If a firewall prompt does appear, you can click **Cancel** / do not allow public networks — OBS on the same computer still works. Do not turn the firewall off.

### Step 8 – Import the Bibles

In the **Set up your Bible library** window:

1. Click **Install bundled Bibles (KJV + LSG, plus WEB)**.
2. Wait about 15 seconds. A message lists each Bible: *King James Version (KJV): 66 books, 1189 chapters, 31,102 verses*, *Louis Segond 1910 (LSG): 66 books, 1189 chapters, 31,102 verses*, and the optional *World English Bible (WEB)*.
3. The status line turns green: *Ready: a complete English and a complete French Bible are installed.*
4. Click **Close**.

KJV is selected for English and LSG for French. You can change this at any time in the **Bible translations** box (top left). To add other Bibles, see [BIBLE_DATA.md](BIBLE_DATA.md).

The library is stored in `%LOCALAPPDATA%\BiblePresenter` (for example `C:\Users\YourName\AppData\Local\BiblePresenter`), not in the project folder, so it is kept when you update or rebuild the program.

### Step 9 – Check the presentation server

In the right-hand panel, scroll to **OBS presentation server**. It starts automatically and shows:

* Status: **● Running (this computer only)**
* OBS URL: `http://127.0.0.1:8765/presentation`

If it shows an error such as *Port 8765 is already in use*, change **Port** to `8766`, click **Start server**, and use that new URL in OBS.

Click **Open in browser** to see the output page in your web browser (it is empty until something is live; in footer mode the page is transparent, so a browser shows it as white or black above the band).

### Step 10 – Connect OBS

Follow [OBS_SETUP.md](OBS_SETUP.md).

### Step 11 – Test the first verse

1. In **Go to reference** (top left), type `John 3:16` (or `Jean 3:16`) and press **Enter**.
2. The centre shows the English and French text and a **PREVIEW** of the slide. OBS does not change yet.
3. Click the red **GO LIVE** button. The verse appears in OBS as a footer band at the bottom of the screen, English and French side by side (and in the *On air* monitor at the top right).
4. Type `Psalm 23` and press Enter. The preview changes, **OBS still shows John 3:16**. Click **GO LIVE** to send Psalm 23.

### Step 12 – Run the automated tests (optional but recommended)

**PowerShell**
```powershell
python -m pytest -v
```

The last line should say `... passed`. The browser rendering tests are skipped unless you also run `python -m playwright install chromium` once.

### Starting the program next time

Open PowerShell in the project folder, then:

**PowerShell**
```powershell
.\.venv\Scripts\python.exe main.py
```

---

## Method B – build the portable Windows program (.exe)

Do Method A first (Steps 1–6). Then, in PowerShell in the project folder:

**PowerShell**
```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean BiblePresenter.spec
```

Or run the build script, which runs the tests, builds, and makes a zip (the `-ExecutionPolicy Bypass` only applies to this one run):

**PowerShell**
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

The build takes a few minutes. The result is:

* `dist\BiblePresenter\BiblePresenter.exe` – double-click to start.
* `dist\BiblePresenter-portable.zip` – (build script only) copy this to the church computer, right-click → **Extract All…**, then run `BiblePresenter.exe` inside the extracted folder.

Keep the whole `BiblePresenter` folder together: the `.exe` needs the `_internal` folder next to it (it contains the web page, the bundled Bibles and Qt). The folder is about 400–500 MB because it includes Chromium (Qt WebEngine) for the slide preview.

### SmartScreen and antivirus warnings

The `.exe` you build is not *code-signed* (signing requires buying a certificate from a certificate authority). Because of that, the first time you run it on a computer, Windows SmartScreen may show **“Windows protected your PC – Microsoft Defender SmartScreen prevented an unrecognized app from starting.”**

* This warning means *Windows does not know who published this file*, not that a virus was found.
* If **you built the file yourself** from this source code (or got it directly from the person who did), click **More info → Run anyway**. Windows remembers the choice for that file.
* If you received the file from somewhere you do not trust, do **not** run it — build it yourself instead.
* Do not disable SmartScreen or your antivirus. If an antivirus quarantines the file (a “false positive” is common for PyInstaller programs), you can submit it to the antivirus vendor for review, or run the program with Method A instead.
* To remove the warning entirely, a church can buy a code-signing certificate and sign `BiblePresenter.exe` with Microsoft's `signtool`; this is optional.

> Note: the build configuration is provided and was checked on Linux (the same PyInstaller recipe produced a working bundle there), but the Windows `.exe` itself has **not** been built or tested by the author of this guide — please run through the [OBS test checklist](OBS_TEST_CHECKLIST.md) after your first Windows build.

---

## Troubleshooting

| Problem | What to do |
|---|---|
| `py` is not recognised | Python is not installed, or *Add to PATH* was not ticked. Re-run the Python installer (Step 1). Then close and reopen PowerShell. |
| `No module named PySide6` | The packages are not installed in the virtual environment. Run Step 6 again, and start the program with `.\.venv\Scripts\python.exe main.py`. |
| The window opens but the preview is blank/white | Update your graphics driver. As a workaround, start with `$env:QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu"; python main.py`. OBS output is not affected. |
| *Port 8765 is already in use* | Another program (or a second copy of Bible Presenter) uses the port. Close the other copy, or pick another port in the Server section and update the OBS URL. |
| *Windows does not allow this program to use port …* | Windows reserves some port ranges. Pick another port, for example `8790`. |
| OBS shows nothing | See the *Recovery* section of [OBS_SETUP.md](OBS_SETUP.md). |
| I want to start over with an empty library and default settings | Close the program and delete the folder `%LOCALAPPDATA%\BiblePresenter`. |
