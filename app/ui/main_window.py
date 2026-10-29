"""Operator window: one search bar, the passage (English | French), the next-verse preview,
GO LIVE and the live controls. Appearance, output and server settings live in the Settings
window; book/chapter/verse pickers in the Browse window."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton,
                               QStackedWidget, QTextBrowser, QToolButton, QVBoxLayout, QWidget)

from ..bible.passage import Passage
from ..bible.reference import ReferenceParseError
from ..core import AppCore
from ..server.presentation_server import ServerStartError
from .controls_panel import ControlsPanel
from .dialogs import LibraryDialog, TranslationInfoDialog, _esc
from .nav_panel import NavPanel
from .output_window import OutputWindow
from .slide_view import SlideView
from .workers import run_with_progress

# Used inside single-quoted HTML style attributes: Qt's rich text takes the family name unquoted
# (quotes of either kind there, or &quot;, make it drop the whole style).
SERIF = "EB Garamond, Garamond, Georgia, serif"

APP_STYLE = """
QMainWindow, QWidget#root { background: #fafafa; }
QWidget { font-family: Inter, 'Segoe UI', system-ui, sans-serif; font-size: 10pt; color: #18181b; }
QFrame#header { background: #ffffff; border-bottom: 1px solid #e4e4e7; }
QLabel#appTitle { font-size: 12pt; font-weight: 700; }
QLineEdit#search { min-height: 44px; padding: 0 14px; border: 1px solid #d4d4d8; border-radius: 12px;
                   background: #ffffff; font-size: 12pt; }
QLineEdit#search:focus { border: 1px solid #2563eb; }
QPushButton, QToolButton { min-height: 40px; padding: 0 14px; border: 1px solid #d4d4d8; border-radius: 10px;
                           background: #ffffff; font-weight: 600; }
QPushButton:hover, QToolButton:hover { background: #f4f4f5; }
QPushButton:disabled { color: #a1a1aa; border-color: #e4e4e7; }
QToolButton::menu-indicator { image: none; width: 0; }
QPushButton#chip { min-height: 32px; padding: 0 12px; border-radius: 16px; border-color: #e4e4e7;
                   font-weight: 500; color: #3f3f46; }
QPushButton#goLive { min-height: 56px; border: 0; border-radius: 12px; background: #dc2626; color: #ffffff;
                     font-size: 13pt; font-weight: 700; letter-spacing: 1px; }
QPushButton#goLive:hover { background: #b91c1c; }
QPushButton#goLive:disabled { background: #e4e4e7; color: #71717a; }
QPushButton#hide:checked { background: #18181b; border-color: #18181b; color: #ffffff; }
QFrame#card { background: #ffffff; border: 1px solid #e4e4e7; border-radius: 14px; }
QFrame#obs { border: 1px dashed #d4d4d8; border-radius: 12px; }
QFrame#preview { border: 2px solid #2563eb; border-radius: 12px; background: #27272a; }
QTextBrowser#passage, QListWidget#results { background: #ffffff; border: 1px solid #e4e4e7; border-radius: 14px; }
QListWidget#results::item { padding: 10px 8px; border-bottom: 1px solid #f4f4f5; }
QListWidget#results::item:selected { background: #eff6ff; color: #18181b; }
QLabel[class="caps"] { font-size: 8pt; font-weight: 700; letter-spacing: 1px; }
"""


class SettingsDialog(QDialog):
    """Appearance, live output, fullscreen and OBS server settings (the former right-hand panel)."""

    def __init__(self, core: AppCore, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(560, 780)
        layout = QVBoxLayout(self)
        self.controls = ControlsPanel(core)
        layout.addWidget(self.controls, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.hide)
        layout.addWidget(buttons)


class BrowseDialog(QDialog):
    """Book → chapter → verse pickers. Choosing verses updates the main window immediately."""

    def __init__(self, core: AppCore, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Browse the Bible")
        self.resize(420, 720)
        layout = QVBoxLayout(self)
        self.nav = NavPanel(core)
        for i in (0, 1):                       # translations and reference boxes live in the main window
            self.nav.layout().itemAt(i).widget().hide()
        for i in range(1, self.nav.tabs.count()):
            self.nav.tabs.setTabVisible(i, False)
        layout.addWidget(self.nav, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.hide)
        layout.addWidget(buttons)


def _caps(text: str, color: str = "#52525b") -> QLabel:
    label = QLabel(text.upper())
    label.setProperty("class", "caps")
    label.setStyleSheet(f"color: {color};")
    return label


class MainWindow(QMainWindow):
    outputChanged = Signal(dict)

    def __init__(self, core: AppCore):
        super().__init__()
        self.core = core
        self.selected: Passage | None = None
        self.preview_page = 0
        self.output_window: OutputWindow | None = None
        self.setWindowTitle("Bible Presenter — English / Français")
        self.setStyleSheet(APP_STYLE)
        self.setMinimumSize(1080, 680)

        self.settings_dialog = SettingsDialog(core, self)
        self.controls = self.settings_dialog.controls
        self.browse_dialog = BrowseDialog(core, self)
        self.nav = self.browse_dialog.nav

        root = QWidget()
        root.setObjectName("root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_header())
        body = QHBoxLayout()
        body.setContentsMargins(28, 24, 28, 20)
        body.setSpacing(28)
        body.addWidget(self._build_passage_area(), 1)
        body.addWidget(self._build_side())
        outer.addLayout(body, 1)
        self.setCentralWidget(root)
        self.statusBar().setStyleSheet("color: #52525b;")

        # Controller notifications may come from a worker thread (imports); the
        # signal hands them to the GUI thread.
        self.outputChanged.connect(self._on_output_changed)
        core.controller.add_listener(self.outputChanged.emit)

        self._connect()
        self._shortcuts()
        self._restore_window()
        self._refresh_translation_buttons()
        self._refresh_chips()
        self._update_live_display(core.controller.output_payload())
        self._update_selection_display()
        QTimer.singleShot(0, self._startup)

    # ================================================================ layout
    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("header")
        row = QHBoxLayout(header)
        row.setContentsMargins(28, 14, 28, 14)
        row.setSpacing(12)
        title = QLabel("Bible Presenter")
        title.setObjectName("appTitle")
        row.addWidget(title)
        row.addSpacing(8)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Reference or words — John 3:16-18 · Jean 3,16 · “so loved”")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Reference or words")
        row.addWidget(self.search, 1)
        self.btn_browse = QPushButton("Browse")
        self.btn_browse.setToolTip("Pick a book, chapter and verses")
        row.addWidget(self.btn_browse)
        self.btn_en = QToolButton()
        self.btn_fr = QToolButton()
        for b, lang in ((self.btn_en, "en"), (self.btn_fr, "fr")):
            b.setPopupMode(QToolButton.InstantPopup)
            b.setToolTip("English translation" if lang == "en" else "French translation")
            row.addWidget(b)
        self.btn_settings = QPushButton("Settings")
        self.btn_settings.setToolTip("Appearance, output and OBS server")
        row.addWidget(self.btn_settings)
        return header

    def _build_passage_area(self) -> QWidget:
        w = QWidget()
        col = QVBoxLayout(w)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(14)

        title_row = QHBoxLayout()
        self.sel_label = QLabel()
        self.sel_label.setTextFormat(Qt.RichText)
        self.sel_label.setWordWrap(True)
        title_row.addWidget(self.sel_label, 1)
        self.btn_prev_ch = QPushButton("‹")
        self.btn_next_ch = QPushButton("›")
        for b, tip in ((self.btn_prev_ch, "Previous chapter"), (self.btn_next_ch, "Next chapter")):
            b.setFixedWidth(44)
            b.setToolTip(tip)
            b.setAccessibleName(tip)
            title_row.addWidget(b)
        col.addLayout(title_row)

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #b91c1c;")
        self.error_label.hide()
        col.addWidget(self.error_label)

        self.stack = QStackedWidget()
        self.text_view = QTextBrowser()
        self.text_view.setObjectName("passage")
        self.text_view.setOpenLinks(False)
        self.stack.addWidget(self.text_view)
        results_page = QWidget()
        rl = QVBoxLayout(results_page)
        rl.setContentsMargins(0, 0, 0, 0)
        self.results_label = QLabel()
        self.results_label.setStyleSheet("color: #52525b;")
        rl.addWidget(self.results_label)
        self.results = QListWidget()
        self.results.setObjectName("results")
        self.results.setWordWrap(True)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rl.addWidget(self.results, 1)
        self.stack.addWidget(results_page)
        col.addWidget(self.stack, 1)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        recent = QLabel("Recent")
        recent.setStyleSheet("color: #52525b;")
        chips.addWidget(recent)
        self.chips_box = QHBoxLayout()
        self.chips_box.setSpacing(8)
        chips.addLayout(self.chips_box)
        chips.addStretch(1)
        self.btn_fav = QPushButton("☆ Save")
        self.btn_fav.setObjectName("chip")
        self.btn_fav.setToolTip("Add this passage to your favourites")
        chips.addWidget(self.btn_fav)
        col.addLayout(chips)
        return w

    def _build_side(self) -> QWidget:
        side = QWidget()
        side.setFixedWidth(430)
        col = QVBoxLayout(side)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(12)

        head = QHBoxLayout()
        head.addWidget(_caps("Next", "#1d4ed8"))
        head.addStretch(1)
        self.page_label = QLabel()
        self.page_label.setStyleSheet("color: #52525b;")
        head.addWidget(self.page_label)
        col.addLayout(head)

        frame = QFrame()
        frame.setObjectName("preview")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(2, 2, 2, 2)
        self.preview_view = SlideView()
        self.preview_view.setFixedHeight(238)
        fl.addWidget(self.preview_view)
        col.addWidget(frame)

        self.btn_go_live = QPushButton("GO LIVE")
        self.btn_go_live.setObjectName("goLive")
        self.btn_go_live.setToolTip("Send the next verse to OBS (Ctrl+Enter or F5)")
        col.addWidget(self.btn_go_live)
        col.addSpacing(8)

        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 16)
        cl.setSpacing(12)
        live_row = QHBoxLayout()
        live_row.setSpacing(8)
        self.live_dot = QLabel("●")
        live_row.addWidget(self.live_dot)
        self.live_tag = _caps("Live", "#b91c1c")
        live_row.addWidget(self.live_tag)
        self.live_ref = QLabel()
        self.live_ref.setWordWrap(True)
        live_row.addWidget(self.live_ref, 1)
        cl.addLayout(live_row)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.btn_prev_live = QPushButton("◀ Prev")
        self.btn_next_live = QPushButton("Next ▶")
        self.btn_black = QPushButton("Hide")
        self.btn_black.setObjectName("hide")
        self.btn_black.setCheckable(True)
        self.btn_prev_live.setToolTip("Ctrl+Left: previous verse on screen")
        self.btn_next_live.setToolTip("Ctrl+Right: next verse on screen")
        self.btn_black.setToolTip("Ctrl+B: hide the verse (camera stays visible); click again to show it")
        for b in (self.btn_prev_live, self.btn_next_live, self.btn_black):
            buttons.addWidget(b)
        cl.addLayout(buttons)
        col.addWidget(card)

        obs = QFrame()
        obs.setObjectName("obs")
        ol = QHBoxLayout(obs)
        ol.setContentsMargins(14, 8, 8, 8)
        self.obs_dot = QLabel("●")
        ol.addWidget(self.obs_dot)
        self.obs_label = QLabel()
        self.obs_label.setStyleSheet("color: #3f3f46;")
        ol.addWidget(self.obs_label, 1)
        self.btn_copy_url = QPushButton("Copy")
        self.btn_copy_url.setToolTip("Copy the address for the OBS Browser Source")
        ol.addWidget(self.btn_copy_url)
        col.addWidget(obs)
        col.addStretch(1)
        return side

    def _connect(self):
        self.search.returnPressed.connect(self.run_search)
        self.btn_browse.clicked.connect(self.open_browse)
        self.btn_settings.clicked.connect(self.open_settings)
        self.nav.passageChosen.connect(self.select_passage)
        self.text_view.anchorClicked.connect(self._verse_clicked)
        self.results.itemClicked.connect(self._result_chosen)
        self.results.itemActivated.connect(self._result_chosen)
        self.btn_prev_ch.clicked.connect(lambda: self._step(self.core.service.prev_chapter))
        self.btn_next_ch.clicked.connect(lambda: self._step(self.core.service.next_chapter))
        self.btn_fav.clicked.connect(self.toggle_favourite)
        self.btn_go_live.clicked.connect(self.go_live)
        self.btn_prev_live.clicked.connect(self.prev_live)
        self.btn_next_live.clicked.connect(self.next_live)
        self.btn_black.toggled.connect(self._hide_toggled)
        self.btn_copy_url.clicked.connect(self._copy_url)

        c = self.controls
        c.restoreLive.connect(self.restore_live)
        c.clearLive.connect(self.core.controller.clear)
        c.openFullscreen.connect(self.open_fullscreen)
        c.closeFullscreen.connect(self.close_fullscreen)
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
        sc(["Alt+Right"], lambda: self._move_preview(1))
        sc(["Alt+Left"], lambda: self._move_preview(-1))
        sc(["Ctrl+L", "Ctrl+F"], lambda: (self.search.setFocus(), self.search.selectAll()))

    # ================================================================ startup / shutdown
    def _startup(self):
        if self.core.settings.get("auto_start_server", True):
            self.start_server(self.core.server.port, quiet=True)
        else:
            self._set_server_status(False)
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
            self.resize(1440, 900)

    def closeEvent(self, event):
        self.core.settings.set("window_geometry", bytes(self.saveGeometry().toBase64()).decode())
        self.close_fullscreen()
        self.core.close()
        super().closeEvent(event)

    def open_settings(self):
        self.settings_dialog.show()
        self.settings_dialog.raise_()

    def open_browse(self):
        self.nav.show_passage(self.selected)
        self.browse_dialog.show()
        self.browse_dialog.raise_()

    # ================================================================ translations
    def _refresh_translation_buttons(self):
        for button, lang in ((self.btn_en, "en"), (self.btn_fr, "fr")):
            current = self.core.english if lang == "en" else self.core.french
            button.setText(current.code if current else ("EN off" if lang == "en" else "FR off"))
            menu = QMenu(button)
            group = QActionGroup(menu)
            for t in self.core.repo.list_translations(lang):
                act = QAction(t.label + ("" if t.is_complete else " (partial)"), menu, checkable=True)
                act.setChecked(current is not None and current.id == t.id)
                act.triggered.connect(lambda _=False, tid=t.id, lg=lang: self._choose_translation(lg, tid))
                group.addAction(act)
                menu.addAction(act)
            off = QAction("Hide English" if lang == "en" else "Hide French", menu, checkable=True)
            off.setChecked(current is None)
            off.triggered.connect(lambda _=False, lg=lang: self._choose_translation(lg, None))
            group.addAction(off)
            menu.addAction(off)
            menu.addSeparator()
            menu.addAction("Bible library…", lambda: self.open_library(first_run=False))
            menu.addAction("Translation information…", self.show_translation_info)
            button.setMenu(menu)

    def _choose_translation(self, lang: str, tid: int | None):
        en = self.core.english.id if self.core.english else None
        fr = self.core.french.id if self.core.french else None
        if lang == "en":
            en = tid
        else:
            fr = tid
        self.core.set_translations(en, fr)
        self._after_library_change()

    def _after_library_change(self):
        self._refresh_translation_buttons()
        self.nav.reload_translations()
        self._translations_changed()

    # ================================================================ search & selection
    def tids(self):
        return self.core.tids()

    def run_search(self):
        """A reference (John 3:16, Jean 3,16) opens the passage; anything else searches the words."""
        text = self.search.text().strip()
        self.error_label.hide()
        if not text:
            return
        quoted = text[:1] in "\"“"
        if not quoted:
            try:
                passage = self.core.service.resolve(text, self.tids())
            except ReferenceParseError as exc:
                if any(ch.isdigit() for ch in text):         # clearly meant as a reference
                    self.error_label.setText(str(exc))
                    self.error_label.show()
                    return
            else:
                self.select_passage(passage)
                return
        self._show_word_results(text)

    def _show_word_results(self, query: str):
        self.results.clear()
        seen = set()
        hits = []
        for t in (self.core.english, self.core.french):
            if not t:
                continue
            for b, c, v, txt in self.core.repo.search(t.id, query, limit=200):
                if (b, c, v) not in seen:
                    seen.add((b, c, v))
                    hits.append((b, c, v, txt, t))
        hits.sort(key=lambda h: h[:3])
        for b, c, v, txt, t in hits[:300]:
            p = Passage(b, c, v, c, v)
            item = QListWidgetItem(f"{p.reference(t.language)}  —  {txt}")
            item.setData(Qt.UserRole, p)
            item.setFont(self._serif_font(12))
            self.results.addItem(item)
        shown = min(len(hits), 300)
        self.results_label.setText(f"{shown} verse{'s' if shown != 1 else ''} containing “{query.strip(chr(34))}”"
                                   " — click one to open it." if hits else
                                   f"No verse contains “{query}”. Accents and capitals are ignored.")
        self.stack.setCurrentIndex(1)

    def _serif_font(self, size: int):
        font = self.font()
        font.setFamilies(["EB Garamond", "Garamond", "Georgia"])
        font.setPointSize(size)
        return font

    def _result_chosen(self, item: QListWidgetItem):
        p = item.data(Qt.UserRole)
        if isinstance(p, Passage):
            self.select_passage(p)

    def select_passage(self, passage: Passage | None, remember: bool = True):
        self.selected = passage
        self.preview_page = 0
        self.stack.setCurrentIndex(0)
        if self.browse_dialog.isVisible():
            self.nav.show_passage(passage)
        if passage is not None:
            self.core.settings.set("last_selection", passage.to_dict())
            if remember:
                self.core.settings.add_recent(passage.to_dict(), passage.reference("en"))
                self._refresh_chips()
        self._update_selection_display()

    def _update_selection_display(self):
        p = self.selected
        has = p is not None and bool(self.tids())
        for b in (self.btn_go_live, self.btn_prev_ch, self.btn_next_ch, self.btn_fav):
            b.setEnabled(has)
        if not has:
            self.sel_label.setText(f"<span style='font-family:{SERIF}; font-size:22pt; font-weight:600'>"
                                   f"{'Find a passage' if self.tids() else 'No Bible installed'}</span>")
            self.text_view.setHtml(
                "<p style='color:#52525b; font-size:11pt; margin:16px'>Type a reference such as "
                "<b>John 3:16</b> or <b>Jean 3,16</b> in the search bar, search for words, or click "
                "<b>Browse</b>.</p>" if self.tids() else
                "<p style='color:#52525b; margin:16px'>Open the KJV / LSG button → <b>Bible library…</b></p>")
            self.preview_view.render(self.core.controller.preview_payload(None))
            self.page_label.setText("")
            return
        self.sel_label.setText(
            f"<span style='font-family:{SERIF}; font-size:22pt; font-weight:600'>{_esc(p.reference('en'))}</span>"
            f"<span style='font-family:{SERIF}; font-size:22pt; font-style:italic; color:#52525b'>"
            f"  ·  {_esc(p.reference('fr'))}</span>")
        fav = self.core.settings.is_favourite(p.to_dict())
        self.btn_fav.setText("★ Saved" if fav else "☆ Save")
        self._render_preview()
        self._render_text(p)

    def _pages(self) -> list:
        return self.core._build_pages(self.selected, self.core.style) if self.selected else []

    def _render_text(self, p: Passage):
        """The passage as a table: verse number | English | French. Click a verse to queue it."""
        en, fr = self.core.english, self.core.french
        rows = self.core.service.aligned(p, self.tids())
        multi = p.start_chapter != p.end_chapter
        pages = self._pages()
        on_page = set()
        if pages and 0 <= self.preview_page < len(pages) and pages[self.preview_page]["columns"]:
            on_page = {v["num"] for v in pages[self.preview_page]["columns"][0]["verses"]}
        head = ("<tr><td></td>" + "".join(
            f"<td style='font-family:Inter, Segoe UI, sans-serif; color:#52525b; font-size:8pt; font-weight:700; "
            f"padding:10px 8px'>"
            f"{'ENGLISH' if t.language == 'en' else 'FRANÇAIS'} · {_esc(t.code)}</td>" for t in (en, fr) if t) + "</tr>")
        body = []
        for av in rows:
            num = f"{av.chapter}:{av.verse}" if multi else str(av.verse)
            link = f"verse:{av.chapter}:{av.verse}"
            bg = "#eff6ff" if num in on_page else "#ffffff"
            numcolor = "#1d4ed8" if num in on_page else "#71717a"
            cells = []
            for t in (en, fr):
                if not t:
                    continue
                txt = av.texts.get(t.id)
                if txt is None:
                    cells.append(f"<td valign='top' style='padding:12px 8px; color:#b45309; font-style:italic'>"
                                 f"<a href='{link}' style='color:#b45309; text-decoration:none'>This verse is not in "
                                 f"{_esc(t.code)} (numbering or source text differs)</a></td>")
                else:
                    cells.append(f"<td valign='top' width='50%' style='padding:12px 8px'>"
                                 f"<a href='{link}' style='color:#18181b; text-decoration:none'>{_esc(txt)}</a></td>")
            body.append(f"<tr style='background:{bg}'><td valign='top' nowrap width='44' "
                        f"style='padding:12px 8px 12px 14px; white-space:nowrap'>"
                        f"<a href='{link}' style='color:{numcolor}; font-weight:700; text-decoration:none'>{num}</a>"
                        f"</td>{''.join(cells)}</tr>")
        self.text_view.setHtml(
            f"<div style='font-family:{SERIF}; font-size:14pt; line-height:140%'>"
            f"<table cellspacing='0' width='100%'>{head}{''.join(body)}</table></div>")

    def _verse_clicked(self, url):
        """Queue the clicked verse as the next one to go live."""
        try:
            _, c, v = url.toString().split(":")
            c, v = int(c), int(v)
        except ValueError:
            return
        multi = self.selected.start_chapter != self.selected.end_chapter
        key = f"{c}:{v}" if multi else str(v)
        for i, page in enumerate(self._pages()):
            if page["columns"] and key in {x["num"] for x in page["columns"][0]["verses"]}:
                self.preview_page = i
                break
        self._render_preview()
        self._render_text(self.selected)

    def _render_preview(self):
        payload = self.core.controller.preview_payload(self.selected, self.preview_page)
        slide = payload.get("slide")
        if slide:
            self.preview_page = slide["page"] - 1
            unit = "verse" if self.core.style.get("verses_per_slide") == 1 else "slide"
            self.page_label.setText(f"{unit} {slide['page']} of {slide['pages']}" if slide["pages"] > 1 else "")
        else:
            self.page_label.setText("")
        self.preview_view.render(payload)

    def _move_preview(self, delta: int):
        """Alt+Right / Alt+Left: queue the next / previous verse of the passage."""
        pages = self._pages()
        if not pages:
            return
        self.preview_page = max(0, min(len(pages) - 1, self.preview_page + delta))
        self._render_preview()
        self._render_text(self.selected)

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
            self.core.settings.add_favourite(p.to_dict(), p.reference("en"))
        self.nav.refresh_favourites()
        self._refresh_chips()
        self._update_selection_display()

    def _refresh_chips(self):
        while self.chips_box.count():
            item = self.chips_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        shown = set()
        entries = [(d, "★ " + label) for d, label in self.core.settings.favourites()[:4]]
        entries += [(d, label) for d, label in self.core.settings.recent()]
        for d, label in entries:
            key = tuple(sorted(d.items()))
            if key in shown:
                continue
            shown.add(key)
            try:
                passage = Passage.from_dict(d)
            except (KeyError, ValueError, TypeError):
                continue
            chip = QPushButton(label.split("  ·  ")[0])
            chip.setObjectName("chip")
            chip.clicked.connect(lambda _=False, p=passage: self.select_passage(p))
            self.chips_box.addWidget(chip)
            if len(shown) >= 6:
                break

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
        # Queue the following verse, ready for the next GO LIVE.
        if self.preview_page < len(self._pages()) - 1:
            self._move_preview(1)

    def next_live(self):
        if not self.core.controller.next_live():
            self.statusBar().showMessage("Nothing further to show.", 3000)

    def prev_live(self):
        if not self.core.controller.prev_live():
            self.statusBar().showMessage("Nothing before this.", 3000)

    def restore_live(self):
        if not self.core.controller.restore():
            self.statusBar().showMessage("There is no previous live slide to restore.", 3000)

    def _hide_toggled(self, hidden: bool):
        if hidden != self.core.controller.is_black:
            self.core.controller.set_black(hidden)

    def _on_output_changed(self, payload: dict):
        self._update_live_display(payload)
        # Appearance changes affect the preview (and which verses it covers) too.
        if self.selected is not None:
            self._render_preview()
            self._render_text(self.selected)

    def _update_live_display(self, payload: dict):
        mode = payload.get("mode")
        controller = self.core.controller
        live = controller.live_passage or (controller.state.last_live.passage if controller.state.last_live else None)
        slide = payload.get("slide")
        serif = f"font-family:{SERIF}; font-size:14pt; font-weight:600"
        if mode == "live" and slide:
            ref = f"{slide['reference']['en']}  ·  {slide['reference']['fr']}"
            self.live_dot.setStyleSheet("color: #dc2626;")
            self.live_tag.setText("LIVE")
            self.live_tag.setStyleSheet("color: #b91c1c;")
            self.live_ref.setText(f"<span style='{serif}'>{_esc(ref)}</span>")
        elif mode == "black":
            self.live_dot.setStyleSheet("color: #18181b;")
            self.live_tag.setText("HIDDEN")
            self.live_tag.setStyleSheet("color: #18181b;")
            self.live_ref.setText(f"<span style='{serif}; color:#71717a'>{_esc(live.reference('en'))}</span>"
                                  if live else "")
        else:
            self.live_dot.setStyleSheet("color: #d4d4d8;")
            self.live_tag.setText("NOTHING LIVE")
            self.live_tag.setStyleSheet("color: #71717a;")
            self.live_ref.setText("")
        self.btn_black.blockSignals(True)
        self.btn_black.setChecked(mode == "black")
        self.btn_black.setText("Show" if mode == "black" else "Hide")
        self.btn_black.blockSignals(False)

    # ================================================================ server & output
    def _set_server_status(self, running: bool, url: str = "", error: str = ""):
        self.controls.set_server_status(running, url, error)
        if running:
            self.obs_dot.setStyleSheet("color: #16a34a;")
            self.obs_label.setText("OBS · " + url.replace("http://", ""))
        else:
            self.obs_dot.setStyleSheet("color: #dc2626;" if error else "color: #a1a1aa;")
            self.obs_label.setText("OBS server not running — Settings" if not error else "OBS server error — see Settings")
        self.btn_copy_url.setEnabled(running)

    def _copy_url(self):
        QGuiApplication.clipboard().setText(self.core.server.url)
        self.statusBar().showMessage(f"Copied {self.core.server.url} — paste it into the OBS Browser Source.", 5000)

    def start_server(self, port: int, quiet: bool = False):
        try:
            url = self.core.start_server(int(port))
        except ServerStartError as exc:
            self._set_server_status(False, error=str(exc))
            QMessageBox.warning(self, "Presentation server did not start",
                                f"{exc}\n\nThe rest of the program still works; OBS cannot show verses until "
                                "the server is running.")
            return
        self._set_server_status(True, url)
        if not quiet:
            self.statusBar().showMessage(f"Server running at {url}", 5000)

    def stop_server(self):
        self.close_fullscreen()
        self.core.stop_server()
        self._set_server_status(False)

    def reconnect_output(self):
        self.core.broadcaster.request_reload()
        if self.output_window and hasattr(self.output_window, "view"):
            self.output_window.view.reload()
        self.statusBar().showMessage("Asked the output page(s) to reload.", 4000)

    def open_fullscreen(self, screen_index: int):
        if not self.core.server.running:
            self.start_server(self.core.server.port)
            if not self.core.server.running:
                return
        self.close_fullscreen()
        self.output_window = OutputWindow(self.core.server.url)
        self.output_window.show_on_screen(screen_index)

    def close_fullscreen(self):
        if self.output_window:
            self.output_window.close()
            self.output_window = None

    # ================================================================ library
    def open_library(self, first_run: bool = False):
        dlg = LibraryDialog(self.core, self, first_run=first_run)
        dlg.exec()
        if dlg.changed:
            self._after_library_change()
        st = self.core.library_status()
        if not (st["en_complete"] and st["fr_complete"]):
            missing = " and ".join(x for x, ok in (("English", st["en_complete"]), ("French", st["fr_complete"]))
                                   if not ok)
            self.statusBar().showMessage(f"Setup needed: no complete {missing} Bible yet — "
                                         "open the KJV / LSG button → Bible library…")

    def install_bundled_bibles(self):
        """Install the Bibles that come with the program (KJV, LSG) in the background."""
        entries = self.core.bundled_catalog()

        def done(trs):
            self._after_library_change()
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
