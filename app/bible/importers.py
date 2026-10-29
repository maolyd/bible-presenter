"""Read Bible text files in documented, publicly used formats.

Supported formats (see docs/BIBLE_DATA.md for details and examples):

* USFX XML          – eBible.org's XML Bible format (root element <usfx>).
* OSIS XML          – Open Scripture Information Standard (root element <osis>).
* Zefania XML       – Zefania XML Bible Markup Language (root element <XMLBIBLE>).
* Beblia XML        – "Holy Bible XML Format" published by Beblia
                      (root <bible>, nested <testament>/<book number>/<chapter number>/<verse number>).
* eBible VPL text   – eBible.org "verse per line" text: ``GEN 1:1 In the beginning...``
* .zip archives containing one of the above.

Every reader produces an :class:`ImportedBible`; nothing is written to the
database here, so a failed or rejected import never touches existing data.
"""
from __future__ import annotations

import io
import re
import xml.sax
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .books import BY_NUMBER, book_from_osis, book_from_usfm

MAX_FILE_BYTES = 200 * 1024 * 1024


class ImportFormatError(ValueError):
    """The file is not in a supported format or is structurally invalid."""


@dataclass
class ImportReport:
    format_name: str = ""
    skipped_books: set = field(default_factory=set)      # books outside the 66-book canon
    invalid_references: list = field(default_factory=list)
    duplicate_references: list = field(default_factory=list)
    empty_verses: list = field(default_factory=list)


@dataclass
class ImportedBible:
    name: str
    code: str
    language: str                       # "en", "fr" or other ISO 639-1 code
    verses: dict                        # (book, chapter, verse) -> text
    report: ImportReport
    source_file: str = ""
    license_text: str = ""

    @property
    def book_count(self) -> int:
        return len({b for b, _, _ in self.verses})

    @property
    def chapter_count(self) -> int:
        return len({(b, c) for b, c, _ in self.verses})

    @property
    def verse_count(self) -> int:
        return len(self.verses)

    @property
    def is_complete(self) -> bool:
        """True when all 66 books are present."""
        return self.book_count == 66

    def missing_books(self) -> list[str]:
        present = {b for b, _, _ in self.verses}
        return [BY_NUMBER[n].name_en for n in range(1, 67) if n not in present]


_WS = re.compile(r"\s+")
_LANG3 = {"eng": "en", "fra": "fr", "fre": "fr", "deu": "de", "ger": "de", "spa": "es",
          "por": "pt", "ita": "it", "nld": "nl", "dut": "nl"}


def _clean(text: str) -> str:
    return _WS.sub(" ", text).strip()


def _lang(code: str | None) -> str:
    code = (code or "").strip().lower()
    code = code.split("-")[0]
    return _LANG3.get(code, code[:2] if len(code) >= 2 else "")


class _Collector:
    """Shared verse bookkeeping for all readers."""

    def __init__(self, fmt: str):
        self.verses: dict = {}
        self.report = ImportReport(format_name=fmt)

    def add(self, book: int | None, chapter, verse, text: str, label: str = "") -> None:
        if book is None:
            if label:
                self.report.skipped_books.add(label)
            return
        try:
            c, v = int(chapter), int(verse)
            if c < 1 or v < 1:
                raise ValueError
        except (TypeError, ValueError):
            self.report.invalid_references.append(f"{label or book} {chapter}:{verse}")
            return
        text = _clean(text)
        key = (book, c, v)
        if not text:
            self.report.empty_verses.append(f"{BY_NUMBER[book].name_en} {c}:{v}")
            return
        if key in self.verses:
            self.report.duplicate_references.append(f"{BY_NUMBER[book].name_en} {c}:{v}")
            self.verses[key] = self.verses[key] + " " + text
            return
        self.verses[key] = text


def _leading_int(value: str | None):
    m = re.match(r"\s*(\d+)", value or "")
    return int(m.group(1)) if m else value


# --------------------------------------------------------------------------- USFX
class _UsfxHandler(xml.sax.ContentHandler):
    # Elements whose text is not part of the verse (notes, headings, titles, alt numbers).
    SKIP = {"f", "x", "fe", "ef", "ex", "note", "rem", "id", "h", "toc", "s", "d", "ca", "va",
            "fig", "rq", "cl", "ide", "generated", "milestone", "periph", "cp", "vp", "fs"}

    def __init__(self, col: _Collector):
        super().__init__()
        self.col = col
        self.book = None
        self.book_label = ""
        self.chapter = None
        self.verse = None
        self.buf: list[str] = []
        self.skip = 0
        self.language = ""
        self._in_lang = False

    def _flush(self):
        if self.verse is not None:
            self.col.add(self.book, self.chapter, self.verse, "".join(self.buf), self.book_label)
        self.verse = None
        self.buf = []

    def startElement(self, name, attrs):
        if name == "languageCode":
            self._in_lang = True
        elif name == "book":
            self._flush()
            self.book_label = attrs.get("id", "")
            b = book_from_usfm(self.book_label)
            self.book = b.number if b else None
            if not b and self.book_label not in ("FRT", "BAK", "GLO", "INT", "OTH", "CNC", "TDX"):
                self.col.report.skipped_books.add(self.book_label)
            self.chapter = None
        elif name == "c":
            self._flush()
            self.chapter = _leading_int(attrs.get("id"))
        elif name == "v":
            self._flush()
            self.verse = _leading_int(attrs.get("id"))
        elif name == "ve":
            self._flush()
        elif name in self.SKIP:
            self.skip += 1

    def endElement(self, name):
        if name == "languageCode":
            self._in_lang = False
        elif name in self.SKIP:
            self.skip -= 1
        elif name == "book":
            self._flush()

    def characters(self, content):
        if self._in_lang:
            self.language += content
        elif self.verse is not None and self.skip == 0 and self.book is not None:
            self.buf.append(content)


# --------------------------------------------------------------------------- OSIS
class _OsisHandler(xml.sax.ContentHandler):
    SKIP = {"note", "title", "reference", "rdg", "catchWord", "milestone"}

    def __init__(self, col: _Collector):
        super().__init__()
        self.col = col
        self.current = None      # (book_num, chapter, verse, label)
        self.buf: list[str] = []
        self.skip = 0
        self.language = ""
        self.title = ""
        self.identifier = ""
        self.rights = ""
        self._meta = None
        self.in_header = False
        self._verse_kinds: list[str] = []   # "milestone" or "container" for each open <verse>

    def _flush(self):
        if self.current:
            b, c, v, label = self.current
            self.col.add(b, c, v, "".join(self.buf), label)
        self.current = None
        self.buf = []

    def startElement(self, name, attrs):
        if name == "osisText":
            self.language = attrs.get("xml:lang", "")
            self.identifier = attrs.get("osisIDWork", "")
        elif name == "header":
            self.in_header = True
        elif self.in_header and name in ("title", "language", "identifier", "rights"):
            self._meta = name
            return
        if name == "verse":
            if attrs.get("eID"):
                self._verse_kinds.append("milestone")
                self._flush()
                return
            # <verse sID=".."/> is a milestone: the text follows until the matching eID.
            self._verse_kinds.append("milestone" if attrs.get("sID") else "container")
            osis_id = attrs.get("osisID") or ""
            self._flush()
            first = osis_id.split()[0] if osis_id else ""
            parts = first.split("!")[0].split(".")
            if len(parts) >= 3:
                b = book_from_osis(parts[0])
                self.current = (b.number if b else None, parts[1], parts[2], parts[0])
        elif name in self.SKIP and not self.in_header:
            self.skip += 1

    def endElement(self, name):
        if name == "header":
            self.in_header = False
        if self._meta == name:
            if name == "rights":
                self.rights += " "
            self._meta = None
            return
        if name == "verse":
            if (self._verse_kinds.pop() if self._verse_kinds else "container") == "container":
                self._flush()
        elif name in self.SKIP and not self.in_header:
            self.skip -= 1

    def characters(self, content):
        if self._meta == "rights":
            self.rights += content
        elif self._meta == "title" and not self.title:
            self.title += content
        elif self._meta == "language" and not self.language:
            self.language = content.strip()
        elif self.current and self.skip == 0:
            self.buf.append(content)


# --------------------------------------------------------------------------- Zefania
class _ZefaniaHandler(xml.sax.ContentHandler):
    SKIP = {"NOTE", "note", "DIV", "XREF", "BR_SKIP"}

    def __init__(self, col: _Collector):
        super().__init__()
        self.col = col
        self.book = None
        self.book_label = ""
        self.chapter = None
        self.verse = None
        self.buf: list[str] = []
        self.skip = 0
        self.meta = {}
        self._meta_key = None
        self.biblename = ""
        self.in_info = False

    def startElement(self, name, attrs):
        if name == "XMLBIBLE":
            self.biblename = attrs.get("biblename", "")
        elif name == "INFORMATION":
            self.in_info = True
        elif self.in_info:
            self._meta_key = name.lower()
        elif name == "BIBLEBOOK":
            num = _leading_int(attrs.get("bnumber"))
            self.book_label = attrs.get("bname") or str(num)
            self.book = num if isinstance(num, int) and 1 <= num <= 66 else None
            if self.book is None:
                self.col.report.skipped_books.add(self.book_label)
        elif name == "CHAPTER":
            self.chapter = attrs.get("cnumber")
        elif name == "VERS":
            self.verse = attrs.get("vnumber")
            self.buf = []
        elif name in self.SKIP:
            self.skip += 1

    def endElement(self, name):
        if name == "INFORMATION":
            self.in_info = False
        elif self.in_info:
            self._meta_key = None
        elif name == "VERS":
            self.col.add(self.book, self.chapter, self.verse, "".join(self.buf), self.book_label)
            self.verse = None
        elif name in self.SKIP:
            self.skip -= 1

    def characters(self, content):
        if self.in_info and self._meta_key:
            self.meta[self._meta_key] = self.meta.get(self._meta_key, "") + content
        elif self.verse is not None and self.skip == 0 and self.book is not None:
            self.buf.append(content)


# --------------------------------------------------------------------------- Beblia
class _BebliaHandler(xml.sax.ContentHandler):
    def __init__(self, col: _Collector):
        super().__init__()
        self.col = col
        self.translation = ""
        self.status = ""
        self.link = ""
        self.book = None
        self.book_label = ""
        self.chapter = None
        self.verse = None
        self.buf: list[str] = []

    def startElement(self, name, attrs):
        if name == "bible":
            self.translation = attrs.get("translation", "")
            self.status = attrs.get("status", "")
            self.link = attrs.get("link", "")
        elif name == "book":
            num = _leading_int(attrs.get("number"))
            self.book_label = str(num)
            self.book = num if isinstance(num, int) and 1 <= num <= 66 else None
            if self.book is None:
                self.col.report.skipped_books.add(self.book_label)
        elif name == "chapter":
            self.chapter = attrs.get("number")
        elif name == "verse":
            self.verse = attrs.get("number")
            self.buf = []

    def endElement(self, name):
        if name == "verse":
            self.col.add(self.book, self.chapter, self.verse, "".join(self.buf), self.book_label)
            self.verse = None

    def characters(self, content):
        if self.verse is not None:
            self.buf.append(content)


# --------------------------------------------------------------------------- detection
def _root_tag(data: bytes) -> str:
    head = data[:4096].decode("utf-8", errors="ignore")
    head = re.sub(r"<\?.*?\?>|<!--.*?-->|<!DOCTYPE[^>]*>", "", head, flags=re.S)
    m = re.search(r"<\s*([A-Za-z_][\w:.-]*)", head)
    return m.group(1).split(":")[-1] if m else ""


_VPL_LINE = re.compile(r"^﻿?([1-4]?[A-Z]{2,3}|[A-Z0-9]{3})\s+(\d+):(\d+)\s+(.*)$")


def detect_format(data: bytes) -> str:
    if data[:4] == b"PK\x03\x04":
        return "zip"
    tag = _root_tag(data)
    if tag:
        return {"usfx": "usfx", "osis": "osis", "XMLBIBLE": "zefania", "bible": "beblia"}.get(tag, "unknown-xml:" + tag)
    text = data[:20000].decode("utf-8", errors="ignore")
    lines = [ln for ln in text.splitlines() if ln.strip()][:20]
    if lines and sum(1 for ln in lines if _VPL_LINE.match(ln.strip())) >= max(1, len(lines) // 2):
        return "vpl"
    return "unknown"


FORMAT_NAMES = {
    "usfx": "USFX XML (eBible.org)",
    "osis": "OSIS XML",
    "zefania": "Zefania XML",
    "beblia": "Beblia Holy Bible XML",
    "vpl": "eBible.org VPL text (verse per line)",
}


def _parse_xml(data: bytes, handler) -> None:
    parser = xml.sax.make_parser()
    # Never fetch external entities or DTDs from user-supplied files.
    parser.setFeature(xml.sax.handler.feature_external_ges, False)
    parser.setFeature(xml.sax.handler.feature_external_pes, False)
    parser.setContentHandler(handler)
    try:
        parser.parse(io.BytesIO(data))
    except xml.sax.SAXParseException as exc:
        raise ImportFormatError(f"The XML file is damaged or incomplete (line {exc.getLineNumber()}): "
                                f"{exc.getMessage()}") from exc


def read_bible_bytes(data: bytes, filename: str = "") -> ImportedBible:
    fmt = detect_format(data)
    stem = Path(filename).stem if filename else "Imported Bible"
    if fmt == "zip":
        return _read_zip(data, filename)
    col = _Collector(FORMAT_NAMES.get(fmt, fmt))
    name, code, language, license_text = stem, "", "", ""

    if fmt == "usfx":
        h = _UsfxHandler(col)
        _parse_xml(data, h)
        language = _lang(h.language)
    elif fmt == "osis":
        h = _OsisHandler(col)
        _parse_xml(data, h)
        name = _clean(h.title) or stem
        code = h.identifier
        language = _lang(h.language)
        license_text = _clean(h.rights)
    elif fmt == "zefania":
        h = _ZefaniaHandler(col)
        _parse_xml(data, h)
        name = _clean(h.meta.get("title", "")) or h.biblename or stem
        code = _clean(h.meta.get("identifier", ""))
        language = _lang(h.meta.get("language"))
        license_text = _clean(h.meta.get("rights", ""))
    elif fmt == "beblia":
        h = _BebliaHandler(col)
        _parse_xml(data, h)
        name = h.translation or stem
        license_text = " ".join(x for x in (h.status, h.link) if x)
        low = name.lower()
        language = "fr" if "french" in low or "fran" in low else ("en" if "english" in low else "")
    elif fmt == "vpl":
        text = data.decode("utf-8-sig", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            m = _VPL_LINE.match(line)
            if not m:
                col.report.invalid_references.append(f"line {lineno}: {line[:40]}")
                continue
            b = book_from_usfm(m.group(1))
            col.add(b.number if b else None, m.group(2), m.group(3), m.group(4), m.group(1))
    elif fmt.startswith("unknown-xml"):
        raise ImportFormatError(
            f"This XML file uses <{fmt.split(':', 1)[1]}> as its main element, which is not a supported "
            "Bible format. Supported: USFX, OSIS, Zefania XML, Beblia XML, eBible VPL text.")
    else:
        raise ImportFormatError(
            "The file format was not recognised. Supported formats: USFX XML, OSIS XML, "
            "Zefania XML, Beblia XML, eBible.org VPL text (or a .zip containing one of them).")

    if not col.verses:
        raise ImportFormatError(f"No verses could be read from this {FORMAT_NAMES.get(fmt, fmt)} file.")
    return ImportedBible(name=_clean(name), code=_clean(code), language=language, verses=col.verses,
                         report=col.report, source_file=filename, license_text=license_text)


def _read_zip(data: bytes, filename: str) -> ImportedBible:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ImportFormatError("The .zip file is damaged.") from exc
    candidates = []
    for info in zf.infolist():
        if info.is_dir() or info.file_size > MAX_FILE_BYTES:
            continue
        if not info.filename.lower().endswith((".xml", ".txt", ".osis", ".usfx")):
            continue
        inner = zf.read(info)
        fmt = detect_format(inner)
        if fmt in FORMAT_NAMES:
            rank = ["usfx", "osis", "zefania", "beblia", "vpl"].index(fmt)
            candidates.append((rank, info.filename, inner))
    if not candidates:
        raise ImportFormatError("The .zip file does not contain a supported Bible file.")
    candidates.sort(key=lambda c: c[0])
    _, inner_name, inner = candidates[0]
    bible = read_bible_bytes(inner, inner_name)
    bible.source_file = f"{filename} → {inner_name}" if filename else inner_name
    return bible


def read_bible_file(path: str | Path) -> ImportedBible:
    path = Path(path)
    if not path.is_file():
        raise ImportFormatError(f"File not found: {path}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ImportFormatError("The file is larger than 200 MB, which is too large for a Bible text.")
    return read_bible_bytes(path.read_bytes(), path.name)
