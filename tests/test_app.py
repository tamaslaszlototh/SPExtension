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
        self.renders = 0
        self.disposed = False
        FakeView.instances.append(self)

    def render(self):
        self.renders += 1

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


def test_start_docks_the_panel_and_shows_the_layout(env):
    adapter = FakeAdapter()
    app = make_app(env, adapter)
    app.start()

    view = FakeView.instances[0]
    assert adapter.docks == [view.widget]
    assert view.renders == 1
    assert [(g.name, [b.name for b in g.buttons]) for g in app.layout.groups] == [
        ("General", ["Save", "Fill layer + Black mask"])
    ]
    assert app.editor.layout is app.layout
    assert not app.read_only and app.messages == []


def test_read_only_layout_is_passed_to_the_panel(env):
    data = Path(env["data_dir"])
    (data / "layout.json").write_text(json.dumps({"schemaVersion": 99, "groups": []}), encoding="utf-8")

    app = make_app(env)
    app.start()

    assert app.read_only and app.editor.read_only
    assert "Update Shelf+ to edit this Layout." in app.messages[0]


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


def panel_json(env):
    return json.loads((Path(env["data_dir"]) / "panel.json").read_text(encoding="utf-8"))


class TestViewState:
    def test_collapsing_a_group_is_saved_in_panel_json(self, env):
        app = make_app(env)
        app.start()
        group_id = app.layout.groups[0].id

        app.set_group_collapsed(group_id, True)
        assert app.is_collapsed(group_id)
        assert panel_json(env)["collapsedGroups"] == [group_id]

        app.set_group_collapsed(group_id, False)
        assert not app.is_collapsed(group_id)
        assert panel_json(env)["collapsedGroups"] == []

    def test_tile_size_and_labels_are_saved_in_panel_json(self, env):
        app = make_app(env)
        app.start()

        app.set_tile_size(64)
        app.set_show_labels(True)

        assert panel_json(env)["tileSize"] == 64
        assert panel_json(env)["showLabels"] is True

    def test_any_whole_tile_size_from_40_to_80_is_accepted(self, env):
        app = make_app(env)
        app.start()

        app.set_tile_size(52)

        assert panel_json(env)["tileSize"] == 52

    @pytest.mark.parametrize("size", [39, 81, 52.5])
    def test_a_tile_size_outside_40_to_80_is_refused(self, env, size):
        app = make_app(env)
        app.start()

        with pytest.raises(ValueError):
            app.set_tile_size(size)
        assert panel_json(env)["tileSize"] == 48

    def test_a_tile_size_not_saved_yet_is_saved_on_close(self, env):
        app = make_app(env)
        app.start()

        app.set_tile_size(60, save=False)
        assert app.panel_state["tileSize"] == 60
        assert panel_json(env)["tileSize"] == 48

        app.close()
        assert panel_json(env)["tileSize"] == 60

    def test_view_state_survives_a_restart(self, env):
        app = make_app(env)
        app.start()
        group_id = app.layout.groups[0].id
        app.set_group_collapsed(group_id, True)
        app.set_tile_size(40)
        app.set_show_labels(True)
        app.close()

        again = make_app(env)
        again.start()

        assert again.is_collapsed(group_id)
        assert again.panel_state["tileSize"] == 40
        assert again.panel_state["showLabels"] is True


def test_close_ends_a_pending_undo_and_deletes_the_icon(env):
    data = Path(env["data_dir"])
    app = make_app(env)
    app.start()
    button = app.layout.groups[0].buttons[0]
    button.raw["icon"] = "icons/x.png"
    (data / "icons").mkdir()
    (data / "icons" / "x.png").write_bytes(b"png")
    app.editor.delete_button(button)

    app.close()

    assert not (data / "icons" / "x.png").exists()


def test_icon_path_is_the_file_in_the_data_folder_or_none(env):
    data = Path(env["data_dir"])
    app = make_app(env)
    app.start()
    button = app.layout.groups[0].buttons[0]
    assert app.icon_path(button) is None

    button.raw["icon"] = "icons/x.png"
    assert app.icon_path(button) is None  # missing file: the automatic icon is used
    (data / "icons").mkdir()
    (data / "icons" / "x.png").write_bytes(b"png")
    assert app.icon_path(button) == data / "icons" / "x.png"
