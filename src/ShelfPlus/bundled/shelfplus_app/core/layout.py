"""The Layout: Groups and their Buttons (PRD R3.2, schema v1).

Buttons keep the exact JSON object they were loaded from (``raw``), so a Button
this code cannot understand ("invalid") is written back unchanged on save, and
keys added by newer code survive a round trip.
"""

import re
import secrets
from dataclasses import dataclass, field

from .channels import value_range

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


_HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{6}")


def _number_in(v, low, high):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and low <= v <= high


def _channels(v):
    return isinstance(v, list) and v != [] and all(_text(c) for c in v) and len(set(v)) == len(v)


def _resource_ref(v):
    """``{"resource": url, "resource_name": optional display name}``"""
    return (
        isinstance(v, dict)
        and _resource(v.get("resource"))
        and set(v) <= {"resource", "resource_name"}
        and ("resource_name" not in v or _text(v["resource_name"]))
    )


def _anchor_ref(v):
    """``{"anchor": name}``: the anchor point of that exact name in the texture set's stack."""
    return isinstance(v, dict) and set(v) == {"anchor"} and _text(v["anchor"])


def _source(v, channel):
    """One channel of a Fill layer: ``{"color": "#rrggbb"}``, ``{"value": 0..1}``, a resource or an
    anchor point. A value is checked against the channel's own range (``channels.value_range``)."""
    if not isinstance(v, dict) or len(v) == 0:
        return False
    if "anchor" in v:
        return _anchor_ref(v)
    if set(v) == {"color"}:
        return isinstance(v["color"], str) and _HEX_COLOUR.fullmatch(v["color"]) is not None
    if set(v) == {"value"}:
        return _number_in(v["value"], *value_range(channel))
    return _resource_ref(v)


def _sources(v):
    return isinstance(v, dict) and v != {} and all(_text(k) and _source(x, k) for k, x in v.items())


def _mask_source(v):
    """A mask's Fill: ``{"value": 0..1}``, a resource or an anchor point (a mask is grey: no colour)."""
    if isinstance(v, dict) and set(v) == {"value"}:
        return _number_in(v["value"], 0, 1)
    if isinstance(v, dict) and "anchor" in v:
        return _anchor_ref(v)
    return _resource_ref(v)


def _opacity(v):
    return isinstance(v, dict) and v != {} and all(
        isinstance(k, str) and isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x <= 100
        for k, x in v.items()
    )


STEP_PARAMS = {
    "add_layer": {"layer": _one_of("fill", "paint", "folder")},
    "add_mask": {"background": _one_of("black", "white")},
    "add_effect": {
        "effect": _one_of("generator", "filter", "levels", "anchor", "fill", "paint"),
        "target": _one_of("mask", "layer"),
    },
    "set_blend": {"blend": _text},
    "set_opacity": {"opacity": _opacity},
    "set_fill": {},
    "add_smart": {"smart": _one_of("material", "mask"), "resource": _resource},
    "select_layer": {"name": _text},
    "select_brush": {"resource": _resource},
    "run_action": {"action": _text},
    "save": {},
}

# ``resource_name``: the resource's display name, stored with its URL (R3.2) when the
# Workflow editor knows it.
OPTIONAL_STEP_PARAMS = {
    # ``channels``: the new layer's active channels (ChannelType names); a Fill layer's
    # content: ``material`` (one resource for every channel) or ``sources`` (per channel).
    "add_layer": {
        "name": lambda v: isinstance(v, str),
        "channels": _channels,
        "material": _resource_ref,
        "sources": _sources,
    },
    # A Fill effect's content: on the layer like a Fill layer's; on the mask one ``source``.
    # ``name``: an anchor point's (Painter's default name without it).
    "add_effect": {
        "name": _text,
        "resource_name": _text,
        "channels": _channels,
        "material": _resource_ref,
        "sources": _sources,
        "source": _mask_source,
    },
    # The Current layer's channels switched on and off (only those; the others stay as they
    # are), and a Fill layer's content in a new Fill layer's form.
    "set_fill": {
        "channels_on": _channels,
        "channels_off": _channels,
        "material": _resource_ref,
        "sources": _sources,
    },
    "add_smart": {"resource_name": _text},
    "select_brush": {"resource_name": _text},
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
    if kind == "add_layer":
        return _layer_content_problem(step)
    if kind == "add_effect":
        return _effect_content_problem(step)
    if kind == "set_fill":
        return _set_fill_problem(step)
    return None


CONTENT_KEYS = ("channels", "material", "sources", "source")


def _content_problem(step, kind):
    """``material`` xor ``sources``, and ``sources`` only on chosen ``channels``."""
    if "material" in step and "sources" in step:
        return f"Step '{kind}' has both 'material' and 'sources'"
    if "channels" in step:
        for channel in step.get("sources", {}):
            if channel not in step["channels"]:
                return f"Step '{kind}' sets '{channel}', which is not one of its channels"
    return None


def _layer_content_problem(step):
    if "source" in step:
        return "Step 'add_layer' cannot have 'source'"
    has_content = "material" in step or "sources" in step
    if has_content and step["layer"] != "fill":
        return f"Step 'add_layer' ({step['layer']}) cannot have 'material' or 'sources'"
    return _content_problem(step, "add_layer")


def _effect_content_problem(step):
    if "name" in step and step["effect"] != "anchor":
        return f"Step 'add_effect' ({step['effect']}) cannot have 'name'"
    if not any(key in step for key in CONTENT_KEYS):
        return None
    if step["effect"] != "fill":
        return f"Step 'add_effect' ({step['effect']}) has no content"
    if step["target"] == "mask":
        if any(key in step for key in ("channels", "material", "sources")):
            return "Step 'add_effect' on the mask takes only 'source'"
        return None
    if "source" in step:
        return "Step 'add_effect' on the layer cannot have 'source'"
    return _content_problem(step, "add_effect")


SET_FILL_KEYS = ("channels_on", "channels_off", "material", "sources")


def _set_fill_problem(step):
    if "source" in step or "channels" in step:
        return f"Step 'set_fill' cannot have '{'source' if 'source' in step else 'channels'}'"
    if not any(key in step for key in SET_FILL_KEYS):
        return "Step 'set_fill' changes nothing"
    on, off = step.get("channels_on", []), step.get("channels_off", [])
    both = next((c for c in on if c in off), None)
    if both:
        return f"Step 'set_fill' switches '{both}' both on and off"
    if "material" in step and "sources" in step:
        return "Step 'set_fill' has both 'material' and 'sources'"
    switched_off = next((c for c in step.get("sources", {}) if c in off), None)
    if switched_off:
        return f"Step 'set_fill' sets '{switched_off}', which it switches off"
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

    @property
    def icon(self):
        """The relative path of the Button's own icon file, or ``None`` (automatic icon)."""
        icon = self._get("icon")
        return icon if _text(icon) else None


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

