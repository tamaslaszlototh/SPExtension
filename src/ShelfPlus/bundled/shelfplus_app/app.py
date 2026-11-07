"""The running application: loads the Layout and panel state, and owns the Panel.

Painter-free: it uses an adapter (see ``adapter/__init__.py``) and a view factory,
so tests drive it with ``FakeAdapter`` and a fake view.
"""

import logging
import platform
from functools import partial
from pathlib import Path

from .core.brush import MISSING, brush_button, brush_icon, resolve, resource_urls_from_drop, select_brush
from .core.diagnostics import build_diagnostics, tail_log
from .core.menu import ActionWatcher, action_id, capture_problem, menu_button, run_action, same_action, search_actions
from .core.editing import LayoutEditor
from .core.panel_state import TILE_SIZE_MAX, TILE_SIZE_MIN, PanelStateStore, valid_tile_size
from .core.storage import READ_ONLY_MESSAGE, LayoutStore, ReadOnlyLayoutError

log = logging.getLogger("ShelfPlus.app")

# The "+" menu of each Group row: (label, handler). A ``None`` handler is shown
# disabled; the slices that add each Button kind fill in the handler.
ADD_BUTTON_KINDS = [
    ("Brush button", None),
    ("Menu button", None),
    ("Workflow button", None),
]

# When the plugin starts, Painter may not even have begun loading its resources, so a
# brush not found yet is not confirmed missing (no badge) until Painter reports a shelf
# loaded with none still loading, or SETTLE_CHECKS quiet checks have passed (for when
# everything was loaded before the plugin started). The checks run every
# LOADING_CHECK_MS; after LOADING_CHECKS the App stops waiting, even if Painter is busy.
LOADING_CHECK_MS = 2000
SETTLE_CHECKS = 15
LOADING_CHECKS = 60
LOADING_MESSAGE = "Painter is still loading its brushes. Try again in a moment."

# Some of Painter's commands exist only once a project is open, so a Menu button with the
# "unavailable" badge is looked up again this often until its command is found.
MENU_CHECK_MS = 10000
WATCH_FAILED_MESSAGE = "Painter's menu cannot be watched. Use “Choose from list…” instead."
LIST_FAILED_MESSAGE = "Painter's commands could not be read. See the log."


def button_steps(button):
    """The Steps a Button runs. A Brush or Menu button is a one-Step Workflow. ``None``:
    this Button kind cannot run yet."""
    if button.kind == "brush":
        return [{"type": "select_brush", "resource": button.raw["resource"]}]
    if button.kind == "menu":
        return [{"type": "run_action", "action": button.raw["action"]}]
    return None


class App:
    def __init__(self, env, adapter, view_factory):
        self.env = env
        self.version = env["version"]
        self.data_dir = Path(env["data_dir"])
        self.adapter = adapter
        self.view_factory = view_factory
        self.layout_store = LayoutStore(self.data_dir, Path(env["version_dir"]) / "default_layout.json")
        self.panel_state_store = PanelStateStore(self.data_dir / "panel.json")
        self.layout = None
        self.read_only = False
        self.messages = []
        self.editor = None
        self.panel_state = None
        self._panel_state_unsaved = False
        handlers = {"Brush button": self.explain_brush_drop, "Menu button": self.start_menu_capture}
        self.add_button_kinds = [(label, handlers.get(label, handler)) for label, handler in ADD_BUTTON_KINDS]
        # ids of Brush buttons whose preset is not on this machine, and of Menu buttons
        # whose command is not in this Painter version
        self.missing = set()
        # Every hook call on Painter's commands goes through it; it also hides the
        # plugin's own trigger() calls (run_action).
        self.action_watcher = ActionWatcher(self._command_run)
        # The UI Steps the App can run so far: Step type -> function(adapter, step, done).
        self.ui_steps = {"select_brush": select_brush, "run_action": partial(run_action, watcher=self.action_watcher)}
        self._capture_group_id = None  # capture mode: the Group a captured command goes to
        self.capture_note = None  # why the last command clicked in capture mode was refused
        self._stop_watching = None  # disconnects the hooks on Painter's commands
        self._menu_timer = None  # looks for missing commands again
        self._running = None  # the Step in progress (its handle has ``cancel()``)
        self._stop_listening = None  # disconnects from Painter's "resources loaded" event
        self._loading_timer = None
        self._loading_checks = 0
        self._settled = False  # a brush not found can be trusted to be missing
        self.view = None
        self._dock = None

    def start(self):
        log.info("Shelf+ v%s starting", self.version)
        result = self.layout_store.load()
        for message in result.messages:
            log.warning(message)
        self.layout = result.layout
        self.read_only = result.read_only
        self.messages = list(result.messages)
        self.editor = LayoutEditor(self.layout, self.layout_store.save, self.data_dir, self.read_only)
        self.panel_state = self.panel_state_store.load()
        try:
            self._stop_listening = self.adapter.on_resources_loaded(self._resources_loaded)
        except Exception:
            log.exception("Could not listen for Painter loading its resources")
        self.check_brushes()
        self.check_menu_buttons()

        self.view = self.view_factory(self)
        self.view.render()
        self._dock = self.adapter.add_dock_widget(self.view.widget)

    # -- view state (panel.json) ---------------------------------------------

    def is_collapsed(self, group_id):
        return group_id in self.panel_state["collapsedGroups"]

    def set_group_collapsed(self, group_id, collapsed):
        groups = [g for g in self.panel_state["collapsedGroups"] if g != group_id]
        if collapsed:
            groups.append(group_id)
        self.panel_state["collapsedGroups"] = groups
        self.save_panel_state()

    def set_tile_size(self, size, save=True):
        """``save=False`` while the slider moves: the size is saved later with
        ``save_panel_state()``, or on close."""
        if not valid_tile_size(size):
            raise ValueError(f"tile size must be a whole number from {TILE_SIZE_MIN} to {TILE_SIZE_MAX}")
        self.panel_state["tileSize"] = size
        if save:
            self.save_panel_state()
        else:
            self._panel_state_unsaved = True

    def set_show_labels(self, show):
        self.panel_state["showLabels"] = bool(show)
        self.save_panel_state()

    def save_panel_state(self):
        self._panel_state_unsaved = False
        try:
            self.panel_state_store.save(self.panel_state)
        except OSError:
            log.exception("Could not save panel.json")

    # -- Buttons -------------------------------------------------------------

    def icon_path(self, button):
        """The Button's own icon file, or ``None`` for the automatic icon."""
        if button.icon is None:
            return None
        path = self.data_dir / button.icon
        return path if path.is_file() else None

    def notify(self, text):
        """A short message for the user, shown on the Panel."""
        log.info("Message: %s", text)
        if self.view is not None and hasattr(self.view, "notify"):
            self.view.notify(text)

    # -- Brush buttons ---------------------------------------------------------

    def is_missing(self, button):
        """Whether ``button`` is a Brush button whose preset is not on this machine."""
        return button.id in self.missing

    def _set_missing(self, button, missing):
        if missing == self.is_missing(button):
            return
        if missing:
            self.missing.add(button.id)
        else:
            self.missing.discard(button.id)
        if self.view is not None:
            self.view.render()

    def _resources_loading(self):
        try:
            return bool(self.adapter.resources_loading())
        except Exception:
            log.exception("Could not ask whether Painter is loading its resources")
            return False

    def _can_confirm_missing(self):
        """Whether a brush not found now is really missing, not just not loaded yet."""
        if self._loading_checks >= LOADING_CHECKS:
            return True
        if self._resources_loading():
            return False
        return self._settled or self._loading_checks >= SETTLE_CHECKS

    def _resources_loaded(self):
        self._settled = True
        self.check_brushes()

    def _buttons_of_kind(self, kind):
        return [b for g in self.layout.groups for b in g.buttons if b.valid and b.kind == kind]

    def check_brushes(self):
        """Clear the badge of every Brush button whose preset is found, and badge the
        others once that is certain (see ``_can_confirm_missing``); until then the check
        runs again on a timer and whenever Painter reports a shelf loaded."""
        not_found = []
        for button in self._buttons_of_kind("brush"):
            if resolve(self.adapter, button.raw["resource"]) is None:
                not_found.append(button)
            else:
                self._set_missing(button, False)
        if not not_found:  # every preset is there, so Painter has loaded them
            self._settled = True
            self._stop_loading_timer()
            return
        if not self._can_confirm_missing():
            log.info("%d Brush button(s) not found yet; checking again once Painter has loaded", len(not_found))
            if self._loading_timer is None:
                self._loading_timer = self.adapter.repeat(LOADING_CHECK_MS, self._loading_tick)
            return
        self._stop_loading_timer()
        for button in not_found:
            self._set_missing(button, True)
        log.info("%d Brush button(s) have no preset on this machine", len(not_found))

    def _loading_tick(self):
        self._loading_checks += 1
        self.check_brushes()

    def _stop_loading_timer(self):
        timer, self._loading_timer = self._loading_timer, None
        if timer is not None:
            timer.stop()

    def explain_brush_drop(self, group):
        self.notify(f"Drag a brush or tool preset from the Assets window onto “{group.name}”.")

    def add_brushes_from_drop(self, group_id, index, uri_list):
        """Brush buttons for the brushes of a ``text/uri-list`` drop, inserted at ``index``
        of the Group. Returns the new Buttons."""
        urls = resource_urls_from_drop(uri_list)
        if not urls:
            return []
        if self.read_only:
            self.notify(READ_ONLY_MESSAGE)
            return []
        added = []
        for url in urls:
            resource = resolve(self.adapter, url)
            if resource is None:
                self.notify(f"Painter does not know this resource: {url}")
                continue
            if not resource.is_brush:
                self.notify(f"“{resource.gui_name}” is not a brush or tool preset.")
                continue
            png = brush_icon(self.adapter, resource)
            try:
                button = self.editor.add_button(group_id, index + len(added), brush_button(resource), icon_png=png)
            except (ReadOnlyLayoutError, ValueError, KeyError, OSError):
                log.exception("Adding a Brush button for %r failed", url)
                self.notify(f"“{resource.gui_name}” could not be added. See the log.")
                break
            log.info("Added Brush button %r (%s), icon: %s", button.name, url, button.icon or "generic")
            added.append(button)
        if added and self.view is not None:
            self.view.render()
        return added

    # -- Menu buttons ------------------------------------------------------------

    def check_menu_buttons(self):
        """Badge every Menu button whose command is not in this Painter, and clear the
        badge of those found. While any is badged, the check runs again on a slow timer:
        some commands appear only once a project is open."""
        buttons = self._buttons_of_kind("menu")
        if not buttons:
            self._stop_menu_timer()
            return
        try:  # one look at Painter's commands for every Button
            found = [action_id(action) for action in self.adapter.list_actions()]
        except Exception:
            log.exception("Could not list Painter's commands")
            return
        unavailable = 0
        for button in buttons:
            here = any(same_action(f, button.raw["action"]) for f in found)
            self._set_missing(button, not here)
            unavailable += not here
        if unavailable and self._menu_timer is None:
            log.info("%d Menu button(s) have no command in this Painter (yet)", unavailable)
            self._menu_timer = self.adapter.repeat(MENU_CHECK_MS, self.check_menu_buttons)
        elif not unavailable and self._menu_timer is not None:
            self._stop_menu_timer()

    def _stop_menu_timer(self):
        timer, self._menu_timer = self._menu_timer, None
        if timer is not None:
            timer.stop()

    @property
    def capturing(self):
        """In capture mode: the Group a captured command goes to; else ``None``."""
        if self._capture_group_id is None:
            return None
        try:
            return self.editor.group(self._capture_group_id)
        except KeyError:
            return None

    def start_menu_capture(self, group):
        """Capture mode: the next command the user runs from Painter's menu becomes a Menu
        button at the end of ``group``. Starting again moves it to another Group."""
        if self.view is None:  # closed meanwhile (the "+" menu starts it a moment later)
            return
        if self.read_only:
            self.notify(READ_ONLY_MESSAGE)
            return
        self._stop_capture_hooks()
        self._capture_group_id = None
        self.capture_note = None
        try:
            self._stop_watching = self.adapter.watch_actions(self.action_watcher.notify)
        except Exception:
            log.exception("Could not hook Painter's commands")
            self.notify(WATCH_FAILED_MESSAGE)
            self._render()
            return
        self._capture_group_id = group.id
        log.info("Capture mode for Group %r", group.name)
        self._render()

    def cancel_menu_capture(self):
        """End capture mode without adding anything (Esc, or the Cancel control)."""
        if self._capture_group_id is None and self._stop_watching is None:
            return
        log.info("Capture mode ended")
        self._end_capture()

    def _end_capture(self):
        self._stop_capture_hooks()
        self._capture_group_id = None
        self.capture_note = None
        self._render()

    def _stop_capture_hooks(self):
        stop, self._stop_watching = self._stop_watching, None
        if stop is not None:
            try:
                stop()
            except Exception:
                log.exception("Could not unhook Painter's commands")

    def _command_run(self, action):
        """A command the user ran in Painter (duplicates and own triggers already dropped)."""
        if self._capture_group_id is None:
            return
        group = self.capturing
        if group is None:  # the Group was deleted meanwhile
            self._end_capture()
            return
        problem = capture_problem(action)
        self.capture_note = problem
        if problem:
            self.notify(problem)
            self._render()  # the capture bar shows it until the next command
            return
        self.add_menu_button(group.id, action)

    def menu_actions(self, query):
        """Painter's commands for the searchable list, filtered by ``query``."""
        try:
            actions = self.adapter.list_actions()
        except Exception:
            log.exception("Could not list Painter's commands")
            self.notify(LIST_FAILED_MESSAGE)
            return []
        return search_actions(actions, query)

    def add_menu_button(self, group_id, action):
        """A Menu button for ``action`` at the end of the Group; ends capture mode.
        Returns the new Button, or ``None``."""
        self._capture_group_id = None
        self.capture_note = None
        self._stop_capture_hooks()
        if self.read_only:
            self.notify(READ_ONLY_MESSAGE)
            return None
        try:
            png = self.adapter.action_icon_png(action)
        except Exception:
            log.exception("Could not read the icon of %r", action.name)
            png = None
        try:
            group = self.editor.group(group_id)
            button = self.editor.add_button(group_id, len(group.buttons), menu_button(action), icon_png=png)
        except (ReadOnlyLayoutError, ValueError, KeyError, OSError):
            log.exception("Adding a Menu button for %r failed", action_id(action))
            self.notify(f"“{action.label}” could not be added. See the log.")
            self._render()
            return None
        log.info("Added Menu button %r (%s), icon: %s", button.name, button.raw["action"], button.icon or "generic")
        self.notify(f"Added “{button.name}” to “{group.name}”.")
        self.check_menu_buttons()
        self._render()
        return button

    def _render(self):
        if self.view is not None:
            self.view.render()

    # -- running ---------------------------------------------------------------

    def run_button(self, button):
        """Clicking a Button: it runs as a Workflow (a Brush button as one ``select_brush`` Step)."""
        if not button.valid:
            self.notify(f"“{button.name}” is invalid and cannot run: {button.problem}.")
            return
        steps = button_steps(button)
        if steps is None:
            log.info("Clicked %r (%s); running this kind is not available yet", button.name, button.kind)
            return
        self._cancel_running()
        # So far only one-Step Workflows of UI Steps run here; the Workflow runner takes over later.
        (step,) = steps
        reported = []

        def done(result):  # a cancelled Step never calls it, so it is always the running one
            reported.append(result)
            self._running = None
            if result.state == MISSING and button.kind == "brush" and not self._can_confirm_missing():
                self.notify(LOADING_MESSAGE)
                return
            if result.state == MISSING:
                self._set_missing(button, True)
                if button.kind == "menu":
                    self.check_menu_buttons()  # starts looking for it again
            if not result.ok:
                self.notify(result.message)

        # The handle is None when ``done`` was already called.
        self._running = self.ui_steps[step["type"]](self.adapter, step, done)
        if not any(r.state == MISSING for r in reported):
            self._set_missing(button, False)  # it was found this time

    def _cancel_running(self):
        running, self._running = self._running, None
        if running is not None:
            running.cancel()

    def close(self):
        self._cancel_running()
        self._stop_loading_timer()
        self._stop_menu_timer()
        self._capture_group_id = None
        self._stop_capture_hooks()
        stop, self._stop_listening = self._stop_listening, None
        if stop is not None:
            try:
                stop()
            except Exception:
                log.exception("Could not stop listening for Painter loading its resources")
        if self._panel_state_unsaved:
            self.save_panel_state()
        if self.editor is not None:
            try:
                self.editor.expire_delete()
            except Exception:
                log.exception("Ending the pending Undo failed")
        if self._dock is not None:
            try:
                self.adapter.delete_ui_element(self._dock)
            except Exception:
                log.exception("delete_ui_element failed")
            self._dock = None
        if self.view is not None:
            try:
                self.view.dispose()
            except Exception:
                log.exception("Disposing the Panel failed")
            self.view = None

    def diagnostics_text(self):
        def safe(query):
            try:
                return str(query())
            except Exception:
                return "unknown"

        versions = {
            "Shelf+ version": self.version,
            "Loader version": str(self.env.get("loader_version", "unknown")),
            "Painter version": safe(self.adapter.painter_version),
            "Python version": platform.python_version(),
            "Qt version": safe(self.adapter.qt_version),
        }
        log_path = self.env.get("log_path")
        lines = tail_log(log_path) if log_path else []
        return build_diagnostics(versions, lines)
