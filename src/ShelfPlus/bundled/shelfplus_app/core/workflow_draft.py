"""The Workflow open in the editor (PRD R7), without Qt.

It holds the flat ``steps[]`` (always in the order the block tree draws them, see
``blocks.py``), the selected Step, the name and the pending icon choice. Nothing is
written until the App saves it; Steps that are still incomplete (a smart mask without a
resource, ``select_layer`` without a name…) block saving.
"""

from urllib.parse import unquote

from . import blocks
from .layout import SET_FILL_KEYS, step_problem
from .workflow import ANCHOR_POINT_NAME, step_label

NEW_NAME = "New Workflow"

# The Steps that can be added by hand: (section, label) in menu order. ``template(label)``
# gives the Step; those that need a choice start incomplete.
_TEMPLATES = [
    ("Layer", "Fill layer", {"type": "add_layer", "layer": "fill"}),
    ("Layer", "Paint layer", {"type": "add_layer", "layer": "paint"}),
    ("Layer", "Folder", {"type": "add_layer", "layer": "folder"}),
    ("Layer", "Smart material", {"type": "add_smart", "smart": "material"}),
    ("Layer", "Select layer by name", {"type": "select_layer", "name": ""}),
    ("Mask", "Black mask", {"type": "add_mask", "background": "black"}),
    ("Mask", "White mask", {"type": "add_mask", "background": "white"}),
    ("Mask", "Smart mask", {"type": "add_smart", "smart": "mask"}),
    ("Effect", "Generator on mask", {"type": "add_effect", "effect": "generator", "target": "mask"}),
    ("Effect", "Filter on mask", {"type": "add_effect", "effect": "filter", "target": "mask"}),
    ("Effect", "Levels on mask", {"type": "add_effect", "effect": "levels", "target": "mask"}),
    ("Effect", "Anchor point on mask", {"type": "add_effect", "effect": "anchor", "target": "mask"}),
    ("Effect", "Paint on mask", {"type": "add_effect", "effect": "paint", "target": "mask"}),
    ("Effect", "Fill on mask", {"type": "add_effect", "effect": "fill", "target": "mask"}),
    ("Effect", "Generator on layer", {"type": "add_effect", "effect": "generator", "target": "layer"}),
    ("Effect", "Filter on layer", {"type": "add_effect", "effect": "filter", "target": "layer"}),
    ("Effect", "Levels on layer", {"type": "add_effect", "effect": "levels", "target": "layer"}),
    ("Effect", "Anchor point on layer", {"type": "add_effect", "effect": "anchor", "target": "layer"}),
    ("Effect", "Paint on layer", {"type": "add_effect", "effect": "paint", "target": "layer"}),
    ("Effect", "Fill on layer", {"type": "add_effect", "effect": "fill", "target": "layer"}),
    ("Setting", "Blend mode", {"type": "set_blend", "blend": "Normal"}),
    ("Setting", "Opacity", {"type": "set_opacity", "opacity": {"BaseColor": 100}}),
    ("Setting", "Fill content", {"type": "set_fill"}),
    ("At the end", "Brush", {"type": "select_brush"}),
    ("At the end", "Menu command", {"type": "run_action", "action": ""}),
    ("At the end", "Save", {"type": "save"}),
]
CATALOG = [(section, label) for section, label, _ in _TEMPLATES]



def template(label):
    """A new Step for a catalog entry."""
    step = next(s for _, name, s in _TEMPLATES if name == label)
    return {k: (dict(v) if isinstance(v, dict) else v) for k, v in step.items()}


def takes_resource(step):
    kind = step.get("type")
    return kind in ("select_brush", "add_smart") or (kind == "add_effect" and step.get("effect") in ("generator", "filter"))


def needs_resource(step):
    """A Step that takes a resource and has none yet."""
    return takes_resource(step) and not step.get("resource")


def _content_slots(step):
    if step.get("type") not in ("add_layer", "add_effect", "set_fill"):
        return []
    return [step.get("material"), step.get("source")] + list((step.get("sources") or {}).values())


def layer_resource_missing(step):
    """A layer's or Fill effect's material or a channel's resource is not chosen yet."""
    return any(isinstance(s, dict) and "resource" in s and not s["resource"] for s in _content_slots(step))


def anchor_name_missing(step):
    """A channel's anchor point source has no name yet."""
    return any(isinstance(s, dict) and "anchor" in s and not s["anchor"] for s in _content_slots(step))


def incomplete(step):
    """What is missing from the Step, for its row ("⚠ choose resource"), or ``None``."""
    problem = step_problem(step)
    if problem is None:
        return None
    if needs_resource(step) or layer_resource_missing(step):
        return "⚠ choose resource"
    if anchor_name_missing(step):
        return "⚠ enter an anchor point name"
    if step.get("type") == "set_fill" and not any(key in step for key in SET_FILL_KEYS):
        return "⚠ choose what to change"
    if step.get("type") == "select_layer":
        return "⚠ enter a name"
    if step.get("type") == "run_action":
        return "⚠ choose a command"
    return f"⚠ {problem}"


def resource_name(url):
    """The display name in a version-less URL: ``resource://starter_assets/Dirt`` -> ``Dirt``."""
    if not isinstance(url, str) or not url:
        return None
    name = unquote(url.partition("?")[0].rstrip("/").rpartition("/")[2])
    return name or None


_LAYERS = {"fill": "Fill layer", "paint": "Paint layer", "folder": "Folder"}
_EFFECTS = {
    "generator": "Generator",
    "filter": "Filter",
    "levels": "Levels",
    "anchor": "Anchor point",
    "fill": "Fill",
    "paint": "Paint",
}


def short_name(step):
    """A Step in a few words, as the automatic name and the tree's rows show it."""
    kind = step.get("type")
    resource = step.get("resource_name") or resource_name(step.get("resource"))
    if kind == "add_layer":
        name = step.get("name") or _LAYERS.get(step.get("layer"), "Layer")
        material = step.get("material") or {}
        material_name = material.get("resource_name") or resource_name(material.get("resource"))
        return f"{name}: {material_name}" if material_name else name
    if kind == "add_mask":
        return f"{str(step.get('background')).capitalize()} mask"
    if kind == "add_effect":
        material = step.get("material") or {}
        material_name = material.get("resource_name") or resource_name(material.get("resource"))
        if material_name:
            return f"{_EFFECTS.get(step.get('effect'), 'Effect')}: {material_name}"
        if step.get("effect") == "anchor" and step.get("name") not in (None, "", ANCHOR_POINT_NAME):
            return f"Anchor point “{step['name']}”"
        return resource or _EFFECTS.get(step.get("effect"), "Effect")
    if kind == "add_smart":
        return resource or f"Smart {step.get('smart')}"
    if kind == "set_blend":
        return f"Blend {step.get('blend')}"
    if kind == "set_opacity":
        values = set((step.get("opacity") or {}).values())
        return f"Opacity {values.pop():g}%" if len(values) == 1 else "Opacity"
    if kind == "set_fill":
        return "Fill content"
    if kind == "select_layer":
        return f"“{step['name']}”" if step.get("name") else "Select layer"
    if kind == "select_brush":
        return resource or "Brush"
    if kind == "run_action":
        return step.get("action") or "Menu command"
    if kind == "save":
        return "Save"
    return str(kind)


def _count(items, one):
    items = list(items)
    return items[0] if len(items) == 1 else f"{len(items)} {one}s"


def source_text(source):
    """One source in a word or two: ``value 0.3``, ``#ff0000``, ``Clouds 1``, ``anchor “Edges”``."""
    if not isinstance(source, dict):
        return None
    if "value" in source:
        return f"value {source['value']:g}"
    if "color" in source:
        return source["color"]
    if source.get("anchor"):
        return f"anchor “{source['anchor']}”"
    if source.get("resource"):
        return source.get("resource_name") or resource_name(source["resource"])
    return None


def _anchors(sources):
    names = dict.fromkeys(s["anchor"] for s in sources if isinstance(s, dict) and s.get("anchor"))
    return ", ".join(f"anchor “{name}”" for name in names) or None


def _content_detail(step):
    """A Fill's content in a word or two (a material is already in the name)."""
    if "sources" in step:
        return ", ".join(p for p in ("per channel", _anchors(step["sources"].values())) if p)
    return source_text(step.get("source"))


def _fill_change_detail(step):
    """What a ``set_fill`` Step changes: ``BaseColor anchor “Edges”``, ``Height on``…"""
    parts = []
    material = step.get("material")
    if material:
        parts.append(f"material {material.get('resource_name') or resource_name(material.get('resource')) or '?'}")
    sources = step.get("sources") or {}
    if len(sources) == 1:
        (channel, source), = sources.items()
        parts.append(" ".join(p for p in (channel, source_text(source)) if p))
    elif sources:
        parts.append(f"{len(sources)} channels set")
    for key, word in (("channels_on", "on"), ("channels_off", "off")):
        if step.get(key):
            parts.append(f"{_count(step[key], 'channel')} {word}")
    return parts


def row_detail(step):
    """What the Step applies to, shown after its name in the editor's rows ("on mask",
    "generator on mask", "BaseColor"…), or ``None`` when the name says it all. Not
    part of the automatic Workflow name."""
    kind = step.get("type")
    parts = []
    if kind == "add_layer":
        if step.get("name"):  # its own name hides what kind of layer it is
            parts.append(_LAYERS.get(step.get("layer"), "Layer"))
        parts.append(_content_detail(step))
        if "channels" in step:
            parts.append(_count(step["channels"], "channel"))
    elif kind == "add_effect":
        target = f"on {step.get('target')}"
        named = step.get("resource") or step.get("material")  # the name is the resource's
        parts.append(f"{_EFFECTS.get(step.get('effect'), 'effect').lower()} {target}" if named and "material" not in step else target)
        parts.append(_content_detail(step))
        if "channels" in step:
            parts.append(_count(step["channels"], "channel"))
    elif kind == "add_smart":
        if step.get("resource"):  # without one the name is "Smart mask" already
            parts.append(f"smart {step.get('smart')}")
    elif kind == "set_opacity":
        parts.append(_count((step.get("opacity") or {}).keys(), "channel") if step.get("opacity") else None)
    elif kind == "set_fill":
        parts.extend(_fill_change_detail(step))
    elif kind == "select_layer":
        if step.get("name"):
            parts.append("select layer")
    elif kind == "select_brush":
        if step.get("resource"):
            parts.append("brush")
    elif kind == "run_action":
        if step.get("action"):
            parts.append("menu command")
    parts = [p for p in parts if p]
    return ", ".join(parts) or None


def auto_name(steps):
    """"Fill layer + Black mask + Dirt": the name of a Workflow the user has not named."""
    return " + ".join(short_name(s) for s in steps) or NEW_NAME


class WorkflowDraft:
    def __init__(self, steps=(), name=None, button_id=None):
        self.steps = blocks.normalized([dict(s) for s in steps])
        self.button_id = button_id  # ``None``: a new Workflow
        self._name = None if name is None or name == auto_name(self.steps) else name
        self.selected = None
        # the icon: a PNG (bytes) replaces the current one; ``icon_reset``: back to automatic
        self.icon_png = None
        self.icon_reset = False

    # -- name ----------------------------------------------------------------

    @property
    def name_is_automatic(self):
        return self._name is None

    @property
    def name(self):
        return self._name if self._name is not None else auto_name(self.steps)

    def set_name(self, text):
        text = (text or "").strip()
        self._name = text if text and text != auto_name(self.steps) else None

    # -- selection -----------------------------------------------------------

    def select(self, index):
        self.selected = index if index is not None and 0 <= index < len(self.steps) else None

    @property
    def selected_step(self):
        return None if self.selected is None else self.steps[self.selected]

    def _apply(self, steps, keep):
        """Take the new list; ``keep`` (a Step object) stays selected."""
        if steps is None:
            return False
        self.steps = steps
        self.selected = next((i for i, s in enumerate(steps) if s is keep), None)
        return True

    # -- editing -------------------------------------------------------------

    def add(self, step):
        self.steps, self.selected = blocks.insert(self.steps, step, self.selected)

    def delete(self, index):
        keep = self.selected_step if self.selected != index else None
        self._apply(blocks.delete(self.steps, index), keep)

    def move_up(self, index):
        return self._apply(blocks.move_up(self.steps, index), self.steps[index])

    def move_down(self, index):
        return self._apply(blocks.move_down(self.steps, index), self.steps[index])

    def drop(self, source, gap):
        """A dragged row dropped at ``gap`` of ``blocks.rows(steps, dragging=True)``.
        ``False``: it breaks a rule and snaps back (nothing changes)."""
        return self._apply(blocks.drop(self.steps, source, gap), self.steps[source])

    def set_step(self, index, step):
        """The settings panel changed a Step (its kind of row stays the same)."""
        self.steps[index] = step
        self._apply(blocks.normalized(self.steps), self.steps[self.selected] if self.selected is not None else None)

    def fill_resource(self, url, name=None):
        """A resource dropped while a Step still waiting for its resource is selected fills
        that Step (``name``: its display name, if known). Returns whether it did."""
        step = self.selected_step
        if step is None or not needs_resource(step):
            return False
        filled = {**step, "resource": url}
        filled.pop("resource_name", None)
        if name:
            filled["resource_name"] = name
        self.steps[self.selected] = filled
        return True

    # -- saving --------------------------------------------------------------

    @property
    def problem(self):
        """Why it cannot be saved yet, or ``None``."""
        if not self.steps:
            return "Add a Step first."
        for index, step in enumerate(self.steps):
            note = incomplete(step)
            if note:
                return f"Step {index + 1} ({step_label(step)}) is incomplete: {note}"
        return None

    def to_raw(self):
        """The Workflow button's JSON without ``id`` and ``icon``."""
        return {"kind": "workflow", "name": self.name, "steps": [dict(s) for s in self.steps]}
