"""Start-up behaviour: logging without a console and installing the bundled Bibles on first start."""
import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import FIXTURES, ROOT


def test_no_console_does_not_crash(tmp_path):
    """pythonw.exe / the packaged .exe have no console (sys.stderr is None): errors go to a log file."""
    code = (
        "import sys; sys.path.insert(0, %r); sys.stdout = None; sys.stderr = None\n"
        "import main, traceback\n"
        "main._log_to_file_without_console()\n"
        "try:\n    raise RuntimeError('boom')\nexcept RuntimeError:\n    traceback.print_exc()\n"
        "print('still running')\n" % str(ROOT))
    env = dict(os.environ, BIBLE_PRESENTER_HOME=str(tmp_path))
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    log = (tmp_path / "bible-presenter.log").read_text(encoding="utf-8")
    assert "RuntimeError: boom" in log and "still running" in log


def test_icon_files_exist():
    assert (ROOT / "app" / "resources" / "bible-presenter.ico").stat().st_size > 1000
    assert (ROOT / "app" / "resources" / "bible-presenter.png").stat().st_size > 1000


def test_first_start_installs_bundled_bibles_without_asking(tmp_path, monkeypatch):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication.instance() or QApplication([])

    bundled = tmp_path / "bundled"
    bundled.mkdir()
    shutil.copy(FIXTURES / "mini_en.usfx.xml", bundled)
    shutil.copy(FIXTURES / "mini_fr.beblia.xml", bundled)
    (bundled / "catalog.json").write_text(json.dumps({"bibles": [
        {"file": "mini_en.usfx.xml", "code": "TEN", "name": "Test English", "language": "en", "default": True},
        {"file": "mini_fr.beblia.xml", "code": "TFR", "name": "Test French", "language": "fr", "default": True},
    ]}), encoding="utf-8")

    from app.core import AppCore
    from app.ui import main_window
    core = AppCore(data_dir=tmp_path / "data", web_root=ROOT / "web", bundled_dir=bundled)
    opened = []
    monkeypatch.setattr(main_window.MainWindow, "open_library", lambda self, first_run=False: opened.append(1))
    monkeypatch.setattr(main_window.MainWindow, "start_server", lambda self, port, quiet=False: None)
    w = main_window.MainWindow(core)
    import time
    end = time.time() + 15
    while time.time() < end and core.library_status()["count"] < 2:
        app.processEvents()
        time.sleep(0.02)
    for _ in range(20):
        app.processEvents()
        time.sleep(0.01)
    assert core.library_status()["count"] == 2
    assert (core.english.code, core.french.code) == ("TEN", "TFR")
    assert opened == []                                   # no setup window was needed
    assert "Bibles installed" in w.statusBar().currentMessage()
    w.close()
    core.close()
