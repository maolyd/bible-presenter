"""Checks against the complete bundled WEB and LSG Bibles."""
from app.bible.books import BOOKS
from app.bible.passage import Passage


def test_both_bibles_are_complete(full_core):
    en, fr = full_core.english, full_core.french
    assert (en.code, en.book_count, en.chapter_count, en.is_complete) == ("KJV", 66, 1189, True)
    assert (fr.code, fr.book_count, fr.chapter_count, fr.is_complete) == ("LSG", 66, 1189, True)
    assert en.verse_count == 31102
    assert fr.verse_count == 31102
    web = full_core.repo.find_by_code("WEB")
    assert (web.book_count, web.verse_count, web.is_complete) == (66, 31098, True)
    assert full_core.library_status() == {"en_complete": True, "fr_complete": True, "count": 3}


def test_chapter_counts_match_book_table(full_core):
    for tr in (full_core.english, full_core.french):
        for b in BOOKS:
            assert len(full_core.repo.chapters(tr.id, b.number)) == b.chapters, (tr.code, b.name_en)


def test_known_verses(full_core):
    en, fr = full_core.english, full_core.french
    r = full_core.repo
    assert r.verse_text(en.id, 43, 3, 16) == ("For God so loved the world, that he gave his only begotten Son, "
                                               "that whosoever believeth in him should not perish, but have "
                                               "everlasting life.")
    assert r.verse_text(fr.id, 43, 3, 16).startswith("Car Dieu a tant aimé le monde")
    assert r.verse_text(en.id, 1, 1, 1) == "In the beginning God created the heaven and the earth."
    assert r.verse_text(en.id, 1, 1, 2).count("was upon the face") == 1        # <transChange> words kept once
    assert r.verse_text(fr.id, 1, 1, 1) == "Au commencement, Dieu créa les cieux et la terre."
    assert r.verse_text(en.id, 39, 4, 6) and r.verse_text(fr.id, 39, 4, 6)        # Malachi 4 exists in both
    assert r.verse_text(en.id, 66, 22, 21) and r.verse_text(fr.id, 66, 22, 21)


def _differences(full_core, en, fr):
    only_en, only_fr = [], []
    for b in BOOKS:
        for ch in range(1, b.chapters + 1):
            e = set(full_core.repo.verse_numbers(en.id, b.number, ch))
            f = set(full_core.repo.verse_numbers(fr.id, b.number, ch))
            only_en += [(b.usfm, ch, v) for v in sorted(e - f)]
            only_fr += [(b.usfm, ch, v) for v in sorted(f - e)]
    return only_en, only_fr


def test_kjv_and_lsg_align_verse_for_verse(full_core):
    assert _differences(full_core, full_core.english, full_core.french) == ([], [])


def test_web_and_lsg_differences_are_only_known_variants(full_core):
    """WEB omits a few textual-variant verses; these get a missing marker instead of shifting."""
    only_en, only_fr = _differences(full_core, full_core.repo.find_by_code("WEB"), full_core.french)
    assert only_en == [("ROM", 14, 24), ("ROM", 14, 25), ("ROM", 14, 26)]
    assert only_fr == [("LUK", 17, 36), ("ACT", 8, 37), ("ACT", 15, 34), ("ACT", 24, 7),
                       ("ROM", 16, 25), ("ROM", 16, 26), ("ROM", 16, 27)]


def test_psalm_23_is_paired_by_verse_number(full_core):
    p = full_core.service.resolve("Psaume 23", full_core.tids())
    rows = full_core.service.aligned(p, full_core.tids())
    en, fr = full_core.english.id, full_core.french.id
    assert len(rows) == 6
    assert rows[0].texts[en] == "The LORD is my shepherd; I shall not want."
    assert "berger" in rows[0].texts[fr]
    assert "valley of the shadow of death" in rows[3].texts[en] and "l'ombre de la mort" in rows[3].texts[fr]


def test_search_full_bible(full_core):
    hits = full_core.repo.search(full_core.french.id, '"Dieu a tant aimé le monde"')
    assert [h[:3] for h in hits] == [(43, 3, 16)]
    assert len(full_core.repo.search(full_core.english.id, "love")) == 281
    assert len(full_core.repo.search(full_core.english.id, "love", limit=50)) == 50


def test_navigation_across_books(full_core):
    s, t = full_core.service, full_core.tids()
    assert s.next_verse(Passage(39, 4, 6, 4, 6), t) == Passage(40, 1, 1, 1, 1)       # Malachi -> Matthew
    assert s.prev_chapter(Passage(40, 1, 1, 1, 1), t) == Passage(39, 4, 1, 4, 1)
    assert s.next_verse(Passage(66, 22, 21, 22, 21), t) is None


def test_long_passages_are_paginated(full_core):
    pages = full_core._build_pages(full_core.service.resolve("Genesis 1", full_core.tids()), full_core.style)
    assert len(pages) > 1
    assert pages[0]["reference"]["en"].startswith("Genesis 1:1")
    assert sum(len(p["columns"][0]["verses"]) for p in pages) == 31
