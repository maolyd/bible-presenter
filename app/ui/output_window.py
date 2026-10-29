"""Optional fullscreen output on a projector / second screen.

It loads the same URL as OBS, so it shows exactly the same live slide.
Press Esc (or double-click) to close it.
"""
from __future__ import annotations

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .slide_view import HAVE_WEBENGINE

if HAVE_WEBENGINE:
    from PySide6.QtWebEngineWidgets import QWebEngineView


class OutputWindow(QWidget):
    def __init__(self, url: str):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
        self.setWindowTitle("Bible Output")
        self.setStyleSheet("background:#000;")
        self.setCursor(Qt.BlankCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if HAVE_WEBENGINE:
            self.view = QWebEngineView()
            self.view.setContextMenuPolicy(Qt.NoContextMenu)
            self.view.page().setBackgroundColor(Qt.black)
            self.view.setUrl(QUrl(url))
            layout.addWidget(self.view)
        else:
            msg = QLabel("Fullscreen output needs Qt WebEngine. Use OBS or open the URL in a web browser:\n" + url)
            msg.setStyleSheet("color:#fff;font-size:20px;")
            msg.setAlignment(Qt.AlignCenter)
            layout.addWidget(msg)

    def show_on_screen(self, index: int):
        screens = QGuiApplication.screens()
        screen = screens[index] if 0 <= index < len(screens) else QGuiApplication.primaryScreen()
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        self.showFullScreen()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.close()
