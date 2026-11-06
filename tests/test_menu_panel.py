"""Menu buttons on the Panel, offscreen: the capture bar, Esc, the searchable list, badges."""

import json
import os
import shutil
from pathlib import Path

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6 import QtCore, QtGui  # noqa: E402

from shelfplus_app.adapter.actions import PainterActions  # noqa: E402
from shelfplus_app.adapter.fake import FakeAdapter  # noqa: E402
from shelfplus_app.app import App  # noqa: E402
from shelfplus_app.core.menu import MenuAction  # noqa: E402
from shelfplus_app.ui.panel import ActionPicker, QtPanelView  # noqa: E402

BUNDLED = Path(__file__).parents[1] / "src" / "ShelfPlus" / "bundled"

SAVE = MenuAction("SAVE_PROJECT", "&Save", ("File",))
SAVE_AS = MenuAction("SAVE_PROJECT_AS", "Save &As...", ("File",))
LOG = MenuAction("show_log", "Log", ("Window", "Views"))

LAYOUT = {
    "schemaVersion": 1,
    "groups": [
        {
            "id": "g1",
            "name": "General",
            "buttons": [
                {"id": "m1", "kind": "menu", "name": "Save", "action": "SAVE_PROJECT", "icon": None},
                {"id": "m2", "kind": "menu", "name": "Bake", "action": "bake_all", "icon": None},
            ],
        },
        {"id": "g2", "name": "Empty", "buttons": []},
    ],
}


@pytest.fixture
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def adapter():
    adapter = FakeAdapter()
    adapter.actions = [SAVE, SAVE_AS, LOG]
    return adapter


@pytest.fixture
def app(qt_app, tmp_path, adapter):
    version_dir = tmp_path / "versions" / "0.4.0"
    version_dir.mkdir(parents=True)
    shutil.copy(BUNDLED / "default_layout.json", version_dir / "default_layout.json")
    (tmp_path / "layout.json").write_text(json.dumps(LAYOUT), encoding="utf-8")
    env = {"version": "0.4.0", "version_dir": str(version_dir), "data_dir": str(tmp_path), "loader_version": 1}
    app = App(env, adapter, QtPanelView)
    app.start()
    app.view.widget.resize(260, 600)
    app.view.widget.show()
    qt_app.processEvents()
    yield app
    app.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    qt_app.processEvents()


def add_menu(app, group_index):
    plus = app.view.group_boxes[group_index].findChild(QtWidgets.QToolButton, "ShelfPlusGroupAdd")
    return plus.menu()


def press_escape(widget):
    event = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_Escape, QtCore.Qt.KeyboardModifier.NoModifier)
    QtWidgets.QApplication.sendEvent(widget, event)


class TestCaptureBar:
    def test_menu_button_in_the_plus_menu_starts_capture_mode_with_a_prompt(self, app, qt_app):
        (entry,) = [a for a in add_menu(app, 1).actions() if a.text() == "Menu button"]
        assert entry.isEnabled()

        entry.trigger()
        qt_app.processEvents()

        assert app.capturing.id == "g2"
        assert not app.view.capture_bar.isHidden()
        assert "Click a command in Painter's menu to add it to “Empty”" in app.view.capture_text.text()

    def test_the_bar_is_hidden_when_not_capturing(self, app):
        assert app.view.capture_bar.isHidden()

    def test_cancel_ends_capture_mode(self, app):
        app.start_menu_capture(app.editor.group("g2"))

        app.view.capture_cancel.click()

        assert app.capturing is None and app.view.capture_bar.isHidden()

    def test_escape_anywhere_in_painter_ends_capture_mode(self, app, qt_app):
        app.start_menu_capture(app.editor.group("g2"))
        elsewhere = QtWidgets.QLineEdit()

        press_escape(elsewhere)
        qt_app.processEvents()

        assert app.capturing is None

    def test_escape_is_watched_only_in_capture_mode(self, app):
        assert not app.view.escape_filter.installed
        app.start_menu_capture(app.editor.group("g2"))
        assert app.view.escape_filter.installed

        app.add_menu_button("g2", LOG)  # ends capture mode

        assert not app.view.escape_filter.installed

    def test_escape_that_closes_an_open_menu_does_not_end_capture_mode(self, app, qt_app, monkeypatch):
        app.start_menu_capture(app.editor.group("g2"))
        monkeypatch.setattr(QtWidgets.QApplication, "activePopupWidget", staticmethod(lambda: object()))

        press_escape(QtWidgets.QLineEdit())

        assert app.capturing is not None

    def test_a_captured_command_appears_as_a_tile(self, app, adapter, qt_app):
        app.start_menu_capture(app.editor.group("g2"))

        adapter.click_command(LOG)
        qt_app.processEvents()

        assert [t.button.name for t in app.view.group_boxes[1].tiles] == ["Log"]
        assert app.view.capture_bar.isHidden()


class TestBadges:
    def test_a_menu_button_without_its_command_shows_unavailable(self, app):
        save, bake = app.view.group_boxes[0].tiles

        assert save.toolTip() == "Save" and not save.missing
        assert bake.missing
        assert bake.toolTip() == "Bake (not available in this Painter version)"


class TestPanelMenusAreNotPainters:
    def test_the_panels_own_menus_are_never_listed_as_painter_commands(self, app):
        app.view.menu  # the ☰ menu exists
        texts = {a.text for a in PainterActions().all()}

        assert not texts & {"Show labels", "New Group…", "Copy diagnostics", "Menu button", "Brush button"}


class TestPicker:
    def test_it_lists_painters_commands_with_their_place_and_object_name(self, app):
        picker = ActionPicker(app, app.editor.group("g2"))

        assert picker.rows() == ["Save — File   [SAVE_PROJECT]", "Save As... — File   [SAVE_PROJECT_AS]", "Log — Window › Views   [show_log]"]

    def test_typing_filters_the_list(self, app):
        picker = ActionPicker(app, app.editor.group("g2"))

        picker.search.setText("save as")

        assert picker.rows() == ["Save As... — File   [SAVE_PROJECT_AS]"]

    def test_the_first_match_is_selected_and_choosing_returns_it(self, app):
        picker = ActionPicker(app, app.editor.group("g2"))
        picker.search.setText("log")

        assert picker.chosen() == LOG

    def test_nothing_matching_says_so_and_cannot_be_chosen(self, app):
        picker = ActionPicker(app, app.editor.group("g2"))

        picker.search.setText("bake")

        assert picker.rows() == []
        assert picker.chosen() is None
        assert not picker.ok_button.isEnabled()
        assert picker.empty_label.text() == "No command matches “bake”."

    def test_the_object_name_is_in_the_rows_tooltip(self, app):
        picker = ActionPicker(app, app.editor.group("g2"))

        assert picker.list.item(0).toolTip() == "SAVE_PROJECT"
