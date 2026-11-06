"""Brush buttons in the App (PRD R5) against the fake adapter: dropping, missing presets, clicking."""

import base64
import json
import shutil
from pathlib import Path

import pytest

from shelfplus_app.adapter.fake import FakeAdapter, FakeResource
from shelfplus_app.app import App
from shelfplus_app.core.brush import POLL_MS

BUNDLED = Path(__file__).parents[1] / "src" / "ShelfPlus" / "bundled"
PNG = b"\x89PNG\r\n\x1a\n" + b"tile" + b"IEND\xaeB`\x82"
SMALL_PNG = b"\x89PNG\r\n\x1a\n" + b"deco" + b"IEND\xaeB`\x82"

HARD = FakeResource("resource://starter_assets/Basic Hard", "Basic Hard")
INKER = FakeResource("resource://starter_assets/Kyle Brush Presets/Archive Inker_24", "Archive Inker")
MATERIAL = FakeResource("resource://starter_assets/Bricks", "Bricks", is_brush=False)


class FakeView:
    def __init__(self, app):
        self.app = app
        self.widget = object()
        self.renders = 0
        self.notes = []

    def render(self):
        self.renders += 1

    def notify(self, text):
        self.notes.append(text)

    def dispose(self):
        pass


def brush(bid, url, name):
    return {"id": bid, "kind": "brush", "name": name, "resource": url, "icon": None}


LAYOUT = {
    "schemaVersion": 1,
    "groups": [
        {"id": "g1", "name": "Brushes", "buttons": [brush("b1", HARD.url, "Hard"), brush("b2", "resource://a/Gone", "Gone")]},
        {"id": "g2", "name": "Empty", "buttons": []},
    ],
}


@pytest.fixture
def adapter():
    adapter = FakeAdapter()
    adapter.add_resource(HARD, tooltip=f'<img src="data:image/png;base64,{base64.b64encode(PNG).decode()}">')
    adapter.add_resource(INKER, decoration=SMALL_PNG)
    adapter.add_resource(MATERIAL)
    return adapter


@pytest.fixture
def env(tmp_path):
    version_dir = tmp_path / "versions" / "0.3.0"
    version_dir.mkdir(parents=True)
    shutil.copy(BUNDLED / "default_layout.json", version_dir / "default_layout.json")
    (tmp_path / "layout.json").write_text(json.dumps(LAYOUT), encoding="utf-8")
    return {"version": "0.3.0", "version_dir": str(version_dir), "data_dir": str(tmp_path), "loader_version": 1}


def start(env, adapter):
    app = App(env, adapter, FakeView)
    app.start()
    return app


def saved(env):
    return json.loads((Path(env["data_dir"]) / "layout.json").read_text(encoding="utf-8"))


def uri_list(*urls):
    return "".join(u.replace(" ", "%20") + "?version=abc.resource\r\n" for u in urls)


class TestDropping:
    def test_a_dropped_preset_becomes_a_brush_button_with_its_tooltip_icon(self, env, adapter):
        app = start(env, adapter)

        added = app.add_brushes_from_drop("g2", 0, uri_list(HARD.url))

        assert [b.name for b in added] == ["Basic Hard"]
        raw = saved(env)["groups"][1]["buttons"][0]
        assert raw == {
            "id": added[0].id,
            "kind": "brush",
            "name": "Basic Hard",
            "resource": "resource://starter_assets/Basic Hard",
            "icon": f"icons/{added[0].id}.png",
        }
        assert (Path(env["data_dir"]) / raw["icon"]).read_bytes() == PNG

    def test_several_resources_land_in_order_at_the_drop_position(self, env, adapter):
        app = start(env, adapter)

        app.add_brushes_from_drop("g1", 1, uri_list(INKER.url, HARD.url))

        assert [b["name"] for b in saved(env)["groups"][0]["buttons"]] == ["Hard", "Archive Inker", "Basic Hard", "Gone"]

    def test_without_any_icon_source_the_button_gets_the_generic_icon(self, env, adapter):
        adapter.add_resource(FakeResource("resource://a/Plain", "Plain"))
        app = start(env, adapter)

        (added,) = app.add_brushes_from_drop("g2", 0, uri_list("resource://a/Plain"))

        assert added.icon is None
        assert not (Path(env["data_dir"]) / "icons").exists()

    def test_a_resource_that_is_not_a_brush_is_refused_with_a_message(self, env, adapter):
        app = start(env, adapter)

        assert app.add_brushes_from_drop("g2", 0, uri_list(MATERIAL.url)) == []

        assert saved(env)["groups"][1]["buttons"] == []
        assert app.view.notes == ["“Bricks” is not a brush or tool preset."]

    def test_an_unknown_resource_is_refused_with_a_message(self, env, adapter):
        app = start(env, adapter)

        assert app.add_brushes_from_drop("g2", 0, uri_list("resource://a/Nowhere")) == []

        assert app.view.notes == ["Painter does not know this resource: resource://a/Nowhere"]

    def test_a_drop_without_resources_changes_nothing(self, env, adapter):
        app = start(env, adapter)

        assert app.add_brushes_from_drop("g2", 0, "file:///C:/x.png") == []
        assert app.view.notes == []

    def test_a_read_only_layout_refuses_the_drop(self, env, adapter):
        data = dict(LAYOUT, schemaVersion=99)
        (Path(env["data_dir"]) / "layout.json").write_text(json.dumps(data), encoding="utf-8")
        app = start(env, adapter)

        assert app.add_brushes_from_drop("g2", 0, uri_list(HARD.url)) == []
        assert "Update Shelf+" in app.view.notes[0]


class TestMissingPreset:
    def test_checked_at_load(self, env, adapter):
        app = start(env, adapter)
        hard, gone = app.layout.groups[0].buttons

        assert not app.is_missing(hard)
        assert app.is_missing(gone)

    def test_a_click_only_shows_a_message(self, env, adapter):
        app = start(env, adapter)
        gone = app.layout.groups[0].buttons[1]

        app.run_button(gone)

        assert app.view.notes == ["This brush is not available on this machine: resource://a/Gone"]
        assert adapter.assets_calls == [] and adapter.clicks == []

    def test_a_click_checks_again_and_clears_the_badge_once_it_is_there(self, env, adapter):
        app = start(env, adapter)
        gone = app.layout.groups[0].buttons[1]
        adapter.add_resource(FakeResource("resource://a/Gone", "Gone"))
        renders = app.view.renders

        app.run_button(gone)

        assert not app.is_missing(gone)
        assert app.view.renders == renders + 1
        assert adapter.assets_calls[0] == "open"

    def test_a_click_finds_it_gone_and_shows_the_badge(self, env, adapter):
        app = start(env, adapter)
        hard = app.layout.groups[0].buttons[0]
        del adapter.resources[HARD.url]

        app.run_button(hard)

        assert app.is_missing(hard)
        assert app.view.notes == ["This brush is not available on this machine: resource://starter_assets/Basic Hard"]

    def test_a_lookup_error_at_load_does_not_stop_the_start(self, env, adapter):
        adapter.resource_error = RuntimeError("not ready")
        app = start(env, adapter)

        assert all(app.is_missing(b) for b in app.layout.groups[0].buttons)


class TestClicking:
    def test_a_click_activates_the_brush_in_the_assets_window(self, env, adapter):
        app = start(env, adapter)
        hard = app.layout.groups[0].buttons[0]

        app.run_button(hard)
        adapter.tiles["Basic Hard"] = (0, 0, 70, 70)  # the Assets window's name, not the Button's
        adapter.fire_timers()
        adapter.fire_timers()

        assert adapter.assets_calls == ["open", f"show_in_ui {HARD.url}"]
        assert adapter.timers[0].interval_ms == POLL_MS
        assert adapter.clicks == [(0, 0, 70, 70)]
        assert app.view.notes == []

    def test_a_time_out_shows_its_message(self, env, adapter, monkeypatch):
        clock = [0]
        monkeypatch.setattr("shelfplus_app.core.brush._now_ms", lambda: clock[0])
        app = start(env, adapter)

        app.run_button(app.layout.groups[0].buttons[0])
        clock[0] = 10_000
        adapter.fire_timers()

        assert app.view.notes == ["“Basic Hard” did not appear in the Assets window within 4 seconds."]

    def test_a_second_click_replaces_the_first_activation(self, env, adapter):
        app = start(env, adapter)
        hard = app.layout.groups[0].buttons[0]

        app.run_button(hard)
        app.run_button(hard)

        assert [t.active for t in adapter.timers] == [False, True]

    def test_close_stops_an_activation_in_progress(self, env, adapter):
        app = start(env, adapter)
        app.run_button(app.layout.groups[0].buttons[0])

        app.close()

        assert not adapter.timers[0].active

    def test_an_invalid_button_does_not_run(self, env, adapter):
        data = json.loads(json.dumps(LAYOUT))
        data["groups"][1]["buttons"] = [{"id": "x", "kind": "brush", "name": "Broken"}]
        (Path(env["data_dir"]) / "layout.json").write_text(json.dumps(data), encoding="utf-8")
        app = start(env, adapter)

        app.run_button(app.layout.groups[1].buttons[0])

        assert app.view.notes == ["“Broken” is invalid and cannot run: missing 'resource'."]
        assert adapter.assets_calls == []


def test_the_add_menu_explains_how_to_add_a_brush_button(env, adapter):
    app = start(env, adapter)
    label, handler = app.add_button_kinds[0]

    handler(app.layout.groups[1])

    assert label == "Brush button"
    assert app.view.notes == ["Drag a brush or tool preset from the Assets window onto “Empty”."]
