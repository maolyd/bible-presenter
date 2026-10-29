"""Renders the OBS output page in a real Chromium (the engine OBS Browser Source uses).

Optional: needs ``pip install playwright`` and ``python -m playwright install chromium``.
Set BIBLE_TEST_CHROMIUM to a Chrome/Chromium executable to use an existing browser.
"""
import os
import socket

import pytest

from app.bible.passage import Passage

sync_api = pytest.importorskip("playwright.sync_api")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        exe = os.environ.get("BIBLE_TEST_CHROMIUM")
        try:
            b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"Chromium not available for Playwright: {exc}")
        yield b
        b.close()


@pytest.fixture
def served(range_core):
    mini_core = range_core
    url = mini_core.start_server(_free_port())
    yield mini_core, url
    mini_core.stop_server()


def _fits(page):
    return page.evaluate("document.getElementById('content-inner').scrollHeight <= "
                         "document.getElementById('content').clientHeight + 1")


@pytest.mark.parametrize("size", [(1920, 1080), (1280, 720), (854, 480), (800, 600)])
def test_live_updates_and_layouts_at_several_resolutions(browser, served, size):
    core, url = served
    page = browser.new_page(viewport={"width": size[0], "height": size[1]})
    page.goto(url)
    page.wait_for_function("window.BiblePresenter !== undefined")

    core.controller.go_live(Passage(43, 3, 16, 3, 18))
    page.wait_for_function("document.getElementById('ref-bottom').textContent.includes('John 3:16')")
    assert page.locator(".grid .lang-en").count() == 3 and page.locator(".grid .lang-fr").count() == 3
    assert _fits(page)
    # stage keeps 16:9 and stays inside the window
    box = page.locator("#stage").bounding_box()
    assert abs(box["width"] / box["height"] - 16 / 9) < 0.01
    assert box["width"] <= size[0] + 1 and box["height"] <= size[1] + 1

    core.update_style(layout="stacked", order="fr-en", show_labels=True)
    page.wait_for_function("document.querySelectorAll('.stack .block').length === 2")
    first = page.locator(".stack .block").first.inner_text()
    assert first.startswith("FRANÇAIS")              # French first, with labels
    assert _fits(page)

    core.controller.set_black(True)
    page.wait_for_function("document.body.classList.contains('black')")
    assert "hidden" in page.locator("#slide").get_attribute("class")
    core.controller.restore()
    page.wait_for_function("!document.body.classList.contains('black')")
    assert "hidden" not in page.locator("#slide").get_attribute("class")
    page.close()


@pytest.mark.parametrize("size", [(1920, 1080), (1280, 720)])
def test_footer_display(browser, served, size):
    core, url = served
    core.update_style(display_mode="footer", verses_per_slide=1, footer_height=34)
    page = browser.new_page(viewport={"width": size[0], "height": size[1]})
    page.goto(url)
    core.controller.go_live(Passage(43, 3, 16, 3, 18))
    page.wait_for_function("document.body.classList.contains('footer') && "
                           "document.getElementById('ref-bottom').textContent.includes('John 3:16')")
    assert page.locator(".grid .lang-en").count() == 1 and page.locator(".grid .lang-fr").count() == 1
    assert _fits(page)
    band = page.locator("#slide").bounding_box()
    assert abs(band["y"] + band["height"] - size[1]) <= 2                  # sits on the bottom edge
    assert abs(band["height"] / size[1] - 0.34) < 0.02                     # 34 % of the screen
    transparent = "rgba(0, 0, 0, 0)"
    assert page.evaluate("getComputedStyle(document.documentElement).backgroundColor") == transparent
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == transparent
    assert page.evaluate("getComputedStyle(document.getElementById('slide')).backgroundColor").startswith("rgba(11, 21, 48, 0.85")
    core.controller.next_live()
    page.wait_for_function("document.getElementById('ref-bottom').textContent.includes('John 3:17')")
    core.controller.set_black(True)                                        # hides the band, camera stays visible
    page.wait_for_function("document.body.classList.contains('black')")
    assert "hidden" in page.locator("#slide").get_attribute("class")
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == transparent
    core.update_style(display_mode="fullscreen")                           # full screen paints the background
    page.wait_for_function("!document.body.classList.contains('footer')")
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") != transparent
    page.close()


def test_output_has_no_operator_controls(browser, served):
    core, url = served
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto(url)
    core.controller.go_live(Passage(44, 8, 36, 8, 38))
    page.wait_for_function("document.querySelectorAll('.missing').length === 1")
    assert page.locator("button, input, select, a, nav, menu").count() == 0
    assert page.evaluate("getComputedStyle(document.body).overflow") == "hidden"   # no scrollbars
    assert "not in this translation" in page.locator(".missing").inner_text()
    page.close()


def test_page_reconnects_after_server_restart(browser, served):
    core, url = served
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    page.goto(url)
    core.controller.go_live(Passage(43, 3, 16, 3, 16))
    page.wait_for_function("document.getElementById('ref-bottom').textContent.includes('John 3:16')")
    port = core.server.port
    core.stop_server()
    core.controller.go_live(Passage(65, 1, 3, 1, 3))      # changed while the server was down
    core.start_server(port)
    page.wait_for_function("document.getElementById('ref-bottom').textContent.includes('Jude 1:3')",
                           timeout=15000)
    page.close()
