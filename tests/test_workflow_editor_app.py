"""The Workflow editor in the App (PRD R7): opening, saving a new or changed Workflow,
its icon, deleting it, and resources dropped onto the editor."""

import json
import shutil
from pathlib import Path

import pytest

from shelfplus_app.adapter.fake import FakeAdapter, FakeLayer, FakeResource
from shelfplus_app.app import App
from shelfplus_app.core.workflow_draft import template

BUNDLED = Path(__file__).parents[1] / "src" / "ShelfPlus" / "bundled"
EDGES = "resource://starter_assets/Edges"
HARD = "resource://starter_assets/Basic Hard"


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
    adapter.add_resource(FakeResource(EDGES, "Edges", is_brush=False))
    adapter.add_resource(FakeResource(HARD, "Basic Hard"))
    return adapter


@pytest.fixture
def app(tmp_path, adapter):
    """The default Layout: "General" with "Save" and "Fill layer + Black mask"."""
    version_dir = tmp_path / "versions" / "0.7.0"
    version_dir.mkdir(parents=True)
    shutil.copy(BUNDLED / "default_layout.json", version_dir / "default_layout.json")
    env = {"version": "0.7.0", "version_dir": str(version_dir), "data_dir": str(tmp_path), "loader_version": 1}
    app = App(env, adapter, FakeView)
    app.start()
    return app


def saved(app):
    data = json.loads((app.data_dir / "layout.json").read_text(encoding="utf-8"))
    return data["groups"][0]["buttons"]


def named(app, name):
    return next(b for g in app.layout.groups for b in g.buttons if b.name == name)


def test_the_workflow_entry_of_the_plus_menu_opens_an_empty_editor(app):
    handler = dict(app.add_button_kinds)["Workflow button"]

    handler(app.layout.groups[0])

    assert app.workflow_draft is not None and app.workflow_draft.steps == []
    assert app.workflow_draft.button_id is None


def test_a_new_workflow_is_saved_at_the_end_of_its_group_and_runs(app, adapter):
    app.new_workflow(app.layout.groups[0])
    for label in ("Fill layer", "Black mask"):
        app.workflow_draft.add(template(label))
    app.workflow_draft.add(template("Opacity"))
    app.workflow_draft.set_step(2, {"type": "set_opacity", "opacity": {"BaseColor": 50}})

    button = app.save_workflow()

    assert app.workflow_draft is None
    assert saved(app)[-1] == {
        "id": button.id,
        "kind": "workflow",
        "name": "Fill layer + Black mask + Opacity 50%",
        "icon": None,
        "steps": [
            {"type": "add_layer", "layer": "fill"},
            {"type": "add_mask", "background": "black"},
            {"type": "set_opacity", "opacity": {"BaseColor": 50}},
        ],
    }
    app.run_button(button)
    fill = adapter.stack.layers[0]
    assert (fill.kind, fill.mask, fill.opacity) == ("fill", "black", {"BaseColor": 50})


def test_an_incomplete_workflow_is_not_saved(app):
    app.new_workflow(app.layout.groups[0])
    app.workflow_draft.add(template("Fill layer"))
    app.workflow_draft.add(template("Smart mask"))

    assert app.save_workflow() is None

    assert app.workflow_draft is not None
    assert app.view.notes == ["Step 2 (Add smart mask) is incomplete: ⚠ choose resource"]
    assert len(saved(app)) == 2


def test_editing_an_existing_workflow_changes_it_in_place(app):
    fill = named(app, "Fill layer + Black mask")
    app.edit_workflow(fill)
    draft = app.workflow_draft
    assert draft.button_id == fill.id and draft.name_is_automatic
    draft.add(template("Save"))

    app.save_workflow()

    buttons = saved(app)
    assert [b["name"] for b in buttons] == ["Save", "Fill layer + Black mask + Save"]
    assert buttons[1]["id"] == fill.id and buttons[1]["steps"][-1] == {"type": "save"}


def test_moving_a_step_to_the_start_block_is_saved_flat(app):
    app.edit_workflow(named(app, "Fill layer + Black mask"))
    app.workflow_draft.move_up(1)  # Black mask above the Fill layer: the Start block

    app.save_workflow()

    assert saved(app)[1]["steps"] == [{"type": "add_mask", "background": "black"}, {"type": "add_layer", "layer": "fill"}]


def test_an_icon_from_disk_is_copied_to_icons_by_button_id(app):
    app.new_workflow(app.layout.groups[0])
    app.workflow_draft.add(template("Save"))
    app.workflow_draft.icon_png = b"\x89PNG own icon"

    button = app.save_workflow()

    assert button.icon == f"icons/{button.id}.png"
    assert (app.data_dir / button.icon).read_bytes() == b"\x89PNG own icon"


def test_a_changed_icon_replaces_the_old_one_and_reset_goes_back_to_automatic(app):
    save = named(app, "Save")
    app.edit_workflow(save)
    app.workflow_draft.icon_png = b"\x89PNG first"
    app.save_workflow()
    app.edit_workflow(save)
    app.workflow_draft.icon_png = b"\x89PNG second"
    app.save_workflow()
    assert (app.data_dir / "icons" / f"{save.id}.png").read_bytes() == b"\x89PNG second"

    app.edit_workflow(save)
    app.workflow_draft.icon_reset = True
    app.save_workflow()

    assert saved(app)[0]["icon"] is None
    assert not (app.data_dir / "icons" / f"{save.id}.png").exists()


def test_deleting_the_open_workflow_removes_its_button(app):
    save = named(app, "Save")
    app.edit_workflow(save)

    app.delete_workflow()

    assert app.workflow_draft is None
    assert [b["name"] for b in saved(app)] == ["Fill layer + Black mask"]
    assert app.editor.pending_delete.button is save  # the Panel's Undo can bring it back


def test_deleting_a_new_workflow_only_closes_the_editor(app):
    app.new_workflow(app.layout.groups[0])

    app.delete_workflow()

    assert app.workflow_draft is None and len(saved(app)) == 2


def test_a_resource_dropped_on_a_selected_incomplete_step_fills_it(app):
    app.new_workflow(app.layout.groups[0])
    app.workflow_draft.add(template("Fill layer"))
    app.workflow_draft.add(template("Smart mask"))

    app.workflow_resource_drop(f"resource://starter_assets/Edges?version=abc\r\n")

    assert app.workflow_draft.steps[1] == {"type": "add_smart", "smart": "mask", "resource": EDGES, "resource_name": "Edges"}


def test_the_automatic_name_uses_the_dropped_resources_display_name(app, adapter):
    dirt = "resource://starter_assets/mg_dirt/mg_dirt"
    adapter.add_resource(FakeResource(dirt, "Dirt", is_brush=False))
    app.new_workflow(app.layout.groups[0])
    app.workflow_draft.add(template("Fill layer"))
    app.workflow_draft.add(template("Generator on the mask"))

    app.workflow_resource_drop(dirt)
    button = app.save_workflow()

    assert button.name == "Fill layer + Dirt"
    assert saved(app)[-1]["steps"][1]["resource_name"] == "Dirt"


def test_a_dropped_brush_adds_a_brush_step_when_nothing_is_waiting_for_it(app):
    app.new_workflow(app.layout.groups[0])
    app.workflow_draft.add(template("Paint layer"))

    app.workflow_resource_drop(HARD)

    assert app.workflow_draft.steps[-1] == {"type": "select_brush", "resource": HARD, "resource_name": "Basic Hard"}


def test_another_dropped_resource_asks_for_a_step_first(app):
    app.new_workflow(app.layout.groups[0])

    app.workflow_resource_drop(EDGES)

    assert app.workflow_draft.steps == []
    assert app.view.notes == ["Select the Step “Edges” is for, then drop it again."]


def test_use_selected_layers_name(app, adapter):
    assert app.selected_layer_name() == "Base"
    adapter.stack.selected = None
    assert app.selected_layer_name() is None


def test_closing_the_editor_keeps_the_layout(app):
    app.edit_workflow(named(app, "Save"))
    app.workflow_draft.add(template("Fill layer"))

    app.close_workflow_editor()

    assert app.workflow_draft is None and [b["steps"] for b in saved(app)][0] == [{"type": "save"}]


def test_a_brush_dropped_on_a_step_waiting_for_another_resource_is_refused(app):
    app.new_workflow(app.layout.groups[0])
    app.workflow_draft.add(template("Fill layer"))
    app.workflow_draft.add(template("Smart mask"))

    app.workflow_resource_drop(HARD)

    assert "resource" not in app.workflow_draft.steps[1]
    assert app.view.notes == ["“Basic Hard” is a brush. This Step needs another kind of resource."]


def test_a_new_icon_removes_an_old_icon_file_of_another_name(app):
    save = named(app, "Save")
    old = app.data_dir / "icons" / "old.png"
    old.parent.mkdir(exist_ok=True)
    old.write_bytes(b"\x89PNG old")
    save.raw["icon"] = "icons/old.png"
    app.edit_workflow(save)
    app.workflow_draft.icon_png = b"\x89PNG new"

    app.save_workflow()

    assert not old.exists() and saved(app)[0]["icon"] == f"icons/{save.id}.png"


def test_the_resource_picker_searches_painters_resources(app):
    assert [r.gui_name for r in app.search_resources("edg")] == ["Edges"]


def test_the_texture_sets_channels_are_offered_when_painter_knows_them(app, adapter):
    assert app.texture_channels()[:3] == ["BaseColor", "Height", "Roughness"]  # the usual ones
    adapter.texture_channels = ["BaseColor", "Opacity"]

    assert app.texture_channels() == ["BaseColor", "Opacity"]
