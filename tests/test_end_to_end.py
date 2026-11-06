"""End to end outside Painter: the real loader entry point installs and starts the real
bundled application, with a stand-in ``substance_painter`` module and offscreen Qt."""

import logging
import os
import sys
import types
from pathlib import Path

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6 import QtGui  # noqa: E402

PLUGIN_DIR = Path(__file__).parents[1] / "src" / "ShelfPlus"


class FakePainterUi(types.ModuleType):
    class UIMode:
        Edition = 1

    def __init__(self):
        super().__init__("substance_painter.ui")
        self.added = []
        self.deleted = []

    def add_dock_widget(self, widget, ui_modes=None):
        dock = QtWidgets.QDockWidget()
        dock.setObjectName(widget.objectName())
        dock.setWidget(widget)
        self.added.append((widget, ui_modes, dock))
        return dock

    def delete_ui_element(self, element):
        self.deleted.append(element)
        element.deleteLater()


@pytest.fixture
def painter(monkeypatch, tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    ui = FakePainterUi()
    application = types.ModuleType("substance_painter.application")
    application.version = lambda: "11.1.0"
    package = types.ModuleType("substance_painter")
    package.ui, package.application = ui, application
    monkeypatch.setitem(sys.modules, "substance_painter", package)
    monkeypatch.setitem(sys.modules, "substance_painter.ui", ui)
    monkeypatch.setitem(sys.modules, "substance_painter.application", application)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(sys, "path", list(sys.path))
    saved_modules = dict(sys.modules)
    yield ui, qt_app
    for name in [n for n in sys.modules if n not in saved_modules]:
        del sys.modules[name]
    sys.modules.update(saved_modules)


def test_loader_installs_starts_and_closes_the_bundled_app(painter, tmp_path):
    ui, qt_app = painter
    import ShelfPlus

    ShelfPlus.start_plugin()
    try:
        data = tmp_path / "ShelfPlus"
        version = (PLUGIN_DIR / "VERSION").read_text(encoding="utf-8")
        installed = [p.name for p in (data / "versions").iterdir()]
        assert len(installed) == 1 and installed[0] in version
        assert (data / "layout.json").is_file()
        assert (data / "panel.json").is_file()
        app_file = Path(sys.modules["shelfplus_app"].__file__)
        assert app_file.is_relative_to(data / "versions" / installed[0])

        [(widget, ui_modes, dock)] = ui.added
        assert widget.objectName() == "ShelfPlusPanel"
        assert ui_modes == FakePainterUi.UIMode.Edition
        assert not widget.windowIcon().isNull()
        names = [t.toolTip() for t in widget.findChildren(QtWidgets.QToolButton, "ShelfPlusTile")]
        assert names == ["Save", "Fill layer + Black mask"]
        group = widget.findChild(QtWidgets.QLabel, "ShelfPlusGroupName")
        assert group.text() == "General"

        menu = widget.findChild(QtWidgets.QToolButton, "ShelfPlusPanelMenu").menu()
        texts = [a.text() for a in menu.actions() if not a.isSeparator()]
        assert texts[0] == f"Shelf+ v{installed[0]}"
        copy = next(a for a in menu.actions() if a.text() == "Copy diagnostics")
        copy.trigger()
        clipboard = QtGui.QGuiApplication.clipboard().text()
        assert "Painter version: 11.1.0" in clipboard
        assert "Loaded Shelf+ v" in clipboard  # the loader's own log lines are included
    finally:
        ShelfPlus.close_plugin()

    assert ui.deleted == [dock]
    assert not [n for n in sys.modules if n.startswith("shelfplus_app")]
    assert not logging.getLogger("ShelfPlus").handlers
    assert (tmp_path / "ShelfPlus" / "logs" / "shelfplus.log").is_file()
    qt_app.processEvents()
