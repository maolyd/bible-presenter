"""Bible Presenter — bilingual (English / French) Bible display for church services and OBS.

Run from the project folder:   python main.py
"""
from __future__ import annotations

import os
import sys
import traceback


def _log_to_file_without_console() -> None:
    """Started from an icon (pythonw.exe or the packaged .exe) there is no console:
    sys.stderr is None and any error report would crash the program. Write to a log file instead."""
    if sys.stderr is not None and sys.stdout is not None:
        return
    from app.paths import user_data_dir
    log = open(user_data_dir() / "bible-presenter.log", "w", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or log
    sys.stderr = sys.stderr or log


def main() -> int:
    # Make "app" importable when launched from another folder or from a packaged exe.
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    _log_to_file_without_console()

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    # Required by Qt WebEngine (used for the slide preview) before the app is created.
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName("Bible Presenter")
    app.setOrganizationName("BiblePresenter")
    app.setStyle("Fusion")
    icon = os.path.join(here, "app", "resources", "bible-presenter.png")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))

    from app.core import AppCore
    from app.ui.main_window import MainWindow

    try:
        core = AppCore()
    except Exception as exc:  # e.g. the data folder cannot be created
        traceback.print_exc()
        QMessageBox.critical(None, "Bible Presenter could not start", str(exc))
        return 1

    window = MainWindow(core)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
