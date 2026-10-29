"""Drives the real operator window (offscreen) to check the search / preview / live workflow."""
import time

import pytest

pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import Qt, QUrl  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication.instance() or QApplication([])
    yield app


def pump(app, ms=200):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def _window(qapp, core, monkeypatch):
    from app.ui import main_window
    monkeypatch.setattr(main_window.MainWindow, "_startup", lambda self: None)   # no server / dialogs
    w = main_window.MainWindow(core)
    w.show()
    pump(qapp)
    return w


@pytest.fixture
def window(qapp, range_core, monkeypatch):
    w = _window(qapp, range_core, monkeypatch)
    yield w
    w.close()
    pump(qapp)


@pytest.fixture
def verse_window(qapp, mini_core, monkeypatch):
    """Default settings: one verse at a time."""
    w = _window(qapp, mini_core, monkeypatch)
    yield w
    w.close()
    pump(qapp)


def search(w, text):
    w.search.setText(text)
    w.run_search()


def test_reference_search_updates_preview_but_not_live(qapp, window):
    core = window.core
    search(window, "Jean 3:16-18")
    assert "John 3:16–18" in window.sel_label.text() and "Jean 3:16-18" in window.sel_label.text()
    assert core.controller.output_payload()["mode"] == "clear"         # nothing live yet
    window.go_live()
    assert core.controller.live_passage == window.selected
    search(window, "Acts 8:36-38")
    pump(qapp)
    assert core.controller.output_payload()["slide"]["reference"]["en"] == "John 3:16–18"   # unchanged
    assert window.live_tag.text() == "LIVE" and "John 3:16–18" in window.live_ref.text()
    assert "not in TWEB" in window.text_view.toPlainText()           # missing-verse indicator


def test_invalid_reference_shows_message(qapp, window):
    search(window, "John 30:1")
    assert window.error_label.isVisibleTo(window)
    assert "chapter 30 does not exist" in window.error_label.text()
    assert window.selected is None


def test_words_search_lists_results_in_both_languages(qapp, window):
    search(window, "eternelle")                                       # French word, accents ignored
    assert window.stack.currentIndex() == 1 and window.results.count() == 1
    window._result_chosen(window.results.item(0))
    assert window.selected.reference("fr") == "Jean 3:16"
    assert window.stack.currentIndex() == 0
    search(window, "loved")                                           # English word
    assert window.results.count() == 1


def test_hide_button_and_restore(qapp, window):
    search(window, "John 3:16")
    window.go_live()
    window.btn_black.click()
    pump(qapp)
    assert window.core.controller.output_payload()["mode"] == "black"
    assert window.live_tag.text() == "HIDDEN" and window.btn_black.text() == "Show"
    window.btn_black.click()                                          # click again: shown
    pump(qapp)
    assert window.core.controller.output_payload()["mode"] == "live"
    window.core.controller.clear()
    window.controls.btn_restore.click()                               # Settings → Restore last slide
    assert window.core.controller.output_payload()["mode"] == "live"


def test_one_verse_at_a_time_queue(qapp, verse_window):
    w = verse_window
    search(w, "John 3:16-18")
    assert w.page_label.text() == "verse 1 of 3"
    w.go_live()
    assert w.core.controller.output_payload()["slide"]["reference"]["en"] == "John 3:16"
    assert w.page_label.text() == "verse 2 of 3"                      # next verse queued automatically
    w._verse_clicked(QUrl("verse:3:18"))                              # click verse 18 in the table
    assert w.page_label.text() == "verse 3 of 3"
    w.go_live()
    assert w.core.controller.output_payload()["slide"]["reference"]["en"] == "John 3:18"
    w.next_live()
    assert w.core.controller.live_passage.reference("en") == "John 4:1"


def test_chapter_buttons_favourites_and_chips(qapp, window):
    search(window, "John 3:16")
    window.btn_next_ch.click()
    assert window.selected.reference("en") == "John 4:1"
    window.btn_prev_ch.click()
    assert window.selected.reference("en") == "John 3:16"
    window.toggle_favourite()
    assert window.btn_fav.text() == "★ Saved"
    labels = [window.chips_box.itemAt(i).widget().text() for i in range(window.chips_box.count())]
    assert "★ John 3:16" in labels and "John 4:1" in labels


def test_browse_window_selects_passages(qapp, window):
    window.open_browse()
    nav = window.nav
    for i in range(nav.book_list.count()):
        if nav.book_list.item(i).text().startswith("Jude"):
            nav.book_list.setCurrentRow(i)
    pump(qapp)
    assert window.selected.reference("en") == "Jude 1:1"
    window.browse_dialog.hide()


def test_translation_menu_can_hide_french(qapp, window):
    search(window, "John 3:16")
    window._choose_translation("fr", None)
    assert window.btn_fr.text() == "FR off"
    assert window.core.french is None
    assert "FRANÇAIS" not in window.text_view.toPlainText()


def test_settings_change_output_style(qapp, window):
    window.open_settings()
    c = window.controls
    c.layout_combo.setCurrentIndex(1)
    c.order_combo.setCurrentIndex(1)
    c.en_size.setValue(80)
    st = window.core.controller.output_payload()["style"]
    assert (st["layout"], st["order"], st["en_size"]) == ("stacked", "fr-en", 80)
    assert window.core.settings.get("style")["en_size"] == 80
    window.settings_dialog.hide()
