import pytest

from app.bible.importers import read_bible_file
from app.bible.repository import BibleRepository, DuplicateTranslationError


@pytest.fixture
def repo(tmp_path):
    r = BibleRepository(tmp_path / "bibles.sqlite")
    yield r
    r.close()


def test_import_and_metadata(repo, fixtures):
    tr = repo.import_bible(read_bible_file(fixtures / "mini_en.usfx.xml"), name="Mini", code="MINI", language="en")
    assert tr.book_count == 4 and tr.verse_count == 13 and not tr.is_complete
    assert repo.find_by_code("mini").id == tr.id          # code lookup is case-insensitive
    assert repo.list_translations("en")[0].name == "Mini"
    assert repo.list_translations("fr") == []


def test_duplicate_translation_detected_and_replace(repo, fixtures):
    bible = read_bible_file(fixtures / "mini_en.usfx.xml")
    repo.import_bible(bible, name="Mini", code="MINI", language="en")
    with pytest.raises(DuplicateTranslationError):
        repo.import_bible(bible, name="Mini again", code="MINI", language="en")
    tr = repo.import_bible(bible, name="Mini again", code="MINI", language="en", replace=True)
    assert tr.name == "Mini again"
    assert len(repo.list_translations()) == 1
    assert repo.verse_text(tr.id, 43, 3, 16).startswith("For God so loved")


def test_failed_import_keeps_existing_data(repo, fixtures, monkeypatch):
    good = repo.import_bible(read_bible_file(fixtures / "mini_en.usfx.xml"), name="Good", code="GOOD", language="en")
    bad = read_bible_file(fixtures / "mini_fr.beblia.xml")
    bad.verses[(43, 3, 99)] = None          # NOT NULL constraint fails part-way through the insert
    with pytest.raises(Exception):
        repo.import_bible(bad, name="Bad", code="GOOD", language="fr", replace=True)
    assert [t.code for t in repo.list_translations()] == ["GOOD"]
    assert repo.get_translation(good.id).name == "Good"
    assert repo.verse_text(good.id, 43, 3, 16).startswith("For God so loved")
    assert repo.search(good.id, "loved")      # search index still intact


def test_search_accents_case_and_phrases(repo, fixtures):
    fr = repo.import_bible(read_bible_file(fixtures / "mini_fr.beblia.xml"), name="F", code="F", language="fr")
    en = repo.import_bible(read_bible_file(fixtures / "mini_en.usfx.xml"), name="E", code="E", language="en")
    assert [r[:3] for r in repo.search(fr.id, "eternelle")] == [(43, 3, 16)]    # é ignored
    assert [r[:3] for r in repo.search(fr.id, "ÉTERNELLE")] == [(43, 3, 16)]
    assert [r[:3] for r in repo.search(en.id, "world loved")] == [(43, 3, 16)]  # all words, any order
    assert [r[:3] for r in repo.search(en.id, '"so loved the world"')] == [(43, 3, 16)]
    assert repo.search(en.id, '"world loved"') == []                          # exact phrase only
    assert repo.search(en.id, "   ") == []
    # results are restricted to the requested translation
    assert repo.search(en.id, "monde") == []


def test_search_fallback_without_fts(repo, fixtures):
    en = repo.import_bible(read_bible_file(fixtures / "mini_en.usfx.xml"), name="E", code="E", language="en")
    repo.has_fts = False
    assert [r[:3] for r in repo.search(en.id, "LOVED world")] == [(43, 3, 16)]


def test_delete_translation(repo, fixtures):
    tr = repo.import_bible(read_bible_file(fixtures / "mini_en.usfx.xml"), name="E", code="E", language="en")
    repo.delete_translation(tr.id)
    assert repo.list_translations() == []
    assert repo.books(tr.id) == []


def test_schema_survives_reopen(tmp_path, fixtures):
    path = tmp_path / "b.sqlite"
    r = BibleRepository(path)
    r.import_bible(read_bible_file(fixtures / "mini_en.usfx.xml"), name="E", code="E", language="en")
    r.close()
    r2 = BibleRepository(path)           # migrations run again without destroying data
    assert [t.code for t in r2.list_translations()] == ["E"]
    r2.close()
