"""The REC bar and the editor's Continue (PRD R8.1), offscreen over a real App and the
fake adapter."""

import os
import shutil
from pathlib import Path

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from shelfplus_app.adapter.fake import FakeAdapter, FakeLayer  # noqa: E402
from shelfplus_app.app import App  # noqa: E402
from shelfplus_app.ui.panel import REC_OFF, REC_ON, QtPanelView  # noqa: E402

BUNDLED = Path(__file__).parents[1] / "src" / "ShelfPlus" / "bundled"


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
    adapter.history = ["Open project"]
    adapter.history_index = 1
    return adapter


@pytest.fixture
def app(qt_app, tmp_path, adapter):
    version_dir = tmp_path / "versions" / "0.8.0"
    version_dir.mkdir(parents=True)
    shutil.copy(BUNDLED / "default_layout.json", version_dir / "default_layout.json")
    env = {"version": "0.8.0", "version_dir": str(version_dir), "data_dir": str(tmp_path), "loader_version": 1}
    app = App(env, adapter, QtPanelView)
    app.start()
    app.view.widget.resize(280, 700)
    app.view.widget.show()
    qt_app.processEvents()
    yield app
    app.close()
    qt_app.processEvents()


def add_fill(adapter):
    layer = FakeLayer("Fill layer 1", "fill")
    adapter.stack.layers.insert(0, layer)
    adapter.stack.selected = layer
    adapter.push_history("Add fill layer")


def test_the_rec_bar_shows_while_recording_with_the_step_count(app, adapter, qt_app):
    view = app.view
    assert not view.rec_bar.isVisible()

    app.start_recording(app.layout.groups[0])
    qt_app.processEvents()
    assert view.rec_bar.isVisible() and view.rec_text.text() == "General: 0 Steps"
    assert view.rec_timer.isActive()

    add_fill(adapter)
    assert view.rec_text.text() == "General: 1 Step"


def test_the_dot_blinks(app, qt_app):
    app.start_recording(app.layout.groups[0])

    first = app.view.rec_dot.text()
    app.view._blink()

    assert {first, app.view.rec_dot.text()} == {REC_ON, REC_OFF}


def test_stop_opens_the_editor_with_the_steps(app, adapter, qt_app):
    view = app.view
    app.start_recording(app.layout.groups[0])
    add_fill(adapter)

    view.rec_stop.click()
    qt_app.processEvents()

    assert not view.rec_bar.isVisible() and not view.rec_timer.isActive()
    assert view.workflow_editor is not None and view.workflow_editor.isVisible()
    assert app.workflow_draft.steps == [{"type": "add_layer", "layer": "fill"}]


def test_continue_in_the_editor_records_more_and_comes_back(app, adapter, qt_app):
    view = app.view
    app.new_workflow(app.layout.groups[0])
    qt_app.processEvents()
    editor = view.workflow_editor

    editor.record_button.click()
    qt_app.processEvents()
    assert view.rec_bar.isVisible() and view.workflow_editor is None

    add_fill(adapter)
    view.rec_stop.click()
    qt_app.processEvents()
    assert view.workflow_editor is not None
    assert app.workflow_draft.steps == [{"type": "add_layer", "layer": "fill"}]
