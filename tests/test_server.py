import json
import re
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest

from app.bible.passage import Passage
from app.server.presentation_server import ServerStartError, port_is_free


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def running(range_core):
    mini_core = range_core
    port = free_port()
    mini_core.start_server(port)
    yield mini_core, f"http://127.0.0.1:{port}"
    mini_core.stop_server()


def get(url, headers=None, data=None):
    req = urllib.request.Request(url, headers=headers or {}, data=data)
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, r.headers, r.read()


def test_start_serves_page_and_assets(running):
    core, base = running
    status, headers, body = get(base + "/presentation")
    assert status == 200 and b"js/presentation.js" in body
    assert get(base + "/css/presentation.css")[1]["Content-Type"].startswith("text/css")
    assert get(base + "/js/presentation.js")[0] == 200
    state = json.loads(get(base + "/api/state")[2])
    assert state["mode"] == "clear"


def test_server_binds_to_localhost_only(running):
    core, _ = running
    assert core.server.host == "127.0.0.1"
    assert core.server._httpd.server_address[0] == "127.0.0.1"


def test_go_live_is_visible_to_obs(running):
    core, base = running
    core.controller.go_live(Passage(43, 3, 16, 3, 18))
    state = json.loads(get(base + "/api/state")[2])
    assert state["mode"] == "live"
    assert state["slide"]["reference"]["fr"] == "Jean 3:16-18"


def test_read_only_and_host_checks(running):
    _, base = running
    with pytest.raises(urllib.error.HTTPError) as e:
        get(base + "/api/state", data=b"{}")
    assert e.value.code == 405
    with pytest.raises(urllib.error.HTTPError) as e:
        get(base + "/api/state", headers={"Host": "attacker.example:80"})
    assert e.value.code == 403
    with pytest.raises(urllib.error.HTTPError) as e:
        get(base + "/css/../../app/core.py")
    assert e.value.code == 404
    with pytest.raises(urllib.error.HTTPError) as e:
        get(base + "/js/%2e%2e/%2e%2e/main.py")
    assert e.value.code == 404


def _read_events(base, count, timeout=6):
    """Collect `count` SSE data messages from /events."""
    resp = urllib.request.urlopen(base + "/events", timeout=timeout)
    out = []
    while len(out) < count:
        line = resp.readline().decode()
        if line.startswith("data: "):
            out.append(json.loads(line[6:]))
    resp.close()
    return out


def test_live_synchronisation_over_sse(running):
    core, base = running
    results = {}
    t = threading.Thread(target=lambda: results.setdefault("events", _read_events(base, 4)))
    t.start()
    time.sleep(0.4)
    core.controller.go_live(Passage(43, 3, 16, 3, 16))
    time.sleep(0.2)
    core.controller.set_black(True)
    time.sleep(0.2)
    core.controller.restore()
    t.join(8)
    modes = [e["mode"] for e in results["events"]]
    assert modes == ["clear", "live", "black", "live"]
    assert results["events"][-1]["slide"]["reference"]["en"] == "John 3:16"


def test_reconnect_request_reaches_pages(running):
    core, base = running
    results = {}
    t = threading.Thread(target=lambda: results.setdefault("events", _read_events(base, 2)))
    t.start()
    time.sleep(0.4)
    core.broadcaster.request_reload()
    t.join(8)
    assert results["events"][1] == {"type": "reload"}


def test_port_conflict_gives_clear_error(mini_core):
    port = free_port()
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", port))
    blocker.listen(1)
    try:
        assert not port_is_free(port)
        with pytest.raises(ServerStartError, match=f"Port {port} is already in use"):
            mini_core.start_server(port)
        assert not mini_core.server.running
    finally:
        blocker.close()
    mini_core.start_server(port)          # works once the port is free again
    assert mini_core.server.running
    mini_core.stop_server()


def test_stop_releases_port_and_closes_streams(mini_core):
    port = free_port()
    mini_core.start_server(port)
    base = f"http://127.0.0.1:{port}"
    resp = urllib.request.urlopen(base + "/events", timeout=5)
    resp.readline()
    start = time.time()
    mini_core.stop_server()
    assert time.time() - start < 3
    assert not mini_core.server.running
    with pytest.raises(OSError):
        get(base + "/health")
    resp.close()
    mini_core.start_server(port)          # restart on the same port
    assert get(base + "/health")[0] == 200
    mini_core.stop_server()


def test_invalid_port(mini_core):
    with pytest.raises(ServerStartError, match="between 1024 and 65535"):
        mini_core.start_server(80)


def test_presentation_page_works_offline(mini_core):
    """The output page must not load anything from the internet."""
    web = mini_core.web_root
    for f in [web / "presentation.html", web / "css" / "presentation.css", web / "js" / "presentation.js"]:
        text = f.read_text(encoding="utf-8")
        assert not re.search(r"(src|href)\s*=\s*[\"']https?://", text), f
        assert "@import" not in text and "fonts.googleapis" not in text
