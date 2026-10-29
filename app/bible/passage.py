"""Passages, navigation and English/French verse alignment."""
from __future__ import annotations

from dataclasses import dataclass

from .books import BY_NUMBER, Book
from .reference import ParsedReference, ReferenceParseError, parse_reference
from .repository import BibleRepository


@dataclass(frozen=True)
class Passage:
    book: int
    start_chapter: int
    start_verse: int
    end_chapter: int
    end_verse: int

    @property
    def start(self) -> tuple[int, int]:
        return (self.start_chapter, self.start_verse)

    @property
    def end(self) -> tuple[int, int]:
        return (self.end_chapter, self.end_verse)

    @property
    def book_info(self) -> Book:
        return BY_NUMBER[self.book]

    def reference(self, lang: str = "en") -> str:
        """Human readable reference, e.g. "John 3:16–18" or "Jean 3:16-18"."""
        name = self.book_info.reference_name(lang)
        dash = "–" if lang == "en" else "-"
        sc, sv, ec, ev = self.start_chapter, self.start_verse, self.end_chapter, self.end_verse
        if (sc, sv) == (ec, ev):
            return f"{name} {sc}:{sv}"
        if sc == ec:
            return f"{name} {sc}:{sv}{dash}{ev}"
        return f"{name} {sc}:{sv}{dash}{ec}:{ev}"

    def to_dict(self) -> dict:
        return {"book": self.book, "start_chapter": self.start_chapter, "start_verse": self.start_verse,
                "end_chapter": self.end_chapter, "end_verse": self.end_verse}

    @classmethod
    def from_dict(cls, d: dict) -> "Passage":
        return cls(int(d["book"]), int(d["start_chapter"]), int(d["start_verse"]),
                   int(d["end_chapter"]), int(d["end_verse"]))


@dataclass(frozen=True)
class AlignedVerse:
    chapter: int
    verse: int
    texts: dict            # translation id -> text, or None when that translation lacks the verse


class PassageService:
    """Resolves references and moves around the Bible.

    Verse lists are the *union* of the selected translations, so a verse that
    exists in only one of them (e.g. Acts 8:37) is shown with a clear
    "missing" marker on the other side instead of being skipped or shifted.
    """

    def __init__(self, repo: BibleRepository):
        self.repo = repo

    # --------------------------------------------------------------- structure
    def chapters(self, book: int, tids: list[int]) -> list[int]:
        out: set[int] = set()
        for tid in tids:
            out.update(self.repo.chapters(tid, book))
        return sorted(out)

    def verses(self, book: int, chapter: int, tids: list[int]) -> list[int]:
        out: set[int] = set()
        for tid in tids:
            out.update(self.repo.verse_numbers(tid, book, chapter))
        return sorted(out)

    def books(self, tids: list[int]) -> list[int]:
        out: set[int] = set()
        for tid in tids:
            out.update(self.repo.books(tid))
        return sorted(out)

    # --------------------------------------------------------------- resolve
    def resolve(self, text_or_ref, tids: list[int]) -> Passage:
        """Turn "John 3:16-18" (or a ParsedReference) into a validated Passage."""
        tids = [t for t in tids if t]
        if not tids:
            raise ReferenceParseError("No Bible translation is selected. Import or select a translation first.")
        ref: ParsedReference = parse_reference(text_or_ref) if isinstance(text_or_ref, str) else text_or_ref
        book = ref.book
        chapters = self.chapters(book.number, tids)
        if not chapters:
            raise ReferenceParseError(f"{book.name_en} / {book.name_fr} is not in the selected translation(s).")
        last_ch = chapters[-1]
        end_chapter = ref.end_chapter if ref.end_chapter is not None else ref.chapter
        for ch in {ref.chapter, end_chapter}:
            if ch not in chapters:
                raise ReferenceParseError(
                    f"{book.name_en} has {last_ch} chapter{'s' if last_ch != 1 else ''}; "
                    f"chapter {ch} does not exist.")
        start_verses = self.verses(book.number, ref.chapter, tids)
        end_verses = self.verses(book.number, end_chapter, tids)
        sv = ref.verse if ref.verse is not None else start_verses[0]
        if ref.end_verse is not None:
            ev = ref.end_verse
        elif ref.end_chapter is not None and ref.verse is None:
            ev = end_verses[-1]                      # chapter range, e.g. Psalm 23-24
        elif ref.verse is None:
            ev = end_verses[-1]                      # whole chapter
        else:
            ev = sv                                  # single verse
        if sv not in start_verses:
            raise ReferenceParseError(
                f"{book.name_en} {ref.chapter} has {start_verses[-1]} verses; verse {sv} does not exist.")
        if ev not in end_verses:
            raise ReferenceParseError(
                f"{book.name_en} {end_chapter} has {end_verses[-1]} verses; verse {ev} does not exist.")
        if (end_chapter, ev) < (ref.chapter, sv):
            raise ReferenceParseError("The end of the range comes before its start.")
        return Passage(book.number, ref.chapter, sv, end_chapter, ev)

    # --------------------------------------------------------------- content
    def aligned(self, passage: Passage, tids: list[int]) -> list[AlignedVerse]:
        tids = [t for t in tids if t]
        texts = {tid: self.repo.verses_between(tid, passage.book, passage.start, passage.end) for tid in tids}
        keys = sorted(set().union(*[set(t) for t in texts.values()])) if texts else []
        return [AlignedVerse(c, v, {tid: texts[tid].get((c, v)) for tid in tids}) for c, v in keys]

    # --------------------------------------------------------------- movement
    def next_verse(self, passage: Passage, tids: list[int]) -> Passage | None:
        """The single verse after the end of the passage (crossing chapters and books)."""
        verses = self.verses(passage.book, passage.end_chapter, tids)
        later = [v for v in verses if v > passage.end_verse]
        if later:
            return Passage(passage.book, passage.end_chapter, later[0], passage.end_chapter, later[0])
        return self._first_verse_after_chapter(passage.book, passage.end_chapter, tids)

    def prev_verse(self, passage: Passage, tids: list[int]) -> Passage | None:
        verses = self.verses(passage.book, passage.start_chapter, tids)
        earlier = [v for v in verses if v < passage.start_verse]
        if earlier:
            v = earlier[-1]
            return Passage(passage.book, passage.start_chapter, v, passage.start_chapter, v)
        chapters = self.chapters(passage.book, tids)
        prev_ch = [c for c in chapters if c < passage.start_chapter]
        if prev_ch:
            v = self.verses(passage.book, prev_ch[-1], tids)[-1]
            return Passage(passage.book, prev_ch[-1], v, prev_ch[-1], v)
        books = [b for b in self.books(tids) if b < passage.book]
        if books:
            ch = self.chapters(books[-1], tids)[-1]
            v = self.verses(books[-1], ch, tids)[-1]
            return Passage(books[-1], ch, v, ch, v)
        return None

    def _first_verse_after_chapter(self, book: int, chapter: int, tids: list[int]) -> Passage | None:
        later_ch = [c for c in self.chapters(book, tids) if c > chapter]
        if later_ch:
            v = self.verses(book, later_ch[0], tids)[0]
            return Passage(book, later_ch[0], v, later_ch[0], v)
        books = [b for b in self.books(tids) if b > book]
        if books:
            ch = self.chapters(books[0], tids)[0]
            v = self.verses(books[0], ch, tids)[0]
            return Passage(books[0], ch, v, ch, v)
        return None

    def chapter_passage(self, book: int, chapter: int, tids: list[int], verse: int | None = None) -> Passage:
        verses = self.verses(book, chapter, tids)
        v = verse if verse in verses else verses[0]
        return Passage(book, chapter, v, chapter, v)

    def next_chapter(self, passage: Passage, tids: list[int]) -> Passage | None:
        """Verse 1 of the following chapter (or the next book)."""
        return self._first_verse_after_chapter(passage.book, passage.end_chapter, tids)

    def prev_chapter(self, passage: Passage, tids: list[int]) -> Passage | None:
        chapters = self.chapters(passage.book, tids)
        prev_ch = [c for c in chapters if c < passage.start_chapter]
        if prev_ch:
            return self.chapter_passage(passage.book, prev_ch[-1], tids)
        books = [b for b in self.books(tids) if b < passage.book]
        if books:
            ch = self.chapters(books[-1], tids)[-1]
            return self.chapter_passage(books[-1], ch, tids)
        return None
