"""Drives the real operator window (offscreen) to check the preview / live workflow."""
import time

import pytest

pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import Qt  # noqa: E402
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


@pytest.fixture
def window(qapp, range_core, monkeypatch):
    mini_core = range_core
    from app.ui import main_window
    monkeypatch.setattr(main_window.MainWindow, "_startup", lambda self: None)   # no server / dialogs
    w = main_window.MainWindow(mini_core)
    w.show()
    pump(qapp)
    yield w
    w.close()
    pump(qapp)


def test_reference_lookup_updates_preview_but_not_live(qapp, window):
    core = window.core
    window.nav.ref_edit.setText("Jean 3:16-18")
    window.nav.lookup_reference()
    assert window.sel_label.text() == "John 3:16–18  ·  Jean 3:16-18"
    assert core.controller.output_payload()["mode"] == "clear"         # nothing live yet
    window.go_live()
    assert core.controller.live_passage == window.selected
    window.nav.ref_edit.setText("Acts 8:36-38")
    window.nav.lookup_reference()
    pump(qapp)
    assert core.controller.output_payload()["slide"]["reference"]["en"] == "John 3:16–18"   # unchanged
    assert "LIVE" in window.live_tag.text() and window.live_ref.text() == "John 3:16–18"
    assert "not in TWEB" in window.text_view.toPlainText()           # missing-verse indicator in centre panel


def test_invalid_reference_shows_message(qapp, window):
    window.nav.ref_edit.setText("John 30:1")
    window.nav.lookup_reference()
    assert window.nav.ref_error.isVisibleTo(window)
    assert "chapter 30 does not exist" in window.nav.ref_error.text()
    assert window.selected is None


def test_black_and_restore_buttons(qapp, window):
    window.nav.ref_edit.setText("John 3:16")
    window.nav.lookup_reference()
    window.go_live()
    window.controls.btn_black.click()
    pump(qapp)
    assert window.core.controller.output_payload()["mode"] == "black"
    assert window.live_tag.text() == "■ BLACK"
    window.controls.btn_restore.click()
    pump(qapp)
    assert window.core.controller.output_payload()["mode"] == "live"
    assert not window.controls.btn_black.isChecked()


def test_selection_navigation_and_range(qapp, window):
    window.nav.ref_edit.setText("John 3:16")
    window.nav.lookup_reference()
    window.btn_next_v.click()
    assert window.selected.reference("en") == "John 3:17"
    window.to_spin.setValue(18)
    assert window.selected.reference("en") == "John 3:17–18"
    window.btn_next_ch.click()
    assert window.selected.reference("en") == "John 4:1"
    assert window.core.controller.output_payload()["mode"] == "clear"   # still nothing live


def test_search_and_favourites(qapp, window):
    window.nav.search_edit.setText("eternelle")
    window.nav.search_lang.setCurrentIndex(1)
    window.nav.run_search()
    assert window.nav.results.count() == 1
    window.nav._passage_item(window.nav.results.item(0))
    assert window.selected.reference("fr") == "Jean 3:16"
    window.toggle_favourite()
    assert window.nav.fav_list.count() == 1
    assert window.nav.recent_list.count() >= 1


def test_appearance_controls_change_output_style(qapp, window):
    window.controls.layout_combo.setCurrentIndex(1)
    window.controls.order_combo.setCurrentIndex(1)
    window.controls.en_size.setValue(80)
    st = window.core.controller.output_payload()["style"]
    assert (st["layout"], st["order"], st["en_size"]) == ("stacked", "fr-en", 80)
    assert window.core.settings.get("style")["en_size"] == 80
