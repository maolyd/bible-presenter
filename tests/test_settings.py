from app.core import AppCore
from app.storage.settings_store import RECENT_LIMIT, SettingsStore


def test_values_persist_after_reopen(tmp_path):
    path = tmp_path / "s.sqlite"
    s = SettingsStore(path)
    s.set("style", {"layout": "stacked", "en_size": 72})
    s.set("server_port", 9000)
    s.close()
    s2 = SettingsStore(path)
    assert s2.get("style") == {"layout": "stacked", "en_size": 72}
    assert s2.get("server_port") == 9000
    assert s2.get("missing", "default") == "default"
    s2.close()


def test_theme_persists_through_app_restart(tmp_path):
    core = AppCore(data_dir=tmp_path, bundled_dir=tmp_path / "none")
    core.update_style(background="#112233", text_color="#ffeedd", layout="stacked", order="fr-en")
    core.close()
    core2 = AppCore(data_dir=tmp_path, bundled_dir=tmp_path / "none")
    st = core2.style
    assert (st["background"], st["text_color"], st["layout"], st["order"]) == ("#112233", "#ffeedd", "stacked", "fr-en")
    assert core2.controller.output_payload()["style"]["background"] == "#112233"
    core2.close()


def test_saved_style_is_upgraded_to_one_verse_footer_once(tmp_path):
    from app.storage.settings_store import SettingsStore as S
    old = S(tmp_path / "settings.sqlite")            # a style saved by the previous version
    old.set("style", {"layout": "stacked", "verses_per_slide": 0, "en_size": 70})
    old.close()
    core = AppCore(data_dir=tmp_path, bundled_dir=tmp_path / "none")
    st = core.style
    assert (st["verses_per_slide"], st["display_mode"]) == (1, "footer")
    assert (st["layout"], st["en_size"]) == ("stacked", 70)        # other choices are kept
    core.update_style(verses_per_slide=0, display_mode="fullscreen")   # operator changes it back
    core.close()
    core2 = AppCore(data_dir=tmp_path, bundled_dir=tmp_path / "none")
    assert (core2.style["verses_per_slide"], core2.style["display_mode"]) == (0, "fullscreen")  # not re-upgraded
    core2.close()


def test_favourites(tmp_path):
    s = SettingsStore(tmp_path / "s.sqlite")
    p = {"book": 43, "start_chapter": 3, "start_verse": 16, "end_chapter": 3, "end_verse": 16}
    s.add_favourite(p, "John 3:16")
    s.add_favourite(p, "John 3:16")          # no duplicates
    assert s.is_favourite(p)
    assert s.favourites() == [(p, "John 3:16")]
    s.remove_favourite(p)
    assert s.favourites() == [] and not s.is_favourite(p)


def test_recent_is_ordered_deduplicated_and_limited(tmp_path):
    s = SettingsStore(tmp_path / "s.sqlite")
    for v in range(1, RECENT_LIMIT + 6):
        s.add_recent({"book": 43, "start_chapter": 3, "start_verse": v, "end_chapter": 3, "end_verse": v}, f"v{v}")
    s.add_recent({"book": 43, "start_chapter": 3, "start_verse": 10, "end_chapter": 3, "end_verse": 10}, "v10")
    labels = [label for _, label in s.recent()]
    assert len(labels) == RECENT_LIMIT
    assert labels[0] == "v10"
    assert labels.count("v10") == 1
    s.clear_recent()
    assert s.recent() == []
