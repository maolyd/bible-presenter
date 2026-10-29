import pytest

from app.bible.books import BOOKS, BookLookupError, find_book
from app.bible.reference import ReferenceParseError, parse_reference


def ref(text):
    r = parse_reference(text)
    return (r.book.usfm, r.chapter, r.verse, r.end_chapter, r.end_verse)


@pytest.mark.parametrize("text, expected", [
    ("John 3:16", ("JHN", 3, 16, None, None)),
    ("Jean 3:16", ("JHN", 3, 16, None, None)),
    ("Jean 3.16", ("JHN", 3, 16, None, None)),
    ("Jean 3,16", ("JHN", 3, 16, None, None)),
    ("jn 3:16", ("JHN", 3, 16, None, None)),
    ("  JOHN   3 : 16 ", ("JHN", 3, 16, None, None)),
    ("John 3:16-18", ("JHN", 3, 16, 3, 18)),
    ("John 3:16–18", ("JHN", 3, 16, 3, 18)),
    ("Jean 3.16-18", ("JHN", 3, 16, 3, 18)),
    ("John 3:16-4:2", ("JHN", 3, 16, 4, 2)),
    ("John 3", ("JHN", 3, None, None, None)),
    ("Psalm 23", ("PSA", 23, None, None, None)),
    ("Psaume 23", ("PSA", 23, None, None, None)),
    ("Psaumes 23:1", ("PSA", 23, 1, None, None)),
    ("Ps 23-24", ("PSA", 23, None, 24, None)),
    ("1 John 1:9", ("1JN", 1, 9, None, None)),
    ("1re Jean 1.9", ("1JN", 1, 9, None, None)),
    ("1 Jean 1:9", ("1JN", 1, 9, None, None)),
    ("I John 1:9", ("1JN", 1, 9, None, None)),
    ("First John 1:9", ("1JN", 1, 9, None, None)),
    ("2nd Kings 5:1", ("2KI", 5, 1, None, None)),
    ("2 Rois 5:1", ("2KI", 5, 1, None, None)),
    ("III John 2", ("3JN", 1, 2, None, None)),
    ("Jude 3", ("JUD", 1, 3, None, None)),
    ("Jude 3-5", ("JUD", 1, 3, 1, 5)),
    ("Philémon 6", ("PHM", 1, 6, None, None)),
    ("Esaïe 53:5", ("ISA", 53, 5, None, None)),
    ("Ésaïe 53:5", ("ISA", 53, 5, None, None)),
    ("Isaiah 53:5", ("ISA", 53, 5, None, None)),
    ("Apocalypse 21:4", ("REV", 21, 4, None, None)),
    ("Rev 21:4", ("REV", 21, 4, None, None)),
    ("Cantique des cantiques 2:1", ("SNG", 2, 1, None, None)),
    ("Song of Solomon 2:1", ("SNG", 2, 1, None, None)),
    ("Phil 4:13", ("PHP", 4, 13, None, None)),
    ("Deuter 6:4", ("DEU", 6, 4, None, None)),         # unique prefix
    ("Actes 2:38", ("ACT", 2, 38, None, None)),
    ("Jacques 1:5", ("JAS", 1, 5, None, None)),
    ("Matthieu 5:3", ("MAT", 5, 3, None, None)),
])
def test_valid_references(text, expected):
    assert ref(text) == expected


@pytest.mark.parametrize("text, message", [
    ("Hezekiah 1:1", "not a recognised"),
    ("Jo 3:16", "could match several books"),
    ("es 1:1", "could match several books"),
    ("John 3:18-16", "before its start"),
    ("John 0:1", "start at 1"),
    ("", "Please type a book name"),
    ("3:16", "Could not understand"),
])
def test_invalid_references(text, message):
    with pytest.raises(ReferenceParseError) as exc:
        parse_reference(text)
    assert message in str(exc.value)


def test_every_english_and_french_name_resolves_to_same_book():
    for b in BOOKS:
        assert find_book(b.name_en) is b
        assert find_book(b.name_fr) is b
        assert find_book(b.usfm) is b
        assert find_book(b.osis) is b
        for alias in b.aliases:
            try:
                assert find_book(alias) is b, alias
            except BookLookupError:
                pass   # alias shared by two books is deliberately ambiguous


def test_english_and_french_references_match():
    pairs = [("John 3:16", "Jean 3:16"), ("Genesis 1:1", "Genèse 1:1"), ("Revelation 22:21", "Apocalypse 22:21"),
             ("Song of Songs 1:1", "Cantique des Cantiques 1:1"), ("1 Kings 3:9", "1 Rois 3:9"),
             ("Ezekiel 37:1", "Ézéchiel 37:1"), ("Zephaniah 3:17", "Sophonie 3:17"), ("Obadiah 1", "Abdias 1")]
    for en, fr in pairs:
        assert ref(en) == ref(fr)


def test_book_table_is_complete():
    assert len(BOOKS) == 66
    assert [b.number for b in BOOKS] == list(range(1, 67))
    assert len({b.usfm for b in BOOKS}) == 66
    assert sum(1 for b in BOOKS if b.testament == "OT") == 39
    assert sum(b.chapters for b in BOOKS) == 1189
