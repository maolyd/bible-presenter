"""Application core: everything except the Qt user interface.

Keeping this separate from the UI lets the automated tests exercise the real
storage, navigation, preview/live logic and web server without a screen.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .bible.importers import ImportedBible, read_bible_file
from .bible.passage import Passage, PassageService
from .bible.repository import BibleRepository, Translation
from .presentation.controller import PresentationController
from .presentation.slide import DEFAULT_STYLE, build_page, paginate, sanitize_style
from .server.presentation_server import (DEFAULT_HOST, DEFAULT_PORT, Broadcaster, PresentationServer)
from .storage.settings_store import SettingsStore
from . import paths


class AppCore:
    def __init__(self, data_dir: str | Path | None = None, web_root: str | Path | None = None,
                 bundled_dir: str | Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else paths.user_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.web_root = Path(web_root) if web_root else paths.web_dir()
        self.bundled_dir = Path(bundled_dir) if bundled_dir else paths.bundled_bibles_dir()
        self.settings = SettingsStore(self.data_dir / "settings.sqlite")
        self.repo = BibleRepository(self.data_dir / "bibles.sqlite")
        self.service = PassageService(self.repo)
        self.broadcaster = Broadcaster()
        self._migrate_style()
        style = dict(DEFAULT_STYLE)
        style.update(self.settings.get("style", {}) or {})
        self.controller = PresentationController(self._build_pages, navigator=self, style=style)
        self.controller.add_listener(self.broadcaster.publish)
        self.broadcaster.publish(self.controller.output_payload())
        port = int(self.settings.get("server_port", DEFAULT_PORT) or DEFAULT_PORT)
        self.server = PresentationServer(self.web_root, self.broadcaster, DEFAULT_HOST, port)

    STYLE_VERSION = 2

    def _migrate_style(self) -> None:
        """Version 2 made "one verse at a time" in a footer the standard display."""
        if (self.settings.get("style_version", 1) or 1) >= self.STYLE_VERSION:
            return
        saved = self.settings.get("style")
        if saved:
            saved.update(verses_per_slide=1, display_mode="footer")
            self.settings.set("style", saved)
        self.settings.set("style_version", self.STYLE_VERSION)

    def close(self) -> None:
        self.server.stop()
        self.repo.close()
        self.settings.close()

    # ------------------------------------------------------------ translations
    HIDDEN = -1   # stored when the operator chooses "(none — hide this language)"

    def _selected(self, key: str, language: str) -> Translation | None:
        tid = self.settings.get(key)
        if tid == self.HIDDEN:
            return None
        tr = self.repo.get_translation(tid) if tid else None
        if tr is None:
            options = self.repo.list_translations(language)
            options.sort(key=lambda t: (not t.is_complete, t.name))
            tr = options[0] if options else None
        return tr

    @property
    def english(self) -> Translation | None:
        return self._selected("translation_en", "en")

    @property
    def french(self) -> Translation | None:
        return self._selected("translation_fr", "fr")

    def set_translations(self, en_id: int | None, fr_id: int | None) -> None:
        self.settings.set("translation_en", self.HIDDEN if en_id is None else en_id)
        self.settings.set("translation_fr", self.HIDDEN if fr_id is None else fr_id)
        self.controller.refresh_live()

    def tids(self) -> list[int]:
        return [t.id for t in (self.english, self.french) if t]

    def library_status(self) -> dict:
        """Whether a complete English and a complete French Bible are installed."""
        trs = self.repo.list_translations()
        return {
            "en_complete": any(t.language == "en" and t.is_complete for t in trs),
            "fr_complete": any(t.language == "fr" and t.is_complete for t in trs),
            "count": len(trs),
        }

    # ------------------------------------------------------------ bundled public-domain Bibles
    def bundled_catalog(self) -> list[dict]:
        catalog = self.bundled_dir / "catalog.json"
        if not catalog.is_file():
            return []
        entries = json.loads(catalog.read_text(encoding="utf-8")).get("bibles", [])
        return [e for e in entries if (self.bundled_dir / e["file"]).is_file()]

    def import_bundled(self, entry: dict, replace: bool = False) -> Translation:
        path = self.bundled_dir / entry["file"]
        expected = entry.get("sha256")
        if expected:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != expected:
                raise ValueError(f"The bundled file {entry['file']} is damaged (checksum mismatch). "
                                 "Download the application again.")
        bible = read_bible_file(path)
        license_text = f"{entry.get('license', '')}\nSource: {entry.get('source', '')}"
        if entry.get("notes"):
            license_text += f"\nNotes: {entry['notes']}"
        tr = self.import_bible(bible, name=entry["name"], code=entry["code"],
                               language=entry["language"], license_text=license_text, replace=replace)
        # The catalog's default Bible (KJV for English, LSG for French) becomes the selected one.
        key = {"en": "translation_en", "fr": "translation_fr"}.get(tr.language)
        if key and entry.get("default"):
            self.settings.set(key, tr.id)
            self.controller.refresh_live()
        return tr

    def import_bible(self, bible: ImportedBible, *, name: str, code: str, language: str,
                     license_text: str = "", replace: bool = False) -> Translation:
        tr = self.repo.import_bible(bible, name=name, code=code, language=language,
                                    license_text=license_text, replace=replace)
        self.controller.refresh_live()
        return tr

    # ------------------------------------------------------------ navigation adapter
    def next_verse(self, passage: Passage) -> Passage | None:
        return self.service.next_verse(passage, self.tids())

    def prev_verse(self, passage: Passage) -> Passage | None:
        return self.service.prev_verse(passage, self.tids())

    # ------------------------------------------------------------ slides
    def _build_pages(self, passage: Passage, style: dict) -> list:
        en, fr = self.english, self.french
        tids = [t.id for t in (en, fr) if t]
        if not tids:
            return []
        verses = self.service.aligned(passage, tids)
        pages = paginate(verses, style, tids)
        return [build_page(passage, page, i, len(pages), en, fr, style) for i, page in enumerate(pages)]

    # ------------------------------------------------------------ style
    @property
    def style(self) -> dict:
        return dict(self.controller.state.style)

    def update_style(self, **changes) -> dict:
        style = sanitize_style({**self.controller.state.style, **changes})
        self.settings.set("style", style)
        self.controller.set_style(style)
        return style

    def reset_style(self) -> dict:
        self.settings.set("style", dict(DEFAULT_STYLE))
        self.controller.set_style(dict(DEFAULT_STYLE))
        return self.style

    # ------------------------------------------------------------ server
    def start_server(self, port: int | None = None) -> str:
        if port is not None and port != self.server.port:
            self.server.stop()
            self.server.port = int(port)
        self.server.start()
        self.settings.set("server_port", self.server.port)
        # Send the current state to pages that connect after a restart.
        self.broadcaster.publish(self.controller.output_payload())
        return self.server.url

    def stop_server(self) -> None:
        self.server.stop()
