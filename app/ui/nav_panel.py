"""Left panel: translations, reference lookup, browse, search, recent and favourites."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem,
                               QPushButton, QTabWidget, QVBoxLayout, QWidget)

from ..bible.books import BY_NUMBER
from ..bible.passage import Passage
from ..bible.reference import ReferenceParseError
from ..core import AppCore


_CELL = QSize(40, 28)   # every chapter/verse cell is wide enough for "150"


def _number_grid() -> QListWidget:
    w = QListWidget()
    w.setViewMode(QListView.ListMode)
    w.setFlow(QListView.LeftToRight)
    w.setWrapping(True)
    w.setResizeMode(QListView.Adjust)
    w.setGridSize(QSize(42, 30))
    w.setSpacing(0)
    return w


class NavPanel(QWidget):
    passageChosen = Signal(object)          # Passage
    translationsChanged = Signal()
    manageLibraryRequested = Signal()
    infoRequested = Signal()

    def __init__(self, core: AppCore, parent=None):
        super().__init__(parent)
        self.core = core
        self._updating = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # ---- translations
        tr_box = QGroupBox("Bible translations")
        tr_form = QFormLayout(tr_box)
        self.en_combo = QComboBox()
        self.fr_combo = QComboBox()
        tr_form.addRow("English:", self.en_combo)
        tr_form.addRow("French:", self.fr_combo)
        row = QHBoxLayout()
        self.btn_library = QPushButton("Bible library…")
        self.btn_info = QPushButton("Translation info")
        row.addWidget(self.btn_library)
        row.addWidget(self.btn_info)
        tr_form.addRow(row)
        layout.addWidget(tr_box)

        # ---- reference lookup
        ref_box = QGroupBox("Go to reference")
        ref_layout = QVBoxLayout(ref_box)
        ref_row = QHBoxLayout()
        self.ref_edit = QLineEdit()
        self.ref_edit.setPlaceholderText("e.g. John 3:16-18  or  Jean 3:16")
        self.ref_edit.setClearButtonEnabled(True)
        self.btn_ref = QPushButton("Go")
        ref_row.addWidget(self.ref_edit, 1)
        ref_row.addWidget(self.btn_ref)
        ref_layout.addLayout(ref_row)
        self.ref_error = QLabel()
        self.ref_error.setWordWrap(True)
        self.ref_error.setStyleSheet("color:#dc2626;")
        self.ref_error.hide()
        ref_layout.addWidget(self.ref_error)
        layout.addWidget(ref_box)

        # ---- tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        browse = QWidget()
        bl = QVBoxLayout(browse)
        bl.setContentsMargins(4, 4, 4, 4)
        self.testament = QComboBox()
        self.testament.addItem("All books", "all")
        self.testament.addItem("Old Testament", "OT")
        self.testament.addItem("New Testament", "NT")
        bl.addWidget(self.testament)
        self.book_list = QListWidget()
        bl.addWidget(QLabel("Book"))
        bl.addWidget(self.book_list, 3)
        bl.addWidget(QLabel("Chapter"))
        self.chapter_grid = _number_grid()
        bl.addWidget(self.chapter_grid, 2)
        bl.addWidget(QLabel("Verse (Shift+click or drag to select a range)"))
        self.verse_grid = _number_grid()
        self.verse_grid.setSelectionMode(QAbstractItemView.ExtendedSelection)
        bl.addWidget(self.verse_grid, 2)
        self.tabs.addTab(browse, "Browse")

        search = QWidget()
        sl = QVBoxLayout(search)
        sl.setContentsMargins(4, 4, 4, 4)
        srow = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('Words, or "an exact phrase"')
        self.search_edit.setClearButtonEnabled(True)
        self.search_lang = QComboBox()
        self.search_lang.addItem("English", "en")
        self.search_lang.addItem("French", "fr")
        self.btn_search = QPushButton("Search")
        srow.addWidget(self.search_edit, 1)
        srow.addWidget(self.search_lang)
        srow.addWidget(self.btn_search)
        sl.addLayout(srow)
        self.search_info = QLabel("Accents and capital letters are ignored.")
        self.search_info.setWordWrap(True)
        sl.addWidget(self.search_info)
        self.results = QListWidget()
        self.results.setWordWrap(True)
        self.results.setAlternatingRowColors(True)
        sl.addWidget(self.results, 1)
        self.tabs.addTab(search, "Search")

        recent = QWidget()
        rl = QVBoxLayout(recent)
        rl.setContentsMargins(4, 4, 4, 4)
        self.recent_list = QListWidget()
        rl.addWidget(self.recent_list, 1)
        self.btn_clear_recent = QPushButton("Clear history")
        rl.addWidget(self.btn_clear_recent)
        self.tabs.addTab(recent, "Recent")

        favs = QWidget()
        fl = QVBoxLayout(favs)
        fl.setContentsMargins(4, 4, 4, 4)
        self.fav_list = QListWidget()
        fl.addWidget(self.fav_list, 1)
        self.btn_remove_fav = QPushButton("Remove selected favourite")
        fl.addWidget(self.btn_remove_fav)
        self.tabs.addTab(favs, "Favourites")

        # ---- signals
        self.en_combo.currentIndexChanged.connect(self._translation_changed)
        self.fr_combo.currentIndexChanged.connect(self._translation_changed)
        self.btn_library.clicked.connect(self.manageLibraryRequested)
        self.btn_info.clicked.connect(self.infoRequested)
        self.ref_edit.returnPressed.connect(self.lookup_reference)
        self.btn_ref.clicked.connect(self.lookup_reference)
        self.testament.currentIndexChanged.connect(self.populate_books)
        self.book_list.currentItemChanged.connect(self._book_changed)
        self.chapter_grid.currentItemChanged.connect(self._chapter_changed)
        self.verse_grid.itemSelectionChanged.connect(self._verses_changed)
        self.search_edit.returnPressed.connect(self.run_search)
        self.btn_search.clicked.connect(self.run_search)
        self.results.itemActivated.connect(self._passage_item)
        self.results.itemClicked.connect(self._passage_item)
        self.recent_list.itemClicked.connect(self._passage_item)
        self.recent_list.itemActivated.connect(self._passage_item)
        self.fav_list.itemClicked.connect(self._passage_item)
        self.fav_list.itemActivated.connect(self._passage_item)
        self.btn_clear_recent.clicked.connect(self._clear_recent)
        self.btn_remove_fav.clicked.connect(self._remove_fav)

        self.reload_translations()

    # ================================================================ translations
    def reload_translations(self):
        self._updating = True
        try:
            for combo, lang, current in ((self.en_combo, "en", self.core.english),
                                         (self.fr_combo, "fr", self.core.french)):
                combo.clear()
                for t in self.core.repo.list_translations(lang):
                    combo.addItem(t.label + ("" if t.is_complete else " (partial)"), t.id)
                combo.addItem("(none — hide this language)", None)
                idx = combo.findData(current.id) if current else combo.count() - 1
                combo.setCurrentIndex(max(idx, 0))
        finally:
            self._updating = False
        self.populate_books()
        self.refresh_recent()
        self.refresh_favourites()

    def _translation_changed(self):
        if self._updating:
            return
        self.core.set_translations(self.en_combo.currentData(), self.fr_combo.currentData())
        self.populate_books()
        self.translationsChanged.emit()

    # ================================================================ browse
    def populate_books(self):
        tids = self.core.tids()
        current = self.book_list.currentItem().data(Qt.UserRole) if self.book_list.currentItem() else None
        which = self.testament.currentData()
        self._updating = True
        try:
            self.book_list.clear()
            for num in self.core.service.books(tids) if tids else []:
                b = BY_NUMBER[num]
                if which != "all" and b.testament != which:
                    continue
                label = b.name_en if b.name_en == b.name_fr else f"{b.name_en}  —  {b.name_fr}"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, num)
                self.book_list.addItem(item)
                if num == current:
                    self.book_list.setCurrentItem(item)
        finally:
            self._updating = False
        if self.book_list.currentItem() is None:
            self.chapter_grid.clear()
            self.verse_grid.clear()

    def _book_changed(self, item, _prev=None):
        if item is None:
            return
        self._fill_chapters(item.data(Qt.UserRole))
        if not self._updating and self.chapter_grid.count():
            self.chapter_grid.setCurrentRow(0)

    def _fill_chapters(self, book: int, select: int | None = None):
        was = self._updating
        self._updating = True
        try:
            self.chapter_grid.clear()
            for ch in self.core.service.chapters(book, self.core.tids()):
                it = QListWidgetItem(str(ch))
                it.setSizeHint(_CELL)
                it.setData(Qt.UserRole, ch)
                it.setTextAlignment(Qt.AlignCenter)
                self.chapter_grid.addItem(it)
                if ch == select:
                    self.chapter_grid.setCurrentItem(it)
        finally:
            self._updating = was

    def _chapter_changed(self, item, _prev=None):
        if item is None or self._updating:
            return
        book = self.book_list.currentItem().data(Qt.UserRole)
        self._fill_verses(book, item.data(Qt.UserRole))
        if self.verse_grid.count():
            self.verse_grid.item(0).setSelected(True)   # emits the passage for verse 1

    def _fill_verses(self, book: int, chapter: int, select: tuple[int, int] | None = None):
        was = self._updating
        self._updating = True
        try:
            self.verse_grid.clear()
            for v in self.core.service.verses(book, chapter, self.core.tids()):
                it = QListWidgetItem(str(v))
                it.setSizeHint(_CELL)
                it.setData(Qt.UserRole, v)
                it.setTextAlignment(Qt.AlignCenter)
                self.verse_grid.addItem(it)
                if select and select[0] <= v <= select[1]:
                    it.setSelected(True)
        finally:
            self._updating = was

    def _verses_changed(self):
        if self._updating:
            return
        selected = [i.data(Qt.UserRole) for i in self.verse_grid.selectedItems()]
        if not selected or not self.book_list.currentItem() or not self.chapter_grid.currentItem():
            return
        book = self.book_list.currentItem().data(Qt.UserRole)
        ch = self.chapter_grid.currentItem().data(Qt.UserRole)
        self.passageChosen.emit(Passage(book, ch, min(selected), ch, max(selected)))

    def show_passage(self, p: Passage | None):
        """Reflect a passage chosen elsewhere (search, lookup, next verse…) without re-emitting it."""
        if p is None:
            self._updating = True
            self.verse_grid.clearSelection()
            self._updating = False
            return
        self._updating = True
        try:
            if self.testament.currentData() not in ("all", p.book_info.testament):
                self.testament.setCurrentIndex(0)
                self.populate_books()
                self._updating = True
            for i in range(self.book_list.count()):
                if self.book_list.item(i).data(Qt.UserRole) == p.book:
                    self.book_list.setCurrentRow(i)
                    self.book_list.scrollToItem(self.book_list.item(i))
                    break
            self._fill_chapters(p.book, select=p.start_chapter)
            sel = (p.start_verse, p.end_verse if p.end_chapter == p.start_chapter else 10**6)
            self._fill_verses(p.book, p.start_chapter, select=sel)
            selected = self.verse_grid.selectedItems()
            if selected:
                self.verse_grid.scrollToItem(selected[0])
        finally:
            self._updating = False

    # ================================================================ lookup & search
    def lookup_reference(self):
        text = self.ref_edit.text().strip()
        if not text:
            return
        try:
            passage = self.core.service.resolve(text, self.core.tids())
        except ReferenceParseError as exc:
            self.ref_error.setText(str(exc))
            self.ref_error.show()
            return
        self.ref_error.hide()
        self.passageChosen.emit(passage)

    def run_search(self):
        query = self.search_edit.text().strip()
        lang = self.search_lang.currentData()
        tr = self.core.english if lang == "en" else self.core.french
        self.results.clear()
        if not query:
            return
        if tr is None:
            self.search_info.setText("No translation is selected for that language.")
            return
        rows = self.core.repo.search(tr.id, query, limit=301)
        more = len(rows) > 300
        rows = rows[:300]
        for b, c, v, text in rows:
            p = Passage(b, c, v, c, v)
            item = QListWidgetItem(f"{p.reference(lang)} — {text}")
            item.setData(Qt.UserRole, p)
            item.setToolTip(text)
            self.results.addItem(item)
        if not rows:
            self.search_info.setText(f"No verses in {tr.code} contain “{query}”.")
        else:
            self.search_info.setText(f"{len(rows)}{'+ (showing the first 300)' if more else ''} verse(s) "
                                     f"found in {tr.code}. Click a result to preview it.")

    def _passage_item(self, item: QListWidgetItem):
        p = item.data(Qt.UserRole)
        if isinstance(p, Passage):
            self.passageChosen.emit(p)

    # ================================================================ recent & favourites
    def refresh_recent(self):
        self.recent_list.clear()
        for d, label in self.core.settings.recent():
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, Passage.from_dict(d))
            self.recent_list.addItem(item)

    def refresh_favourites(self):
        self.fav_list.clear()
        for d, label in self.core.settings.favourites():
            item = QListWidgetItem("★ " + label)
            item.setData(Qt.UserRole, Passage.from_dict(d))
            self.fav_list.addItem(item)

    def _clear_recent(self):
        self.core.settings.clear_recent()
        self.refresh_recent()

    def _remove_fav(self):
        item = self.fav_list.currentItem()
        if item:
            self.core.settings.remove_favourite(item.data(Qt.UserRole).to_dict())
            self.refresh_favourites()
