"""The Workflow runner (PRD R4), without Painter: the layer stack is reached through the adapter.

A run has four parts:

1. **Preflight** (R4.4), before anything changes: the Step order, Steps this version
   cannot run, an open project in edition state (only if a layer or ``save`` Step needs
   it), a selected layer if the first block acts on one, every resource and every menu
   command. Any failure: nothing changes, and the message names the Step.
2. Every layer Step inside **one** ``adapter.layer_scope`` (Painter's
   ``ScopedModification``: one History entry, one Ctrl+Z). Painter refuses selection
   changes inside it, so Steps work on layer handles and the **Current layer** (R4.6)
   is tracked here: it starts as the selected layer; ``add_layer`` inserts above it (on
   top of the stack when there is none) and becomes it, and so does a smart material;
   ``select_layer`` makes the one layer with that exact name it.
3. After the scope closes, the final Current layer is selected if it is not the start
   layer any more (not part of the undo).
4. The UI Steps (``select_brush``, ``run_action``, ``save``) one after another. They may
   finish later (``select_brush`` polls), so each reports through ``done(StepResult)``.

A failing Step stops the run (R4.7). There is no rollback: what the scope already did
stays and is undone with one Ctrl+Z.

The layer side of the adapter (see ``adapter/__init__.py``): ``project_ready``,
``selected_layer``, ``layer_scope``, ``insert_layer``, ``add_mask``, ``has_mask``,
``insert_effect``, ``insert_smart_material``, ``insert_smart_mask``, ``set_blend``,
``set_opacity``, ``find_layers``, ``select_layer`` and ``save_project``; for anchor points
``find_anchors``, for ``set_fill`` ``layer_kind`` and ``active_channels``.
"""

import logging

from . import brush, menu, smart_material
from .steps import DONE, FAILED, MISSING, StepResult

log = logging.getLogger("ShelfPlus.app.workflow")

UI_STEP_TYPES = ("select_brush", "run_action", "save")
SCOPE_PREFIX = "Shelf+: "  # the History entry of a Workflow's layer changes

NO_PROJECT = "open a project first"
BRUSH_NEEDS_PAINT_TARGET = (
    "needs a Paint layer or a mask: Painter does not change the brush while a Fill layer "
    "or folder is selected. Add a mask before it."
)
SELECTION_UNREADABLE = "Painter's selected layer could not be read. See the log."
LAYER_NAMES = {"fill": "Fill layer", "paint": "Paint layer", "folder": "folder"}
EFFECT_NAMES = {"anchor": "anchor point"}
NO_MASK = "The Current layer has no mask. Add a mask before this Step."
ANCHOR_POINT_NAME = "Anchor point"  # what Painter names a new anchor point
ANCHOR_EXISTS = "An anchor point named “{}” already exists."
NO_ANCHOR = "No anchor point named “{}”."
TWIN_ANCHORS = "Several anchor points named “{}”."
NEEDS_FILL = "needs a Fill layer."
NEEDS_FILL_OR_PAINT = "needs a Fill or Paint layer."


class StepError(Exception):
    """A Step that cannot do its job; the message is for the user."""


def step_label(step):
    """A Step's name for people, as messages show it."""
    kind = step.get("type")
    if kind == "add_layer":
        return f"Add {LAYER_NAMES.get(step.get('layer'), 'layer')}"
    if kind == "add_mask":
        return f"Add {step.get('background')} mask"
    if kind == "add_effect":
        effect = EFFECT_NAMES.get(step.get("effect"), step.get("effect"))
        return f"Add {effect} to the {step.get('target')}"
    if kind == "add_smart":
        return f"Add smart {step.get('smart')}"
    if kind == "set_blend":
        return f"Set blend mode to {step.get('blend')}"
    if kind == "set_opacity":
        return "Set opacity"
    if kind == "set_fill":
        return "Set Fill content"
    if kind == "select_layer":
        return f"Select layer “{step.get('name')}”"
    if kind == "select_brush":
        return "Select brush"
    if kind == "run_action":
        return "Run menu command"
    if kind == "save":
        return "Save"
    return str(kind)


def scope_label(steps, name=None):
    """The History entry of a Workflow's layer changes: "Shelf+: <name or first Step>"."""
    return SCOPE_PREFIX + (name or step_label(steps[0]))


def needs_current_layer(step):
    """Whether the Step acts on the Current layer (rather than creating or picking one)."""
    kind = step["type"]
    return kind in ("add_mask", "add_effect", "set_blend", "set_opacity", "set_fill") or (
        kind == "add_smart" and step.get("smart") == "mask"
    )


# -- the layer Steps: function(adapter, step, current) -> the new Current layer ----------


def _require(current):
    if current is None:  # preflight makes sure this does not happen
        raise StepError("there is no layer to act on")
    return current


def add_layer(adapter, step, current):
    """A new layer above the Current layer, then its active channels and (a Fill layer)
    its content: one material, or per channel a colour, value or resource.

    A Fill or Paint layer made through Painter's Python API starts with no channel
    switched on (unlike one made in Painter's own UI), so without chosen channels every
    channel of the texture set is switched on: what the editor shows as all ticked."""
    layer = adapter.insert_layer(step["layer"], above=current, name=step.get("name") or None)
    if step["layer"] in ("fill", "paint"):
        set_content(adapter, layer, step)
    return layer


def set_content(adapter, node, step):
    """A new Fill or Paint layer's, or a Fill effect's, channels and content.

    Without chosen channels every channel of the texture set is switched on (a node made
    through Painter's Python API starts with none, unlike one made in Painter's UI). That
    default is only logged if Painter refuses it; chosen channels that fail stop the Step.
    A Fill on a mask has one grey ``source`` instead."""
    if "source" in step:
        adapter.set_channel_source(node, None, dict(step["source"]))
        return
    if "channels" in step:
        adapter.set_active_channels(node, list(step["channels"]))
    else:
        channels = _texture_channels(adapter)
        if channels:
            try:
                adapter.set_active_channels(node, channels)
            except Exception:
                log.warning("Could not switch on every channel of the new %s", step["type"], exc_info=True)
    if "material" in step:
        adapter.set_material(node, step["material"]["resource"])
    for channel, source in step.get("sources", {}).items():
        adapter.set_channel_source(node, channel, dict(source))


def anchor_name(step):
    """The name an anchor point Step gives its anchor point, or ``None`` for another Step."""
    if step.get("type") == "add_effect" and step.get("effect") == "anchor":
        return step.get("name") or ANCHOR_POINT_NAME
    return None


def anchor_sources(step):
    """The names of the anchor points a Step uses as Fill sources, in order, once each."""
    sources = [step.get("source"), *(step.get("sources") or {}).values()]
    names = [s["anchor"] for s in sources if isinstance(s, dict) and s.get("anchor")]
    return list(dict.fromkeys(names))


def fill_target_problem(kind, step):
    """Why ``set_fill`` cannot act on a layer of ``kind`` (fill, paint, folder…), or ``None``."""
    if ("material" in step or "sources" in step) and kind != "fill":
        return NEEDS_FILL
    if kind not in ("fill", "paint"):
        return NEEDS_FILL_OR_PAINT
    return None


def set_fill(adapter, step, current):
    """An existing layer's channels and content: only the channels named are switched on
    or off (a channel given a source is switched on too); then a Fill layer's material or
    per-channel sources."""
    layer = _require(current)
    problem = fill_target_problem(adapter.layer_kind(layer), step)
    if problem:
        raise StepError(problem)
    off = step.get("channels_off", [])
    on = [c for c in dict.fromkeys([*step.get("channels_on", []), *step.get("sources", {})]) if c not in off]
    active = list(adapter.active_channels(layer) or [])
    wanted = [c for c in active if c not in off] + [c for c in on if c not in active]
    if wanted != active:
        adapter.set_active_channels(layer, wanted)
    if "material" in step:
        adapter.set_material(layer, step["material"]["resource"])
    for channel, source in step.get("sources", {}).items():
        adapter.set_channel_source(layer, channel, dict(source))
    return current


def add_mask(adapter, step, current):
    adapter.add_mask(_require(current), step["background"])
    return current


def set_blend(adapter, step, current):
    adapter.set_blend(_require(current), step["blend"])
    return current


def set_opacity(adapter, step, current):
    layer = _require(current)
    for channel, percent in step["opacity"].items():
        adapter.set_opacity(layer, channel, percent)
    return current


def add_effect(adapter, step, current):
    """A generator, filter (both with a resource), levels or anchor point, on top of the
    Current layer's mask stack or content stack."""
    layer = _require(current)
    target = step["target"]
    if target == "mask" and not adapter.has_mask(layer):
        raise StepError(NO_MASK)
    if step["effect"] == "anchor":
        node = adapter.insert_effect(layer, target, "anchor", name=anchor_name(step))
    else:
        node = adapter.insert_effect(layer, target, step["effect"], resource=step.get("resource"))
    if step["effect"] == "fill" and target == "layer":
        set_content(adapter, node, step)
    elif step["effect"] == "fill" and "source" in step:
        adapter.set_channel_source(node, None, dict(step["source"]))
    return current


def add_smart(adapter, step, current):
    """A smart material is inserted like a new layer and becomes the Current layer; a smart
    mask goes onto the Current layer's mask."""
    if step["smart"] == "material":
        return adapter.insert_smart_material(step["resource"], above=current)
    adapter.insert_smart_mask(_require(current), step["resource"])
    return current


def select_layer(adapter, step, current):
    name = step["name"]
    found = list(adapter.find_layers(name))
    if not found:
        raise StepError(f"No layer named “{name}”.")
    if len(found) > 1:
        raise StepError(f"Several layers named “{name}”.")
    return found[0]


LAYER_STEPS = {
    "add_layer": add_layer,
    "add_mask": add_mask,
    "add_effect": add_effect,
    "add_smart": add_smart,
    "set_blend": set_blend,
    "set_opacity": set_opacity,
    "set_fill": set_fill,
    "select_layer": select_layer,
}


# -- the save Step -------------------------------------------------------------------


def save(adapter, step, done):
    """The ``save`` UI Step: ``project.save()``. Calls ``done`` before it returns."""
    try:
        adapter.save_project()
    except Exception as error:
        log.exception("Saving the project failed")
        done(StepResult(FAILED, _reason(error)))
        return None
    log.info("Saved the project")
    done(StepResult(DONE))
    return None


def _reason(error):
    text = str(error).strip()
    return text if text else "Painter refused it. See the log."


# -- the runner ------------------------------------------------------------------------


def step_resources(step):
    """Every ``resource://`` URL a Step refers to (a layer's material and channel sources too)."""
    urls = [step["resource"]] if step.get("resource") else []
    if isinstance(step.get("material"), dict):
        urls.append(step["material"]["resource"])
    for source in [step.get("source"), *(step.get("sources") or {}).values()]:
        if isinstance(source, dict) and source.get("resource"):
            urls.append(source["resource"])
    return urls


def _check_resources(adapter, step):
    """A MISSING message if what this Step refers to is not here, else ``None``."""
    if step["type"] == "run_action":
        if menu.find_action(adapter, step["action"]) is None:
            return menu.missing_message(step["action"])
        return None
    for url in step_resources(step):
        if brush.resolve(adapter, url) is None:
            if step["type"] == "select_brush":
                return brush.missing_message(url)
            if step["type"] == "add_smart" and step["smart"] == "material":
                return smart_material.missing_message(url)
            return f"This resource is not available on this machine: {url}"
    return None


def _named_channels(step):
    """The channels a Step names (a new layer's, or those ``set_fill`` switches or sets)."""
    if step["type"] == "add_layer":
        return list(step.get("channels", []))
    if step["type"] == "set_fill":
        return list(dict.fromkeys([*step.get("channels_on", []), *step.get("channels_off", []), *step.get("sources", {})]))
    return []


def _texture_channels(adapter):
    """The channels of the active texture set (in Painter's order), or ``None`` if Painter
    cannot tell."""
    try:
        channels = adapter.stack_channels()
    except Exception:
        log.exception("Could not read the texture set's channels")
        return None
    if channels is None:
        log.warning("Painter did not list the texture set's channels")
        return None
    return list(channels)


def _project_ready(adapter):
    try:
        return bool(adapter.project_ready())
    except Exception:
        log.exception("Could not ask whether a project is ready")
        return False


class WorkflowRun:
    def __init__(self, adapter, steps, done, ui_steps, name):
        self.adapter = adapter
        self.steps = steps
        self._done = done
        self.ui_steps = {"save": save, **(ui_steps or {})}
        self.name = name
        # the index of the first UI Step: the layer Steps all come before it
        self.first_ui = next((i for i, s in enumerate(steps) if s.get("type") in UI_STEP_TYPES), len(steps))
        self.finished = False
        self.cancelled = False
        self._handle = None  # the UI Step in progress

    # -- messages --------------------------------------------------------------

    @property
    def _title(self):
        return f"“{self.name or 'The Workflow'}”"

    @property
    def _single_step_button(self):
        """A Brush or Menu button (no name): its one Step's message is shown as it is."""
        return self.name is None and len(self.steps) == 1

    def _step(self, index):
        return f"Step {index + 1} ({step_label(self.steps[index])})"

    def _not_started(self, state, text, index=None):
        if self._single_step_button:
            return StepResult(state, text if index is not None else text[:1].upper() + text[1:])
        detail = text if index is None else f"{self._step(index)}: {text}"
        return StepResult(state, f"{self._title} did not start: {detail}")

    def _problem(self, index, text):
        """A preflight problem about the Step itself: "… Step 2 (Save) needs …"."""
        return StepResult(FAILED, f"{self._title} did not start: {self._step(index)} {text}")

    def _stopped(self, index, result):
        if self._single_step_button:
            return result
        return StepResult(result.state, f"{self._title} stopped at {self._step(index)}: {result.message}")

    def _finish(self, result):
        if self.finished or self.cancelled:
            return
        self.finished = True
        self._handle = None
        if not result.ok:
            log.warning("Workflow %r: %s", self.name, result.message)
        self._done(result)

    # -- preflight -------------------------------------------------------------

    def _preflight(self):
        """``(problem, start layer)``: problem is a StepResult, or ``None`` if it can run."""
        steps = self.steps
        for index, step in enumerate(steps):
            kind = step.get("type")
            if kind not in UI_STEP_TYPES and index > self.first_ui:
                return self._problem(index, "must come before the brush, menu and save Steps."), None
            if kind not in LAYER_STEPS and kind not in self.ui_steps:
                return self._problem(index, "is not available in this version of Shelf+."), None

        needs_project = self.first_ui > 0 or any(s["type"] == "save" for s in steps)
        if needs_project and not _project_ready(self.adapter):
            return self._not_started(FAILED, f"{NO_PROJECT}."), None

        start = None
        if self.first_ui > 0:
            try:
                start = self.adapter.selected_layer()
            except Exception:
                # not "nothing selected": that would put new layers on top of the stack
                log.exception("Could not read the selected layer")
                return self._not_started(FAILED, SELECTION_UNREADABLE), None
            # the first block: the Steps before the first one that creates or picks a layer
            for index, step in enumerate(steps[: self.first_ui]):
                if not needs_current_layer(step):
                    break
                if start is None:
                    return self._problem(index, "needs a selected layer."), None

        index = self._brush_without_paint_target()
        if index is not None:
            return self._problem(index, BRUSH_NEEDS_PAINT_TARGET), None

        index, problem = self._fill_target_problem()
        if problem:
            return self._problem(index, problem), None

        wanted = [(i, _named_channels(s)) for i, s in enumerate(steps) if _named_channels(s)]
        available = _texture_channels(self.adapter) if wanted else None
        if available is not None:
            for index, channels in wanted:
                missing = next((c for c in channels if c not in available), None)
                if missing:
                    return self._problem(index, f"uses the {missing} channel, which this texture set does not have."), None

        index, problem = self._anchor_problem()
        if problem:
            return self._not_started(FAILED, problem, index), None

        for index, step in enumerate(steps):
            missing = _check_resources(self.adapter, step)
            if missing:
                return self._not_started(MISSING, missing, index), None
        return None, start

    def _fill_target_problem(self):
        """``(index, problem)`` of a ``set_fill`` Step on a layer the Workflow itself made
        and that cannot take it (a source on a new Paint layer…); ``(None, None)`` if none.
        The start layer and a picked layer are checked when the Step runs."""
        kind = None  # unknown until a Step creates a layer
        for index, step in enumerate(self.steps[: self.first_ui]):
            if step["type"] == "add_layer":
                kind = step["layer"]
            elif step["type"] == "add_smart" and step["smart"] == "material":
                kind = "folder"
            elif step["type"] == "select_layer":
                kind = None
            elif step["type"] == "set_fill" and kind is not None:
                problem = fill_target_problem(kind, step)
                if problem:
                    return index, problem
        return None, None

    def _anchor_problem(self):
        """``(index, problem)``: an anchor point Step whose name is taken already (in the
        stack, or by an earlier Step), or an anchor source that is not exactly one anchor
        point of the stack or made by an earlier Step; ``(None, None)`` if none."""
        counts = {}

        def count(name):
            if name not in counts:
                try:
                    counts[name] = len(list(self.adapter.find_anchors(name)))
                except Exception:
                    log.exception("Could not look for the anchor point %r", name)
                    counts[name] = None  # unknown: the Step finds out when it runs
            return counts[name]

        made = set()
        for index, step in enumerate(self.steps[: self.first_ui]):
            for name in anchor_sources(step):
                found = 1 if name in made else count(name)
                if found == 0:
                    return index, NO_ANCHOR.format(name)
                if found is not None and found > 1:
                    return index, TWIN_ANCHORS.format(name)
            name = anchor_name(step)
            if name is not None:
                if name in made or count(name):
                    return index, ANCHOR_EXISTS.format(name)
                made.add(name)
        return None, None

    def _brush_without_paint_target(self):
        """The index of a ``select_brush`` Step that surely has nothing to paint on: the
        last layer the Workflow creates is a Fill layer, folder or smart material, and no
        mask is added to it. (A start layer or a picked layer is checked at run time.)"""
        brush = next((i for i in range(self.first_ui, len(self.steps)) if self.steps[i]["type"] == "select_brush"), None)
        if brush is None:
            return None
        paintable = None  # unknown until a Step creates a layer
        for step in self.steps[: self.first_ui]:
            kind = step["type"]
            if kind == "add_layer":
                paintable = step["layer"] == "paint"
            elif kind == "add_smart" and step["smart"] == "material":
                paintable = False
            elif kind == "select_layer":
                paintable = None
            elif kind == "add_mask" or (kind == "add_smart" and step["smart"] == "mask"):
                paintable = paintable if paintable is None else True
        return brush if paintable is False else None

    # -- running ---------------------------------------------------------------

    def start(self):
        problem, current = self._preflight()
        if problem is not None:
            self._finish(problem)
            return
        if self.first_ui > 0 and not self._run_layer_steps(current):
            return
        self._next_ui_step(self.first_ui)

    def _run_layer_steps(self, current):
        """Run the layer Steps in one scope, then select the final Current layer (unless
        it is still the start layer, so a selected mask stays selected).
        ``False`` if a Step failed (the run is finished)."""
        start = current
        failure = None
        label = scope_label(self.steps, self.name)
        try:
            with self.adapter.layer_scope(label):
                for index in range(self.first_ui):
                    step = self.steps[index]
                    try:
                        current = LAYER_STEPS[step["type"]](self.adapter, step, current)
                    except StepError as error:
                        failure = self._stopped(index, StepResult(FAILED, str(error)))
                    except Exception as error:
                        log.exception("Step %d (%s) failed", index + 1, step["type"])
                        failure = self._stopped(index, StepResult(FAILED, _reason(error)))
                    if failure is not None:
                        break
        except Exception as error:  # opening or closing the scope
            log.exception("The layer stack change failed")
            failure = failure or StepResult(FAILED, f"{self._title} stopped: {_reason(error)}")
        if current is not None and current is not start:
            try:
                self.adapter.select_layer(current)
            except Exception:
                log.exception("Could not select the Current layer")
        if failure is not None:
            self._finish(failure)
            return False
        return True

    def _next_ui_step(self, index):
        if self.cancelled or self.finished:
            return
        if index >= len(self.steps):
            self._finish(StepResult(DONE))
            return
        step = self.steps[index]
        reported = []

        def done(result):
            reported.append(result)
            if self.cancelled or self.finished:
                return
            self._handle = None
            if result.ok:
                self._next_ui_step(index + 1)
            else:
                self._finish(self._stopped(index, result))

        handle = self.ui_steps[step["type"]](self.adapter, step, done)
        if not reported and handle is not None:  # the Step is still running
            self._handle = handle

    def cancel(self):
        self.cancelled = True
        handle, self._handle = self._handle, None
        if handle is not None:
            handle.cancel()


def run_workflow(adapter, steps, done, ui_steps=None, name=None):
    """Run ``steps``; ``done(StepResult)`` is called exactly once, maybe before this
    returns, unless the run is cancelled. Returns a handle with ``cancel()`` while a UI
    Step is still in progress, else ``None``.

    ``ui_steps``: Step type -> ``function(adapter, step, done) -> handle | None`` for the
    UI Steps (``save`` is built in). ``name``: the Workflow's name for messages; ``None``
    for a Brush or Menu button, whose one Step's message is shown as it is.
    """
    run = WorkflowRun(adapter, steps, done, ui_steps, name)
    run.start()
    return None if run.finished else run
