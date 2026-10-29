"""Run slow work (reading or importing a Bible) without freezing the window."""
from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import QProgressDialog


class _Worker(QObject):
    finished = Signal(object)
    failed = Signal(object)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    @Slot()
    def run(self):
        try:
            self.finished.emit(self.fn())
        except Exception as exc:          # reported to the user by the caller
            traceback.print_exc()
            self.failed.emit(exc)


class _Job(QObject):
    """Lives in the GUI thread, so the callbacks run safely in the GUI thread."""

    def __init__(self, parent, message, fn, on_done, on_error):
        super().__init__(parent)
        self.on_done, self.on_error = on_done, on_error
        self.dialog = QProgressDialog(message, None, 0, 0, parent)
        self.dialog.setWindowTitle("Please wait")
        self.dialog.setWindowModality(Qt.WindowModal)
        self.dialog.setMinimumDuration(0)
        self.dialog.setCancelButton(None)
        self.thread = QThread(self)
        self.worker = _Worker(fn)
        self.worker.moveToThread(self.thread)
        self.worker.finished.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.thread.started.connect(self.worker.run)

    def start(self):
        self.dialog.show()
        self.thread.start()

    def _finish(self):
        self.dialog.close()
        self.thread.quit()
        self.thread.wait()
        self.worker.deleteLater()
        self.deleteLater()

    @Slot(object)
    def _done(self, result):
        self._finish()
        self.on_done(result)

    @Slot(object)
    def _failed(self, exc):
        self._finish()
        self.on_error(exc)


def run_with_progress(parent, message: str, fn, on_done, on_error) -> None:
    """Run ``fn()`` in a background thread while showing a busy dialog."""
    _Job(parent, message, fn, on_done, on_error).start()
