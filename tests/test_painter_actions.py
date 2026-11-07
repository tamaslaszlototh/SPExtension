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


class TestHiddenMenus:
    """Painter 11.1 has about 130 menus, but allWidgets() lists only 32 of them."""

    @pytest.fixture
    def only_the_menu_bar(self, painter, monkeypatch):
        bar = painter.window.menuBar()
        visible = [painter.window, bar]
        monkeypatch.setattr(QtWidgets.QApplication, "allWidgets", staticmethod(lambda: list(visible)))
        return bar

    def test_menus_are_followed_from_the_entries_that_open_them(self, painter, only_the_menu_bar):
        actions = {a.name: a for a in PainterActions().all()}

        assert actions["SAVE_PROJECT"].path == ("File",)
        assert actions["recent_1"].path == ("File", "Recent")

    def test_commands_in_such_menus_are_watched(self, painter, only_the_menu_bar):
        seen = []
        stop = PainterActions().watch(seen.append)

        painter.recent.trigger()
        stop()

        assert {(a.name, a.path) for a in seen} == {("recent_1", ("File", "Recent"))}


def release_on(menu):
    """A mouse release inside ``menu``, as when an entry is clicked."""
    QtWidgets.QApplication.sendEvent(
        menu,
        QtGui.QMouseEvent(
            QtCore.QEvent.Type.MouseButtonRelease, QtCore.QPointF(1, 1), QtCore.QPointF(1, 1),
            QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.NoButton, QtCore.Qt.KeyboardModifier.NoModifier,
        ),
    )


class TestMenuClicks:
    """Painter 11.1 runs Window > Views > Log without the QAction's triggered signal
    reaching a hook; the click in the menu is what shows it."""

    def test_the_entry_clicked_in_a_menu_is_reported_with_its_place(self, painter):
        views = painter.window.menuBar().addMenu("Window").addMenu("Views")
        log = views.addAction("Log")
        seen = []
        stop = PainterActions().watch(seen.append)
        views.setActiveAction(log)

        release_on(views)
        stop()

        # first the click; any hook calls that follow are duplicates the core drops
        assert (seen[0].label, seen[0].path, seen[0].handle is log) == ("Log", ("Window", "Views"), True)
        assert {(a.label, a.path) for a in seen} == {("Log", ("Window", "Views"))}

    def test_a_click_on_a_disabled_entry_or_a_submenu_is_not_reported(self, painter):
        file_menu = painter.save.associatedObjects()[0]
        seen = []
        stop = PainterActions().watch(seen.append)
        painter.save.setEnabled(False)
        file_menu.setActiveAction(painter.save)
        release_on(file_menu)
        recent_entry = [a for a in file_menu.actions() if a.menu() is not None][0]
        file_menu.setActiveAction(recent_entry)
        release_on(file_menu)
        stop()

        assert seen == []

    def test_clicks_in_the_panels_own_menus_are_not_reported(self, painter):
        seen = []
        stop = PainterActions().watch(seen.append)
        painter.own_menu.setActiveAction(painter.own)

        release_on(painter.own_menu)
        stop()

        assert seen == []


class TestClickLog:
    def test_a_click_in_a_menu_is_logged_while_watching_and_not_after(self, painter, caplog):
        menu = painter.save.associatedObjects()[0]
        release = lambda: release_on(menu)  # noqa: E731
        caplog.set_level("DEBUG", logger="ShelfPlus.app.actions")
        stop = PainterActions().watch(lambda action: None)

        release()
        stop()
        release()

        clicks = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Menu click")]
        assert len(clicks) == 1 and "title '&File'" in clicks[0]


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

    def test_a_command_without_an_object_name_is_found_by_its_place_in_the_menu(self, painter):
        unnamed = painter.window.menuBar().addMenu("Window").addMenu("Views").addAction("Log")

        found = PainterActions().find("menu:Window › Views › Log")

        assert found.handle is unnamed and found.path == ("Window", "Views")
        assert PainterActions().find("menu:Window › Views › Nope") is None

    def test_an_unnamed_command_in_several_menus_is_found_by_any_of_its_places(self, painter, monkeypatch):
        log = QtGui.QAction("Log", painter.window)
        untitled = QtWidgets.QMenu(painter.window)  # e.g. a context menu, met first
        untitled.addAction(log)
        painter.window.menuBar().addMenu("Window").addMenu("Views").addAction(log)
        order = [untitled, painter.window.menuBar(), painter.window]  # Views only via its entry
        monkeypatch.setattr(QtWidgets.QApplication, "allWidgets", staticmethod(lambda: list(order)))

        found = PainterActions().find("menu:Window › Views › Log")
        places = {a.path for a in PainterActions().all() if a.handle is log}

        assert found is not None and found.handle is log
        assert ("Window", "Views") in places

    def test_a_place_saved_without_its_outer_menus_is_still_found(self, painter):
        # v0.4.3 could not see the Window menu above Views, and saved "menu:Views › Log".
        unnamed = painter.window.menuBar().addMenu("Window").addMenu("Views").addAction("Log")

        assert PainterActions().find("menu:Views › Log").handle is unnamed
        assert PainterActions().find("menu:iews › Log") is None

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

    def test_commands_on_any_widget_are_reported(self, painter):
        # Painter 11.1's main menu commands are in no QMenu that allWidgets() lists:
        # they were caught only by hooking the actions of every widget.
        seen = []
        stop = PainterActions().watch(seen.append)

        painter.shortcut.trigger()
        painter.paint.trigger()
        painter.save.trigger()
        stop()

        assert {a.name for a in seen} == {"swap_views", "paint_tool", "SAVE_PROJECT"}

    def test_a_command_in_no_menu_is_reported_with_the_named_widget_it_is_on(self, painter):
        painter.window.setObjectName("MainWindow")
        log = QtGui.QAction("Log", painter.window)
        painter.window.addAction(log)
        seen = []
        stop = PainterActions().watch(seen.append)

        log.trigger()
        stop()

        assert {(a.label, a.path, a.owner) for a in seen} == {("Log", (), "MainWindow")}
        assert PainterActions().find("widget:MainWindow › Log").handle is log

    def test_the_panels_own_commands_are_not_reported(self, painter):
        seen = []
        stop = PainterActions().watch(seen.append)

        painter.own.trigger()
        stop()

        assert seen == []

    def test_a_menu_command_also_on_the_main_window_is_hooked_with_its_menu_place(self, painter):
        # Painter 11.1 adds its menu commands to the main window too (for the shortcuts),
        # and allWidgets() lists the main window before the menus.
        log = QtGui.QAction("Log", painter.window)
        painter.window.addAction(log)
        painter.window.menuBar().addMenu("Window").addMenu("Views").addAction(log)
        seen = []
        stop = PainterActions().watch(seen.append)

        log.trigger()
        stop()

        # one report per hook (the action's, and each menu's); the core drops the duplicates
        assert {(a.label, a.path) for a in seen} == {("Log", ("Window", "Views"))}
        assert PainterActions().find("menu:Window › Views › Log").handle is log

    def test_a_command_run_is_reported_with_its_place_in_the_menu(self, painter):
        seen = []
        stop = PainterActions().watch(seen.append)

        painter.recent.trigger()
        stop()

        assert {a.path for a in seen} == {("File", "Recent")}

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
