"""The Layout: Groups and their Buttons (PRD R3.2, schema v1).

Buttons keep the exact JSON object they were loaded from (``raw``), so a Button
this code cannot understand ("invalid") is written back unchanged on save, and
keys added by newer code survive a round trip.
"""

import secrets
from dataclasses import dataclass, field

SCHEMA_VERSION = 1

BUTTON_KINDS = ("brush", "menu", "workflow")


class LayoutError(ValueError):
    """The document is not a Layout at all (as opposed to one invalid Button)."""


def new_id():
    """A stable, short, random id for a new Group or Button."""
    return secrets.token_hex(4)


# -- validation -------------------------------------------------------------
#
# One table per Step type: parameter name -> check. Optional parameters are
# listed in OPTIONAL. Later slices refine the less settled Steps.


def _one_of(*values):
    return lambda v: v in values


def _text(v):
    return isinstance(v, str) and v != ""


def _resource(v):
    return isinstance(v, str) and v.startswith("resource://")


def _opacity(v):
    return isinstance(v, dict) and v != {} and all(
        isinstance(k, str) and isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x <= 100
        for k, x in v.items()
    )


STEP_PARAMS = {
    "add_layer": {"layer": _one_of("fill", "paint", "folder")},
    "add_mask": {"background": _one_of("black", "white")},
    "add_effect": {"effect": _one_of("generator", "filter", "levels", "anchor"), "target": _one_of("mask", "layer")},
    "set_blend": {"blend": _text},
    "set_opacity": {"opacity": _opacity},
    "add_smart": {"smart": _one_of("material", "mask"), "resource": _resource},
    "select_layer": {"name": _text},
    "select_brush": {"resource": _resource},
    "run_action": {"action": _text},
    "save": {},
}

OPTIONAL_STEP_PARAMS = {
    "add_layer": {"name": lambda v: isinstance(v, str)},
}


def step_problem(step):
    if not isinstance(step, dict):
        return "a Step is not an object"
    kind = step.get("type")
    if kind not in STEP_PARAMS:
        return f"unknown Step type {kind!r}"
    for name, check in STEP_PARAMS[kind].items():
        if name not in step:
            return f"Step {kind!r} is missing {name!r}"
        if not check(step[name]):
            return f"Step {kind!r} has an invalid {name!r}"
    for name, check in OPTIONAL_STEP_PARAMS.get(kind, {}).items():
        if name in step and not check(step[name]):
            return f"Step {kind!r} has an invalid {name!r}"
    if kind == "add_effect" and step["effect"] in ("generator", "filter") and not _resource(step.get("resource")):
        return f"Step 'add_effect' ({step['effect']}) is missing 'resource'"
    return None


def _icon_ok(raw):
    return "icon" not in raw or raw["icon"] is None or _text(raw["icon"])


def button_problem(raw):
    """Why this Button cannot be used, or ``None`` if it is valid."""
    if not isinstance(raw, dict):
        return "the Button is not an object"
    for name in ("id", "name"):
        if not _text(raw.get(name)):
            return f"missing {name!r}"
    kind = raw.get("kind")
    if kind not in BUTTON_KINDS:
        return f"unknown kind {kind!r}"
    if not _icon_ok(raw):
        return "invalid 'icon'"
    if kind == "brush" and not _resource(raw.get("resource")):
        return "missing 'resource'"
    if kind == "menu" and not _text(raw.get("action")):
        return "missing 'action'"
    if kind == "workflow":
        steps = raw.get("steps")
        if not isinstance(steps, list) or not steps:
            return "missing 'steps'"
        for index, step in enumerate(steps, start=1):
            problem = step_problem(step)
            if problem:
                return f"Step {index}: {problem}"
    return None


# -- model ------------------------------------------------------------------


@dataclass
class Button:
    raw: object
    problem: str = None

    @classmethod
    def from_json(cls, raw):
        return cls(raw, button_problem(raw))

    @property
    def valid(self):
        return self.problem is None

    def _get(self, key):
        return self.raw.get(key) if isinstance(self.raw, dict) else None

    @property
    def id(self):
        return self._get("id")

    @property
    def kind(self):
        return self._get("kind")

    @property
    def name(self):
        name = self._get("name")
        return name if _text(name) else "(invalid)"


@dataclass
class Group:
    id: str
    name: str
    buttons: list = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_json(cls, raw):
        if not isinstance(raw, dict):
            raise LayoutError("a Group is not an object")
        if not _text(raw.get("id")) or not isinstance(raw.get("name"), str):
            raise LayoutError("a Group is missing its id or name")
        buttons = raw.get("buttons", [])
        if not isinstance(buttons, list):
            raise LayoutError(f"Group {raw['id']!r} has no Button list")
        extra = {k: v for k, v in raw.items() if k not in ("id", "name", "buttons")}
        return cls(raw["id"], raw["name"], [Button.from_json(b) for b in buttons], extra)

    def to_json(self):
        data = {"id": self.id, "name": self.name}
        data.update(self.extra)
        data["buttons"] = [b.raw for b in self.buttons]
        return data


@dataclass
class Layout:
    schema_version: int = SCHEMA_VERSION
    groups: list = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_json(cls, data):
        if not isinstance(data, dict):
            raise LayoutError("the Layout is not an object")
        version = data.get("schemaVersion")
        if not isinstance(version, int) or isinstance(version, bool):
            raise LayoutError("missing schemaVersion")
        groups = data.get("groups")
        if not isinstance(groups, list):
            raise LayoutError("missing groups")
        extra = {k: v for k, v in data.items() if k not in ("schemaVersion", "groups")}
        return cls(version, [Group.from_json(g) for g in groups], extra)

    def to_json(self):
        data = {"schemaVersion": self.schema_version}
        data.update(self.extra)
        data["groups"] = [g.to_json() for g in self.groups]
        return data


def layout_lines(layout):
    """Plain-text listing of the Layout for the first Panel slice."""
    lines = []
    for group in layout.groups:
        lines.append(group.name)
        for button in group.buttons:
            lines.append("    " + button.name + ("" if button.valid else "  (invalid)"))
    return lines
