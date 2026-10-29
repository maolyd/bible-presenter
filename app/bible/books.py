"""Canonical list of the 66 books of the Protestant Bible.

Every translation is stored against these canonical book numbers (1-66), so
English and French verses are paired by (book, chapter, verse) and never by
their position in a list.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Book:
    number: int            # 1..66
    usfm: str              # USFM / Paratext code, e.g. "JHN"
    osis: str              # OSIS id, e.g. "John"
    name_en: str
    name_fr: str
    chapters: int          # chapter count in the common English versification
    aliases: tuple = field(default=())   # extra abbreviations (any language)

    @property
    def testament(self) -> str:
        return "OT" if self.number <= 39 else "NT"

    def name(self, lang: str) -> str:
        return self.name_fr if lang == "fr" else self.name_en

    def reference_name(self, lang: str) -> str:
        """Name used before a chapter number: "Psalm 23", "Psaume 23"."""
        if self.number == 19:
            return "Psaume" if lang == "fr" else "Psalm"
        return self.name(lang)


_RAW = [
    # num, usfm, osis, English, French, chapters, aliases
    (1, "GEN", "Gen", "Genesis", "Genèse", 50, ("gn", "ge")),
    (2, "EXO", "Exod", "Exodus", "Exode", 40, ("ex",)),
    (3, "LEV", "Lev", "Leviticus", "Lévitique", 27, ("lv", "le")),
    (4, "NUM", "Num", "Numbers", "Nombres", 36, ("nb", "nm", "nu")),
    (5, "DEU", "Deut", "Deuteronomy", "Deutéronome", 34, ("dt", "de")),
    (6, "JOS", "Josh", "Joshua", "Josué", 24, ("jos", "jsh")),
    (7, "JDG", "Judg", "Judges", "Juges", 21, ("jg", "jdg", "jug", "jge")),
    (8, "RUT", "Ruth", "Ruth", "Ruth", 4, ("rt", "ru")),
    (9, "1SA", "1Sam", "1 Samuel", "1 Samuel", 31, ("1s", "1sm")),
    (10, "2SA", "2Sam", "2 Samuel", "2 Samuel", 24, ("2s", "2sm")),
    (11, "1KI", "1Kgs", "1 Kings", "1 Rois", 22, ("1r", "1kgs", "1k")),
    (12, "2KI", "2Kgs", "2 Kings", "2 Rois", 25, ("2r", "2kgs", "2k")),
    (13, "1CH", "1Chr", "1 Chronicles", "1 Chroniques", 29, ("1ch", "1chr")),
    (14, "2CH", "2Chr", "2 Chronicles", "2 Chroniques", 36, ("2ch", "2chr")),
    (15, "EZR", "Ezra", "Ezra", "Esdras", 10, ("esd", "ezr")),
    (16, "NEH", "Neh", "Nehemiah", "Néhémie", 13, ("ne", "neh")),
    (17, "EST", "Esth", "Esther", "Esther", 10, ("est", "es")),
    (18, "JOB", "Job", "Job", "Job", 42, ("jb",)),
    (19, "PSA", "Ps", "Psalms", "Psaumes", 150, ("ps", "psa", "psalm", "psaume", "pss")),
    (20, "PRO", "Prov", "Proverbs", "Proverbes", 31, ("pr", "prv", "pro")),
    (21, "ECC", "Eccl", "Ecclesiastes", "Ecclésiaste", 12, ("ec", "ecc", "qo", "qoh", "qohelet")),
    (22, "SNG", "Song", "Song of Songs", "Cantique des Cantiques", 8,
     ("song", "sos", "so", "song of solomon", "canticles", "ct", "cant", "cantique")),
    (23, "ISA", "Isa", "Isaiah", "Ésaïe", 66, ("is", "isa", "esa", "es", "isaie")),
    (24, "JER", "Jer", "Jeremiah", "Jérémie", 52, ("jr", "je", "jer")),
    (25, "LAM", "Lam", "Lamentations", "Lamentations", 5, ("lm", "la")),
    (26, "EZK", "Ezek", "Ezekiel", "Ézéchiel", 48, ("ez", "ezk", "eze")),
    (27, "DAN", "Dan", "Daniel", "Daniel", 12, ("dn", "da")),
    (28, "HOS", "Hos", "Hosea", "Osée", 14, ("ho", "os")),
    (29, "JOL", "Joel", "Joel", "Joël", 3, ("jl", "jol")),
    (30, "AMO", "Amos", "Amos", "Amos", 9, ("am",)),
    (31, "OBA", "Obad", "Obadiah", "Abdias", 1, ("ob", "abd")),
    (32, "JON", "Jonah", "Jonah", "Jonas", 4, ("jon", "jnh")),
    (33, "MIC", "Mic", "Micah", "Michée", 7, ("mi", "mic")),
    (34, "NAM", "Nah", "Nahum", "Nahum", 3, ("na",)),
    (35, "HAB", "Hab", "Habakkuk", "Habacuc", 3, ("ha", "hab")),
    (36, "ZEP", "Zeph", "Zephaniah", "Sophonie", 3, ("zp", "so", "soph")),
    (37, "HAG", "Hag", "Haggai", "Aggée", 2, ("hg", "ag")),
    (38, "ZEC", "Zech", "Zechariah", "Zacharie", 14, ("zc", "za", "zech")),
    (39, "MAL", "Mal", "Malachi", "Malachie", 4, ("ml",)),
    (40, "MAT", "Matt", "Matthew", "Matthieu", 28, ("mt", "mat")),
    (41, "MRK", "Mark", "Mark", "Marc", 16, ("mk", "mc", "mrk")),
    (42, "LUK", "Luke", "Luke", "Luc", 24, ("lk", "lc")),
    (43, "JHN", "John", "John", "Jean", 21, ("jn", "jhn")),
    (44, "ACT", "Acts", "Acts", "Actes", 28, ("ac", "act")),
    (45, "ROM", "Rom", "Romans", "Romains", 16, ("rm", "ro")),
    (46, "1CO", "1Cor", "1 Corinthians", "1 Corinthiens", 16, ("1co", "1cor")),
    (47, "2CO", "2Cor", "2 Corinthians", "2 Corinthiens", 13, ("2co", "2cor")),
    (48, "GAL", "Gal", "Galatians", "Galates", 6, ("ga",)),
    (49, "EPH", "Eph", "Ephesians", "Éphésiens", 6, ("ep",)),
    (50, "PHP", "Phil", "Philippians", "Philippiens", 4, ("php", "phil", "phi")),
    (51, "COL", "Col", "Colossians", "Colossiens", 4, ("cl",)),
    (52, "1TH", "1Thess", "1 Thessalonians", "1 Thessaloniciens", 5, ("1th", "1thes", "1ts")),
    (53, "2TH", "2Thess", "2 Thessalonians", "2 Thessaloniciens", 3, ("2th", "2thes", "2ts")),
    (54, "1TI", "1Tim", "1 Timothy", "1 Timothée", 6, ("1ti", "1tm")),
    (55, "2TI", "2Tim", "2 Timothy", "2 Timothée", 4, ("2ti", "2tm")),
    (56, "TIT", "Titus", "Titus", "Tite", 3, ("tt", "ti")),
    (57, "PHM", "Phlm", "Philemon", "Philémon", 1, ("phm", "phlm", "philem", "phmn")),
    (58, "HEB", "Heb", "Hebrews", "Hébreux", 13, ("he", "hb")),
    (59, "JAS", "Jas", "James", "Jacques", 5, ("jas", "jc", "jq", "jm")),
    (60, "1PE", "1Pet", "1 Peter", "1 Pierre", 5, ("1p", "1pe", "1pt", "1pi")),
    (61, "2PE", "2Pet", "2 Peter", "2 Pierre", 3, ("2p", "2pe", "2pt", "2pi")),
    (62, "1JN", "1John", "1 John", "1 Jean", 5, ("1jn", "1jo", "1jhn", "1j")),
    (63, "2JN", "2John", "2 John", "2 Jean", 1, ("2jn", "2jo", "2jhn", "2j")),
    (64, "3JN", "3John", "3 John", "3 Jean", 1, ("3jn", "3jo", "3jhn", "3j")),
    (65, "JUD", "Jude", "Jude", "Jude", 1, ("jd",)),
    (66, "REV", "Rev", "Revelation", "Apocalypse", 22, ("rv", "re", "ap", "apoc", "revelations")),
]

BOOKS: list[Book] = [Book(n, u, o, en, fr, ch, al) for n, u, o, en, fr, ch, al in _RAW]
BY_NUMBER: dict[int, Book] = {b.number: b for b in BOOKS}
BY_USFM: dict[str, Book] = {b.usfm: b for b in BOOKS}
BY_OSIS: dict[str, Book] = {b.osis.lower(): b for b in BOOKS}



def normalize(text: str) -> str:
    """Lower-case, strip accents, collapse whitespace, drop dots."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace(".", " ").replace("’", "'")
    return " ".join(text.split())


def compact(text: str) -> str:
    return normalize(text).replace(" ", "")


def _build_alias_table() -> dict[str, int]:
    table: dict[str, set[int]] = {}

    def add(alias: str, num: int) -> None:
        table.setdefault(compact(alias), set()).add(num)

    for b in BOOKS:
        for alias in (b.name_en, b.name_fr, b.usfm, b.osis, *b.aliases):
            add(alias, b.number)
    # Common alternative full names.
    extra = {
        "Isaïe": 23, "Esaie": 23, "Psalm": 19, "Psaume": 19, "Cantiques": 22,
        "Cantique des cantiques": 22, "Ecclesiaste": 21, "Qohéleth": 21,
        "Actes des apôtres": 44, "Acts of the Apostles": 44, "Révélation": 66,
        "Apocalypse de Jean": 66, "Sophonias": 36, "Abdias": 31, "Habakuk": 35,
        "Philemon": 57, "Hebrews": 58,
    }
    for alias, num in extra.items():
        add(alias, num)
    # An abbreviation shared by two books (e.g. "so", "es") is dropped so the
    # parser asks the user to type more letters instead of guessing.
    return {alias: next(iter(nums)) for alias, nums in table.items() if len(nums) == 1}


ALIASES: dict[str, int] = _build_alias_table()

# Full names (compact form) used for unique-prefix matching, e.g. "Deuter".
_FULL_NAMES: list[tuple[str, int]] = []
for _b in BOOKS:
    for _n in {compact(_b.name_en), compact(_b.name_fr)}:
        _FULL_NAMES.append((_n, _b.number))


class BookLookupError(ValueError):
    def __init__(self, message: str, candidates: list[Book] | None = None):
        super().__init__(message)
        self.candidates = candidates or []


def find_book(text: str) -> Book:
    """Resolve an English or French book name / abbreviation to a Book."""
    key = compact(text)
    if not key:
        raise BookLookupError("Please type a book name, for example “John 3:16” or “Jean 3:16”.")
    if key in ALIASES:
        return BY_NUMBER[ALIASES[key]]
    matches = sorted({num for name, num in _FULL_NAMES if name.startswith(key)})
    if len(key) >= 2 and len(matches) == 1:
        return BY_NUMBER[matches[0]]
    if len(matches) > 1:
        cands = [BY_NUMBER[m] for m in matches]
        names = ", ".join(f"{b.name_en} / {b.name_fr}" for b in cands[:6])
        raise BookLookupError(f"“{text.strip()}” could match several books: {names}. "
                              "Please type more letters.", cands)
    raise BookLookupError(f"“{text.strip()}” is not a recognised Bible book name "
                          "(English or French).")


def book_from_usfm(code: str) -> Book | None:
    return BY_USFM.get(code.strip().upper())


def book_from_osis(code: str) -> Book | None:
    return BY_OSIS.get(code.strip().lower())
