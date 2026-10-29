"""Parse human-typed Bible references in English or French.

Accepted examples:
    John 3:16            Jean 3:16          Jean 3.16        Jean 3,16
    John 3:16-18         Jn 3:16–18         1 John 1:9       1re Jean 1.9
    I Corinthians 13     Psaume 23          Jude 3           John 3:16-4:2
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .books import Book, BookLookupError, find_book, normalize


class ReferenceParseError(ValueError):
    """Raised for references that cannot be understood or do not exist."""


@dataclass(frozen=True)
class ParsedReference:
    book: Book
    chapter: int
    verse: int | None = None          # None = whole chapter
    end_chapter: int | None = None
    end_verse: int | None = None


_ORDINALS = [
    (re.compile(r"^(1st|1er|1re|1ere|first|premier|premiere|i)\s+"), "1 "),
    (re.compile(r"^(2nd|2e|2eme|second|seconde|deuxieme|ii)\s+"), "2 "),
    (re.compile(r"^(3rd|3e|3eme|third|troisieme|iii)\s+"), "3 "),
    (re.compile(r"^([123])(st|nd|rd|er|re|ere|e|eme)\s*"), r"\1 "),
]

# book part, then chapter[ sep verse][ - [chapter sep] verse]
_REF_RE = re.compile(
    r"""^\s*(?P<book>[1-3]?\s*[^\d]+?)\s*
        (?:(?P<c1>\d+)
           (?:\s*[:.,]\s*(?P<v1>\d+))?
           (?:\s*[-–—]\s*(?:(?P<c2>\d+)\s*[:.,]\s*)?(?P<v2>\d+))?
        )?\s*$""",
    re.VERBOSE,
)


def parse_reference(text: str) -> ParsedReference:
    raw = text
    if not text.strip():
        raise ReferenceParseError("Please type a book name and chapter, for example “John 3:16” or “Jean 3:16”.")
    if re.match(r"^\s*\d+\s*[:.,]", text):
        raise ReferenceParseError(f"Could not understand “{raw.strip()}”: please include the book name, "
                                  "for example “John 3:16”.")
    text = normalize(text.replace("–", "-").replace("—", "-"))
    # normalize() turns "3.16" into "3 16"; restore a separator between numbers
    text = re.sub(r"(\d)\s+(\d)", r"\1:\2", text)
    for pattern, repl in _ORDINALS:
        text = pattern.sub(repl, text)
    m = _REF_RE.match(text)
    if not m:
        raise ReferenceParseError(f"Could not understand “{raw.strip()}”. "
                              "Try a format like “John 3:16”, “John 3:16-18” or “Jean 3:16”.")
    try:
        book = find_book(m.group("book"))
    except BookLookupError as exc:
        raise ReferenceParseError(str(exc)) from exc

    c1 = m.group("c1")
    if c1 is None:
        return ParsedReference(book, 1)   # book name alone: chapter 1
    c1, v1 = int(c1), m.group("v1")
    c2, v2 = m.group("c2"), m.group("v2")

    if book.chapters == 1 and v1 is None:
        # "Jude 3" / "Jude 3-5" means verses of the only chapter.
        start = c1
        end = int(v2) if v2 else None
        return _checked(ParsedReference(book, 1, start, 1 if end else None, end))

    if v1 is None:
        if v2 is not None and c2 is None:
            # "Psalm 23-24": a chapter range, expressed as whole chapters.
            return _checked(ParsedReference(book, c1, None, int(v2), None))
        return _checked(ParsedReference(book, c1))
    v1 = int(v1)
    if v2 is None:
        return _checked(ParsedReference(book, c1, v1))
    end_chapter = int(c2) if c2 else c1
    return _checked(ParsedReference(book, c1, v1, end_chapter, int(v2)))


def _checked(ref: ParsedReference) -> ParsedReference:
    if ref.chapter < 1 or (ref.verse is not None and ref.verse < 1):
        raise ReferenceParseError("Chapter and verse numbers start at 1.")
    if ref.end_chapter is not None:
        start = (ref.chapter, ref.verse or 0)
        end = (ref.end_chapter, ref.end_verse if ref.end_verse is not None else 10**6)
        if end < start:
            raise ReferenceParseError("The end of the range comes before its start.")
    return ref
