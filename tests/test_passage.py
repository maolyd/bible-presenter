import pytest

from app.bible.passage import Passage
from app.bible.reference import ReferenceParseError


def test_resolve_single_range_chapter(mini_core):
    s, t = mini_core.service, mini_core.tids()
    assert s.resolve("John 3:16", t) == Passage(43, 3, 16, 3, 16)
    assert s.resolve("Jean 3:16-18", t) == Passage(43, 3, 16, 3, 18)
    assert s.resolve("John 3", t) == Passage(43, 3, 16, 3, 18)          # whole chapter (as stored)
    assert s.resolve("John 3:17-4:1", t) == Passage(43, 3, 17, 4, 1)
    assert s.resolve("Jude 2", t) == Passage(65, 1, 2, 1, 2)


@pytest.mark.parametrize("text, msg", [
    ("John 25:1", "chapter 25 does not exist"),
    ("John 3:40", "verse 40 does not exist"),
    ("John 3:16-40", "verse 40 does not exist"),
    ("Exodus 1:1", "not in the selected translation"),
])
def test_resolve_errors(mini_core, text, msg):
    with pytest.raises(ReferenceParseError, match=msg):
        mini_core.service.resolve(text, mini_core.tids())


def test_resolve_without_translation(mini_core):
    with pytest.raises(ReferenceParseError, match="No Bible translation"):
        mini_core.service.resolve("John 3:16", [])


def test_next_and_previous_verse_cross_chapter_and_book(mini_core):
    s, t = mini_core.service, mini_core.tids()
    assert s.next_verse(Passage(43, 3, 16, 3, 16), t) == Passage(43, 3, 17, 3, 17)
    assert s.next_verse(Passage(43, 3, 16, 3, 18), t) == Passage(43, 4, 1, 4, 1)       # end of range -> next chapter
    assert s.next_verse(Passage(43, 4, 1, 4, 1), t) == Passage(44, 8, 36, 8, 36)       # next book
    assert s.prev_verse(Passage(43, 4, 1, 4, 1), t) == Passage(43, 3, 18, 3, 18)
    assert s.prev_verse(Passage(43, 3, 16, 3, 16), t) == Passage(1, 2, 1, 2, 1)        # previous book
    assert s.prev_verse(Passage(1, 1, 1, 1, 1), t) is None
    assert s.next_verse(Passage(65, 1, 3, 1, 3), t) is None


def test_next_and_previous_chapter(mini_core):
    s, t = mini_core.service, mini_core.tids()
    assert s.next_chapter(Passage(43, 3, 17, 3, 17), t) == Passage(43, 4, 1, 4, 1)
    assert s.prev_chapter(Passage(43, 4, 1, 4, 1), t) == Passage(43, 3, 16, 3, 16)
    assert s.next_chapter(Passage(1, 1, 1, 1, 1), t) == Passage(1, 2, 1, 2, 1)


def test_alignment_marks_verse_missing_in_one_translation(mini_core):
    en, fr = mini_core.english, mini_core.french
    rows = mini_core.service.aligned(Passage(44, 8, 36, 8, 38), [en.id, fr.id])
    assert [(r.chapter, r.verse) for r in rows] == [(8, 36), (8, 37), (8, 38)]
    v37 = rows[1]
    assert v37.texts[en.id] is None                                # English lacks Acts 8:37
    assert v37.texts[fr.id].startswith("Philippe dit")
    # the following verses stay paired with their own numbers, never shifted
    assert rows[2].texts[en.id].startswith("He commanded the chariot")
    assert rows[2].texts[fr.id].startswith("Il fit arrêter le char")


def test_references_in_both_languages():
    p = Passage(19, 23, 1, 23, 6)
    assert p.reference("en") == "Psalm 23:1–6"
    assert p.reference("fr") == "Psaume 23:1-6"
    assert Passage(43, 3, 16, 4, 2).reference("en") == "John 3:16–4:2"
    assert Passage(43, 3, 16, 3, 16).reference("fr") == "Jean 3:16"
    assert Passage.from_dict(p.to_dict()) == p
