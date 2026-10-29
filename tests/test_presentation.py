from app.bible.passage import Passage
from app.presentation.slide import DEFAULT_STYLE, MISSING_TEXT, sanitize_style

JOHN = Passage(43, 3, 16, 3, 18)
ACTS = Passage(44, 8, 36, 8, 38)


def test_preview_never_changes_live(range_core):
    mini_core = range_core
    c = mini_core.controller
    c.go_live(JOHN)
    before = c.output_payload()
    preview = c.preview_payload(ACTS)
    assert preview["slide"]["reference"]["en"] == "Acts 8:36–38"
    after = c.output_payload()
    assert after == before
    assert after["slide"]["reference"]["en"] == "John 3:16–18"


def test_go_live_publishes_to_output(range_core):
    mini_core = range_core
    received = []
    mini_core.controller.add_listener(received.append)
    mini_core.controller.go_live(ACTS)
    assert received[-1]["mode"] == "live"
    assert received[-1]["slide"]["reference"] == {"en": "Acts 8:36–38", "fr": "Actes 8:36-38"}
    # the broadcaster (what OBS reads) has the same state
    _, payload = mini_core.broadcaster.snapshot()
    assert '"Acts 8:36–38"' in payload


def test_bilingual_slide_contents_and_missing_marker(range_core):
    mini_core = range_core
    slide = mini_core.controller.preview_payload(ACTS)["slide"]
    en, fr = slide["columns"]
    assert en["lang"] == "en" and fr["lang"] == "fr"
    assert [v["num"] for v in en["verses"]] == ["36", "37", "38"]
    assert [v["num"] for v in fr["verses"]] == ["36", "37", "38"]
    assert en["verses"][1]["missing"] is True
    assert en["verses"][1]["text"] == MISSING_TEXT["en"].format(n="8:37")
    assert fr["verses"][1]["missing"] is False


def test_black_screen_keeps_and_restores_live_passage(range_core):
    mini_core = range_core
    c = mini_core.controller
    c.go_live(JOHN)
    c.set_black(True)
    out = c.output_payload()
    assert out["mode"] == "black" and out["slide"] is None      # nothing visible
    assert c.live_passage == JOHN                                # but still remembered
    c.restore()
    out = c.output_payload()
    assert out["mode"] == "live" and out["slide"]["reference"]["en"] == "John 3:16–18"


def test_clear_then_restore(range_core):
    mini_core = range_core
    c = mini_core.controller
    c.go_live(JOHN)
    c.clear()
    assert c.output_payload()["mode"] == "clear" and c.live_passage is None
    assert c.restore() is True
    assert c.output_payload()["slide"]["reference"]["en"] == "John 3:16–18"


def test_restore_with_nothing_live(mini_core):
    assert mini_core.controller.restore() is False


def test_next_and_previous_live(mini_core):
    c = mini_core.controller
    c.go_live(Passage(43, 3, 16, 3, 16))
    assert c.next_live() and c.live_passage == Passage(43, 3, 17, 3, 17)
    assert c.next_live() and c.live_passage == Passage(43, 3, 18, 3, 18)
    assert c.next_live() and c.live_passage == Passage(43, 4, 1, 4, 1)
    assert c.prev_live() and c.live_passage == Passage(43, 3, 18, 3, 18)


def test_one_verse_per_slide_pages_then_moves_on(mini_core):
    mini_core.update_style(verses_per_slide=1)
    c = mini_core.controller
    c.go_live(JOHN)
    assert c.output_payload()["slide"]["pages"] == 3
    assert c.output_payload()["slide"]["reference"]["en"] == "John 3:16"
    c.next_live()
    assert c.output_payload()["slide"]["reference"]["en"] == "John 3:17"
    assert c.live_passage == JOHN                              # still the same passage, page 2
    c.next_live()
    c.next_live()                                              # past the last page -> next verse
    assert c.live_passage == Passage(43, 4, 1, 4, 1)
    c.prev_live()
    assert c.output_payload()["slide"]["reference"]["en"] == "John 3:18"   # last page of previous


def test_next_live_while_black_stays_black(mini_core):
    c = mini_core.controller
    c.go_live(Passage(43, 3, 16, 3, 16))
    c.set_black(True)
    c.next_live()
    assert c.output_payload()["mode"] == "black"
    c.restore()
    assert c.output_payload()["slide"]["reference"]["en"] == "John 3:17"


def test_style_changes_apply_to_live_and_persist(mini_core, tmp_path):
    mini_core.controller.go_live(JOHN)
    mini_core.update_style(layout="stacked", order="fr-en", en_size=70, background="#000000")
    out = mini_core.controller.output_payload()
    assert out["style"]["layout"] == "stacked" and out["style"]["order"] == "fr-en"
    assert mini_core.settings.get("style")["en_size"] == 70


def test_sanitize_style_rejects_bad_values():
    st = sanitize_style({"en_size": 5000, "layout": "weird", "background": "red;}", "line_spacing": "x",
                         "font_family": 'Arial"; color:red', "show_en": 0})
    assert st["en_size"] == 200
    assert st["layout"] == DEFAULT_STYLE["layout"]
    assert st["background"] == DEFAULT_STYLE["background"]
    assert st["line_spacing"] == DEFAULT_STYLE["line_spacing"]
    assert '"' not in st["font_family"] and ";" in st["font_family"] or "Arial" in st["font_family"]
    assert st["show_en"] is False


def test_default_is_one_verse_at_a_time_in_a_footer(mini_core):
    st = mini_core.style
    assert (st["verses_per_slide"], st["display_mode"]) == (1, "footer")
    c = mini_core.controller
    c.go_live(JOHN)
    out = c.output_payload()
    assert out["slide"]["reference"]["en"] == "John 3:16" and out["slide"]["pages"] == 3
    assert [len(col["verses"]) for col in out["slide"]["columns"]] == [1, 1]     # one EN + one FR verse
    c.next_live()
    assert c.output_payload()["slide"]["reference"] == {"en": "John 3:17", "fr": "Jean 3:17"}
    # the operator preview also shows one verse
    assert c.preview_payload(ACTS)["slide"]["reference"]["en"] == "Acts 8:36"


def test_footer_settings_are_validated():
    st = sanitize_style({"display_mode": "banner", "footer_height": 5, "footer_opacity": 400})
    assert (st["display_mode"], st["footer_height"], st["footer_opacity"]) == ("footer", 15, 100)
    assert sanitize_style({"display_mode": "fullscreen"})["display_mode"] == "fullscreen"


def test_translation_hidden_gives_single_column(mini_core):
    mini_core.set_translations(mini_core.english.id, None)
    slide = mini_core.controller.preview_payload(JOHN)["slide"]
    assert [c["lang"] for c in slide["columns"]] == ["en"]


def test_default_font_is_bundled_serif(mini_core):
    from pathlib import Path
    assert mini_core.style["font_family"] == "EB Garamond"
    fonts = Path(mini_core.web_root) / "fonts"
    assert (fonts / "EBGaramond.ttf").stat().st_size > 100000
    assert (fonts / "OFL-EBGaramond.txt").is_file()
    css = (Path(mini_core.web_root) / "css" / "presentation.css").read_text(encoding="utf-8")
    assert 'url("../fonts/EBGaramond.ttf")' in css
