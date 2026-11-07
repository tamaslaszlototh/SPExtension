"""The Workflow open in the editor (PRD R7), without Qt.

It holds the flat ``steps[]`` (always in the order the block tree draws them, see
``blocks.py``), the selected Step, the name and the pending icon choice. Nothing is
written until the App saves it; Steps that are still incomplete (a smart mask without a
resource, ``select_layer`` without a name…) block saving.
"""

from urllib.parse import unquote

from . import blocks
from .layout import step_problem
from .workflow import step_label

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
    ("Effect", "Generator on the mask", {"type": "add_effect", "effect": "generator", "target": "mask"}),
    ("Effect", "Filter on the mask", {"type": "add_effect", "effect": "filter", "target": "mask"}),
    ("Effect", "Levels on the mask", {"type": "add_effect", "effect": "levels", "target": "mask"}),
    ("Effect", "Anchor point on the mask", {"type": "add_effect", "effect": "anchor", "target": "mask"}),
    ("Effect", "Generator on the layer", {"type": "add_effect", "effect": "generator", "target": "layer"}),
    ("Effect", "Filter on the layer", {"type": "add_effect", "effect": "filter", "target": "layer"}),
    ("Effect", "Levels on the layer", {"type": "add_effect", "effect": "levels", "target": "layer"}),
    ("Effect", "Anchor point on the layer", {"type": "add_effect", "effect": "anchor", "target": "layer"}),
    ("Setting", "Blend mode", {"type": "set_blend", "blend": "Normal"}),
    ("Setting", "Opacity", {"type": "set_opacity", "opacity": {"BaseColor": 100}}),
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


def layer_resource_missing(step):
    """A new layer whose material or a channel's resource is not chosen yet."""
    if step.get("type") != "add_layer":
        return False
    slots = [step.get("material")] + list((step.get("sources") or {}).values())
    return any(isinstance(s, dict) and "resource" in s and not s["resource"] for s in slots)


def incomplete(step):
    """What is missing from the Step, for its row ("⚠ choose resource"), or ``None``."""
    problem = step_problem(step)
    if problem is None:
        return None
    if needs_resource(step) or layer_resource_missing(step):
        return "⚠ choose resource"
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
_EFFECTS = {"generator": "Generator", "filter": "Filter", "levels": "Levels", "anchor": "Anchor point"}


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
        return resource or _EFFECTS.get(step.get("effect"), "Effect")
    if kind == "add_smart":
        return resource or f"Smart {step.get('smart')}"
    if kind == "set_blend":
        return f"Blend {step.get('blend')}"
    if kind == "set_opacity":
        values = set((step.get("opacity") or {}).values())
        return f"Opacity {values.pop():g}%" if len(values) == 1 else "Opacity"
    if kind == "select_layer":
        return f"“{step['name']}”" if step.get("name") else "Select layer"
    if kind == "select_brush":
        return resource or "Brush"
    if kind == "run_action":
        return step.get("action") or "Menu command"
    if kind == "save":
        return "Save"
    return str(kind)


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
