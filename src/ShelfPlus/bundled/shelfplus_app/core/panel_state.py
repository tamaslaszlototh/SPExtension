"""``panel.json``: the Panel's view state and the updater's state (PRD R3.1).

A missing or broken file, or a wrong value, silently falls back to the default.
"""

import copy
import json
import logging
from pathlib import Path

from . import jsonio

log = logging.getLogger("ShelfPlus.app.panel_state")

# The tile size slider: any whole number of pixels in this range.
TILE_SIZE_MIN = 40
TILE_SIZE_MAX = 80


def valid_tile_size(value):
    return isinstance(value, int) and not isinstance(value, bool) and TILE_SIZE_MIN <= value <= TILE_SIZE_MAX

DEFAULTS = {
    "collapsedGroups": [],
    "tileSize": 48,
    "showLabels": False,
    "updater": {"lastCheck": None, "skippedVersion": None},
}


def _number_or_none(v):
    return v is None or (isinstance(v, (int, float)) and not isinstance(v, bool))


def _text_or_none(v):
    return v is None or isinstance(v, str)


def _normalise(data):
    state = copy.deepcopy(DEFAULTS)
    if not isinstance(data, dict):
        return state
    for key, value in data.items():
        if key not in DEFAULTS:
            state[key] = value  # written by newer code: keep it
    groups = data.get("collapsedGroups")
    if isinstance(groups, list):
        state["collapsedGroups"] = [g for g in groups if isinstance(g, str)]
    if valid_tile_size(data.get("tileSize")):
        state["tileSize"] = data["tileSize"]
    if isinstance(data.get("showLabels"), bool):
        state["showLabels"] = data["showLabels"]
    updater = data.get("updater")
    if isinstance(updater, dict):
        for key, value in updater.items():
            if key not in DEFAULTS["updater"]:
                state["updater"][key] = value
        if _number_or_none(updater.get("lastCheck")):
            state["updater"]["lastCheck"] = updater.get("lastCheck")
        if _text_or_none(updater.get("skippedVersion")):
            state["updater"]["skippedVersion"] = updater.get("skippedVersion")
    return state


class PanelStateStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        """Read the state; create the file with defaults if it is missing."""
        if not self.path.exists():
            state = copy.deepcopy(DEFAULTS)
            try:
                self.save(state)
            except OSError:
                log.exception("Could not write %s", self.path)
            return state
        try:
            data = json.loads(self.path.read_bytes().decode("utf-8-sig"))
        except (OSError, ValueError):
            log.info("panel.json is unreadable; using defaults")
            data = None
        return _normalise(data)

    def save(self, state):
        jsonio.write_json_atomic(self.path, state)
