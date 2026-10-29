"""Preview / live state machine.

The operator works on the *preview*. Nothing reaches the audience until
``go_live`` is called. Black screen hides the live slide without forgetting
it, so ``restore`` brings it back exactly as it was.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable

from ..bible.passage import Passage
from .slide import sanitize_style

# pages_builder(passage, style) -> list of page dicts (see slide.build_page)
PagesBuilder = Callable[[Passage, dict], list]


@dataclass
class LiveSlide:
    passage: Passage
    pages: list
    page_index: int = 0

    @property
    def page(self) -> dict:
        return self.pages[self.page_index]


@dataclass
class OutputState:
    version: int = 0
    mode: str = "clear"          # clear | live | black
    live: LiveSlide | None = None
    last_live: LiveSlide | None = None   # kept so "Restore" works after Clear
    style: dict = field(default_factory=dict)


class PresentationController:
    def __init__(self, pages_builder: PagesBuilder, navigator=None, style: dict | None = None):
        """``navigator`` must offer next_verse(passage) / prev_verse(passage) -> Passage | None."""
        self._build_pages = pages_builder
        self._navigator = navigator
        self._lock = threading.RLock()
        self.state = OutputState(style=sanitize_style(style or {}))
        self._listeners: list[Callable[[dict], None]] = []

    # ------------------------------------------------------------- listeners
    def add_listener(self, fn: Callable[[dict], None]) -> None:
        self._listeners.append(fn)

    def _changed(self) -> None:
        with self._lock:
            self.state.version += 1
            snapshot = self.output_payload()
        for fn in list(self._listeners):
            fn(snapshot)

    # ------------------------------------------------------------- payloads
    def output_payload(self) -> dict:
        """What the audience sees (served to OBS)."""
        with self._lock:
            s = self.state
            slide = s.live.page if (s.live and s.mode == "live") else None
            return {
                "type": "state",
                "version": s.version,
                "mode": s.mode if (s.mode != "live" or slide) else "clear",
                "slide": slide,
                "style": dict(s.style),
            }

    def preview_payload(self, passage: Passage | None, page_index: int = 0) -> dict:
        """Render data for the operator preview. Never changes the live output."""
        with self._lock:
            style = dict(self.state.style)
        if passage is None:
            return {"type": "state", "version": 0, "mode": "clear", "slide": None, "style": style}
        pages = self._build_pages(passage, self.state.style)
        if not pages:
            return {"type": "state", "version": 0, "mode": "clear", "slide": None, "style": style}
        page_index = max(0, min(page_index, len(pages) - 1))
        return {"type": "state", "version": 0, "mode": "live", "slide": pages[page_index], "style": style}

    @property
    def live_passage(self) -> Passage | None:
        return self.state.live.passage if self.state.live else None

    @property
    def is_black(self) -> bool:
        return self.state.mode == "black"

    # ------------------------------------------------------------- actions
    def go_live(self, passage: Passage, page_index: int = 0) -> None:
        pages = self._build_pages(passage, self.state.style)
        if not pages:
            raise ValueError("The selected passage has no text in the selected translations.")
        with self._lock:
            self.state.live = LiveSlide(passage, pages, max(0, min(page_index, len(pages) - 1)))
            self.state.last_live = self.state.live
            self.state.mode = "live"
        self._changed()

    def next_live(self) -> bool:
        """Next page of the live passage, or else the next verse. Returns False at the end."""
        with self._lock:
            live = self.state.live
            if not live:
                return False
            if live.page_index < len(live.pages) - 1:
                live.page_index += 1
                target = None
            else:
                target = self._navigator.next_verse(live.passage) if self._navigator else None
                if target is None:
                    return False
        if target is not None:
            return self._move_live(target, 0)
        self._changed()
        return True

    def prev_live(self) -> bool:
        with self._lock:
            live = self.state.live
            if not live:
                return False
            if live.page_index > 0:
                live.page_index -= 1
                target = None
            else:
                target = self._navigator.prev_verse(live.passage) if self._navigator else None
                if target is None:
                    return False
        if target is not None:
            return self._move_live(target, -1)
        self._changed()
        return True

    def _move_live(self, passage: Passage, page_index: int) -> bool:
        pages = self._build_pages(passage, self.state.style)
        if not pages:
            return False
        with self._lock:
            idx = len(pages) - 1 if page_index < 0 else 0
            self.state.live = LiveSlide(passage, pages, idx)
            self.state.last_live = self.state.live
            if self.state.mode != "black":
                self.state.mode = "live"
        self._changed()
        return True

    def set_black(self, black: bool) -> None:
        with self._lock:
            if black:
                self.state.mode = "black"
            else:
                self.state.mode = "live" if self.state.live else "clear"
        self._changed()

    def restore(self) -> bool:
        """Bring back the last live slide after Black screen or Clear."""
        with self._lock:
            if self.state.live is None and self.state.last_live is not None:
                last = self.state.last_live
                pages = self._build_pages(last.passage, self.state.style) or last.pages
                self.state.live = LiveSlide(last.passage, pages, min(last.page_index, len(pages) - 1))
            if self.state.live is None:
                return False
            self.state.mode = "live"
        self._changed()
        return True

    def clear(self) -> None:
        with self._lock:
            if self.state.live:
                self.state.last_live = self.state.live
            self.state.live = None
            self.state.mode = "clear"
        self._changed()

    def set_style(self, style: dict) -> None:
        with self._lock:
            self.state.style = sanitize_style(style)
            # Re-paginate the live passage so typography changes apply immediately.
            if self.state.live:
                pages = self._build_pages(self.state.live.passage, self.state.style)
                if pages:
                    idx = min(self.state.live.page_index, len(pages) - 1)
                    self.state.live = LiveSlide(self.state.live.passage, pages, idx)
                    self.state.last_live = self.state.live
        self._changed()

    def refresh_live(self) -> None:
        """Rebuild the live slide (e.g. after the selected translations change)."""
        self.set_style(self.state.style)
