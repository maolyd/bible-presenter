"""A 16:9 widget that renders a slide with the very same HTML/CSS/JS as the OBS output."""
from __future__ import annotations

import json

from PySide6.QtCore import QUrl, Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .. import paths

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAVE_WEBENGINE = True
except ImportError:          # pragma: no cover - depends on the PySide6 installation
    HAVE_WEBENGINE = False


class AspectBox(QWidget):
    """Keeps its single child at 16:9, centred."""

    def __init__(self, child: QWidget, parent=None):
        super().__init__(parent)
        self.child = child
        child.setParent(self)
        self.setMinimumSize(160, 90)

    def resizeEvent(self, event):
        w, h = self.width(), self.height()
        cw = min(w, int(h * 16 / 9))
        ch = int(cw * 9 / 16)
        self.child.setGeometry((w - cw) // 2, (h - ch) // 2, cw, ch)
        super().resizeEvent(event)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return int(w * 9 / 16)


class SlideView(QWidget):
    """Shows a presentation state dict (same format the server sends to OBS)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pending: dict | None = None
        self._loaded = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if HAVE_WEBENGINE:
            self.view = QWebEngineView()
            self.view.setContextMenuPolicy(Qt.NoContextMenu)
            self.view.page().setBackgroundColor(Qt.black)
            self.view.loadFinished.connect(self._on_loaded)
            url = QUrl.fromLocalFile(str(paths.web_dir() / "presentation.html"))
            url.setQuery("preview=1")
            self.view.setUrl(url)
            inner = self.view
        else:
            self.view = None
            self.fallback = QLabel()
            self.fallback.setWordWrap(True)
            self.fallback.setAlignment(Qt.AlignCenter)
            self.fallback.setStyleSheet("background:#0b1530;color:#fff8ec;padding:8px;")
            inner = self.fallback
        layout.addWidget(AspectBox(inner))

    def _on_loaded(self, ok: bool):
        self._loaded = ok
        if ok and self._pending is not None:
            self.render(self._pending)

    def render(self, state: dict) -> None:
        self._pending = state
        if self.view is None:
            self._render_fallback(state)
            return
        if not self._loaded:
            return
        js = "window.BiblePresenter && window.BiblePresenter.render(%s);" % json.dumps(state)
        self.view.page().runJavaScript(js)

    def _render_fallback(self, state: dict) -> None:
        slide = state.get("slide")
        if state.get("mode") == "black":
            self.fallback.setText("■ BLACK SCREEN")
        elif not slide:
            self.fallback.setText("")
        else:
            parts = []
            for col in slide["columns"]:
                parts.append(" ".join(f"{v['num']} {v['text']}" for v in col["verses"]))
            parts.append(slide["reference"]["en"])
            self.fallback.setText("\n\n".join(parts))
