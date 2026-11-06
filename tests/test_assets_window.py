"""The Assets window automation (adapter layer), offscreen, against a stand-in dock.

Painter's list view class is ``Alg::ResourceListView``; here a plain ``QListView`` stands in.
"""

import os

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6 import QtCore, QtGui  # noqa: E402

from shelfplus_app.adapter.assets import AssetsWindow  # noqa: E402
from shelfplus_app.adapter.fake import FakeAdapter  # noqa: E402
from shelfplus_app.core.brush import DONE, BrushActivation, BrushResource  # noqa: E402


@pytest.fixture
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class Painter:
    """A main window with an Assets dock holding a list of tiles, and another dock."""

    def __init__(self, names=("Basic Hard", "Archive Inker", "Dirt")):
        self.window = QtWidgets.QMainWindow()
        self.window.resize(800, 600)
        self.dock = self.make_dock(names)
        self.other = QtWidgets.QDockWidget("Layers")
        self.other.setObjectName("Layers")
        self.other.setWidget(QtWidgets.QLabel("layers"))
        self.window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.other)
        self.window.show()

    def make_dock(self, names):
        dock = QtWidgets.QDockWidget("Assets")
        dock.setObjectName("NewShelf")
        holder = QtWidgets.QWidget()
        column = QtWidgets.QVBoxLayout(holder)
        self.view = QtWidgets.QListView()
        self.view.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.view.setGridSize(QtCore.QSize(80, 80))
        self.model = QtGui.QStandardItemModel()
        for name in names:
            item = QtGui.QStandardItem(name)
            pixmap = QtGui.QPixmap(34, 34)
            pixmap.fill(QtGui.QColor("#3d8fd1"))
            item.setIcon(QtGui.QIcon(pixmap))
            item.setToolTip(f"<p>{name}</p>")
            self.model.appendRow(item)
        self.view.setModel(self.model)
        column.addWidget(self.view)
        dock.setWidget(holder)
        self.window.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        return dock

    def close(self):
        self.window.close()
        self.window.deleteLater()


@pytest.fixture
def painter(qt_app):
    painter = Painter()
    qt_app.processEvents()
    yield painter
    painter.close()
    flush_deletes(qt_app)


def flush_deletes(qt_app):
    qt_app.processEvents()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    qt_app.processEvents()


def assets():
    return AssetsWindow(view_class="QListView")


def test_finds_the_dock_by_object_name_and_the_view_inside_it(painter):
    window = assets()

    assert window.dock() is painter.dock
    assert window.view() is painter.view


def test_open_shows_a_closed_dock(painter, qt_app):
    painter.dock.hide()
    window = assets()

    assert window.open()
    qt_app.processEvents()

    assert painter.dock.isVisible()


def test_no_dock_means_it_cannot_open(qt_app):
    assert not AssetsWindow(dock_name="NoSuchDock").open()


def test_tile_rect_and_a_qt_click_select_the_tile(painter, qt_app):
    window = assets()
    window.open()
    qt_app.processEvents()

    rect = window.tile_rect("Archive Inker")
    assert rect is not None
    window.click(rect)

    selected = painter.view.selectionModel().selectedIndexes()
    assert [i.data() for i in selected] == ["Archive Inker"]


def test_an_unknown_tile_has_no_rect(painter, qt_app):
    assert assets().tile_rect("Nope") is None


def test_a_hidden_view_has_no_rect(painter, qt_app):
    painter.dock.hide()
    qt_app.processEvents()

    assert assets().tile_rect("Basic Hard") is None


def test_a_recreated_dock_is_found_again(painter, qt_app):
    window = assets()
    assert window.view() is painter.view
    painter.dock.setParent(None)
    painter.dock.deleteLater()
    flush_deletes(qt_app)

    new_dock = painter.make_dock(["Basic Hard"])
    qt_app.processEvents()

    assert window.dock() is new_dock
    assert window.view() is painter.view
    assert window.tile_rect("Basic Hard") is not None


def test_icon_sources_read_the_tooltip_and_the_decoration_as_png(painter):
    tooltip, decoration = assets().icon_sources("Dirt")

    assert tooltip == "<p>Dirt</p>"
    assert decoration.startswith(b"\x89PNG\r\n\x1a\n")
    assert QtGui.QImage.fromData(decoration).size() == QtCore.QSize(34, 34)


def test_icon_sources_of_an_unknown_tile(painter):
    assert assets().icon_sources("Nope") == (None, None)


def test_the_activation_state_machine_against_the_real_view(painter, qt_app):
    """The poll from ``core.brush`` drives this Qt code as it will in Painter."""
    window = assets()
    adapter = FakeAdapter()
    adapter.open_assets = window.open
    adapter.tile_rect = window.tile_rect
    adapter.click_tile = window.click
    painter.dock.hide()
    activation = BrushActivation(adapter, BrushResource("resource://a/Dirt", "Dirt"), now=lambda: 0)

    activation.start()
    states = []
    for _ in range(5):
        qt_app.processEvents()
        states.append(activation.poll())
        if states[-1] == DONE:
            break

    assert states[-1] == DONE
    assert [i.data() for i in painter.view.selectionModel().selectedIndexes()] == ["Dirt"]
