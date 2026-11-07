"""Recording in the App (PRD R8.1): starting from a Group's "+", Stop opening the editor
with the captured Steps, Continue appending to a Workflow, smart materials found by
name, and the project closing."""

import shutil
from pathlib import Path

import pytest

from shelfplus_app.adapter.fake import FakeAdapter, FakeLayer, FakeResource
from shelfplus_app.app import App
from shelfplus_app.core.menu import MenuAction
from shelfplus_app.core.recording import NO_PROJECT

BUNDLED = Path(__file__).parents[1] / "src" / "ShelfPlus" / "bundled"
RUST = "resource://starter_assets/Rust Iron"
CAVITY = "resource://starter_assets/Cavity Rust"


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
    adapter.project_is_open = True
    adapter.stack.layers = [FakeLayer("Base")]
    adapter.stack.selected = adapter.stack.layers[0]
    adapter.history = ["Open project"]
    adapter.history_index = 1
    return adapter


@pytest.fixture
def app(tmp_path, adapter):
    """The default Layout: "General" with "Save" and "Fill layer + Black mask"."""
    version_dir = tmp_path / "versions" / "0.8.0"
    version_dir.mkdir(parents=True)
    shutil.copy(BUNDLED / "default_layout.json", version_dir / "default_layout.json")
    env = {"version": "0.8.0", "version_dir": str(version_dir), "data_dir": str(tmp_path), "loader_version": 1}
    app = App(env, adapter, FakeView)
    app.start()
    return app


def general(app):
    return app.layout.groups[0]


def add_fill_with_mask(adapter):
    layer = FakeLayer("Fill layer 1", "fill")
    adapter.stack.layers.insert(0, layer)
    adapter.stack.selected = layer
    adapter.push_history("Add fill layer")
    layer.mask = "black"
    adapter.push_history("Add black mask")
    return layer


def test_the_plus_menu_starts_a_recording(app, adapter):
    handler = dict(app.add_button_kinds)["Recorded Workflow"]

    handler(general(app))

    assert app.recording is not None and app.recording_target == "General"
    assert adapter.history_watchers and adapter.hooks  # History, and commands for names
    assert app.workflow_draft is None


def test_stop_opens_the_editor_with_the_captured_steps_and_saving_adds_it(app, adapter):
    app.start_recording(general(app))
    add_fill_with_mask(adapter)
    assert app.recording_steps == 2

    app.stop_recording()

    assert app.recording is None and adapter.history_watchers == [] and adapter.hooks == []
    assert app.workflow_draft.steps == [{"type": "add_layer", "layer": "fill"}, {"type": "add_mask", "background": "black"}]
    button = app.save_workflow()
    assert button in general(app).buttons and button.raw["steps"] == app.layout.groups[0].buttons[-1].raw["steps"]


def test_nothing_recorded_still_opens_the_editor_and_says_so(app, adapter):
    app.start_recording(general(app))

    app.stop_recording()

    assert app.workflow_draft is not None and app.workflow_draft.steps == []
    assert "Nothing was recorded." in app.view.notes


def test_without_a_project_it_does_not_start(app, adapter):
    adapter.project_is_open = False

    app.start_recording(general(app))

    assert app.recording is None and NO_PROJECT in app.view.notes


def test_continue_appends_to_the_workflow_in_the_editor(app, adapter):
    fill_mask = next(b for b in general(app).buttons if b.kind == "workflow" and len(b.raw["steps"]) == 2)
    app.edit_workflow(fill_mask)
    draft = app.workflow_draft

    app.continue_recording()
    assert app.workflow_draft is None and app.recording_target == fill_mask.name
    layer = adapter.stack.layers[0]
    layer.blend = "Multiply"
    adapter.push_history("set blending mode")
    app.stop_recording()

    assert app.workflow_draft is draft
    assert draft.steps[-1] == {"type": "set_blend", "blend": "Multiply"} and len(draft.steps) == 3
    app.save_workflow()
    assert fill_mask.raw["steps"][-1] == {"type": "set_blend", "blend": "Multiply"}


def test_the_commands_clicked_reach_the_recording(app, adapter):
    """Through the App's watcher: duplicate hook calls dropped, Painter's text first line."""
    app.start_recording(general(app))
    layer = FakeLayer("Fill layer 1", "fill")
    adapter.stack.layers.insert(0, layer)
    adapter.push_history("Add fill layer")

    adapter.click_command(MenuAction("", "Add white mask\n\nHold Alt to…"))
    layer.mask = "on"
    adapter.push_history("Add mask")
    app.stop_recording()

    assert app.workflow_draft.steps[-1] == {"type": "add_mask", "background": "white"}


def test_a_smart_material_is_matched_by_name(app, adapter):
    adapter.add_resource(FakeResource(RUST, "Rust Iron", is_brush=False))
    app.start_recording(general(app))
    adapter.stack.layers.insert(0, FakeLayer("Rust Iron", "folder", children=[FakeLayer("Rust", "fill")]))
    adapter.push_history("Drop layer preset")

    app.stop_recording()

    assert app.workflow_draft.steps == [
        {"type": "add_smart", "smart": "material", "resource": RUST, "resource_name": "Rust Iron"}
    ]


def test_an_ambiguous_smart_material_is_left_for_the_user_to_pick(app, adapter):
    adapter.add_resource(FakeResource(RUST, "Rust Iron", is_brush=False))
    adapter.add_resource(FakeResource(RUST + " 2", "Rust Iron", is_brush=False))
    app.start_recording(general(app))
    adapter.stack.layers.insert(0, FakeLayer("Rust Iron", "folder", children=[FakeLayer("Rust", "fill")]))
    adapter.push_history("Drop layer preset")

    app.stop_recording()

    draft = app.workflow_draft
    assert draft.steps[0]["resource"] == "" and draft.problem
    assert any("several" in n for n in app.view.notes)
    assert draft.selected == 0  # selected, so a resource dropped now fills it


def test_a_smart_mask_waits_for_its_resource_and_a_drop_fills_it(app, adapter):
    adapter.add_resource(FakeResource(CAVITY, "Cavity Rust", is_brush=False))
    app.start_recording(general(app))
    layer = FakeLayer("Fill layer 1", "fill")
    adapter.stack.layers.insert(0, layer)
    adapter.push_history("Add fill layer")
    from shelfplus_app.adapter.fake import FakeEffect

    layer.mask = "on"
    layer.effect_nodes.append(FakeEffect("mask", "generator", name="Mask Editor"))
    adapter.push_history("Drop resource on new mask")
    app.stop_recording()

    draft = app.workflow_draft
    assert draft.steps[-1] == {"type": "add_smart", "smart": "mask"}
    assert draft.selected == 1
    app.workflow_resource_drop(CAVITY + "\r\n")
    assert draft.steps[-1]["resource"] == CAVITY and draft.problem is None


def test_the_project_closing_stops_the_recording(app, adapter):
    app.start_recording(general(app))
    add_fill_with_mask(adapter)

    adapter.close_project()

    assert app.recording is None and len(app.workflow_draft.steps) == 2


def test_closing_the_plugin_while_recording_unhooks_everything(app, adapter):
    app.start_recording(general(app))

    app.close()

    assert adapter.history_watchers == [] and adapter.hooks == [] and adapter.closing_watchers == []
