"""The QtNetwork client of the updater against a local HTTP server (no internet needed).

GitHub's asset links answer 302 to another host; the client must follow it.
"""

import http.server
import os
import threading
import time

import pytest

QtCore = pytest.importorskip("PySide6.QtCore")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from shelfplus_app.adapter.network import QtHttp  # noqa: E402


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.seen.append((self.path, self.headers.get("User-Agent"), self.headers.get("Accept")))
        if self.path.startswith("/redirect/"):
            hops = int(self.path.rsplit("/", 1)[1])
            self.send_response(302)
            self.send_header("Location", f"/redirect/{hops - 1}" if hops > 1 else "/asset")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path == "/asset":
            body = b"asset bytes"
            self.send_response(200)
        else:
            body = b"nope"
            self.send_response(404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    httpd.seen = []
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def fetch(qt_app, url, **kwargs):
    http_client = QtHttp("ShelfPlus/test")
    results = []
    http_client.get(url, results.append, **kwargs)
    deadline = time.monotonic() + 15
    while not results and time.monotonic() < deadline:
        qt_app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 20)
        time.sleep(0.005)  # test-only wait: the server answers on its own thread
    http_client.close()
    assert len(results) == 1
    return results[0]


def base(server):
    return f"http://127.0.0.1:{server.server_address[1]}"


def test_follows_a_302_redirect(qt_app, server):
    response = fetch(qt_app, base(server) + "/redirect/1")

    assert (response.status, response.body, response.error) == (200, b"asset bytes", None)
    assert [p for p, _, _ in server.seen] == ["/redirect/1", "/asset"]


def test_follows_several_redirects(qt_app, server):
    response = fetch(qt_app, base(server) + "/redirect/3")

    assert (response.status, response.body) == (200, b"asset bytes")


def test_sends_user_agent_and_accept(qt_app, server):
    fetch(qt_app, base(server) + "/asset", accept="application/vnd.github+json")

    assert server.seen == [("/asset", "ShelfPlus/test", "application/vnd.github+json")]


def test_an_http_error_has_its_status(qt_app, server):
    response = fetch(qt_app, base(server) + "/missing")

    assert response.status == 404 and response.error


def test_too_many_redirects_fail(qt_app, server):
    response = fetch(qt_app, base(server) + "/redirect/30")

    assert response.error and response.status != 200
