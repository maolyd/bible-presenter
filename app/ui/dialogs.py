"""Bible library management, import review and translation information dialogs."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem, QTextBrowser,
                               QVBoxLayout)

from ..bible.importers import ImportedBible, ImportFormatError, read_bible_file
from ..bible.repository import DuplicateTranslationError
from ..core import AppCore
from .workers import run_with_progress

LANGUAGES = [("en", "English"), ("fr", "French / Français")]

SETUP_TEXT = """
<h2>Welcome to Bible Presenter</h2>
<p>Before you can present verses, the program needs a <b>complete English Bible</b> and a
<b>complete French Bible</b> in its library. Nothing is shown to the audience until then.</p>
<p><b>Easiest option:</b> click <i>Install bundled Bibles</i>. This adds the
<b>King James Version (KJV)</b> and the <b>Louis Segond 1910 (LSG)</b>, which came with this program,
KJV is selected for English and LSG for French. It takes about 10 seconds and works offline.</p>
<p><b>Other translations:</b> click <i>Import Bible file…</i> to add a Bible file you are allowed to use
(USFX, OSIS, Zefania XML, Beblia XML, or eBible.org VPL text). See <i>docs/BIBLE_DATA.md</i>.
Many modern translations are copyrighted; only import them if you have permission.</p>
"""


class LibraryDialog(QDialog):
    def __init__(self, core: AppCore, parent=None, first_run: bool = False):
        super().__init__(parent)
        self.core = core
        self.changed = False
        self.setWindowTitle("Bible Library" if not first_run else "Set up your Bible library")
        self.resize(820, 560)
        layout = QVBoxLayout(self)

        self.intro = QTextBrowser()
        self.intro.setHtml(SETUP_TEXT)
        self.intro.setMaximumHeight(230)
        self.intro.setVisible(first_run)
        layout.addWidget(self.intro)

        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Code", "Name", "Language", "Books", "Verses", "Complete?"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.btn_bundled = QPushButton("Install bundled Bibles (KJV + LSG)")
        self.btn_bundled.setStyleSheet("font-weight:600;")
        self.btn_import = QPushButton("Import Bible file…")
        self.btn_info = QPushButton("Information")
        self.btn_remove = QPushButton("Remove")
        for b in (self.btn_bundled, self.btn_import, self.btn_info, self.btn_remove):
            buttons.addWidget(b)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.accept)
        close.accepted.connect(self.accept)
        layout.addWidget(close)

        self.btn_bundled.clicked.connect(self.install_bundled)
        self.btn_import.clicked.connect(self.import_file)
        self.btn_info.clicked.connect(self.show_info)
        self.btn_remove.clicked.connect(self.remove_selected)
        self.refresh()

    # ------------------------------------------------------------------ table
    def refresh(self):
        trs = self.core.repo.list_translations()
        self.table.setRowCount(len(trs))
        for row, t in enumerate(trs):
            lang = dict(LANGUAGES).get(t.language, t.language)
            values = [t.code, t.name, lang, str(t.book_count), f"{t.verse_count:,}",
                      "Yes — 66 books" if t.is_complete else "No (partial)"]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setData(Qt.UserRole, t.id)
                self.table.setItem(row, col, item)
        st = self.core.library_status()
        ok = "✔"
        missing = []
        if not st["en_complete"]:
            missing.append("a complete English Bible")
        if not st["fr_complete"]:
            missing.append("a complete French Bible")
        if missing:
            self.status.setText("<span style='color:#b45309'><b>Still needed:</b> " + " and ".join(missing) +
                                ".</span>")
        else:
            self.status.setText(f"<span style='color:#15803d'><b>{ok} Ready:</b> a complete English and a "
                                "complete French Bible are installed.</span>")
        self.btn_bundled.setEnabled(bool(self.core.bundled_catalog()))

    def _selected_id(self):
        items = self.table.selectedItems()
        return items[0].data(Qt.UserRole) if items else None

    # ------------------------------------------------------------------ actions
    def install_bundled(self):
        entries = self.core.bundled_catalog()
        installed = {t.code.upper() for t in self.core.repo.list_translations()}
        todo = [e for e in entries if e["code"].upper() not in installed]
        if not todo:
            QMessageBox.information(self, "Already installed",
                                    "The bundled Bibles (KJV and LSG) are already in your library.")
            return

        def work():
            return [self.core.import_bundled(e) for e in todo]

        def done(trs):
            self.changed = True
            self.refresh()
            QMessageBox.information(self, "Bibles installed", "\n".join(
                f"✔ {t.name} ({t.code}): {t.book_count} books, {t.chapter_count} chapters, "
                f"{t.verse_count:,} verses" for t in trs))

        run_with_progress(self, "Installing the bundled Bibles… (about 10 seconds)", work, done,
                          lambda exc: QMessageBox.critical(self, "Installation failed",
                                                           f"{exc}\n\nYour existing Bible library was not changed."))

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a Bible file to import", "",
            "Bible files (*.xml *.usfx *.osis *.txt *.zip);;All files (*)")
        if not path:
            return
        run_with_progress(self, "Reading the Bible file…", lambda: read_bible_file(path),
                          self._review_import, self._read_failed)

    def _read_failed(self, exc):
        if isinstance(exc, ImportFormatError):
            QMessageBox.warning(self, "Cannot import this file", str(exc))
        else:
            QMessageBox.critical(self, "Cannot import this file", f"Unexpected error while reading the file:\n{exc}")

    def _review_import(self, bible: ImportedBible):
        dlg = ImportReviewDialog(bible, self)
        if dlg.exec() != QDialog.Accepted:
            return
        self._store(bible, dlg.values(), replace=False)

    def _store(self, bible, values, replace):
        def work():
            return self.core.import_bible(bible, replace=replace, **values)

        def failed(exc):
            if isinstance(exc, DuplicateTranslationError):
                answer = QMessageBox.question(
                    self, "Translation already installed",
                    f"{exc}\n\nReplace the installed copy with this file?\n"
                    "(Choose No to keep the existing one; you can also import again with a different code.)")
                if answer == QMessageBox.Yes:
                    self._store(bible, values, replace=True)
                return
            QMessageBox.critical(self, "Import failed",
                                 f"{exc}\n\nNothing was changed: your previously imported Bibles are intact.")

        def done(tr):
            self.changed = True
            self.refresh()
            QMessageBox.information(self, "Import complete",
                                    f"✔ {tr.name} ({tr.code}) imported: {tr.book_count} books, "
                                    f"{tr.chapter_count} chapters, {tr.verse_count:,} verses.")

        run_with_progress(self, "Saving the Bible into the library…", work, done, failed)

    def show_info(self):
        tid = self._selected_id()
        if tid is None:
            QMessageBox.information(self, "Information", "Select a translation in the list first.")
            return
        TranslationInfoDialog(self.core, [tid], self).exec()

    def remove_selected(self):
        tid = self._selected_id()
        tr = self.core.repo.get_translation(tid) if tid else None
        if not tr:
            QMessageBox.information(self, "Remove", "Select a translation in the list first.")
            return
        if QMessageBox.question(self, "Remove translation",
                                f"Remove {tr.name} ({tr.code}) from the library?\n"
                                "You can import it again later.") != QMessageBox.Yes:
            return
        self.core.repo.delete_translation(tid)
        self.core.controller.refresh_live()
        self.changed = True
        self.refresh()


class ImportReviewDialog(QDialog):
    """Shows what was found in the file and lets the user confirm name, code and language."""

    def __init__(self, bible: ImportedBible, parent=None):
        super().__init__(parent)
        self.bible = bible
        self.setWindowTitle("Review Bible import")
        self.resize(640, 520)
        layout = QVBoxLayout(self)
        r = bible.report

        summary = [
            f"<b>File:</b> {_esc(bible.source_file)}",
            f"<b>Format:</b> {_esc(r.format_name)}",
            f"<b>Found:</b> {bible.book_count} books, {bible.chapter_count} chapters, {bible.verse_count:,} verses",
        ]
        if bible.is_complete:
            summary.append("<span style='color:#15803d'><b>✔ All 66 books are present.</b></span>")
        else:
            missing = bible.missing_books()
            summary.append("<span style='color:#b45309'><b>⚠ This is not a complete Bible.</b> Missing "
                           f"{len(missing)} book(s): {_esc(', '.join(missing[:12]))}"
                           f"{'…' if len(missing) > 12 else ''}. It will be marked as partial.</span>")
        if r.skipped_books:
            summary.append(f"<b>Skipped (outside the 66-book canon):</b> {_esc(', '.join(sorted(r.skipped_books)))}")
        if r.empty_verses:
            summary.append(f"<b>Verse markers without text (not imported):</b> {len(r.empty_verses)} — "
                           f"{_esc(', '.join(r.empty_verses[:8]))}{'…' if len(r.empty_verses) > 8 else ''}")
        if r.duplicate_references:
            summary.append(f"<b>Duplicate verse references (texts joined):</b> {len(r.duplicate_references)} — "
                           f"{_esc(', '.join(r.duplicate_references[:8]))}")
        if r.invalid_references:
            summary.append(f"<b>Invalid references ignored:</b> {len(r.invalid_references)} — "
                           f"{_esc(', '.join(r.invalid_references[:8]))}")
        if bible.license_text:
            summary.append(f"<b>Licence stated in file:</b> {_esc(bible.license_text)}")
        info = QTextBrowser()
        info.setHtml("<br>".join(summary))
        layout.addWidget(info, 1)

        form = QFormLayout()
        self.name = QLineEdit(bible.name)
        self.code = QLineEdit(bible.code or _suggest_code(bible.name))
        self.code.setMaxLength(16)
        self.language = QComboBox()
        for code, label in LANGUAGES:
            self.language.addItem(label, code)
        idx = self.language.findData(bible.language)
        self.language.setCurrentIndex(idx if idx >= 0 else 0)
        self.license = QLineEdit(bible.license_text)
        self.license.setPlaceholderText("e.g. Public Domain, or the permission you have")
        form.addRow("Translation name:", self.name)
        form.addRow("Short code (e.g. KJV, LSG):", self.code)
        form.addRow("Language:", self.language)
        form.addRow("Licence / permission:", self.license)
        layout.addLayout(form)

        note = QLabel("Only import Bibles you are legally allowed to use. Nothing is saved until you click Import.")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox()
        buttons.addButton("Import", QDialogButtonBox.AcceptRole)
        buttons.addButton(QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self):
        if not self.name.text().strip() or not self.code.text().strip():
            QMessageBox.warning(self, "Missing information", "Please enter a name and a short code.")
            return
        self.accept()

    def values(self) -> dict:
        return {"name": self.name.text().strip(), "code": self.code.text().strip(),
                "language": self.language.currentData(), "license_text": self.license.text().strip()}


class TranslationInfoDialog(QDialog):
    def __init__(self, core: AppCore, tids: list[int], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bible translation information")
        self.resize(640, 480)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        parts = []
        for tid in tids:
            t = core.repo.get_translation(tid)
            if not t:
                continue
            lang = dict(LANGUAGES).get(t.language, t.language)
            parts.append(
                f"<h3>{_esc(t.name)} ({_esc(t.code)})</h3>"
                f"<p><b>Language:</b> {_esc(lang)}<br>"
                f"<b>Contents:</b> {t.book_count} books, {t.chapter_count} chapters, {t.verse_count:,} verses"
                f" — {'complete 66-book Bible' if t.is_complete else 'partial'}<br>"
                f"<b>Imported from:</b> {_esc(t.source_file)}<br>"
                f"<b>Imported on:</b> {_esc(t.imported_at)}</p>"
                f"<p><b>Licence and attribution:</b><br>{_esc(t.license).replace(chr(10), '<br>') or 'Not specified'}</p>")
        if not parts:
            parts.append("<p>No translation is selected.</p>")
        parts.append("<hr><p style='color:#666'>Verses are paired by book, chapter and verse number. When a verse "
                     "exists in only one translation (for example Acts 8:37), the other side shows a clear "
                     "“missing verse” note instead of a different verse.</p>")
        browser.setHtml("".join(parts))
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


def _esc(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _suggest_code(name: str) -> str:
    words = [w for w in name.replace("(", " ").replace(")", " ").split() if w[:1].isalnum()]
    code = "".join(w[0] for w in words if w[0].isalpha()).upper()
    return (code or "BIBLE")[:8]
