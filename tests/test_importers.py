import pytest

from app.bible.importers import ImportFormatError, detect_format, read_bible_bytes, read_bible_file


def test_usfx_reader(fixtures):
    b = read_bible_file(fixtures / "mini_en.usfx.xml")
    assert b.report.format_name.startswith("USFX")
    assert b.language == "en"
    assert b.verses[(43, 3, 16)].startswith("For God so loved the world")
    # footnotes and headings are not verse text
    assert "footnote" not in b.verses[(1, 1, 2)]
    assert "Creation" not in b.verses[(1, 1, 1)]
    # deuterocanonical book skipped, empty verse marker reported (Acts 8:37)
    assert "TOB" in b.report.skipped_books
    assert (44, 8, 37) not in b.verses
    assert "Acts 8:37" in b.report.empty_verses
    assert b.book_count == 4 and not b.is_complete
    assert "Exodus" in b.missing_books()


def test_beblia_reader(fixtures):
    b = read_bible_file(fixtures / "mini_fr.beblia.xml")
    assert detect_format((fixtures / "mini_fr.beblia.xml").read_bytes()) == "beblia"
    assert b.language == "fr"
    assert b.verses[(44, 8, 37)].startswith("Philippe dit")
    assert b.license_text == "Public Domain"


def test_osis_reader_milestones_and_containers(fixtures):
    b = read_bible_file(fixtures / "mini.osis.xml")
    assert b.name == "Test OSIS Bible"
    assert b.code == "TESTOSIS"
    assert b.language == "en"
    assert b.verses[(43, 3, 16)] == "For God so loved the world."      # note removed
    assert b.verses[(43, 3, 17)].startswith("For God didn’t send")


def test_zefania_reader(fixtures):
    b = read_bible_file(fixtures / "mini.zefania.xml")
    assert b.name == "Test Zefania Bible"
    assert b.code == "TESTZEF"
    assert b.language == "fr"
    assert b.verses[(43, 3, 16)] == "Car Dieu a tant aimé le monde qu'il a donné son Fils unique."


def test_vpl_reader_reports_duplicates_and_unknown_books(fixtures):
    b = read_bible_file(fixtures / "mini.vpl.txt")
    assert b.report.format_name.startswith("eBible.org VPL")
    assert b.verse_count == 3
    assert "John 3:16" in b.report.duplicate_references
    assert "XYZ" in b.report.skipped_books


def test_zip_container(fixtures):
    b = read_bible_file(fixtures / "mini_vpl.zip")
    assert b.verse_count == 3
    assert "eng-test_vpl.txt" in b.source_file


def test_damaged_xml_is_rejected(fixtures):
    with pytest.raises(ImportFormatError, match="damaged or incomplete"):
        read_bible_file(fixtures / "broken.xml")


def test_unknown_xml_is_rejected(fixtures):
    with pytest.raises(ImportFormatError, match="not a supported"):
        read_bible_file(fixtures / "not_a_bible.xml")


def test_random_bytes_are_rejected():
    with pytest.raises(ImportFormatError, match="not recognised"):
        read_bible_bytes(b"\x00\x01hello world", "x.bin")


def test_missing_file(tmp_path):
    with pytest.raises(ImportFormatError, match="not found"):
        read_bible_file(tmp_path / "nope.xml")


def test_external_entities_are_not_loaded(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOPSECRET")
    xml = (f'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file://{secret.as_posix()}">]>'
           '<XMLBIBLE><BIBLEBOOK bnumber="1"><CHAPTER cnumber="1"><VERS vnumber="1">a &e; b</VERS>'
           '</CHAPTER></BIBLEBOOK></XMLBIBLE>').encode()
    b = read_bible_bytes(xml, "x.xml")
    assert "TOPSECRET" not in b.verses[(1, 1, 1)]
