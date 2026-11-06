"""The Panel's Qt view, offscreen, over a real App with the fake adapter."""

import json
import os
import shutil
from pathlib import Path

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import QByteArray, QMimeData, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QDropEvent, QWheelEvent  # noqa: E402

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


def test_a_flat_strip_keeps_every_button_in_one_row_and_scrolls_sideways(app, qt_app):
    view = show(app, qt_app, 420, 120)

    assert view.orientation == "flat"
    assert tile_names(view) == [[f"Button {i}" for i in range(6)], ["Fill", "Paint"], []]
    tops = {t.mapTo(view.content, QPoint(0, 0)).y() for box in view.group_boxes for t in box.tiles}
    assert len(tops) == 1  # one row
    assert view.scroll.horizontalScrollBar().maximum() > 0
    assert view.scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_a_tall_panel_scrolls_up_and_down_only(app, qt_app):
    view = show(app, qt_app, 260, 700)

    assert view.scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert view.scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded


def test_the_mouse_wheel_scrolls_a_flat_strip_sideways(app, qt_app):
    view = show(app, qt_app, 420, 120)
    bar = view.scroll.horizontalScrollBar()
    viewport = view.scroll.viewport()
    centre = QPointF(viewport.rect().center())

    wheel = QWheelEvent(
        centre, QPointF(viewport.mapToGlobal(centre.toPoint())), QPoint(0, 0), QPoint(0, -120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False,
    )
    QtWidgets.QApplication.sendEvent(viewport, wheel)

    assert bar.value() > 0


def test_holding_a_dragged_button_at_an_edge_scrolls(app, qt_app):
    view = show(app, qt_app, 420, 120)
    bar = view.scroll.horizontalScrollBar()
    viewport = view.scroll.viewport()

    view.edge_scroll_at(QPoint(viewport.width() - 2, viewport.height() // 2))
    assert bar.value() > 0
    moved = bar.value()

    view.edge_scroll_at(QPoint(viewport.width() // 2, viewport.height() // 2))
    assert bar.value() == moved

    view.edge_scroll_at(QPoint(1, viewport.height() // 2))
    assert bar.value() < moved


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


def test_menu_buttons_show_no_drop_down_arrow(app, qt_app):
    """Qt draws a down arrow on a QToolButton that has a menu set (in a 20 px "+" it
    hides the "+" itself), so ☰ and + open their menus themselves instead."""
    view = show(app, qt_app, 260, 700)
    plus = view.group_boxes[0].findChild(QtWidgets.QToolButton, "ShelfPlusGroupAdd")

    for button in (view.panel_menu_tool, plus):
        assert QtWidgets.QToolButton.menu(button) is None  # nothing for Qt to draw an arrow for
        assert button.menu().actions()
    assert plus.text() == "+"


def test_the_tile_size_is_a_slider_from_40_to_80_in_the_panel_menu(app, qt_app):
    view = show(app, qt_app, 260, 700)
    sliders = [
        a.defaultWidget().findChild(QtWidgets.QSlider)
        for a in view.menu.actions()
        if isinstance(a, QtWidgets.QWidgetAction) and a.defaultWidget().findChild(QtWidgets.QSlider)
    ]

    assert len(sliders) == 1
    slider = sliders[0]
    assert (slider.minimum(), slider.maximum(), slider.value()) == (40, 80, 48)
    assert slider.orientation() == Qt.Orientation.Horizontal


def test_moving_the_slider_resizes_the_tiles_at_once_and_saves_when_it_stops(app, qt_app):
    view = show(app, qt_app, 260, 700)

    view.tile_slider.setValue(60)

    assert view.group_boxes[1].tiles[0].width() == 60
    assert "60 px" in view.tile_size_label.text()
    saved = json.loads((app.data_dir / "panel.json").read_text(encoding="utf-8"))
    assert saved["tileSize"] == 48  # not on every step of the slider
    assert view.tile_save_timer.isActive()

    view.tile_save_timer.timeout.emit()
    saved = json.loads((app.data_dir / "panel.json").read_text(encoding="utf-8"))
    assert saved["tileSize"] == 60


def test_the_slider_shows_the_saved_size_after_a_restart(app, qt_app):
    app.set_tile_size(72)
    view = show(app, qt_app, 260, 700)
    view.render()

    assert view.tile_slider.value() == 72


def test_in_a_flat_strip_each_group_name_is_above_its_tiles(app, qt_app):
    view = show(app, qt_app, 420, 140)
    assert view.orientation == "flat"

    for box in view.group_boxes:
        if not box.tiles:
            continue
        name = box.findChild(QtWidgets.QLabel, "ShelfPlusGroupName")
        name_bottom = name.mapTo(box, QPoint(0, name.height())).y()
        first = box.tiles[0].mapTo(box, QPoint(0, 0))
        assert name_bottom <= first.y()  # above, not before
        assert first.x() <= name.mapTo(box, QPoint(0, 0)).x() + 30  # the tiles start under the header


def test_the_plus_is_a_drawn_icon_the_same_size_as_the_collapse_arrow(app, qt_app):
    view = show(app, qt_app, 260, 700)
    box = view.group_boxes[0]
    plus = box.findChild(QtWidgets.QToolButton, "ShelfPlusGroupAdd")
    arrow = box.findChild(QtWidgets.QToolButton, "ShelfPlusGroupToggle")

    assert plus.size() == arrow.size()
    assert not plus.icon().isNull()
    assert plus.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert plus.iconSize().width() < plus.width()  # a little room around the cross


@pytest.mark.parametrize("width, height", [(260, 700), (900, 140)])  # tall, flat
def test_the_groups_do_not_touch_the_top_of_their_container(app, qt_app, width, height):
    from shelfplus_app.ui.panel import CONTENT_TOP_PADDING

    view = show(app, qt_app, width, height)
    first = view.group_boxes[0]
    toggle = first.findChild(QtWidgets.QToolButton, "ShelfPlusGroupToggle")

    assert CONTENT_TOP_PADDING > 0
    assert toggle.mapTo(view.content, QPoint(0, 0)).y() >= CONTENT_TOP_PADDING


@pytest.mark.parametrize("width, height", [(260, 700), (900, 140)])  # tall, flat
def test_the_plus_comes_right_after_the_collapse_arrow_before_the_name(app, qt_app, width, height):
    view = show(app, qt_app, width, height)

    for box in view.group_boxes:
        arrow = box.findChild(QtWidgets.QToolButton, "ShelfPlusGroupToggle")
        plus = box.findChild(QtWidgets.QToolButton, "ShelfPlusGroupAdd")
        name = box.findChild(QtWidgets.QLabel, "ShelfPlusGroupName")
        xs = [w.mapTo(box, QPoint(0, 0)).x() for w in (arrow, plus, name)]
        assert xs == sorted(xs) and len(set(xs)) == 3


def drag_event(cls, box, pos, view, button):
    from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent

    view.dragging = button
    mime = QMimeData()
    mime.setData("application/x-shelfplus-button", QByteArray(b"button"))
    kind = {"enter": QDragEnterEvent, "move": QDragMoveEvent}[cls]
    event = kind(QPointF(pos), Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    event.keep_mime_alive = mime  # the event does not own it; freeing it crashes Qt
    return event


def test_dragging_over_a_collapsed_group_name_highlights_that_group(app, qt_app):
    app.set_group_collapsed("g2", True)
    view = show(app, qt_app, 260, 700)
    layers = view.group_boxes[1]
    name = layers.findChild(QtWidgets.QLabel, "ShelfPlusGroupName")
    over_name = name.mapTo(layers, name.rect().center())
    button = app.layout.groups[0].buttons[0]

    assert not layers.drop_highlighted
    layers.dragEnterEvent(drag_event("enter", layers, over_name, view, button))
    layers.dragMoveEvent(drag_event("move", layers, over_name, view, button))
    assert layers.drop_highlighted
    assert "border" in layers.styleSheet()

    from PySide6.QtGui import QDragLeaveEvent

    layers.dragLeaveEvent(QDragLeaveEvent())
    assert not layers.drop_highlighted
    assert layers.styleSheet() == ""
    view.end_drag()


def test_dropping_on_a_collapsed_group_adds_the_tile_at_its_end(app, qt_app):
    app.set_group_collapsed("g2", True)
    view = show(app, qt_app, 260, 700)
    layers = view.group_boxes[1]
    name = layers.findChild(QtWidgets.QLabel, "ShelfPlusGroupName")
    button = app.layout.groups[0].buttons[0]

    drop_on(layers, view, button, name.mapTo(layers, name.rect().center()))

    assert [b.name for b in app.layout.groups[1].buttons] == ["Fill", "Paint", "Button 0"]
    assert not view.group_boxes[1].drop_highlighted


# -- Brush buttons ---------------------------------------------------------------


def assets_drop(widget, local_pos, uri_list):
    """Drop what the Assets window drags (``text/uri-list``) on ``widget``."""
    mime = QMimeData()
    mime.setData("text/uri-list", QByteArray(uri_list.encode("utf-8")))
    event = QDropEvent(
        QPointF(local_pos), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    )
    widget.dropEvent(event)
    return event


def test_a_brush_dropped_from_the_assets_window_becomes_a_tile_where_it_was_dropped(app, qt_app):
    from shelfplus_app.adapter.fake import FakeResource

    app.adapter.add_resource(FakeResource("resource://starter_assets/Basic Hard", "Basic Hard"))
    view = show(app, qt_app, 260, 700)
    layers = view.group_boxes[1]
    paint = layers.tiles[1]

    event = assets_drop(layers, paint.mapTo(layers, QPoint(2, paint.height() // 2)),
                        "resource://starter_assets/Basic%20Hard?version=abc.resource\r\n")

    assert event.dropAction() == Qt.DropAction.CopyAction
    assert saved_names(app)[1] == ["Fill", "Basic Hard", "Paint"]
    assert tile_names(view)[1] == ["Fill", "Basic Hard", "Paint"]
    assert not view.group_boxes[1].tiles[1].icon().isNull()  # the generic brush icon


def test_the_assets_drag_is_accepted_and_highlights_an_empty_group(app, qt_app):
    from PySide6.QtGui import QDragEnterEvent

    view = show(app, qt_app, 260, 700)
    empty = view.group_boxes[2]
    mime = QMimeData()
    mime.setData("text/uri-list", QByteArray(b"resource://a/B?version=1\r\n"))
    event = QDragEnterEvent(QPointF(5, 5), Qt.DropAction.CopyAction | Qt.DropAction.MoveAction, mime,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)

    empty.dragEnterEvent(event)

    assert event.isAccepted() and event.dropAction() == Qt.DropAction.CopyAction
    assert empty.drop_highlighted


def test_other_urls_are_not_accepted(app, qt_app):
    from PySide6.QtGui import QDragEnterEvent

    view = show(app, qt_app, 260, 700)
    mime = QMimeData()
    mime.setData("text/uri-list", QByteArray(b"file:///C:/x.png\r\n"))
    event = QDragEnterEvent(QPointF(5, 5), Qt.DropAction.CopyAction, mime,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    event.ignore()

    view.group_boxes[2].dragEnterEvent(event)

    assert not event.isAccepted()


def test_a_missing_preset_has_a_badge_and_says_so(qt_app, tmp_path):
    from shelfplus_app.adapter.fake import FakeResource

    version_dir = tmp_path / "versions" / "0.3.0"
    version_dir.mkdir(parents=True)
    shutil.copy(BUNDLED / "default_layout.json", version_dir / "default_layout.json")
    brush = {"kind": "brush", "icon": None}
    layout = {"schemaVersion": 1, "groups": [{"id": "g1", "name": "Brushes", "buttons": [
        dict(brush, id="b1", name="Hard", resource="resource://a/Hard"),
        dict(brush, id="b2", name="Gone", resource="resource://a/Gone"),
    ]}]}
    (tmp_path / "layout.json").write_text(json.dumps(layout), encoding="utf-8")
    adapter = FakeAdapter()
    adapter.add_resource(FakeResource("resource://a/Hard", "Hard"))
    env = {"version": "0.3.0", "version_dir": str(version_dir), "data_dir": str(tmp_path), "loader_version": 1}
    app = App(env, adapter, QtPanelView)
    app.start()
    try:
        view = show(app, qt_app, 260, 700)
        hard, gone = view.group_boxes[0].tiles

        assert not hard.missing and hard.toolTip() == "Hard"
        assert gone.missing and gone.toolTip() == "Gone (not available on this machine)"

        gone.click()
        assert view.notice.isVisibleTo(view.widget)
        assert view.notice.text() == "This brush is not available on this machine: resource://a/Gone"
        assert adapter.assets_calls == []
    finally:
        app.close()
        qt_app.processEvents()
