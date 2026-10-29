"""Turn a passage into presentation slides (pages) for the output webpage."""
from __future__ import annotations

from ..bible.passage import AlignedVerse, Passage
from ..bible.repository import Translation

DEFAULT_STYLE: dict = {
    "background": "#0b1530",        # dark navy
    "text_color": "#fff8ec",        # warm white
    "reference_color": "#e9c46a",   # soft gold for the reference line
    "font_family": "EB Garamond",   # bundled in web/fonts, a classic Bible serif
    "en_size": 60,                  # px on the 1920x1080 design canvas
    "fr_size": 60,
    "ref_size": 40,
    "line_spacing": 1.3,
    "align": "center",              # left | center | right | justify
    "layout": "side",               # side | stacked
    "order": "en-fr",               # en-fr | fr-en
    "show_reference": True,
    "reference_position": "bottom", # top | bottom
    "show_labels": False,
    "show_en": True,
    "show_fr": True,
    "show_verse_numbers": True,
    "stacked_gap": 48,              # px between languages in stacked layout
    "verses_per_slide": 1,          # 1 = one verse at a time; 0 = whole selection (auto-paginate)
    "transparent_background": False,
    "display_mode": "footer",       # footer (lower-third band) | fullscreen
    "footer_height": 34,            # footer band height, % of the screen
    "footer_opacity": 85,           # footer band background opacity, %
    "label_en": "English",
    "label_fr": "Français",
}

MISSING_TEXT = {
    "en": "[Verse {n} is not in this translation — the verse numbering or source text differs.]",
    "fr": "[Le verset {n} n’existe pas dans cette traduction — numérotation ou texte source différent.]",
}

# Rough characters-per-slide budget per language at the default 56px size.
# The webpage additionally shrinks text to fit, so this only splits very long passages.
_AUTO_BUDGET = {"side": 720, "stacked": 700}


def sanitize_style(style: dict) -> dict:
    """Merge with defaults and clamp values so a bad setting can't break the output."""
    out = dict(DEFAULT_STYLE)
    for key, default in DEFAULT_STYLE.items():
        if key not in style:
            continue
        val = style[key]
        try:
            if isinstance(default, bool):
                out[key] = bool(val)
            elif isinstance(default, int):
                out[key] = int(val)
            elif isinstance(default, float):
                out[key] = float(val)
            else:
                out[key] = str(val)
        except (TypeError, ValueError):
            pass
    for key, lo, hi in (("en_size", 16, 200), ("fr_size", 16, 200), ("ref_size", 12, 160),
                        ("stacked_gap", 0, 300), ("verses_per_slide", 0, 50),
                        ("footer_height", 15, 70), ("footer_opacity", 0, 100)):
        out[key] = max(lo, min(hi, out[key]))
    out["line_spacing"] = max(0.9, min(2.5, out["line_spacing"]))
    for key, allowed in (("align", ("left", "center", "right", "justify")), ("layout", ("side", "stacked")),
                         ("display_mode", ("footer", "fullscreen")),
                         ("order", ("en-fr", "fr-en")), ("reference_position", ("top", "bottom"))):
        if out[key] not in allowed:
            out[key] = DEFAULT_STYLE[key]
    for key in ("background", "text_color", "reference_color"):
        v = out[key]
        if not (isinstance(v, str) and v.startswith("#") and len(v) in (4, 7)
                and all(ch in "0123456789abcdefABCDEF" for ch in v[1:])):
            out[key] = DEFAULT_STYLE[key]
    out["font_family"] = "".join(ch for ch in out["font_family"] if ch not in "\"';{}<>\\")[:80] or "EB Garamond"
    return out


def paginate(verses: list[AlignedVerse], style: dict, tids: list[int]) -> list[list[AlignedVerse]]:
    if not verses:
        return []
    per = style.get("verses_per_slide", 0)
    if per and per > 0:
        return [verses[i:i + per] for i in range(0, len(verses), per)]
    size = max(style.get("en_size", 56), style.get("fr_size", 56))
    budget = _AUTO_BUDGET.get(style.get("layout", "side"), 540) * (56 / size) ** 2
    if style.get("display_mode") == "footer":
        budget *= style.get("footer_height", 34) / 80     # the band is only part of the screen
    pages: list[list[AlignedVerse]] = []
    current: list[AlignedVerse] = []
    used = 0.0
    for av in verses:
        length = max((len(av.texts.get(t) or "") for t in tids), default=0) + 6
        if current and used + length > budget:
            pages.append(current)
            current, used = [], 0.0
        current.append(av)
        used += length
    if current:
        pages.append(current)
    return pages


def build_page(passage: Passage, page: list[AlignedVerse], page_index: int, page_count: int,
               en: Translation | None, fr: Translation | None, style: dict) -> dict:
    multi_chapter = passage.start_chapter != passage.end_chapter
    columns = []
    for lang, tr in (("en", en), ("fr", fr)):
        if tr is None:
            continue
        verses = []
        for av in page:
            text = av.texts.get(tr.id)
            num = f"{av.chapter}:{av.verse}" if multi_chapter else str(av.verse)
            verses.append({
                "num": num,
                "text": text if text is not None else MISSING_TEXT[lang].format(n=f"{av.chapter}:{av.verse}"),
                "missing": text is None,
            })
        label = style.get(f"label_{lang}") or ("English" if lang == "en" else "Français")
        columns.append({"lang": lang, "label": f"{label} · {tr.code}", "verses": verses})

    # Reference for exactly what is on this page.
    first, last = page[0], page[-1]
    shown = Passage(passage.book, first.chapter, first.verse, last.chapter, last.verse)
    return {
        "reference": {"en": shown.reference("en"), "fr": shown.reference("fr")},
        "passage_reference": {"en": passage.reference("en"), "fr": passage.reference("fr")},
        "columns": columns,
        "page": page_index + 1,
        "pages": page_count,
    }
