"""Smart material buttons (issue #47) against the fake adapter: dropping, clicking,
missing smart materials, and Recording."""

import base64
import json
import shutil
from pathlib import Path

import pytest

from shelfplus_app.adapter.fake import FakeAdapter, FakeResource
from shelfplus_app.app import App
from shelfplus_app.core.layout import button_problem

BUNDLED = Path(__file__).parents[1] / "src" / "ShelfPlus" / "bundled"
PNG = b"\x89PNG\r\n\x1a\n" + b"rust" + b"IEND\xaeB`\x82"

RUST = FakeResource("resource://starter_assets/Rust Iron", "Rust Iron", is_brush=False, kind="Smart material")
HARD = FakeResource("resource://starter_assets/Basic Hard", "Basic Hard")
BRICKS = FakeResource("resource://starter_assets/Bricks", "Bricks", is_brush=False, kind="Material")


def smart(bid, url, name):
    return {"id": bid, "kind": "smart_material", "name": name, "resource": url, "icon": None}


LAYOUT = {
    "schemaVersion": 1,
    "groups": [
        {"id": "g1", "name": "Smart", "buttons": [smart("s1", RUST.url, "Rust Iron"), smart("s2", "resource://a/Gone", "Gone")]},
        {"id": "g2", "name": "Empty", "buttons": []},
    ],
}


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


@pytest.fixture
def adapter():
    adapter = FakeAdapter()
    adapter.add_resource(RUST, tooltip=f'<img src="data:image/png;base64,{base64.b64encode(PNG).decode()}">')
    adapter.add_resource(HARD)
    adapter.add_resource(BRICKS)
    return adapter


@pytest.fixture
def env(tmp_path):
    version_dir = tmp_path / "versions" / "0.9.0"
    version_dir.mkdir(parents=True)
    shutil.copy(BUNDLED / "default_layout.json", version_dir / "default_layout.json")
    (tmp_path / "layout.json").write_text(json.dumps(LAYOUT), encoding="utf-8")
    return {"version": "0.9.0", "version_dir": str(version_dir), "data_dir": str(tmp_path), "loader_version": 1}


def start(env, adapter, loaded=True):
    app = App(env, adapter, FakeView)
    app.start()
    if loaded:
        adapter.finish_loading()
    return app


def saved(env):
    return json.loads((Path(env["data_dir"]) / "layout.json").read_text(encoding="utf-8"))


def uri_list(*urls):
    return "".join(u.replace(" ", "%20") + "?version=abc.resource\r\n" for u in urls)


class TestLayout:
    def test_a_smart_material_button_is_valid_with_its_resource(self):
        assert button_problem(smart("s1", RUST.url, "Rust Iron")) is None

    def test_a_smart_material_button_without_a_resource_is_invalid(self):
        assert button_problem({"id": "s1", "kind": "smart_material", "name": "Rust Iron"}) == "missing 'resource'"


class TestDropping:
    def test_a_dropped_smart_material_becomes_a_button_with_its_assets_icon(self, env, adapter):
        app = start(env, adapter)

        (added,) = app.add_buttons_from_drop("g2", 0, uri_list(RUST.url))

        raw = saved(env)["groups"][1]["buttons"][0]
        assert raw == {
            "id": added.id,
            "kind": "smart_material",
            "name": "Rust Iron",
            "resource": "resource://starter_assets/Rust Iron",
            "icon": f"icons/{added.id}.png",
        }
        assert (Path(env["data_dir"]) / raw["icon"]).read_bytes() == PNG

    def test_a_mixed_drop_adds_brushes_and_smart_materials_in_order_and_skips_the_rest(self, env, adapter):
        app = start(env, adapter)

        app.add_buttons_from_drop("g2", 0, uri_list(RUST.url, BRICKS.url, HARD.url))

        buttons = saved(env)["groups"][1]["buttons"]
        assert [(b["kind"], b["name"]) for b in buttons] == [("smart_material", "Rust Iron"), ("brush", "Basic Hard")]
        assert app.view.notes == ["“Bricks” is not a brush, tool preset or smart material."]


def button(app, bid):
    return next(b for g in app.layout.groups for b in g.buttons if b.id == bid)


@pytest.fixture
def project(adapter):
    from shelfplus_app.adapter.fake import FakeLayer

    adapter.project_is_open = True
    base = FakeLayer("Base")
    adapter.stack.layers = [base, FakeLayer("Below")]
    adapter.stack.selected = base
    return adapter


class TestClicking:
    def test_a_click_puts_the_smart_material_above_the_selected_layer_and_selects_it(self, env, project):
        app = start(env, project)

        app.run_button(button(app, "s1"))

        assert [layer.name for layer in project.stack.layers] == ["Rust Iron", "Base", "Below"]
        assert project.stack.selected is project.stack.layers[0]
        assert len(project.stack.scopes) == 1  # one History entry
        assert app.view.notes == []

    def test_inside_a_folder_it_goes_into_the_same_folder(self, env, project):
        from shelfplus_app.adapter.fake import FakeLayer

        inner = FakeLayer("Inner")
        project.stack.layers = [FakeLayer("Folder", "folder", children=[inner])]
        project.stack.selected = inner
        app = start(env, project)

        app.run_button(button(app, "s1"))

        assert [layer.name for layer in project.stack.layers[0].children] == ["Rust Iron", "Inner"]

    def test_with_no_layer_selected_it_goes_on_top_of_the_stack(self, env, project):
        project.stack.selected = None
        app = start(env, project)

        app.run_button(button(app, "s1"))

        assert [layer.name for layer in project.stack.layers] == ["Rust Iron", "Base", "Below"]

    def test_without_a_project_it_asks_for_one(self, env, adapter):
        app = start(env, adapter)

        app.run_button(button(app, "s1"))

        assert app.view.notes == ["Open a project first."]


class TestMissing:
    def test_a_missing_smart_material_is_badged_once_painter_has_loaded(self, env, adapter):
        app = start(env, adapter, loaded=False)
        assert not app.is_missing(button(app, "s2"))  # not yet: Painter may still be loading

        adapter.finish_loading()

        assert app.is_missing(button(app, "s2")) and not app.is_missing(button(app, "s1"))

    def test_clicking_it_says_so_and_changes_nothing(self, env, project):
        app = start(env, project)

        app.run_button(button(app, "s2"))

        assert app.view.notes == ["This smart material is not available on this machine: resource://a/Gone"]
        assert [layer.name for layer in project.stack.layers] == ["Base", "Below"]
        assert project.stack.scopes == []

    def test_clicking_it_while_painter_is_still_loading_asks_to_wait(self, env, project):
        project.loading = True
        app = start(env, project, loaded=False)

        app.run_button(button(app, "s2"))

        assert app.view.notes == ["Painter is still loading its smart materials. Try again in a moment."]
        assert not app.is_missing(button(app, "s2"))


class TestRecording:
    @pytest.fixture
    def recording(self, env, project):
        project.history = ["Open project"]
        project.history_index = 1
        app = start(env, project)
        app.start_recording(app.layout.groups[1])
        return app

    def test_a_click_while_recording_records_a_complete_smart_material_step(self, recording, project):
        recording.run_button(button(recording, "s1"))
        project.push_history(project.stack.scopes[-1])  # Painter's History row of the scope

        recording.stop_recording()

        assert recording.workflow_draft.steps == [
            {"type": "add_smart", "smart": "material", "resource": RUST.url, "resource_name": "Rust Iron"}
        ]
        assert recording.workflow_draft.problem is None

    def test_a_click_that_changed_nothing_does_not_make_the_next_own_row_recorded(self, recording, project):
        from shelfplus_app.core.recording import OWN_WORKFLOW

        recording.run_button(button(recording, "s2"))  # missing: nothing is put in
        project.push_history("Shelf+: Add smart material")  # a Workflow of that name, say

        recording.stop_recording()

        assert OWN_WORKFLOW in recording.view.notes

    def test_own_workflows_are_still_not_recorded(self, recording, project):
        from shelfplus_app.core.recording import OWN_WORKFLOW

        recording.run_button(button(recording, "s1"))
        project.push_history("Shelf+: Fill layer + Black mask")  # not the smart material's row

        recording.stop_recording()

        assert OWN_WORKFLOW in recording.view.notes


class TestDraggingOut:
    def test_a_smart_material_tile_carries_its_resource_like_an_assets_drag(self, env, adapter):
        from shelfplus_app.core.brush import resource_urls_from_drop

        app = start(env, adapter)

        uri_list = app.drag_uri_list(button(app, "s1"))

        assert uri_list == "resource://starter_assets/Rust%20Iron\r\n"
        assert resource_urls_from_drop(uri_list) == [RUST.url]  # read back as a drop onto Painter

    def test_a_missing_smart_material_can_only_be_dragged_within_the_panel(self, env, adapter):
        app = start(env, adapter)

        assert app.is_missing(button(app, "s2")) and app.drag_uri_list(button(app, "s2")) is None

    def test_other_buttons_carry_nothing_out_of_the_panel(self, env, adapter):
        app = start(env, adapter)
        (brush,) = app.add_buttons_from_drop("g2", 0, uri_list(HARD.url))

        assert app.drag_uri_list(brush) is None
