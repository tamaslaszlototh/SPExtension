"""panel.json (PRD R3.1): view and updater state, silently falling back to defaults."""

import json

import pytest

from shelfplus_app.core.panel_state import DEFAULTS, PanelStateStore


@pytest.fixture
def path(tmp_path):
    return tmp_path / "panel.json"


def test_missing_file_gives_defaults_and_is_created(path):
    s = PanelStateStore(path)

    state = s.load()

    assert state == DEFAULTS
    assert json.loads(path.read_text(encoding="utf-8")) == DEFAULTS


def test_defaults(path):
    assert DEFAULTS == {
        "collapsedGroups": [],
        "tileSize": 48,
        "showLabels": False,
        "updater": {"lastCheck": None, "skippedVersion": None},
    }


@pytest.mark.parametrize("content", ["not json", "[]", "null", ""])
def test_broken_file_silently_gives_defaults(path, content):
    path.write_text(content, encoding="utf-8")

    assert PanelStateStore(path).load() == DEFAULTS


def test_wrong_or_missing_values_fall_back_one_by_one(path):
    path.write_text(
        json.dumps({"tileSize": 64, "showLabels": "yes", "collapsedGroups": ["g1", 3], "updater": {"skippedVersion": "0.3.0"}}),
        encoding="utf-8",
    )

    state = PanelStateStore(path).load()

    assert state["tileSize"] == 64
    assert state["showLabels"] is False
    assert state["collapsedGroups"] == ["g1"]
    assert state["updater"] == {"lastCheck": None, "skippedVersion": "0.3.0"}


def test_unknown_tile_size_falls_back(path):
    path.write_text(json.dumps({"tileSize": 41}), encoding="utf-8")

    assert PanelStateStore(path).load()["tileSize"] == 48


def test_save_round_trips_and_keeps_unknown_keys(path):
    path.write_text(json.dumps({"fromTheFuture": 1}), encoding="utf-8")
    s = PanelStateStore(path)
    state = s.load()
    state["showLabels"] = True

    s.save(state)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["showLabels"] is True
    assert saved["fromTheFuture"] == 1
    assert PanelStateStore(path).load()["showLabels"] is True


def test_loading_does_not_mutate_defaults(path):
    state = PanelStateStore(path).load()
    state["collapsedGroups"].append("g1")
    state["updater"]["lastCheck"] = 5

    assert DEFAULTS["collapsedGroups"] == []
    assert DEFAULTS["updater"]["lastCheck"] is None
