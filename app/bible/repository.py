"""SQLite storage for imported Bible translations.

Bible text lives in its own database file (``bibles.sqlite``), separate from
settings, so translations can be added or removed without touching preferences.
"""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .books import normalize
from .importers import ImportedBible

SCHEMA_VERSION = 1


class DuplicateTranslationError(Exception):
    def __init__(self, existing: "Translation"):
        super().__init__(f"A translation with the code “{existing.code}” is already installed "
                         f"({existing.name}).")
        self.existing = existing


@dataclass(frozen=True)
class Translation:
    id: int
    code: str
    name: str
    language: str
    license: str
    source_file: str
    imported_at: str
    book_count: int
    chapter_count: int
    verse_count: int
    is_complete: bool

    @property
    def label(self) -> str:
        return f"{self.code} — {self.name}"


def _migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < 1:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY,
                code TEXT NOT NULL UNIQUE COLLATE NOCASE,
                name TEXT NOT NULL,
                language TEXT NOT NULL,
                license TEXT NOT NULL DEFAULT '',
                source_file TEXT NOT NULL DEFAULT '',
                imported_at TEXT NOT NULL,
                book_count INTEGER NOT NULL,
                chapter_count INTEGER NOT NULL,
                verse_count INTEGER NOT NULL,
                is_complete INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS verses (
                id INTEGER PRIMARY KEY,
                translation_id INTEGER NOT NULL REFERENCES translations(id) ON DELETE CASCADE,
                book INTEGER NOT NULL,
                chapter INTEGER NOT NULL,
                verse INTEGER NOT NULL,
                text TEXT NOT NULL,
                UNIQUE (translation_id, book, chapter, verse)
            );
            PRAGMA user_version = 1;
        """)
    # Future schema changes go here as "if version < 2: ..." so existing
    # imported Bibles are kept when the application is updated.


class BibleRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(self.db_path, isolation_level=None, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL" if self.db_path != ":memory:" else "PRAGMA journal_mode = MEMORY")
        _migrate(self.conn)
        self.has_fts = self._init_fts()

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    # ----------------------------------------------------------------- search index
    def _init_fts(self) -> bool:
        try:
            self.conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS verses_fts USING fts5("
                "text, content='verses', content_rowid='id', "
                "tokenize='unicode61 remove_diacritics 2')")
            return True
        except sqlite3.OperationalError:
            return False   # SQLite built without FTS5: fall back to LIKE search

    # ----------------------------------------------------------------- translations
    def _row_to_translation(self, row) -> Translation:
        return Translation(row[0], row[1], row[2], row[3], row[4], row[5], row[6],
                           row[7], row[8], row[9], bool(row[10]))

    def list_translations(self, language: str | None = None) -> list[Translation]:
        sql = "SELECT * FROM translations"
        args: tuple = ()
        if language:
            sql += " WHERE language = ?"
            args = (language,)
        with self._lock:
            rows = self.conn.execute(sql + " ORDER BY language, name", args).fetchall()
        return [self._row_to_translation(r) for r in rows]

    def get_translation(self, translation_id: int | None) -> Translation | None:
        if translation_id is None:
            return None
        with self._lock:
            row = self.conn.execute("SELECT * FROM translations WHERE id=?", (translation_id,)).fetchone()
        return self._row_to_translation(row) if row else None

    def find_by_code(self, code: str) -> Translation | None:
        with self._lock:
            row = self.conn.execute("SELECT * FROM translations WHERE code=?", (code,)).fetchone()
        return self._row_to_translation(row) if row else None

    def import_bible(self, bible: ImportedBible, *, name: str, code: str, language: str,
                     license_text: str = "", replace: bool = False) -> Translation:
        """Store a parsed Bible atomically.

        Everything happens in one transaction: if anything fails, the database
        is rolled back and previously imported translations are untouched.
        """
        code = code.strip()
        if not code or not name.strip():
            raise ValueError("The translation needs a name and a short code (e.g. WEB, LSG).")
        if language not in ("en", "fr") and len(language) != 2:
            raise ValueError("Language must be a two-letter code such as “en” or “fr”.")
        with self._lock:
            existing = self.find_by_code(code)
            if existing and not replace:
                raise DuplicateTranslationError(existing)
            cur = self.conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                if existing:
                    cur.execute("DELETE FROM verses WHERE translation_id=?", (existing.id,))
                    cur.execute("DELETE FROM translations WHERE id=?", (existing.id,))
                cur.execute(
                    "INSERT INTO translations (code, name, language, license, source_file, imported_at,"
                    " book_count, chapter_count, verse_count, is_complete) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (code, name.strip(), language, license_text or bible.license_text,
                     bible.source_file, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     bible.book_count, bible.chapter_count, bible.verse_count, int(bible.is_complete)))
                tid = cur.lastrowid
                cur.executemany(
                    "INSERT INTO verses (translation_id, book, chapter, verse, text) VALUES (?,?,?,?,?)",
                    ((tid, b, c, v, t) for (b, c, v), t in sorted(bible.verses.items())))
                if self.has_fts:
                    cur.execute("INSERT INTO verses_fts(verses_fts) VALUES('rebuild')")
                cur.execute("COMMIT")
            except BaseException:
                cur.execute("ROLLBACK")
                raise
        return self.get_translation(tid)

    def delete_translation(self, translation_id: int) -> None:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                cur.execute("DELETE FROM verses WHERE translation_id=?", (translation_id,))
                cur.execute("DELETE FROM translations WHERE id=?", (translation_id,))
                if self.has_fts:
                    cur.execute("INSERT INTO verses_fts(verses_fts) VALUES('rebuild')")
                cur.execute("COMMIT")
            except BaseException:
                cur.execute("ROLLBACK")
                raise

    # ----------------------------------------------------------------- navigation
    def books(self, tid: int) -> list[int]:
        with self._lock:
            return [r[0] for r in self.conn.execute(
                "SELECT DISTINCT book FROM verses WHERE translation_id=? ORDER BY book", (tid,))]

    def chapters(self, tid: int, book: int) -> list[int]:
        with self._lock:
            return [r[0] for r in self.conn.execute(
                "SELECT DISTINCT chapter FROM verses WHERE translation_id=? AND book=? ORDER BY chapter",
                (tid, book))]

    def verse_numbers(self, tid: int, book: int, chapter: int) -> list[int]:
        with self._lock:
            return [r[0] for r in self.conn.execute(
                "SELECT verse FROM verses WHERE translation_id=? AND book=? AND chapter=? ORDER BY verse",
                (tid, book, chapter))]

    def verses_between(self, tid: int, book: int, start: tuple[int, int], end: tuple[int, int]) -> dict:
        """Return {(chapter, verse): text} for start <= (c, v) <= end."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT chapter, verse, text FROM verses WHERE translation_id=? AND book=? "
                "AND (chapter > ? OR (chapter = ? AND verse >= ?)) "
                "AND (chapter < ? OR (chapter = ? AND verse <= ?)) ORDER BY chapter, verse",
                (tid, book, start[0], start[0], start[1], end[0], end[0], end[1])).fetchall()
        return {(c, v): t for c, v, t in rows}

    def verse_text(self, tid: int, book: int, chapter: int, verse: int) -> str | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT text FROM verses WHERE translation_id=? AND book=? AND chapter=? AND verse=?",
                (tid, book, chapter, verse)).fetchone()
        return row[0] if row else None

    # ----------------------------------------------------------------- search
    def search(self, tid: int, query: str, limit: int = 300) -> list[tuple[int, int, int, str]]:
        """Keyword search. All words must appear; text in "quotes" is an exact phrase.

        Accents and case are ignored, so ``eternel`` finds ``Éternel``.
        """
        query = query.strip()
        if not query:
            return []
        phrases, words = _split_query(query)
        if not phrases and not words:
            return []
        with self._lock:
            if self.has_fts:
                parts = [_fts_quote(p) for p in phrases] + [_fts_quote(w) for w in words]
                fts_query = " AND ".join(parts)
                try:
                    rows = self.conn.execute(
                        "SELECT v.book, v.chapter, v.verse, v.text FROM verses_fts f "
                        "JOIN verses v ON v.id = f.rowid WHERE verses_fts MATCH ? AND v.translation_id = ? "
                        "ORDER BY v.book, v.chapter, v.verse LIMIT ?", (fts_query, tid, limit)).fetchall()
                    return rows
                except sqlite3.OperationalError:
                    pass
            # Fallback: scan with accent-insensitive comparison in Python.
            needles = [normalize(p) for p in phrases + words]
            out = []
            for b, c, v, t in self.conn.execute(
                    "SELECT book, chapter, verse, text FROM verses WHERE translation_id=? "
                    "ORDER BY book, chapter, verse", (tid,)):
                nt = normalize(t)
                if all(n in nt for n in needles):
                    out.append((b, c, v, t))
                    if len(out) >= limit:
                        break
            return out


def _split_query(query: str) -> tuple[list[str], list[str]]:
    phrases, words = [], []
    parts = query.replace("“", '"').replace("”", '"').split('"')
    for i, part in enumerate(parts):
        if i % 2 == 1:
            if part.strip():
                phrases.append(part.strip())
        else:
            words.extend(w for w in part.split() if w.strip(".,;:!?"))
    return phrases, words


def _fts_quote(text: str) -> str:
    return '"' + text.replace('"', '""') + '"'
