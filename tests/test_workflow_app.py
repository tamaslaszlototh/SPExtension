"""Workflow buttons in the App (PRD R4): the default Layout's Buttons run through the runner."""

import shutil
from pathlib import Path

import pytest

from shelfplus_app.adapter.fake import FakeAdapter, FakeLayer
from shelfplus_app.app import App

BUNDLED = Path(__file__).parents[1] / "src" / "ShelfPlus" / "bundled"


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
def env(tmp_path):
    """No layout.json: the default Layout ("Save", "Fill layer + Black mask") is copied in."""
    version_dir = tmp_path / "versions" / "0.5.0"
    version_dir.mkdir(parents=True)
    shutil.copy(BUNDLED / "default_layout.json", version_dir / "default_layout.json")
    return {"version": "0.5.0", "version_dir": str(version_dir), "data_dir": str(tmp_path), "loader_version": 1}


@pytest.fixture
def base():
    return FakeLayer("Base")


@pytest.fixture
def adapter(base):
    adapter = FakeAdapter()
    adapter.project_is_open = True
    adapter.stack.layers = [base]
    return adapter


def started(env, adapter):
    app = App(env, adapter, FakeView)
    app.start()
    return app


def button(app, name):
    return next(b for g in app.layout.groups for b in g.buttons if b.name == name)


def test_fill_layer_and_black_mask(env, adapter, base):
    adapter.stack.selected = base
    app = started(env, adapter)

    app.run_button(button(app, "Fill layer + Black mask"))

    fill = adapter.stack.layers[0]
    assert [layer.name for layer in adapter.stack.layers] == ["Fill layer", "Base"]
    assert fill.mask == "black" and adapter.stack.selected is fill
    assert adapter.stack.scopes == ["Shelf+: Fill layer + Black mask"]
    assert app.view.notes == []


def test_save(env, adapter):
    app = started(env, adapter)

    app.run_button(button(app, "Save"))

    assert adapter.saves == 1 and app.view.notes == []


def test_a_failure_is_shown(env, adapter):
    adapter.project_is_open = False
    app = started(env, adapter)

    app.run_button(button(app, "Fill layer + Black mask"))

    assert app.view.notes == ["“Fill layer + Black mask” did not start: open a project first."]
    assert adapter.stack.scopes == []


def test_a_workflow_is_never_badged_missing(env, adapter):
    app = started(env, adapter)
    save = button(app, "Save")
    adapter.save_error = RuntimeError("The project is locked.")

    app.run_button(save)

    assert not app.is_missing(save)
    assert app.view.notes == ["“Save” stopped at Step 1 (Save): The project is locked."]
