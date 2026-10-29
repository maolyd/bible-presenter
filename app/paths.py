"""File locations that work both from source and from a PyInstaller build.

* Resource files (web page, bundled Bible files) are read from the program folder
  (or PyInstaller's temporary folder ``sys._MEIPASS``).
* User data (imported Bibles, settings) is written to
  ``%LOCALAPPDATA%\\BiblePresenter`` on Windows, never into the program folder,
  so updating the program does not delete it.
  Set the environment variable ``BIBLE_PRESENTER_HOME`` to use another folder.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "BiblePresenter"


def resource_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    return Path(__file__).resolve().parent.parent


def web_dir() -> Path:
    return resource_dir() / "web"


def bundled_bibles_dir() -> Path:
    return resource_dir() / "data" / "bibles"


def user_data_dir() -> Path:
    override = os.environ.get("BIBLE_PRESENTER_HOME")
    if override:
        path = Path(override)
    elif os.name == "nt":
        path = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / APP_NAME
    else:
        path = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path
