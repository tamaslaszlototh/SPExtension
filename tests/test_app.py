"""The application's lifecycle against the fake adapter and a fake Panel view."""

import json
import shutil
from pathlib import Path

import pytest

from shelfplus_app.adapter.fake import FakeAdapter
from shelfplus_app.app import App

BUNDLED = Path(__file__).parents[1] / "src" / "ShelfPlus" / "bundled"


class FakeView:
    instances = []

    def __init__(self, app):
        self.app = app
        self.widget = object()
        self.shown = None
        self.disposed = False
        FakeView.instances.append(self)

    def show_layout(self, lines, read_only, messages):
        self.shown = (lines, read_only, messages)

    def dispose(self):
        self.disposed = True


@pytest.fixture
def env(tmp_path):
    version_dir = tmp_path / "data" / "versions" / "0.1.0"
    version_dir.mkdir(parents=True)
    shutil.copy(BUNDLED / "default_layout.json", version_dir / "default_layout.json")
    log_path = tmp_path / "data" / "logs" / "shelfplus.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("hello from the log\n", encoding="utf-8")
    return {
        "version": "0.1.0",
        "version_dir": str(version_dir),
        "data_dir": str(tmp_path / "data"),
        "loader_version": 1,
        "log_path": str(log_path),
    }


def make_app(env, adapter=None):
    FakeView.instances.clear()
    return App(env, adapter or FakeAdapter(), FakeView)


def test_first_start_creates_layout_and_panel_files(env):
    make_app(env).start()

    data = Path(env["data_dir"])
    assert json.loads((data / "layout.json").read_text(encoding="utf-8"))["groups"][0]["name"] == "General"
    assert json.loads((data / "panel.json").read_text(encoding="utf-8"))["tileSize"] == 48


def test_start_docks_the_panel_and_lists_the_layout(env):
    adapter = FakeAdapter()
    make_app(env, adapter).start()

    view = FakeView.instances[0]
    assert adapter.docks == [view.widget]
    assert view.shown == (["General", "    Save", "    Fill layer + Black mask"], False, [])


def test_read_only_layout_is_passed_to_the_panel(env):
    data = Path(env["data_dir"])
    (data / "layout.json").write_text(json.dumps({"schemaVersion": 99, "groups": []}), encoding="utf-8")

    make_app(env).start()

    _, read_only, messages = FakeView.instances[0].shown
    assert read_only
    assert "Update Shelf+ to edit this Layout." in messages[0]


def test_close_removes_every_ui_element(env):
    adapter = FakeAdapter()
    app = make_app(env, adapter)
    app.start()

    app.close()

    assert adapter.deleted == adapter.docks
    assert FakeView.instances[0].disposed
    app.close()  # twice is harmless
    assert len(adapter.deleted) == 1


def test_a_failing_start_raises_so_the_loader_can_mark_the_version_bad(env):
    adapter = FakeAdapter(fail_on_dock=True)
    app = make_app(env, adapter)

    with pytest.raises(RuntimeError):
        app.start()

    app.close()
    assert FakeView.instances[0].disposed


def test_diagnostics_names_every_version_and_includes_the_log(env):
    app = make_app(env, FakeAdapter(painter_version="12.2.0", qt_version="6.8.7"))
    app.start()

    text = app.diagnostics_text()

    assert "Shelf+ version: 0.1.0" in text
    assert "Loader version: 1" in text
    assert "Painter version: 12.2.0" in text
    assert "Python version: 3." in text
    assert "Qt version: 6.8.7" in text
    assert text.rstrip().endswith("hello from the log")


def test_diagnostics_survive_a_failing_version_query(env):
    adapter = FakeAdapter()
    adapter.painter_version = lambda: (_ for _ in ()).throw(RuntimeError("no app"))
    app = make_app(env, adapter)

    assert "Painter version: unknown" in app.diagnostics_text()
