"""Self-update (PRD R9) wired into the App and the Panel: start-up check, the menu entry,
the non-blocking dialog, and the QtNetwork client."""

import json
import os
import shutil
from pathlib import Path

import pytest

from shelfplus_app.adapter.fake import FakeAdapter
from shelfplus_app.app import App
from shelfplus_app.core.updater import LATEST_URL

from test_updater import VERSION_URL, FakeNetwork, release_json

BUNDLED = Path(__file__).parents[1] / "src" / "ShelfPlus" / "bundled"
NOW = 2_000_000.0


class FakeView:
    def __init__(self, app):
        self.app = app
        self.widget = object()
        self.offers, self.messages, self.busy = [], [], []

    def render(self):
        pass

    def dispose(self):
        pass

    def offer_update(self, offer):
        self.offers.append(offer)

    def show_message(self, text):
        self.messages.append(text)

    def show_busy(self, text):
        self.busy.append(text)


@pytest.fixture
def env(tmp_path):
    version_dir = tmp_path / "versions" / "0.1.0"
    (version_dir / "shelfplus_app").mkdir(parents=True)
    (version_dir / "shelfplus_app" / "__init__.py").write_text("", encoding="utf-8")
    shutil.copy(BUNDLED / "default_layout.json", version_dir / "default_layout.json")
    return {"version": "0.1.0", "version_dir": str(version_dir), "data_dir": str(tmp_path), "loader_version": 1}


def panel_json(env):
    return json.loads((Path(env["data_dir"]) / "panel.json").read_text(encoding="utf-8"))


def test_start_checks_and_records_the_time_in_panel_json(env):
    network = FakeNetwork()
    app = App(env, FakeAdapter(), FakeView, network=network, clock=lambda: NOW)
    app.start()

    assert [r.url for r in network.requests] == [LATEST_URL]
    assert panel_json(env)["updater"]["lastCheck"] == NOW
    network.answer(LATEST_URL, body=release_json())
    network.answer(VERSION_URL, body={"version": "0.2.0", "min_loader": 1})
    assert [o.version for o in app.view.offers] == ["0.2.0"]

    app.skip_update()
    assert panel_json(env)["updater"]["skippedVersion"] == "0.2.0"
    app.close()


def test_start_does_not_check_within_24_hours(env):
    (Path(env["data_dir"]) / "panel.json").write_text(
        json.dumps({"updater": {"lastCheck": NOW - 3600, "skippedVersion": None}}), encoding="utf-8"
    )
    network = FakeNetwork()
    app = App(env, FakeAdapter(), FakeView, network=network, clock=lambda: NOW)
    app.start()

    assert network.requests == []
    app.check_for_updates()
    assert [r.url for r in network.requests] == [LATEST_URL]
    network.answer(LATEST_URL, status=None, error="Network unreachable")
    assert app.view.messages == ["Could not check for updates: Network unreachable."]
    app.close()


def test_close_aborts_the_check(env):
    network = FakeNetwork()
    app = App(env, FakeAdapter(), FakeView, network=network, clock=lambda: NOW)
    app.start()
    app.close()

    assert network.requests[0].aborted


def test_without_a_network_check_for_updates_says_so(env):
    app = App(env, FakeAdapter(), FakeView)
    app.start()
    app.check_for_updates()

    assert app.view.messages == ["Updates cannot be checked in this session."]
    app.close()


# -- the Qt side ---------------------------------------------------------------


@pytest.fixture
def qt_app():
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def panel_app(qt_app, env):
    from shelfplus_app.ui.panel import QtPanelView

    network = FakeNetwork()
    app = App(env, FakeAdapter(), QtPanelView, network=network, clock=lambda: NOW)
    app.start()
    app.test_network = network
    yield app
    app.close()
    qt_app.processEvents()


def offer(app, min_loader=1):
    app.test_network.answer(LATEST_URL, body=release_json(body="**Bold** notes"))
    app.test_network.answer(VERSION_URL, body={"version": "0.2.0", "min_loader": min_loader})
    return app.view.update_dialog


def test_the_panel_menu_has_check_for_updates(panel_app):
    texts = [a.text() for a in panel_app.view.menu.actions()]
    assert texts.index("Check for updates") < texts.index("Copy diagnostics")

    panel_app.view.update_action.trigger()
    assert panel_app.view.status.text() == "Checking for updates…"


def test_the_update_dialog_is_non_blocking_with_three_buttons(panel_app):
    dialog = offer(panel_app)

    assert dialog.isVisible() and not dialog.isModal()
    assert dialog.text.text() == "Shelf+ v0.2.0 is available (you have v0.1.0)."
    assert "Bold" in dialog.notes.toPlainText()
    assert [dialog.main_button.text(), dialog.later_button.text(), dialog.skip_button.text()] == [
        "Update", "Later", "Skip this version"
    ]

    dialog.skip_button.click()
    assert not dialog.isVisible()
    assert panel_app.panel_state["updater"]["skippedVersion"] == "0.2.0"


def test_update_button_starts_the_download(panel_app):
    dialog = offer(panel_app)
    dialog.main_button.click()

    assert [r.url for r in panel_app.test_network.pending][-1].endswith("SHA256SUMS")
    assert panel_app.view.status.text() == "Downloading Shelf+ v0.2.0…"


def test_closing_the_dialog_means_later(panel_app):
    dialog = offer(panel_app)
    dialog.close()

    assert panel_app.updater.offer is None
    assert panel_app.panel_state["updater"]["skippedVersion"] is None


def test_a_reinstall_offer_opens_the_releases_page(panel_app):
    dialog = offer(panel_app, min_loader=2)

    assert dialog.main_button.text() == "Open the Releases page"
    assert "needs a manual reinstall" in dialog.text.text()


def test_messages_are_non_modal_boxes(panel_app):
    panel_app.show_message("Update downloaded; it will be active the next time Painter starts.")

    box = panel_app.view.message_box
    assert box.isVisible() and not box.isModal()


def test_dispose_closes_the_updater_windows(panel_app, qt_app):
    dialog = offer(panel_app)
    panel_app.show_message("hello")
    box = panel_app.view.message_box
    panel_app.view.dispose()
    panel_app.view = None

    assert not dialog.isVisible() and not box.isVisible()


def test_qt_http_reads_a_file_url(qt_app, tmp_path):
    from PySide6 import QtCore

    from shelfplus_app.adapter.network import QtHttp

    path = tmp_path / "hello.txt"
    path.write_bytes(b"hello")
    http = QtHttp("ShelfPlus/test")
    results = []
    http.get(QtCore.QUrl.fromLocalFile(str(path)).toString(), results.append)
    for _ in range(200):
        if results:
            break
        qt_app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 20)
    http.close()

    [response] = results
    assert response.body == b"hello" and response.error is None
