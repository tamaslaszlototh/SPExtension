"""The Workflow editor inside the Panel (PRD R7), offscreen over a real App and the fake
adapter: opening it, building a Workflow by hand, snap-back, confirmations, the icon."""

import json
import os
import shutil
from pathlib import Path

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6 import QtCore, QtGui  # noqa: E402

from shelfplus_app.adapter.fake import FakeAdapter, FakeLayer, FakeResource  # noqa: E402
from shelfplus_app.app import App  # noqa: E402
from shelfplus_app.ui.panel import QtPanelView  # noqa: E402

BUNDLED = Path(__file__).parents[1] / "src" / "ShelfPlus" / "bundled"
DIRT = "resource://starter_assets/Dirt"


@pytest.fixture
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def adapter():
    adapter = FakeAdapter()
    adapter.project_is_open = True
    adapter.stack.layers = [FakeLayer("Base")]
    adapter.stack.selected = adapter.stack.layers[0]
    adapter.add_resource(FakeResource(DIRT, "Dirt", is_brush=False))
    return adapter


@pytest.fixture
def app(qt_app, tmp_path, adapter):
    """The default Layout: "General" with "Save" and "Fill layer + Black mask"."""
    version_dir = tmp_path / "versions" / "0.7.0"
    version_dir.mkdir(parents=True)
    shutil.copy(BUNDLED / "default_layout.json", version_dir / "default_layout.json")
    env = {"version": "0.7.0", "version_dir": str(version_dir), "data_dir": str(tmp_path), "loader_version": 1}
    app = App(env, adapter, QtPanelView)
    app.start()
    app.view.widget.resize(280, 700)
    app.view.widget.show()
    qt_app.processEvents()
    yield app
    app.close()
    qt_app.processEvents()


@pytest.fixture
def answer(monkeypatch):
    """Every Yes/No question gets this answer; the questions asked are recorded."""
    asked = []
    state = {"answer": QtWidgets.QMessageBox.StandardButton.Yes}

    def question(parent, title, text, *args, **kwargs):
        asked.append(text)
        return state["answer"]

    monkeypatch.setattr(QtWidgets.QMessageBox, "question", question)
    state["asked"] = asked
    return state


def saved(app):
    data = json.loads((app.data_dir / "layout.json").read_text(encoding="utf-8"))
    return data["groups"][0]["buttons"]


def open_new(app, qt_app):
    app.new_workflow(app.layout.groups[0])
    qt_app.processEvents()
    return app.view.workflow_editor


def tiles(app):
    return app.view.group_boxes[0].tiles


def test_the_editor_replaces_the_groups_while_it_is_open(app, qt_app):
    editor = open_new(app, qt_app)

    assert editor.isVisibleTo(app.view.widget) and not app.view.scroll.isVisibleTo(app.view.widget)
    assert editor.visible_rows() == ["At the end of the Workflow"]
    assert not editor.save_button.isEnabled()

    editor.cancel_button.click()
    qt_app.processEvents()
    assert app.view.workflow_editor is None and app.view.scroll.isVisibleTo(app.view.widget)


def test_building_fill_black_mask_dirt_opacity_by_hand(app, qt_app, adapter):
    editor = open_new(app, qt_app)
    for label in ("Fill layer", "Black mask", "Generator on the mask", "Opacity"):
        editor.add_step(label)

    assert editor.visible_rows() == [
        "Fill layer",
        "├ Black mask",
        "├ Generator — on the mask  ⚠ choose resource",
        "└ Opacity 100% — BaseColor",
        "At the end of the Workflow",
    ]
    assert not editor.save_button.isEnabled()

    editor.select_step(2)
    editor.drop_resource(DIRT)  # dragged from the Assets window onto the selected Step
    editor.select_step(3)
    box, spin = editor.fields["opacity"]["BaseColor"]
    spin.setValue(50)

    assert editor.name_edit.text() == "Fill layer + Black mask + Dirt + Opacity 50%"
    assert editor.save_button.isEnabled()
    editor.save_button.click()
    qt_app.processEvents()

    assert app.view.workflow_editor is None
    button = app.layout.groups[0].buttons[-1]
    assert button.name == "Fill layer + Black mask + Dirt + Opacity 50%"
    app.run_button(button)
    fill = adapter.stack.layers[0]
    assert (fill.mask, fill.effects, fill.opacity) == ("black", [("mask", "generator", DIRT)], {"BaseColor": 50})


def test_a_double_click_opens_the_editor_and_does_not_run_the_workflow(app, qt_app, adapter):
    save = tiles(app)[0]
    save.click()  # the first click of the double-click
    event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonDblClick, QtCore.QPointF(5, 5), QtCore.QPointF(5, 5),
        QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier,
    )
    QtWidgets.QApplication.sendEvent(save, event)
    qt_app.processEvents()

    assert app.workflow_draft is not None and app.workflow_draft.button_id == "b3f80d16"
    assert not app.view.run_timer.isActive() and adapter.saves == 0


def test_a_single_click_runs_the_workflow_once_no_second_click_follows(app, qt_app, adapter):
    save = tiles(app)[0]

    save.click()
    assert adapter.saves == 0
    app.view.run_timer.timeout.emit()

    assert adapter.saves == 1 and app.workflow_draft is None


def test_moving_opacity_into_the_start_block(app, qt_app):
    app.edit_workflow(app.layout.groups[0].buttons[1])  # Fill layer + Black mask
    qt_app.processEvents()
    editor = app.view.workflow_editor
    assert editor.visible_rows() == ["Fill layer", "└ Black mask", "At the end of the Workflow"]

    editor.row_widgets[1].buttons["up"].click()

    assert editor.visible_rows() == [
        "Start: the layer selected when it runs",
        "└ Black mask",
        "Fill layer",
        "At the end of the Workflow",
    ]


def test_the_start_block_title_shows_while_dragging(app, qt_app):
    app.edit_workflow(app.layout.groups[0].buttons[1])
    qt_app.processEvents()
    editor = app.view.workflow_editor

    editor.show_start_row(True)

    assert editor.visible_rows()[0] == "Start: the layer selected when it runs"


def test_save_dragged_above_a_layer_step_snaps_back(app, qt_app):
    editor = open_new(app, qt_app)
    editor.add_step("Fill layer")
    editor.add_step("Save")
    before = list(editor.draft.steps)

    editor.drop_row(1, 1)  # above the Fill layer
    qt_app.processEvents()

    assert editor.draft.steps == before
    assert app.view.status.text() == "A Step cannot go there; it was put back."


def test_a_headers_x_asks_only_when_its_block_has_steps(app, qt_app, answer):
    editor = open_new(app, qt_app)
    for label in ("Fill layer", "Black mask", "Paint layer"):
        editor.add_step(label)
    answer["answer"] = QtWidgets.QMessageBox.StandardButton.No

    editor.row_widgets[0].buttons["delete"].click()
    assert len(editor.draft.steps) == 3 and answer["asked"] == ["Delete “Fill layer” and the 1 Step(s) acting on it?"]

    editor.row_widgets[2].buttons["delete"].click()  # the Paint layer: nothing below it
    assert [s["layer"] for s in editor.draft.steps if s["type"] == "add_layer"] == ["fill"]
    assert len(answer["asked"]) == 1


def test_the_trash_deletes_the_workflow_after_yes(app, qt_app, answer):
    app.edit_workflow(app.layout.groups[0].buttons[0])
    qt_app.processEvents()
    editor = app.view.workflow_editor

    answer["answer"] = QtWidgets.QMessageBox.StandardButton.No
    editor.trash.click()
    assert app.workflow_draft is not None and len(saved(app)) == 2

    answer["answer"] = QtWidgets.QMessageBox.StandardButton.Yes
    editor.trash.click()
    qt_app.processEvents()
    assert answer["asked"] == ["Delete “Save”?", "Delete “Save”?"]
    assert app.workflow_draft is None and [b["name"] for b in saved(app)] == ["Fill layer + Black mask"]
    assert app.view.undo_button.isVisibleTo(app.view.widget)


def test_select_layer_uses_the_selected_layers_name(app, qt_app):
    editor = open_new(app, qt_app)
    editor.add_step("Select layer by name")
    assert not editor.save_button.isEnabled()

    editor.fields["use_selected"].click()

    assert editor.fields["name"].text() == "Base"
    assert editor.draft.steps == [{"type": "select_layer", "name": "Base"}]
    assert editor.save_button.isEnabled()


def test_an_icon_from_disk_is_copied_to_the_icons_folder(app, qt_app, tmp_path):
    image = QtGui.QImage(512, 300, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor("#ff0000"))
    path = tmp_path / "mine.jpg"
    image.save(str(path))
    app.edit_workflow(app.layout.groups[0].buttons[0])
    qt_app.processEvents()

    app.view.workflow_editor.set_icon_file(path)
    app.view.workflow_editor.save_button.click()
    qt_app.processEvents()

    icon = app.data_dir / "icons" / "b3f80d16.png"
    stored = QtGui.QImage(str(icon))
    assert saved(app)[0]["icon"] == "icons/b3f80d16.png"
    assert (stored.width(), stored.height()) == (256, 150)  # scaled down, kept as PNG


def test_ui_steps_are_marked_as_part_of_the_end_section(app, qt_app):
    editor = open_new(app, qt_app)
    for label in ("Paint layer", "Save", "Brush"):
        editor.add_step(label)

    assert editor.visible_rows() == ["Paint layer", "At the end of the Workflow", "├ Save", "└ Brush  ⚠ choose resource"]


# -- a new layer's channels and content ---------------------------------------------

RUST = "resource://starter_assets/Rust"


@pytest.fixture
def picks(monkeypatch, adapter):
    """The resource picker returns these, in order (as if the user chose them)."""
    adapter.add_resource(FakeResource(RUST, "Rust", is_brush=False))
    queue = []
    asked = []

    def pick(editor, title, query=""):
        asked.append(title)
        return adapter.resources[queue.pop(0)] if queue else None

    monkeypatch.setattr("shelfplus_app.ui.workflow_editor.WorkflowEditor._pick_resource", pick)
    return queue


def settled(qt_app):
    qt_app.processEvents()  # the settings are rebuilt after the signal that changed them
    qt_app.processEvents()


def test_a_fill_layer_gets_its_channels_and_per_channel_content(app, qt_app, adapter, picks):
    adapter.texture_channels = ["BaseColor", "Height", "Roughness", "Normal"]
    editor = open_new(app, qt_app)
    editor.add_step("Fill layer")
    editor.select_step(0)

    editor.fields["channels"]["Height"].setChecked(False)
    settled(qt_app)
    editor.fields["content"].setCurrentText("Per channel")
    settled(qt_app)
    editor.fields["value_Roughness"].setValue(0.7)
    editor.fields["kind_Normal"].setCurrentText("Resource")
    settled(qt_app)
    assert editor.draft.problem == "Step 1 (Add Fill layer) is incomplete: ⚠ choose resource"
    picks.append(DIRT)
    editor.fields["choose_source_Normal"].click()
    settled(qt_app)

    step = editor.draft.steps[0]
    assert step == {
        "type": "add_layer",
        "layer": "fill",
        "channels": ["BaseColor", "Roughness", "Normal"],
        "sources": {
            "BaseColor": {"color": "#808080"},
            "Roughness": {"value": 0.7},
            "Normal": {"resource": DIRT, "resource_name": "Dirt"},
        },
    }
    editor.save_button.click()
    qt_app.processEvents()
    app.run_button(app.layout.groups[0].buttons[-1])
    layer = adapter.stack.layers[0]
    assert layer.channels == ["BaseColor", "Roughness", "Normal"] and layer.sources["Normal"] == {"resource": DIRT}


def test_one_material_for_a_fill_layer_is_chosen_from_the_picker(app, qt_app, picks):
    editor = open_new(app, qt_app)
    editor.add_step("Fill layer")
    editor.select_step(0)
    editor.fields["content"].setCurrentText("One material")
    settled(qt_app)
    assert not editor.save_button.isEnabled()

    picks.append(RUST)
    editor.fields["choose_material"].click()
    settled(qt_app)

    assert editor.draft.steps[0]["material"] == {"resource": RUST, "resource_name": "Rust"}
    assert editor.visible_rows()[0] == "Fill layer: Rust"
    assert editor.save_button.isEnabled()


def test_a_paint_layer_has_channels_but_no_content(app, qt_app):
    editor = open_new(app, qt_app)
    editor.add_step("Paint layer")
    editor.select_step(0)

    assert "channels" in editor.fields and "content" not in editor.fields


def test_a_generator_is_chosen_from_the_picker(app, qt_app, picks):
    editor = open_new(app, qt_app)
    editor.add_step("Fill layer")
    editor.add_step("Generator on the mask")
    editor.select_step(1)

    picks.append(DIRT)
    editor.fields["choose_resource"].click()
    settled(qt_app)

    assert editor.draft.steps[1]["resource"] == DIRT and editor.visible_rows()[1] == "└ Dirt — generator on the mask"


def test_the_resource_picker_lists_matches_by_name(app, qt_app):
    from shelfplus_app.ui.resource_picker import ResourcePicker

    picker = ResourcePicker(app, "Choose", "dir")

    assert picker.rows() == ["Dirt"] and picker.chosen().url == DIRT
    picker.search.setText("nothing like it")
    picker.run_search()
    assert picker.rows() == [] and not picker.ok_button.isEnabled()
    picker.deleteLater()


def test_the_choose_button_shows_the_chosen_resource_and_still_chooses(app, qt_app, adapter, picks):
    editor = open_new(app, qt_app)
    editor.add_step("Fill layer")
    editor.select_step(0)
    editor.fields["content"].setCurrentText("Per channel")
    settled(qt_app)
    editor.fields["kind_Normal"].setCurrentText("Resource")
    settled(qt_app)
    assert editor.fields["choose_source_Normal"].text() == "Choose…"
    assert "source_Normal" not in editor.fields  # no text box next to it

    picks.append(DIRT)
    editor.fields["choose_source_Normal"].click()
    settled(qt_app)
    assert editor.fields["choose_source_Normal"].text() == "Dirt"

    picks.append(RUST)  # it still opens the list
    editor.fields["choose_source_Normal"].click()
    settled(qt_app)
    assert editor.fields["choose_source_Normal"].text() == "Rust"
    assert editor.draft.steps[0]["sources"]["Normal"] == {"resource": RUST, "resource_name": "Rust"}


def test_a_resource_dropped_on_the_choose_button_is_chosen(app, qt_app, picks):
    editor = open_new(app, qt_app)
    editor.add_step("Fill layer")
    editor.select_step(0)
    editor.fields["content"].setCurrentText("One material")
    settled(qt_app)

    assert editor.fields["choose_material"].accepts(f"{RUST}?version=abc\r\n")
    editor.fields["choose_material"].drop_text(f"{RUST}?version=abc\r\n")
    settled(qt_app)

    assert editor.draft.steps[0]["material"] == {"resource": RUST, "resource_name": "Rust"}
    assert editor.fields["choose_material"].text() == "Rust"


def test_a_brush_dropped_on_a_choose_button_for_another_kind_is_refused(app, qt_app, adapter, picks):
    adapter.add_resource(FakeResource("resource://a/Hard", "Hard"))
    editor = open_new(app, qt_app)
    editor.add_step("Fill layer")
    editor.add_step("Generator on the mask")
    editor.select_step(1)

    editor.fields["choose_resource"].drop_text("resource://a/Hard")
    settled(qt_app)

    assert "resource" not in editor.draft.steps[1]
    assert app.view.notice.text() == "“Hard” is a brush. This setting needs another kind of resource."


def test_per_channel_values_follow_each_channels_range_and_start(app, qt_app, adapter):
    adapter.texture_channels = ["BaseColor", "Height", "Roughness", "Normal"]
    editor = open_new(app, qt_app)
    editor.add_step("Fill layer")
    editor.select_step(0)

    editor.fields["content"].setCurrentText("Per channel")
    settled(qt_app)

    height = editor.fields["value_Height"]
    assert (height.minimum(), height.maximum(), height.value()) == (-1, 1, 0)
    roughness = editor.fields["value_Roughness"]
    assert (roughness.minimum(), roughness.maximum()) == (0, 1)
    assert editor.fields["colour_Normal"].text() == "#8080ff"
    height.setValue(-0.4)
    assert editor.draft.steps[0]["sources"]["Height"] == {"value": -0.4} and editor.draft.problem is None


def test_number_fields_keep_the_number_off_their_buttons(app, qt_app):
    editor = open_new(app, qt_app)
    editor.add_step("Fill layer")
    editor.add_step("Opacity")
    editor.select_step(0)
    editor.fields["content"].setCurrentText("Per channel")
    settled(qt_app)

    def margins(spin):
        m = spin.lineEdit().textMargins()
        return m.left(), m.right()

    assert margins(editor.fields["value_Roughness"]) == (6, 6)
    editor.select_step(1)  # the settings are rebuilt for the Opacity Step
    assert margins(editor.fields["opacity"]["BaseColor"][1]) == (6, 6)


def test_a_fill_on_the_layer_has_the_fill_layer_settings(app, qt_app, adapter):
    adapter.texture_channels = ["BaseColor", "Roughness"]
    editor = open_new(app, qt_app)
    editor.add_step("Fill layer")
    editor.add_step("Fill on the layer")
    editor.select_step(1)

    assert set(editor.fields["channels"]) == {"BaseColor", "Roughness"}
    editor.fields["content"].setCurrentText("Per channel")
    settled(qt_app)
    editor.fields["value_Roughness"].setValue(0.8)

    assert editor.draft.steps[1] == {
        "type": "add_effect", "effect": "fill", "target": "layer",
        "sources": {"BaseColor": {"color": "#808080"}, "Roughness": {"value": 0.8}},
    }


def test_a_fill_on_the_mask_takes_one_value_or_one_resource(app, qt_app, picks):
    editor = open_new(app, qt_app)
    editor.add_step("Fill layer")
    editor.add_step("Black mask")
    editor.add_step("Fill on the mask")
    editor.select_step(2)
    assert "channels" not in editor.fields

    editor.fields["content"].setCurrentText("Value")
    settled(qt_app)
    editor.fields["value_mask"].setValue(0.25)
    assert editor.draft.steps[2]["source"] == {"value": 0.25}

    editor.fields["content"].setCurrentText("Resource")
    settled(qt_app)
    assert not editor.save_button.isEnabled()  # waiting for its resource
    picks.append(DIRT)
    editor.fields["choose_source"].click()
    settled(qt_app)
    assert editor.draft.steps[2]["source"] == {"resource": DIRT, "resource_name": "Dirt"}
    assert editor.save_button.isEnabled()


def test_moving_a_fill_between_layer_and_mask_drops_the_content_that_does_not_fit(app, qt_app):
    editor = open_new(app, qt_app)
    editor.add_step("Fill layer")
    editor.add_step("Fill on the mask")
    editor.select_step(1)
    editor.fields["content"].setCurrentText("Value")
    settled(qt_app)

    editor.fields["target"].setCurrentText("layer")
    settled(qt_app)

    assert editor.draft.steps[1] == {"type": "add_effect", "effect": "fill", "target": "layer"}
    assert "channels" in editor.fields
