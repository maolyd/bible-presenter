"""Operator window: navigation (left), selection & preview (centre), controls (right)."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
                               QSpinBox, QSplitter, QTextBrowser, QVBoxLayout, QWidget)

from ..bible.passage import Passage
from ..core import AppCore
from ..server.presentation_server import ServerStartError
from .controls_panel import ControlsPanel
from .dialogs import LibraryDialog, TranslationInfoDialog, _esc
from .nav_panel import NavPanel
from .slide_view import SlideView
from .workers import run_with_progress

APP_STYLE = """
QMainWindow, QWidget { font-size: 10pt; }
QGroupBox { font-weight: 600; margin-top: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
QPushButton { padding: 5px 10px; }
QPushButton#goLive { background: #dc2626; color: white; font-size: 15pt; font-weight: 700;
                     padding: 10px 24px; border-radius: 6px; }
QPushButton#goLive:hover { background: #b91c1c; }
QPushButton#goLive:disabled { background: #9ca3af; }
QLabel#previewTag { background: #2563eb; color: white; font-weight: 700; padding: 3px 8px; border-radius: 4px; }
QLabel#liveTag { background: #dc2626; color: white; font-weight: 700; padding: 3px 8px; border-radius: 4px; }
QLabel#liveTag[state="black"] { background: #111; }
QLabel#liveTag[state="clear"] { background: #6b7280; }
"""


class MainWindow(QMainWindow):
    outputChanged = Signal(dict)

    def __init__(self, core: AppCore):
        super().__init__()
        self.core = core
        self.selected: Passage | None = None
        self.preview_page = 0
        self.setWindowTitle("Bible Presenter — English / Français")
        self.setStyleSheet(APP_STYLE)

        self.nav = NavPanel(core)
        self.controls = ControlsPanel(core)
        centre = self._build_centre()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.nav)
        splitter.addWidget(centre)
        splitter.addWidget(self.controls)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([340, 820, 380])
        self.splitter = splitter
        self.setCentralWidget(splitter)
        self.statusBar().showMessage("Ready")

        # Controller notifications may come from a worker thread (imports); the
        # signal hands them to the GUI thread.
        self.outputChanged.connect(self._on_output_changed)
        core.controller.add_listener(self.outputChanged.emit)

        self._connect()
        self._shortcuts()
        self._restore_window()
        self._update_live_display(core.controller.output_payload())
        self._update_selection_display()
        QTimer.singleShot(0, self._startup)

    # ================================================================ layout
    def _build_centre(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(6, 4, 6, 4)

        head = QHBoxLayout()
        tag = QLabel("PREVIEW")
        tag.setObjectName("previewTag")
        tag.setToolTip("The preview is never shown to the audience until you click Go Live.")
        self.sel_label = QLabel()
        self.sel_label.setStyleSheet("font-size:14pt;font-weight:700;")
        head.addWidget(tag)
        head.addWidget(self.sel_label, 1)
        self.live_tag = QLabel("LIVE")
        self.live_tag.setObjectName("liveTag")
        self.live_ref = QLabel()
        self.live_ref.setStyleSheet("font-weight:600;")
        head.addWidget(self.live_tag)
        head.addWidget(self.live_ref)
        layout.addLayout(head)

        rng = QHBoxLayout()
        rng.addWidget(QLabel("Verses:"))
        self.from_spin = QSpinBox()
        self.to_spin = QSpinBox()
        self.from_spin.setPrefix("from ")
        self.to_spin.setPrefix("to ")
        rng.addWidget(self.from_spin)
        rng.addWidget(self.to_spin)
        self.btn_fav = QPushButton("☆ Add to favourites")
        rng.addStretch(1)
        rng.addWidget(self.btn_fav)
        layout.addLayout(rng)

        self.text_view = QTextBrowser()
        self.text_view.setMinimumHeight(120)
        layout.addWidget(self.text_view, 2)

        self.preview_view = SlideView()
        self.preview_view.setMinimumHeight(220)
        frame = QFrame()
        frame.setFrameShape(QFrame.Box)
        frame.setStyleSheet("QFrame { border: 3px solid #2563eb; }")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(2, 2, 2, 2)
        fl.addWidget(self.preview_view)
        layout.addWidget(frame, 3)

        pages = QHBoxLayout()
        self.btn_prev_page = QPushButton("◀ Page")
        self.btn_next_page = QPushButton("Page ▶")
        self.page_label = QLabel()
        pages.addWidget(self.btn_prev_page)
        pages.addWidget(self.page_label)
        pages.addWidget(self.btn_next_page)
        pages.addStretch(1)
        layout.addLayout(pages)

        nav = QHBoxLayout()
        self.btn_prev_ch = QPushButton("⏮ Prev chapter")
        self.btn_prev_v = QPushButton("◀ Prev verse")
        self.btn_next_v = QPushButton("Next verse ▶")
        self.btn_next_ch = QPushButton("Next chapter ⏭")
        self.btn_clear_sel = QPushButton("Clear selection")
        self.btn_go_live = QPushButton("GO LIVE")
        self.btn_go_live.setObjectName("goLive")
        self.btn_go_live.setToolTip("Send the preview to the audience (Ctrl+Enter or F5)")
        for b in (self.btn_prev_ch, self.btn_prev_v, self.btn_next_v, self.btn_next_ch, self.btn_clear_sel):
            nav.addWidget(b)
        nav.addStretch(1)
        nav.addWidget(self.btn_go_live)
        layout.addLayout(nav)
        return w

    def _connect(self):
        self.nav.passageChosen.connect(self.select_passage)
        self.nav.translationsChanged.connect(self._translations_changed)
        self.nav.manageLibraryRequested.connect(lambda: self.open_library(first_run=False))
        self.nav.infoRequested.connect(self.show_translation_info)

        self.from_spin.valueChanged.connect(self._range_changed)
        self.to_spin.valueChanged.connect(self._range_changed)
        self.btn_fav.clicked.connect(self.toggle_favourite)
        self.btn_prev_v.clicked.connect(lambda: self._step(self.core.service.prev_verse))
        self.btn_next_v.clicked.connect(lambda: self._step(self.core.service.next_verse))
        self.btn_prev_ch.clicked.connect(lambda: self._step(self.core.service.prev_chapter))
        self.btn_next_ch.clicked.connect(lambda: self._step(self.core.service.next_chapter))
        self.btn_clear_sel.clicked.connect(lambda: self.select_passage(None))
        self.btn_go_live.clicked.connect(self.go_live)
        self.btn_prev_page.clicked.connect(lambda: self._change_preview_page(-1))
        self.btn_next_page.clicked.connect(lambda: self._change_preview_page(1))

        c = self.controls
        c.prevLive.connect(self.prev_live)
        c.nextLive.connect(self.next_live)
        c.blackToggled.connect(self.core.controller.set_black)
        c.restoreLive.connect(self.restore_live)
        c.clearLive.connect(self.core.controller.clear)
        c.startServer.connect(self.start_server)
        c.stopServer.connect(self.stop_server)
        c.reconnectOutput.connect(self.reconnect_output)
        c.openInBrowser.connect(lambda: QDesktopServices.openUrl(QUrl(self.core.server.url)))

    def _shortcuts(self):
        def sc(keys, fn):
            for k in keys:
                QShortcut(QKeySequence(k), self, activated=fn)
        sc(["Ctrl+Return", "Ctrl+Enter", "F5"], self.go_live)
        sc(["Ctrl+B"], lambda: self.core.controller.set_black(not self.core.controller.is_black))
        sc(["Ctrl+R"], self.restore_live)
        sc(["Ctrl+Right"], self.next_live)
        sc(["Ctrl+Left"], self.prev_live)
        sc(["Alt+Right"], lambda: self._step(self.core.service.next_verse))
        sc(["Alt+Left"], lambda: self._step(self.core.service.prev_verse))
        sc(["Ctrl+L"], lambda: (self.nav.ref_edit.setFocus(), self.nav.ref_edit.selectAll()))
        sc(["Ctrl+F"], lambda: (self.nav.tabs.setCurrentIndex(1), self.nav.search_edit.setFocus()))

    # ================================================================ startup / shutdown
    def _startup(self):
        if self.core.settings.get("auto_start_server", True):
            self.start_server(self.core.server.port, quiet=True)
        else:
            self.controls.set_server_status(False)
        st = self.core.library_status()
        if st["count"] == 0 and self.core.bundled_catalog():
            self.install_bundled_bibles()          # first start: no clicks needed
        elif not (st["en_complete"] and st["fr_complete"]):
            self.open_library(first_run=True)
        last = self.core.settings.get("last_selection")
        if last and self.core.tids():
            try:
                self.select_passage(Passage.from_dict(last), remember=False)
            except (KeyError, ValueError, TypeError):
                pass

    def _restore_window(self):
        geo = self.core.settings.get("window_geometry")
        if geo:
            self.restoreGeometry(QByteArray.fromBase64(geo.encode()))
        else:
            self.resize(1500, 900)
        split = self.core.settings.get("splitter_state")
        if split:
            self.splitter.restoreState(QByteArray.fromBase64(split.encode()))

    def closeEvent(self, event):
        self.core.settings.set("window_geometry", bytes(self.saveGeometry().toBase64()).decode())
        self.core.settings.set("splitter_state", bytes(self.splitter.saveState().toBase64()).decode())
        self.core.close()
        super().closeEvent(event)

    # ================================================================ selection & preview
    def tids(self):
        return self.core.tids()

    def select_passage(self, passage: Passage | None, remember: bool = True):
        self.selected = passage
        self.preview_page = 0
        self.nav.show_passage(passage)
        if passage is not None:
            self.core.settings.set("last_selection", passage.to_dict())
            if remember:
                self.core.settings.add_recent(passage.to_dict(), f"{passage.reference('en')}  ·  {passage.reference('fr')}")
                self.nav.refresh_recent()
        self._update_selection_display()

    def _update_selection_display(self):
        p = self.selected
        has = p is not None and bool(self.tids())
        for b in (self.btn_go_live, self.btn_prev_v, self.btn_next_v, self.btn_prev_ch, self.btn_next_ch,
                  self.btn_clear_sel, self.btn_fav, self.from_spin, self.to_spin):
            b.setEnabled(has)
        if not has:
            self.sel_label.setText("No passage selected" if self.tids() else "No Bible selected — open the Bible library")
            self.text_view.setHtml("<p style='color:#666'>Choose a book, chapter and verse on the left, type a "
                                   "reference such as <b>John 3:16</b> or <b>Jean 3:16</b>, or search for words.</p>")
            self.preview_view.render(self.core.controller.preview_payload(None))
            self.page_label.setText("")
            self.btn_prev_page.setEnabled(False)
            self.btn_next_page.setEnabled(False)
            return
        self.sel_label.setText(f"{p.reference('en')}  ·  {p.reference('fr')}")
        self._sync_range_spins(p)
        self.btn_fav.setText("★ Remove favourite" if self.core.settings.is_favourite(p.to_dict())
                             else "☆ Add to favourites")
        self._render_text(p)
        self._render_preview()

    def _sync_range_spins(self, p: Passage):
        verses = self.core.service.verses(p.book, p.start_chapter, self.tids())
        for spin in (self.from_spin, self.to_spin):
            spin.blockSignals(True)
            spin.setRange(verses[0] if verses else 1, verses[-1] if verses else 1)
        self.from_spin.setValue(p.start_verse)
        self.to_spin.setValue(p.end_verse if p.end_chapter == p.start_chapter else verses[-1])
        # Cross-chapter selections are edited by typing a reference; the spins cover one chapter.
        multi = p.end_chapter != p.start_chapter
        self.to_spin.setEnabled(not multi)
        for spin in (self.from_spin, self.to_spin):
            spin.blockSignals(False)

    def _range_changed(self):
        p = self.selected
        if p is None:
            return
        a, b = self.from_spin.value(), self.to_spin.value()
        if self.sender() is self.from_spin and a > b:
            b = a
        if self.sender() is self.to_spin and b < a:
            a = b
        end_ch = p.end_chapter if p.end_chapter != p.start_chapter else p.start_chapter
        end_v = b if end_ch == p.start_chapter else p.end_verse
        self.select_passage(Passage(p.book, p.start_chapter, a, end_ch, end_v), remember=False)

    def _render_text(self, p: Passage):
        en, fr = self.core.english, self.core.french
        rows = self.core.service.aligned(p, self.tids())
        multi = p.start_chapter != p.end_chapter
        head = "<tr><th></th>" + "".join(f"<th align='left'>{_esc(t.code)}</th>" for t in (en, fr) if t) + "</tr>"
        body = []
        for av in rows:
            num = f"{av.chapter}:{av.verse}" if multi else str(av.verse)
            cells = []
            for t in (en, fr):
                if not t:
                    continue
                txt = av.texts.get(t.id)
                cells.append(f"<td valign='top' width='50%'>{_esc(txt)}</td>" if txt is not None else
                             "<td valign='top' style='color:#b45309'><i>⚠ This verse is not in "
                             f"{_esc(t.code)} (numbering or source text differs)</i></td>")
            body.append(f"<tr><td valign='top' nowrap style='color:#888'><b>{num}</b></td>{''.join(cells)}</tr>")
        self.text_view.setHtml(f"<table cellspacing='6' width='100%'>{head}{''.join(body)}</table>")

    def _render_preview(self):
        payload = self.core.controller.preview_payload(self.selected, self.preview_page)
        slide = payload.get("slide")
        pages = slide["pages"] if slide else 0
        self.preview_page = (slide["page"] - 1) if slide else 0
        self.page_label.setText(f"Preview page {slide['page']} of {pages}" if pages > 1 else "")
        self.btn_prev_page.setEnabled(pages > 1 and self.preview_page > 0)
        self.btn_next_page.setEnabled(pages > 1 and self.preview_page < pages - 1)
        self.btn_prev_page.setVisible(pages > 1)
        self.btn_next_page.setVisible(pages > 1)
        self.preview_view.render(payload)

    def _change_preview_page(self, delta: int):
        self.preview_page += delta
        self._render_preview()

    def _step(self, fn):
        if self.selected is None:
            return
        target = fn(self.selected, self.tids())
        if target is None:
            self.statusBar().showMessage("Reached the beginning or end of the Bible.", 4000)
            return
        self.select_passage(target)

    def toggle_favourite(self):
        p = self.selected
        if not p:
            return
        if self.core.settings.is_favourite(p.to_dict()):
            self.core.settings.remove_favourite(p.to_dict())
        else:
            self.core.settings.add_favourite(p.to_dict(), f"{p.reference('en')}  ·  {p.reference('fr')}")
        self.nav.refresh_favourites()
        self._update_selection_display()

    def _translations_changed(self):
        if self.selected:
            try:
                self.selected = self.core.service.resolve(
                    _passage_ref(self.selected), self.tids()) if self.tids() else None
            except ValueError:
                self.selected = None
        self._update_selection_display()

    # ================================================================ live
    def go_live(self):
        if self.selected is None:
            return
        try:
            self.core.controller.go_live(self.selected, self.preview_page)
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot go live", str(exc))
            return
        self.statusBar().showMessage(f"LIVE: {self.selected.reference('en')}", 4000)

    def next_live(self):
        if not self.core.controller.next_live():
            self.statusBar().showMessage("Nothing further to show.", 3000)

    def prev_live(self):
        if not self.core.controller.prev_live():
            self.statusBar().showMessage("Nothing before this.", 3000)

    def restore_live(self):
        if not self.core.controller.restore():
            self.statusBar().showMessage("There is no previous live slide to restore.", 3000)

    def _on_output_changed(self, payload: dict):
        self._update_live_display(payload)
        # Appearance changes affect the preview too.
        if self.selected is not None:
            self._render_preview()

    def _update_live_display(self, payload: dict):
        mode = payload.get("mode")
        live = self.core.controller.live_passage or (self.core.controller.state.last_live.passage
                                                     if self.core.controller.state.last_live else None)
        slide = payload.get("slide")
        if mode == "live" and slide:
            ref = slide["reference"]["en"]
            page = f" (page {slide['page']}/{slide['pages']})" if slide["pages"] > 1 else ""
            self.live_tag.setText("● LIVE")
            self.live_tag.setProperty("state", "live")
            self.live_ref.setText(ref + page)
            self.controls.live_label.setText(f"<span style='color:#dc2626'>● LIVE:</span> {ref}{page}")
        elif mode == "black":
            self.live_tag.setText("■ BLACK")
            self.live_tag.setProperty("state", "black")
            self.live_ref.setText(f"(hidden: {live.reference('en')})" if live else "")
            self.controls.live_label.setText("■ <b>Black screen</b> — the audience sees nothing. "
                                             "Click Restore (Ctrl+R) to show the verse again.")
        else:
            self.live_tag.setText("NOTHING LIVE")
            self.live_tag.setProperty("state", "clear")
            self.live_ref.setText("")
            self.controls.live_label.setText("Nothing is live. Select a passage and click GO LIVE.")
        self.live_tag.style().unpolish(self.live_tag)
        self.live_tag.style().polish(self.live_tag)
        self.controls.set_black_checked(mode == "black")

    # ================================================================ server & output
    def start_server(self, port: int, quiet: bool = False):
        try:
            url = self.core.start_server(int(port))
        except ServerStartError as exc:
            self.controls.set_server_status(False, error=str(exc))
            QMessageBox.warning(self, "Presentation server did not start",
                                f"{exc}\n\nThe rest of the program still works; OBS cannot show verses until "
                                "the server is running.")
            return
        self.controls.set_server_status(True, url)
        if not quiet:
            self.statusBar().showMessage(f"Server running at {url}", 5000)

    def stop_server(self):
        self.core.stop_server()
        self.controls.set_server_status(False)

    def reconnect_output(self):
        self.core.broadcaster.request_reload()
        self.statusBar().showMessage("Asked the output page(s) to reload.", 4000)

    # ================================================================ library
    def open_library(self, first_run: bool = False):
        dlg = LibraryDialog(self.core, self, first_run=first_run)
        dlg.exec()
        if dlg.changed:
            self.nav.reload_translations()
            self._translations_changed()
        st = self.core.library_status()
        if not (st["en_complete"] and st["fr_complete"]):
            missing = " and ".join(x for x, ok in (("English", st["en_complete"]), ("French", st["fr_complete"]))
                                   if not ok)
            self.statusBar().showMessage(f"Setup needed: no complete {missing} Bible yet — "
                                         "open “Bible library…” on the left.")

    def install_bundled_bibles(self):
        """Install the Bibles that come with the program (KJV, LSG) in the background."""
        entries = self.core.bundled_catalog()

        def done(trs):
            self.nav.reload_translations()
            self._translations_changed()
            names = ", ".join(t.code for t in trs)
            self.statusBar().showMessage(f"Bibles installed: {names}. Type a reference such as John 3:16 to begin.",
                                         15000)

        def failed(exc):
            QMessageBox.warning(self, "Bibles not installed",
                                f"The bundled Bibles could not be installed automatically:\n{exc}")
            self.open_library(first_run=True)

        run_with_progress(self, "First start: installing the King James Version and Louis Segond 1910… "
                                "(about 10 seconds)",
                          lambda: [self.core.import_bundled(e) for e in entries], done, failed)

    def show_translation_info(self):
        TranslationInfoDialog(self.core, self.tids(), self).exec()


def _passage_ref(p: Passage) -> str:
    """Rebuild a reference string so it can be re-validated against new translations."""
    return p.reference("en").replace("–", "-")
