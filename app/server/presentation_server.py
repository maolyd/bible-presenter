"""Local web server for the OBS Browser Source.

Design choices:
* Python standard library only (``http.server``), no extra dependency.
* Bound to 127.0.0.1 by default, so other computers on the network cannot reach it.
* Read-only: it serves the presentation page, its CSS/JS, the current state
  (``/api/state``) and a live update stream (``/events``, Server-Sent Events).
  There is no control endpoint at all — the operator window changes the
  presentation directly inside the application process.
* Server-Sent Events reconnect automatically in OBS/Chromium when the
  connection drops; the page also polls ``/api/state`` as a fallback.
"""
from __future__ import annotations

import errno
import json
import mimetypes
import os
import socket
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
HEARTBEAT_SECONDS = 15


class ServerStartError(RuntimeError):
    pass


class Broadcaster:
    """Holds the latest output state and wakes up every connected page when it changes."""

    def __init__(self):
        self._cond = threading.Condition()
        # Lets the page tell "older state from this run" apart from "new run after an app restart".
        self.instance = uuid.uuid4().hex
        self._payload = json.dumps({"type": "state", "version": 0, "instance": self.instance,
                                    "mode": "clear", "slide": None, "style": {}})
        self._seq = 0          # increases on every publish (including reloads)
        self._reload_seq = -1
        self._closed = False

    def publish(self, state: dict) -> None:
        data = json.dumps({**state, "instance": self.instance}, ensure_ascii=False)
        with self._cond:
            self._payload = data
            self._seq += 1
            self._cond.notify_all()

    def request_reload(self) -> None:
        """Ask every connected output page to reload itself (used by "Reconnect output")."""
        with self._cond:
            self._reload_seq = self._seq + 1
            self._seq += 1
            self._cond.notify_all()

    def snapshot(self) -> tuple[int, str]:
        with self._cond:
            return self._seq, self._payload

    def wait(self, last_seq: int, timeout: float) -> tuple[int, str, bool]:
        """Block until something newer than last_seq is published, or timeout."""
        with self._cond:
            if self._seq == last_seq and not self._closed:
                self._cond.wait(timeout)
            reload = self._reload_seq == self._seq and self._seq != last_seq
            return self._seq, self._payload, reload

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify_all()

    def reopen(self) -> None:
        with self._cond:
            self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR would let two programs share a port silently;
    # we want a clear "port in use" error instead.
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def _make_handler(web_root: Path, broadcaster: Broadcaster, allowed_hosts: set[str]):
    web_root = web_root.resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "BiblePresenter"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):   # keep the console quiet
            pass

        # -- security helpers --------------------------------------------------
        def _host_ok(self) -> bool:
            # Rejects requests whose Host header is not this machine (DNS-rebinding protection).
            host = (self.headers.get("Host") or "").lower()
            return host in allowed_hosts

        def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _error(self, code: int, msg: str):
            self._send(code, msg.encode(), "text/plain; charset=utf-8")

        # -- methods -------------------------------------------------------------
        def do_HEAD(self):
            self.do_GET()

        def do_POST(self):
            self._error(405, "This server is read-only.")

        do_PUT = do_DELETE = do_PATCH = do_POST

        def do_GET(self):
            if not self._host_ok():
                return self._error(403, "Forbidden host.")
            path = urlsplit(self.path).path
            if path in ("/", "/presentation", "/presentation/", "/presentation.html"):
                return self._file(web_root / "presentation.html")
            if path == "/api/state":
                _, payload = broadcaster.snapshot()
                return self._send(200, payload.encode("utf-8"), "application/json; charset=utf-8")
            if path == "/events":
                return self._events()
            if path == "/health":
                return self._send(200, b'{"ok": true}', "application/json")
            if path.startswith(("/css/", "/js/", "/fonts/")):
                target = (web_root / path.lstrip("/")).resolve()
                if web_root not in target.parents:
                    return self._error(404, "Not found")
                return self._file(target)
            return self._error(404, "Not found")

        def _file(self, target: Path):
            if not target.is_file():
                return self._error(404, "Not found")
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript",):
                ctype += "; charset=utf-8"
            self._send(200, target.read_bytes(), ctype)

        def _events(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.close_connection = True
            seq, payload = broadcaster.snapshot()
            try:
                self.wfile.write(b"retry: 1000\n")
                self._write_event(payload)
                while not broadcaster.closed:
                    new_seq, payload, reload = broadcaster.wait(seq, HEARTBEAT_SECONDS)
                    if broadcaster.closed:
                        break
                    if new_seq != seq:
                        seq = new_seq
                        if reload:
                            self._write_event(json.dumps({"type": "reload"}))
                        else:
                            self._write_event(payload)
                    else:
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                pass   # page closed or OBS source removed

        def _write_event(self, payload: str):
            self.wfile.write(b"data: " + payload.encode("utf-8") + b"\n\n")
            self.wfile.flush()

    return Handler


class PresentationServer:
    def __init__(self, web_root: str | Path, broadcaster: Broadcaster, host: str = DEFAULT_HOST,
                 port: int = DEFAULT_PORT):
        self.web_root = Path(web_root)
        self.broadcaster = broadcaster
        self.host = host
        self.port = port
        self._httpd: _Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._httpd is not None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/presentation"

    def start(self) -> None:
        if self.running:
            return
        if not (self.web_root / "presentation.html").is_file():
            raise ServerStartError(f"The presentation page is missing from {self.web_root}.")
        if not (1024 <= int(self.port) <= 65535):
            raise ServerStartError("The port must be a number between 1024 and 65535.")
        allowed = {f"{h}:{self.port}" for h in ("127.0.0.1", "localhost", self.host)}
        handler = _make_handler(self.web_root, self.broadcaster, allowed)
        self.broadcaster.reopen()
        try:
            self._httpd = _Server((self.host, int(self.port)), handler)
        except OSError as exc:
            self._httpd = None
            winerr = getattr(exc, "winerror", None)
            if exc.errno == errno.EACCES or winerr == 10013:
                raise ServerStartError(
                    f"Windows does not allow this program to use port {self.port} (it may be reserved by the "
                    f"system). Choose a different port in the Server section, for example {int(self.port) + 1}.") from exc
            if exc.errno in (errno.EADDRINUSE, getattr(errno, "WSAEADDRINUSE", 10048)) or winerr == 10048:
                raise ServerStartError(
                    f"Port {self.port} is already in use by another program (or another copy of this app). "
                    f"Choose a different port in the Server section (for example {int(self.port) + 1}), "
                    "then update the URL in OBS.") from exc
            raise ServerStartError(f"The presentation server could not start: {exc}") from exc
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="presentation-server",
                                        kwargs={"poll_interval": 0.25}, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._httpd:
            return
        self.broadcaster.close()          # ends every open /events stream
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread:
            self._thread.join(timeout=5)
        self._httpd = None
        self._thread = None


def port_is_free(port: int, host: str = DEFAULT_HOST) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False
