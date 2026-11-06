"""Painter's commands (adapter layer), offscreen, against a stand-in main window with menus."""

import os

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6 import QtCore, QtGui  # noqa: E402

from shelfplus_app.adapter.actions import PainterActions  # noqa: E402


@pytest.fixture
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def icon():
    pixmap = QtGui.QPixmap(32, 32)
    pixmap.fill(QtGui.QColor("#8a63c9"))
    return QtGui.QIcon(pixmap)


def named(action, name):
    action.setObjectName(name)
    return action


class Painter:
    """A main window: File menu (Save with an icon, a Recent submenu, a separator), a
    toolbar, a window-wide shortcut action, and the Panel's own menu."""

    def __init__(self):
        self.window = QtWidgets.QMainWindow()
        file_menu = self.window.menuBar().addMenu("&File")
        self.save = named(file_menu.addAction(icon(), "&Save"), "SAVE_PROJECT")
        file_menu.addSeparator()
        recent = file_menu.addMenu("Recent")
        self.recent = named(recent.addAction("project.spp"), "recent_1")
        self.unnamed = file_menu.addAction("Add layer\n\nHold Alt to enable all channels")
        toolbar = self.window.addToolBar("Tools")
        self.paint = named(toolbar.addAction("Paint"), "paint_tool")
        self.shortcut = named(QtGui.QAction("Swap 3D/2D", self.window), "swap_views")
        self.window.addAction(self.shortcut)
        self.own_menu = QtWidgets.QMenu(self.window)
        self.own_menu.setObjectName("ShelfPlusPanelMenu")
        self.own = self.own_menu.addAction("Copy diagnostics")
        self.window.show()

    def close(self):
        self.window.close()
        self.window.deleteLater()


@pytest.fixture
def painter(qt_app):
    painter = Painter()
    yield painter
    painter.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    qt_app.processEvents()


def by_name(actions):
    return {a.name: a for a in actions}


class TestListing:
    def test_every_command_is_listed_once_with_the_menus_it_sits_in(self, painter):
        actions = by_name(PainterActions().all())

        assert actions["SAVE_PROJECT"].text == "&Save" and actions["SAVE_PROJECT"].path == ("File",)
        assert actions["recent_1"].path == ("File", "Recent")
        assert actions["paint_tool"].path == () and actions["swap_views"].path == ()
        assert actions[""].text.startswith("Add layer")

    def test_separators_submenu_entries_and_the_panels_own_menus_are_left_out(self, painter):
        texts = [a.text for a in PainterActions().all()]

        assert "" not in texts
        assert "Recent" not in texts
        assert "Copy diagnostics" not in texts

    def test_a_command_is_found_by_its_object_name(self, painter):
        found = PainterActions().find("recent_1")

        assert found.handle is painter.recent and found.label == "project.spp"
        assert PainterActions().find("nope") is None
        assert PainterActions().find("") is None


class TestReferences:
    def test_every_widget_and_command_found_is_kept_after_later_scans(self, painter):
        actions = PainterActions()
        found = actions.find("recent_1")

        actions.all()
        actions.find("SAVE_PROJECT")

        assert any(obj is found.handle for obj in actions.kept())
        assert any(obj is painter.window for obj in actions.kept())


class TestRunning:
    def test_of_two_commands_with_one_object_name_an_enabled_one_is_found(self, painter):
        painter.save.setEnabled(False)
        second = named(painter.window.menuBar().addMenu("Edit").addAction("Save"), "SAVE_PROJECT")

        assert PainterActions().find("SAVE_PROJECT").handle is second

    def test_triggering_runs_the_command(self, painter):
        seen = []
        painter.save.triggered.connect(lambda: seen.append("save"))
        actions = PainterActions()

        assert actions.trigger(actions.find("SAVE_PROJECT")) is True
        assert seen == ["save"]

    def test_a_disabled_command_is_not_triggered(self, painter):
        painter.save.setEnabled(False)
        actions = PainterActions()

        assert actions.trigger(actions.find("SAVE_PROJECT")) is False

    def test_the_icon_becomes_png_bytes_and_an_empty_icon_none(self, painter):
        actions = PainterActions()

        assert actions.icon_png(actions.find("SAVE_PROJECT")).startswith(b"\x89PNG\r\n\x1a\n")
        assert actions.icon_png(actions.find("recent_1")) is None


class TestWatching:
    def test_every_hook_reports_a_command_run_until_stopped(self, painter):
        seen = []
        stop = PainterActions().watch(seen.append)

        painter.recent.trigger()
        names = [a.name for a in seen]
        stop()
        painter.recent.trigger()

        # QAction.triggered and the submenu's QMenu.triggered: duplicates are the core's job.
        assert names and set(names) == {"recent_1"}
        assert len(seen) == len(names)

    def test_only_commands_in_menus_are_reported_not_toolbars_or_hotkeys(self, painter):
        seen = []
        stop = PainterActions().watch(seen.append)

        painter.shortcut.trigger()
        painter.paint.trigger()
        painter.save.trigger()
        stop()

        assert {a.name for a in seen} == {"SAVE_PROJECT"}

    def test_the_panels_own_commands_are_not_reported(self, painter):
        seen = []
        stop = PainterActions().watch(seen.append)

        painter.own.trigger()
        stop()

        assert seen == []

    def test_menus_created_after_watching_started_are_hooked_on_the_next_rescan(self, painter):
        seen = []
        stop = PainterActions().watch(seen.append)
        late = painter.window.menuBar().addMenu("Bake")
        late_action = named(late.addAction("Bake all"), "bake_all")

        stop.rescan()
        late_action.trigger()
        stop()

        assert {a.name for a in seen} == {"bake_all"}

    def test_rescanning_does_not_hook_a_command_twice(self, painter):
        seen = []
        stop = PainterActions().watch(seen.append)

        stop.rescan()
        stop.rescan()
        painter.save.trigger()
        stop()

        assert len(seen) == 2  # the action's own hook and its menu's, once each
