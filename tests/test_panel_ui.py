"""The Panel's Qt view, offscreen, over a real App with the fake adapter."""

import json
import os
import shutil
from pathlib import Path

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import QByteArray, QMimeData, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QDropEvent  # noqa: E402

from shelfplus_app.adapter.fake import FakeAdapter  # noqa: E402
from shelfplus_app.app import App  # noqa: E402
from shelfplus_app.ui.panel import QtPanelView, Tile  # noqa: E402

BUNDLED = Path(__file__).parents[1] / "src" / "ShelfPlus" / "bundled"


def workflow(bid, name):
    return {"id": bid, "kind": "workflow", "name": name, "icon": None, "steps": [{"type": "save"}]}


LAYOUT = {
    "schemaVersion": 1,
    "groups": [
        {"id": "g1", "name": "General", "buttons": [workflow(f"a{i}", f"Button {i}") for i in range(6)]},
        {"id": "g2", "name": "Layers", "buttons": [workflow("b0", "Fill"), workflow("b1", "Paint")]},
        {"id": "g3", "name": "Empty", "buttons": []},
    ],
}


@pytest.fixture
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def app(qt_app, tmp_path):
    version_dir = tmp_path / "versions" / "0.1.0"
    version_dir.mkdir(parents=True)
    shutil.copy(BUNDLED / "default_layout.json", version_dir / "default_layout.json")
    (tmp_path / "layout.json").write_text(json.dumps(LAYOUT), encoding="utf-8")
    env = {"version": "0.1.0", "version_dir": str(version_dir), "data_dir": str(tmp_path), "loader_version": 1}
    app = App(env, FakeAdapter(), QtPanelView)
    app.start()
    yield app
    app.close()
    qt_app.processEvents()


def show(app, qt_app, width, height):
    widget = app.view.widget
    widget.resize(width, height)
    widget.show()
    qt_app.processEvents()
    app.view.relayout_if_needed()
    qt_app.processEvents()
    return app.view


def tile_names(view):
    return [[t.button.name for t in box.tiles] for box in view.group_boxes]


def saved_names(app):
    data = json.loads((app.data_dir / "layout.json").read_text(encoding="utf-8"))
    return [[b["name"] for b in g["buttons"]] for g in data["groups"]]


def test_a_tall_panel_stacks_every_group_with_named_icon_tiles(app, qt_app):
    view = show(app, qt_app, 260, 700)

    assert view.orientation == "tall"
    assert tile_names(view) == [[f"Button {i}" for i in range(6)], ["Fill", "Paint"], []]
    tile = view.group_boxes[1].tiles[0]
    assert tile.toolTip() == "Fill"
    assert tile.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert not tile.icon().isNull()
    assert view.overflow_tool is None


def test_a_flat_strip_puts_buttons_that_do_not_fit_under_the_overflow_button(app, qt_app):
    view = show(app, qt_app, 420, 90)

    assert view.orientation == "flat"
    assert view.overflow_tool is not None
    shown = sum(len(names) for names in tile_names(view))
    hidden = [a.text() for a in view.overflow_tool.menu().actions() if a.data() is not None]
    assert shown + len(hidden) == 8
    assert hidden[-1] == "Paint"

    view = show(app, qt_app, 2000, 90)
    assert view.overflow_tool is None
    assert tile_names(view) == [[f"Button {i}" for i in range(6)], ["Fill", "Paint"], []]


def test_collapsing_hides_the_tiles_and_is_remembered(app, qt_app):
    view = show(app, qt_app, 260, 700)

    view.toggle_group(app.layout.groups[0])

    assert tile_names(view)[0] == []
    assert app.is_collapsed("g1")


def test_tile_size_and_labels(app, qt_app):
    view = show(app, qt_app, 260, 700)

    view.set_tile_size(64)
    view.set_show_labels(True)

    tile = view.group_boxes[1].tiles[0]
    assert tile.width() == 64 and tile.height() > 64
    assert tile.text() == "Fill"


def test_delete_then_undo_brings_the_button_back(app, qt_app):
    view = show(app, qt_app, 260, 700)
    fill = app.layout.groups[1].buttons[0]

    view.delete_button(fill)
    assert tile_names(view)[1] == ["Paint"]
    assert view.undo_button.isVisibleTo(view.widget)
    assert saved_names(app)[1] == ["Paint"]

    view.undo_button.click()
    assert tile_names(view)[1] == ["Fill", "Paint"]
    assert not view.undo_button.isVisibleTo(view.widget)
    assert saved_names(app)[1] == ["Fill", "Paint"]


def test_moving_a_button_to_another_group_from_its_menu(app, qt_app):
    view = show(app, qt_app, 260, 700)
    fill = app.layout.groups[1].buttons[0]

    [rename, move_to, delete] = view.button_actions(fill)
    assert [rename[0], move_to[0], delete[0]] == ["Rename…", "Move to", "Delete"]
    target = next(entry for entry in move_to[2] if entry[0] == "Empty")
    target[2]()

    assert tile_names(view) == [[f"Button {i}" for i in range(6)], ["Paint"], ["Fill"]]


def test_group_menu_reorders_and_deletes_only_empty_groups(app, qt_app):
    view = show(app, qt_app, 260, 700)
    general, layers, empty = app.layout.groups

    entries = {text: (enabled, run) for text, enabled, run in view.group_actions(general)}
    assert not entries["Move up"][0] and entries["Move down"][0]
    assert not entries["Delete Group"][0]

    entries["Move down"][1]()
    assert [g.name for g in app.layout.groups] == ["Layers", "General", "Empty"]

    dict((t, r) for t, _, r in view.group_actions(empty))["Delete Group"]()
    assert [g.name for g in app.layout.groups] == ["Layers", "General"]


def test_the_plus_menu_lists_the_button_kinds(app, qt_app):
    view = show(app, qt_app, 260, 700)

    plus = view.group_boxes[0].findChild(QtWidgets.QToolButton, "ShelfPlusGroupAdd")
    texts = [a.text() for a in plus.menu().actions()]

    assert [t.split(" (")[0] for t in texts] == ["Brush button", "Menu button", "Workflow button"]


def test_every_panel_element_has_a_name_for_the_pen(app, qt_app):
    view = show(app, qt_app, 260, 700)
    box = view.group_boxes[0]
    elements = [
        box.tiles[0],
        box.findChild(QtWidgets.QToolButton, "ShelfPlusGroupToggle"),
        box.findChild(QtWidgets.QLabel, "ShelfPlusGroupName"),
        box.findChild(QtWidgets.QToolButton, "ShelfPlusGroupAdd"),
        view.panel_menu_tool,
        view.trash,
        view.undo_button,
    ]

    for element in elements:
        target, text = view.pen_hover.named_element(element)
        assert target is element and text

    assert view.pen_hover.named_element(QtWidgets.QWidget()) == (None, "")


def test_a_read_only_layout_cannot_be_changed_from_the_panel(app, qt_app):
    app.read_only = app.editor.read_only = True
    view = show(app, qt_app, 260, 700)
    view.render()

    assert all(not enabled for _, enabled, _ in view.button_actions(app.layout.groups[0].buttons[0]))
    assert all(not enabled for _, enabled, _ in view.group_actions(app.layout.groups[0]))
    assert not view.group_boxes[0].acceptDrops()
    assert isinstance(view.group_boxes[0].tiles[0], Tile)


def drop_on(widget, view, button, local_pos):
    """Drop ``button`` on ``widget`` as a finished drag would (QDrag.exec cannot run headless)."""
    view.dragging = button
    mime = QMimeData()
    mime.setData("application/x-shelfplus-button", QByteArray(b"button"))
    event = QDropEvent(
        QPointF(local_pos), Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    )
    widget.dropEvent(event)
    view.end_drag()


def test_dropping_a_tile_before_another_tile_of_another_group(app, qt_app):
    view = show(app, qt_app, 260, 700)
    paint = app.layout.groups[1].buttons[1]
    target_box = view.group_boxes[0]
    first = target_box.tiles[0]
    left_half = first.mapTo(target_box, first.rect().center()) - QPoint(
        first.width() // 4, 0
    )

    drop_on(target_box, view, paint, left_half)

    assert tile_names(view)[0][:2] == ["Paint", "Button 0"]
    assert saved_names(app)[1] == ["Fill"]


def test_dropping_on_the_trash_deletes_with_undo(app, qt_app):
    view = show(app, qt_app, 260, 700)
    fill = app.layout.groups[1].buttons[0]

    drop_on(view.trash, view, fill, view.trash.rect().center())

    assert tile_names(view)[1] == ["Paint"]
    assert view.undo_button.isVisibleTo(view.widget)
    assert not view.trash.isVisibleTo(view.widget)


def test_the_content_is_not_rebuilt_during_a_drag(app, qt_app):
    view = show(app, qt_app, 260, 700)
    tile = view.group_boxes[1].tiles[0]
    view.dragging = tile.button

    view.set_tile_size(64)
    assert view.group_boxes[1].tiles[0] is tile  # the dragged tile is still alive

    view.end_drag()
    assert view.group_boxes[1].tiles[0] is not tile
    assert view.group_boxes[1].tiles[0].width() == 64


def test_a_collapsed_group_cut_off_in_the_flat_row_is_still_under_overflow(app, qt_app):
    app.set_group_collapsed("g2", True)
    view = show(app, qt_app, 300, 90)

    texts = [a.text() for a in view.overflow_tool.menu().actions()]

    assert "Layers" in texts and "Fill" in texts
    assert "Empty" in texts and "(no Buttons)" in texts


def test_overflow_entries_carry_their_button_for_the_right_click_menu(app, qt_app):
    view = show(app, qt_app, 300, 90)

    entries = [a for a in view.overflow_tool.menu().actions() if a.data() is not None]

    assert entries and all(a.data().name == a.text() for a in entries)


def test_the_panel_never_touches_the_style_object(qt_app, tmp_path, monkeypatch):
    """On Painter 11.1 the Python wrapper of the application style is already deleted
    ("Internal C++ object (QCommonStyle) already deleted"), so ``style()`` must not be used."""

    def stale_style(self):
        raise RuntimeError("Internal C++ object (PySide6.QtWidgets.QCommonStyle) already deleted.")

    monkeypatch.setattr(QtWidgets.QWidget, "style", stale_style)
    version_dir = tmp_path / "versions" / "0.1.0"
    version_dir.mkdir(parents=True)
    shutil.copy(BUNDLED / "default_layout.json", version_dir / "default_layout.json")
    env = {"version": "0.1.0", "version_dir": str(version_dir), "data_dir": str(tmp_path), "loader_version": 1}
    app = App(env, FakeAdapter(), QtPanelView)
    try:
        app.start()
        for width, height in [(260, 700), (900, 90)]:
            view = show(app, qt_app, width, height)
            view.render()
        assert not view.trash.icon().isNull()
    finally:
        app.close()
        qt_app.processEvents()


def test_the_pen_helper_ignores_a_dead_widget_under_the_cursor(app, qt_app):
    from shiboken6 import delete

    view = show(app, qt_app, 260, 700)
    dead = QtWidgets.QWidget()
    delete(dead)

    assert view.pen_hover.named_element(dead) == (None, "")


def heading_text(action):
    widget = action.defaultWidget() if isinstance(action, QtWidgets.QWidgetAction) else None
    return widget.text() if isinstance(widget, QtWidgets.QLabel) and widget.isEnabled() else None


def test_the_version_heading_is_a_readable_label_not_a_disabled_item(app, qt_app):
    view = show(app, qt_app, 260, 700)

    first = view.menu.actions()[0]

    assert heading_text(first) == "Shelf+ v0.1.0"
    assert first.text() == "Shelf+ v0.1.0"


def test_overflow_group_names_are_readable_headings(app, qt_app):
    view = show(app, qt_app, 300, 90)

    headings = [heading_text(a) for a in view.overflow_tool.menu().actions() if heading_text(a)]

    assert "Layers" in headings


def test_menu_buttons_show_no_drop_down_arrow(app, qt_app):
    """Qt draws a down arrow on a QToolButton that has a menu set (in a 20 px "+" it
    hides the "+" itself), so ☰, + and » open their menus themselves instead."""
    view = show(app, qt_app, 300, 90)
    plus = view.group_boxes[0].findChild(QtWidgets.QToolButton, "ShelfPlusGroupAdd")

    for button in (view.panel_menu_tool, plus, view.overflow_tool):
        assert QtWidgets.QToolButton.menu(button) is None  # nothing for Qt to draw an arrow for
        assert button.menu().actions()
    assert plus.text() == "+"
