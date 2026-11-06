"""Menu buttons (PRD R6), without Qt or Painter: Painter's QActions are reached through the adapter.

- Creating, primary: **capture mode**. The adapter hooks ``QAction.triggered`` (and
  ``QMenu.triggered``, which fires on 12.2) and reports every command run to an
  ``ActionWatcher``. It drops the duplicates of one click and the plugin's own
  ``trigger()`` calls, then hands the command to its listener.
- Creating, fallback: ``search_actions`` filters the commands of the main window for
  the searchable list (on 11.1 the only way to add submenu commands).
- A Menu button stores the QAction's ``objectName`` (``menu_button``). Commands with
  an empty ``objectName`` (e.g. the layer stack's) cannot be found again, so they
  cannot become Buttons (``capture_problem``).
- ``run_action`` is the ``run_action`` Step: the Workflow runner calls it too.
"""

import html
import logging
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass

from .steps import DONE, FAILED, MISSING, StepResult

log = logging.getLogger("ShelfPlus.app.menu")

# The plugin's own QMenus and QActions have objectNames with this prefix; they are never
# captured or listed.
OWN_PREFIX = "ShelfPlus"

# Hook calls for the same command closer together than this are one click (the action's
# and the menu's signal, or two menus holding the same action).
DEDUPE_MS = 250


@dataclass(frozen=True)
class MenuAction:
    """One of Painter's commands (a QAction) as the adapter reports it.

    ``name`` is the ``objectName`` (may be empty), ``text`` the raw ``text()``, and
    ``path`` the titles of the menus it sits in (outermost first; may be empty).
    ``icon`` and ``handle`` belong to the adapter (a ``QIcon`` and the ``QAction``);
    the core never looks inside them.
    """

    name: str
    text: str
    path: tuple = ()
    icon: object = None
    handle: object = None

    @property
    def label(self):
        return action_label(self.text) or self.name

    @property
    def key(self):
        """What tells two hook calls apart: the objectName, or the text if it has none."""
        return self.name or action_label(self.text)

    @property
    def own(self):
        return self.name.startswith(OWN_PREFIX)


_TAG = re.compile(r"<[^>]*>")
_MNEMONIC = re.compile(r"&(.)")


def action_label(text):
    """A command's name for people: the first line of its text, without HTML markup
    (``Translate tool (<b>W</b>)``) and ``&`` mnemonics (``&&`` is a real ``&``)."""
    if not isinstance(text, str):
        return ""
    first = text.strip().split("\n", 1)[0]
    first = html.unescape(_TAG.sub("", first))
    first = _MNEMONIC.sub(r"\1", first)
    return " ".join(first.split())


def menu_button(action):
    """The Layout's JSON for a new Menu button, without ``id`` and ``icon`` (see
    ``LayoutEditor.add_button``)."""
    return {"kind": "menu", "name": action.label, "action": action.name}


def capture_problem(action):
    """Why this command cannot become a Menu button, or ``None`` if it can."""
    if not action.name:
        return (
            f"“{action.label}” cannot be a Menu button: Painter gives it no name to find it by. Try another command."
        )
    return None


# -- the hook watcher -------------------------------------------------------------


def _now_ms():
    return time.monotonic() * 1000


class ActionWatcher:
    """Turns the adapter's raw hook calls into one call of ``listener(action)`` per click.

    - Calls for the same command (``MenuAction.key``) within ``window_ms`` of the
      previous one are duplicates of the same click.
    - Calls while ``replaying()`` are the plugin's own ``trigger()`` and are dropped.
    - The plugin's own commands (objectName ``ShelfPlus…``) are dropped.
    """

    def __init__(self, listener=None, now=None, window_ms=DEDUPE_MS):
        self.listener = listener
        self.now = now or _now_ms
        self.window_ms = window_ms
        self._replaying = 0
        self._accepted = {}  # key -> time of the latest call that counted as a click

    @contextmanager
    def replaying(self):
        self._replaying += 1
        try:
            yield
        finally:
            self._replaying -= 1

    def notify(self, action):
        """Called by the adapter's hooks, inside Painter's signal: never raises."""
        try:
            self._notify(action)
        except Exception:
            log.exception("Handling the command %r failed", getattr(action, "text", action))

    def _notify(self, action):
        if self._replaying:
            log.debug("Own trigger of %r ignored", action.key)
            return
        if action.own:
            return
        now = self.now()
        previous = self._accepted.get(action.key)
        if previous is not None and now - previous <= self.window_ms:
            return  # a duplicate does not move the window, so a burst cannot swallow a click
        self._accepted[action.key] = now
        log.debug("Command run: %r (%s)", action.label, action.name or "no objectName")
        if self.listener is not None:
            self.listener(action)


# -- the searchable list ------------------------------------------------------------


def _usable(action):
    return bool(action.name) and not action.own and bool(action_label(action.text))


def search_actions(actions, query):
    """The commands for the searchable list: those with an objectName and a text, each
    objectName once (the first place it was found), sorted by menu path and label.
    Every word of ``query`` must appear (ignoring case) in the label, the objectName
    or the menu path."""
    words = query.lower().split()
    found = {}
    for action in actions:
        if not _usable(action) or action.name in found:
            continue
        haystack = " ".join((action.label, action.name, *action.path)).lower()
        if all(word in haystack for word in words):
            found[action.name] = action
    return sorted(found.values(), key=lambda a: ([p.lower() for p in a.path], a.label.lower(), a.name))


# -- the run_action Step -------------------------------------------------------------


def missing_message(name):
    return f"This menu command is not available in this Painter version: {name}"


def find_action(adapter, name):
    """The command named ``name`` in this Painter, or ``None`` if it is missing."""
    try:
        return adapter.find_action(name)
    except Exception:
        log.exception("Looking up the command %r failed", name)
        return None


def run_action(adapter, step, done, watcher=None):
    """Run a ``run_action`` Step: ``done(StepResult)`` is called exactly once, before this
    returns (``trigger()`` is synchronous). Returns ``None`` (nothing to cancel).

    While triggering, ``watcher`` (if given) ignores the hook calls, so the plugin's own
    trigger is not captured or recorded."""
    name = step["action"]
    action = find_action(adapter, name)
    if action is None:
        done(StepResult(MISSING, missing_message(name)))
        return None
    try:
        if watcher is not None:
            with watcher.replaying():
                triggered = adapter.trigger_action(action)
        else:
            triggered = adapter.trigger_action(action)
    except Exception:
        log.exception("Triggering %r failed", name)
        done(StepResult(FAILED, f"“{action.label}” could not be run. See the log."))
        return None
    if triggered is False:  # Painter has disabled it (e.g. Save with no project open)
        log.info("The command %r (%s) is disabled", action.label, name)
        done(StepResult(FAILED, f"“{action.label}” cannot be used right now in Painter."))
        return None
    log.info("Ran the command %r (%s)", action.label, name)
    done(StepResult(DONE))
    return None
