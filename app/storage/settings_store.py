"""SQLite storage for preferences, favourites and recently viewed passages.

No personal information is stored: only presentation preferences and Bible
references chosen by the operator.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

RECENT_LIMIT = 30


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < 1:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS favourites (
                id INTEGER PRIMARY KEY,
                passage TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recent (
                passage TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                viewed_at TEXT NOT NULL
            );
            PRAGMA user_version = 1;
        """)
    # Add "if version < 2:" blocks here for future changes; never drop user tables.


class SettingsStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        _migrate(self.conn)
        self.conn.commit()

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    # ---------------------------------------------------------- key/value settings
    def get(self, key: str, default=None):
        with self._lock:
            row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row[0])
        except ValueError:
            return default

    def set(self, key: str, value) -> None:
        with self._lock:
            self.conn.execute("INSERT INTO settings(key, value) VALUES(?, ?) "
                              "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                              (key, json.dumps(value)))
            self.conn.commit()

    # ---------------------------------------------------------- favourites
    def add_favourite(self, passage: dict, label: str) -> None:
        with self._lock:
            self.conn.execute("INSERT OR IGNORE INTO favourites(passage, label, created_at) VALUES(?,?,?)",
                              (json.dumps(passage, sort_keys=True), label, _now()))
            self.conn.commit()

    def remove_favourite(self, passage: dict) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM favourites WHERE passage=?", (json.dumps(passage, sort_keys=True),))
            self.conn.commit()

    def is_favourite(self, passage: dict) -> bool:
        with self._lock:
            return self.conn.execute("SELECT 1 FROM favourites WHERE passage=?",
                                     (json.dumps(passage, sort_keys=True),)).fetchone() is not None

    def favourites(self) -> list[tuple[dict, str]]:
        with self._lock:
            rows = self.conn.execute("SELECT passage, label FROM favourites ORDER BY created_at DESC, id DESC").fetchall()
        return [(json.loads(p), label) for p, label in rows]

    # ---------------------------------------------------------- recent
    def add_recent(self, passage: dict, label: str) -> None:
        with self._lock:
            self.conn.execute("INSERT INTO recent(passage, label, viewed_at) VALUES(?,?,?) "
                              "ON CONFLICT(passage) DO UPDATE SET viewed_at=excluded.viewed_at, label=excluded.label",
                              (json.dumps(passage, sort_keys=True), label, _now()))
            self.conn.execute("DELETE FROM recent WHERE passage NOT IN "
                              "(SELECT passage FROM recent ORDER BY viewed_at DESC, rowid DESC LIMIT ?)", (RECENT_LIMIT,))
            self.conn.commit()

    def recent(self) -> list[tuple[dict, str]]:
        with self._lock:
            rows = self.conn.execute("SELECT passage, label FROM recent ORDER BY viewed_at DESC, rowid DESC").fetchall()
        return [(json.loads(p), label) for p, label in rows]

    def clear_recent(self) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM recent")
            self.conn.commit()
