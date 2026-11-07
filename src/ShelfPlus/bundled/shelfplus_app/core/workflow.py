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
   top of the stack when there is none) and becomes it; ``select_layer`` makes the one
   layer with that exact name it.
3. After the scope closes, the final Current layer is selected if it is not the start
   layer any more (not part of the undo).
4. The UI Steps (``select_brush``, ``run_action``, ``save``) one after another. They may
   finish later (``select_brush`` polls), so each reports through ``done(StepResult)``.

A failing Step stops the run (R4.7). There is no rollback: what the scope already did
stays and is undone with one Ctrl+Z.

The layer side of the adapter (see ``adapter/__init__.py``): ``project_ready``,
``selected_layer``, ``layer_scope``, ``insert_layer``, ``add_mask``, ``set_blend``,
``set_opacity``, ``find_layers``, ``select_layer`` and ``save_project``.
"""

import logging

from . import brush, menu
from .steps import DONE, FAILED, MISSING, StepResult

log = logging.getLogger("ShelfPlus.app.workflow")

UI_STEP_TYPES = ("select_brush", "run_action", "save")
SCOPE_PREFIX = "Shelf+: "  # the History entry of a Workflow's layer changes

NO_PROJECT = "open a project first"
LAYER_NAMES = {"fill": "Fill layer", "paint": "Paint layer", "folder": "folder"}


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
        return f"Add {step.get('effect')}"
    if kind == "add_smart":
        return f"Add smart {step.get('smart')}"
    if kind == "set_blend":
        return f"Set blend mode to {step.get('blend')}"
    if kind == "set_opacity":
        return "Set opacity"
    if kind == "select_layer":
        return f"Select layer “{step.get('name')}”"
    if kind == "select_brush":
        return "Select brush"
    if kind == "run_action":
        return "Run menu command"
    if kind == "save":
        return "Save"
    return str(kind)


def needs_current_layer(step):
    """Whether the Step acts on the Current layer (rather than creating or picking one)."""
    kind = step["type"]
    return kind in ("add_mask", "add_effect", "set_blend", "set_opacity") or (
        kind == "add_smart" and step.get("smart") == "mask"
    )


# -- the layer Steps: function(adapter, step, current) -> the new Current layer ----------


def _require(current):
    if current is None:  # preflight makes sure this does not happen
        raise StepError("there is no layer to act on")
    return current


def add_layer(adapter, step, current):
    return adapter.insert_layer(step["layer"], above=current, name=step.get("name") or None)


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
    "set_blend": set_blend,
    "set_opacity": set_opacity,
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


def _check_resources(adapter, step):
    """A MISSING message if what this Step refers to is not here, else ``None``."""
    if step["type"] == "run_action":
        if menu.find_action(adapter, step["action"]) is None:
            return menu.missing_message(step["action"])
        return None
    url = step.get("resource")
    if url is not None and brush.resolve(adapter, url) is None:
        if step["type"] == "select_brush":
            return brush.missing_message(url)
        return f"This resource is not available on this machine: {url}"
    return None


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
        if self._single_step_button and index is not None:
            return StepResult(state, text)
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
                log.exception("Could not read the selected layer")
            # the first block: the Steps before the first one that creates or picks a layer
            for index, step in enumerate(steps[: self.first_ui]):
                if not needs_current_layer(step):
                    break
                if start is None:
                    return self._problem(index, "needs a selected layer."), None

        for index, step in enumerate(steps):
            missing = _check_resources(self.adapter, step)
            if missing:
                return self._not_started(MISSING, missing, index), None
        return None, start

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
        label = SCOPE_PREFIX + (self.name or step_label(self.steps[0]))
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
