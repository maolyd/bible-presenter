# Bible Presenter — English / Français

A Windows desktop program for showing Bible verses in **English and French on the same slide** during services, presentations and livestreams, with **OBS Studio Browser Source** output.

* **Operator window** – search, browse and preview passages. Nothing reaches the audience until you click **GO LIVE**.
* **Presentation output** – by default a **footer (lower-third) band** at the bottom of the screen showing **one verse at a time**, English and French side by side, with the rest of the screen transparent so the camera shows through in OBS. A **full-screen** display is one click away for projectors. It is a clean 16:9 webpage (`http://127.0.0.1:8765/presentation`) with only the verses and the reference, captured by OBS. It can also be shown fullscreen on a projector.
* Works **offline**. Comes with complete public-domain Bibles: **King James Version** (English, default), **Louis Segond 1910** (French).

## Start here

| I want to… | Read |
|---|---|
| **Install on Windows: download `BiblePresenter-Setup-1.0.0.exe` from [Releases](https://github.com/maolyd/bible-presenter/releases/latest)** (or double-click `Install Bible Presenter.bat` from the zip) | [docs/INSTALL_WINDOWS.md](docs/INSTALL_WINDOWS.md) |
| Install manually, run from source, build the `.exe` | [docs/INSTALL_WINDOWS.md](docs/INSTALL_WINDOWS.md) |
| Connect OBS Studio | [docs/OBS_SETUP.md](docs/OBS_SETUP.md) |
| Add or understand Bible translations and licences | [docs/BIBLE_DATA.md](docs/BIBLE_DATA.md), [LICENSES.md](LICENSES.md) |
| Check everything before a service | [docs/OBS_TEST_CHECKLIST.md](docs/OBS_TEST_CHECKLIST.md) |
| See the automated test results | [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md) |

Quick start (PowerShell, in this folder, after installing Python 3.12):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe main.py
```

### On a Mac

The app also runs on macOS (Python 3.10–3.13). Set it up once in Terminal, in this folder:

```bash
python3.10 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Then double-click **Start Bible Presenter.command** in Finder to start it. The first time, macOS may say it cannot check the file: right-click it → **Open** → **Open**. To put it on the Desktop or Dock, make an alias (right-click → *Make Alias*) and leave the original in this folder. Shortcuts use **Cmd** instead of Ctrl. A Windows `.exe` can only be built on Windows.

## Using it

1. Type a reference — `John 3:16`, `Jean 3.16-18`, `1re Jean 1:9`, `Psaume 23`, `Rom 8:28-39` — and press Enter, or browse *Book → Chapter → Verse* (Shift+click for a range), or search words (`"exact phrase"` works; accents are ignored).
2. Check the **PREVIEW** (blue frame). The *On air* monitor (top right) shows what OBS currently shows.
3. Click **GO LIVE** (Ctrl+Enter / F5). With *one verse at a time*, a selection such as John 3:16-18 goes live verse by verse: press **Next live verse ▶** (Ctrl+Right) to move to 3:17, 3:18, then on to the following verse. The reference shows `(1/3)` while you step through a selection.

Keyboard shortcuts:

| Keys | Action |
|---|---|
| Ctrl+Enter or F5 | Go live with the preview |
| Ctrl+Right / Ctrl+Left | Next / previous live verse (or page) |
| Alt+Right / Alt+Left | Next / previous verse in the preview |
| Ctrl+B | Black screen on/off |
| Ctrl+R | Restore the last live slide |
| Ctrl+L | Jump to the reference box |
| Ctrl+F | Jump to search |

Presentation options (right panel, saved automatically): display as footer (lower third, with adjustable height and background opacity) or full screen, side-by-side or stacked layout, English-first or French-first, verses per slide (one verse at a time — the default; 2–5 verses; or the whole selection with automatic page split), reference on top or bottom, show/hide reference, labels, verse numbers, English or French text, colours, font, independent English/French/reference sizes, line spacing, alignment, space between languages, transparent background for overlays.

Long passages are shrunk to fit and, if they would become too small, split into pages (`(1/3)` is shown after the reference). The output never scrolls or cuts text off.

## How it works

```
main.py                      starts the Qt application
app/
  core.py                    wires everything together (no UI) – used by the tests too
  paths.py                   program files vs. user data (%LOCALAPPDATA%\BiblePresenter)
  bible/books.py             the 66 books, English & French names and abbreviations
  bible/reference.py         parses "John 3:16-18", "Jean 3,16", "1re Jean 1.9"...
  bible/importers.py         USFX, OSIS, Zefania, Beblia XML, eBible VPL, .zip
  bible/repository.py        SQLite Bible library + accent-insensitive full-text search
  bible/passage.py           passages, navigation, English/French verse alignment
  presentation/slide.py      slide contents, pagination, style defaults/validation
  presentation/controller.py preview / live / black screen / restore state machine
  server/presentation_server.py  local read-only web server (127.0.0.1) + live updates (Server-Sent Events)
  storage/settings_store.py  preferences, favourites, recent passages (SQLite)
  ui/                        operator window (PySide6): navigation, preview, controls, dialogs
web/                         the output page OBS shows (HTML / CSS / JavaScript)
data/bibles/                 bundled public-domain Bible files + catalog.json
data/sample/                 tiny labelled sample files (not complete Bibles)
tests/                       automated tests (pytest)
scripts/                     PowerShell helpers: setup, run, tests, Windows build
BiblePresenter.spec          PyInstaller build recipe
```

Technology: Python 3.12, PySide6 6.8 (Qt Widgets + Qt WebEngine for an exact slide preview), SQLite, HTML/CSS/JS, PyInstaller.
The live link uses **Server-Sent Events** instead of WebSockets: the output only needs to *receive* updates, SSE reconnects automatically in OBS's browser, and it needs no extra Python package. The server is **read-only** — it has no control endpoint at all; only the operator window, running in the same process, can change what is shown. It binds to `127.0.0.1` only and rejects requests whose `Host` header is not this computer.

## Data and privacy

Your library and settings are stored in `%LOCALAPPDATA%\BiblePresenter` (`bibles.sqlite`, `settings.sqlite`). No account, password, personal data or internet connection is used. Database schemas are versioned so future updates keep your data.
