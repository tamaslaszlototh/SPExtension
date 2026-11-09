"""The running application: loads the Layout and panel state, and owns the Panel.

Painter-free: it uses an adapter (see ``adapter/__init__.py``) and a view factory,
so tests drive it with ``FakeAdapter`` and a fake view.
"""

import logging
import platform
import time
from functools import partial
from pathlib import Path

from .core.brush import MISSING, brush_button, brush_icon, resolve, resource_urls_from_drop, select_brush
from .core.diagnostics import build_diagnostics, tail_log
from .core.menu import ActionWatcher, action_id, capture_problem, menu_button, run_action, same_action, search_actions
from .core.editing import LayoutEditor
from .core.smart_material import drag_uri_list, is_smart_material, smart_material_button, smart_material_step
from .core.panel_state import TILE_SIZE_MAX, TILE_SIZE_MIN, PanelStateStore, valid_tile_size
from .core.storage import READ_ONLY_MESSAGE, LayoutStore, ReadOnlyLayoutError
from .core.updater import Updater
from .core import blocks
from .core.recording import Recording
from .core.workflow import run_workflow, scope_label
from .core.channels import DEFAULT_CHANNELS
from .core.workflow_draft import WorkflowDraft, incomplete, needs_resource, resource_name

log = logging.getLogger("ShelfPlus.app")

# The "+" menu of each Group row: (label, handler). A ``None`` handler is shown
# disabled; the slices that add each Button kind fill in the handler.
ADD_BUTTON_KINDS = [
    ("Brush button", None),
    ("Menu button", None),
    ("Workflow button", None),
    ("Recorded Workflow", None),
]

# When the plugin starts, Painter may not even have begun loading its resources, so a
# brush not found yet is not confirmed missing (no badge) until Painter reports a shelf
# loaded with none still loading, or SETTLE_CHECKS quiet checks have passed (for when
# everything was loaded before the plugin started). The checks run every
# LOADING_CHECK_MS; after LOADING_CHECKS the App stops waiting, even if Painter is busy.
LOADING_CHECK_MS = 2000
SETTLE_CHECKS = 15
LOADING_CHECKS = 60
LOADING_MESSAGE = "Painter is still loading its {what}. Try again in a moment."
LOADING_WHAT = {"brush": "brushes", "smart_material": "smart materials"}
RESOURCE_KINDS = tuple(LOADING_WHAT)  # the Buttons whose resource may be missing

# Painter builds many of its menus only once a project is open, so a Menu button whose
# command is not found is badged only after a project has been open for
# MENU_SETTLE_CHECKS checks in a row, MENU_CHECK_MS apart. Until then nothing is shown.
# After that, a badged Button is looked up again every MENU_RECHECK_MS.
MENU_CHECK_MS = 2000
MENU_SETTLE_CHECKS = 3
MENU_RECHECK_MS = 10000
NOT_YET_MESSAGE = (
    "“{name}” is not available yet. Painter may still be building its menus, "
    "or the command needs an open project."
)
WATCH_FAILED_MESSAGE = "Painter's menu cannot be watched. Use “Choose from list…” instead."
LIST_FAILED_MESSAGE = "Painter's commands could not be read. See the log."


def button_steps(button):
    """The Steps a Button runs. A Brush, Smart material or Menu button is a one-Step Workflow."""
    if button.kind == "brush":
        return [{"type": "select_brush", "resource": button.raw["resource"]}]
    if button.kind == "smart_material":
        return [smart_material_step(button)]
    if button.kind == "menu":
        return [{"type": "run_action", "action": button.raw["action"]}]
    return button.raw["steps"]


class App:
    def __init__(self, env, adapter, view_factory, network=None, clock=time.time):
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
        handlers = {
            "Brush button": self.explain_brush_drop,
            "Menu button": self.start_menu_capture,
            "Workflow button": self.new_workflow,
            "Recorded Workflow": self.start_recording,
        }
        self.add_button_kinds = [(label, handlers.get(label, handler)) for label, handler in ADD_BUTTON_KINDS]
        # ids of Brush buttons whose preset is not on this machine, and of Menu buttons
        # whose command is not in this Painter version
        self.missing = set()
        # Every hook call on Painter's commands goes through it; it also hides the
        # plugin's own trigger() calls (run_action).
        self.action_watcher = ActionWatcher(self._command_run)
        # The UI Steps besides ``save``: Step type -> function(adapter, step, done).
        self.ui_steps = {"select_brush": select_brush, "run_action": partial(run_action, watcher=self.action_watcher)}
        self._capture_group_id = None  # capture mode: the Group a captured command goes to
        self.capture_note = None  # why the last command clicked in capture mode was refused
        self._stop_watching = None  # disconnects the hooks on Painter's commands
        self._menu_timer = None  # looks for missing commands again
        self._menu_timer_ms = None
        self._project_checks = 0  # timer checks in a row with a project open
        self._running = None  # the Step in progress (its handle has ``cancel()``)
        self._stop_listening = None  # disconnects from Painter's "resources loaded" event
        self._loading_timer = None
        self._loading_checks = 0
        self._settled = False  # a brush not found can be trusted to be missing
        # the Workflow editor (R7): the Workflow open in it, and the Group a new one goes to
        self.workflow_draft = None
        self._draft_group_id = None
        # Recording (R8): the one in progress, what it records into (a Group for a new
        # Workflow, or the draft it continues), and its hooks on Painter's commands
        self.recording = None
        self._recording_group_id = None
        self._recording_draft = None
        self._stop_recording_watch = None
        # Self-update (R9): the HTTP client (``core/updater.py`` has its interface; None:
        # no updates) and the flow, made once panel.json is loaded
        self.network = network
        self.clock = clock
        self.updater = None
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
        self._start_updater()

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

    # -- self-update (R9) ------------------------------------------------------

    def _start_updater(self):
        if self.network is None:
            return
        self.updater = Updater(
            self.network,
            self.data_dir,
            self.version,
            self.env.get("loader_version", 1),
            self.panel_state["updater"],
            self.save_panel_state,
            _UpdaterUi(self),
            clock=self.clock,
        )
        try:
            self.updater.check_on_start()
        except Exception:
            log.exception("The start-up update check failed")

    def check_for_updates(self):
        """**Check for updates** in the Panel menu."""
        if self.updater is None:
            self.show_message("Updates cannot be checked in this session.")
            return
        self.updater.check_now()

    def update_now(self):
        if self.updater is not None:
            self.updater.update()

    def update_later(self):
        if self.updater is not None:
            self.updater.later()

    def skip_update(self):
        if self.updater is not None:
            self.updater.skip()

    def show_message(self, text):
        """A message that stays until the user closes it (the updater's results)."""
        log.info("Message: %s", text)
        if self.view is not None and hasattr(self.view, "show_message"):
            self.view.show_message(text)

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

    # -- Brush and Smart material buttons -----------------------------------------

    def is_missing(self, button):
        """Whether ``button`` is a Brush or Smart material button whose resource is not on
        this machine, or a Menu button whose command is not in this Painter version."""
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

    def _buttons_of_kind(self, *kinds):
        return [b for g in self.layout.groups for b in g.buttons if b.valid and b.kind in kinds]

    def check_brushes(self):
        """Clear the badge of every Brush and Smart material button whose resource is
        found, and badge the
        others once that is certain (see ``_can_confirm_missing``); until then the check
        runs again on a timer and whenever Painter reports its resources loaded."""
        not_found = []
        for button in self._buttons_of_kind(*RESOURCE_KINDS):
            if resolve(self.adapter, button.raw["resource"]) is None:
                not_found.append(button)
            else:
                self._set_missing(button, False)
        if not not_found:  # every preset is there, so Painter has loaded them
            self._settled = True
            self._stop_loading_timer()
            return
        if not self._can_confirm_missing():
            log.info("%d Button(s) not found yet; checking again once Painter has loaded", len(not_found))
            if self._loading_timer is None:
                self._loading_timer = self.adapter.repeat(LOADING_CHECK_MS, self._loading_tick)
            return
        self._stop_loading_timer()
        for button in not_found:
            self._set_missing(button, True)
        log.info("%d Button(s) have no resource on this machine", len(not_found))

    def _loading_tick(self):
        self._loading_checks += 1
        self.check_brushes()

    def _stop_loading_timer(self):
        timer, self._loading_timer = self._loading_timer, None
        if timer is not None:
            timer.stop()

    def explain_brush_drop(self, group):
        self.notify(f"Drag a brush, tool preset or smart material from the Assets window onto “{group.name}”.")

    def add_buttons_from_drop(self, group_id, index, uri_list):
        """A Brush button for every brush and a Smart material button for every smart
        material of a ``text/uri-list`` drop, in the dropped order, inserted at ``index`` of
        the Group; anything else is skipped with a message. Returns the new Buttons."""
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
            if resource.is_brush:
                raw, label = brush_button(resource), "Brush button"
            elif is_smart_material(resource):
                raw, label = smart_material_button(resource), "Smart material button"
            else:
                self.notify(f"“{resource.gui_name}” is not a brush, tool preset or smart material.")
                continue
            png = brush_icon(self.adapter, resource)
            try:
                button = self.editor.add_button(group_id, index + len(added), raw, icon_png=png)
            except (ReadOnlyLayoutError, ValueError, KeyError, OSError):
                log.exception("Adding a %s for %r failed", label, url)
                self.notify(f"“{resource.gui_name}” could not be added. See the log.")
                break
            log.info("Added %s %r (%s), icon: %s", label, button.name, url, button.icon or "generic")
            added.append(button)
        if added and self.view is not None:
            self.view.render()
        return added

    def drag_uri_list(self, button):
        """What a tile dragged out of the Panel carries besides itself: a Smart material
        button whose smart material is here carries it as ``text/uri-list``, like a drag
        from the Assets window; every other Button ``None`` (it can only be dragged within
        the Panel)."""
        if not button.valid or button.kind != "smart_material" or self.is_missing(button):
            return None
        return drag_uri_list(button.raw["resource"])

    # -- Menu buttons ------------------------------------------------------------

    def _project_open(self):
        try:
            return bool(self.adapter.project_open())
        except Exception:
            log.exception("Could not ask whether a project is open")
            return False

    def _menus_settled(self):
        """Whether a command not found now is really missing: a project has been open for
        MENU_SETTLE_CHECKS timer checks in a row, so Painter has built its menus, and it
        is still open (the count is not updated while the timer is stopped)."""
        return self._project_checks >= MENU_SETTLE_CHECKS and self._project_open()

    def _menu_tick(self):
        self._project_checks = self._project_checks + 1 if self._project_open() else 0
        self.check_menu_buttons()

    def check_menu_buttons(self):
        """Clear the badge of every Menu button whose command is found. The others are
        badged only once Painter has settled (``_menus_settled``); until then nothing is
        shown, and the check runs every MENU_CHECK_MS. While any Button is badged, it
        runs every MENU_RECHECK_MS: a command may still appear."""
        buttons = self._buttons_of_kind("menu")
        if not buttons:
            self._stop_menu_timer()
            return
        try:  # one look at Painter's commands for every Button
            found = [action_id(action) for action in self.adapter.list_actions()]
        except Exception:
            log.exception("Could not list Painter's commands")
            return
        settled = self._menus_settled()
        not_found = 0
        for button in buttons:
            here = any(same_action(f, button.raw["action"]) for f in found)
            if here:
                self._set_missing(button, False)
            elif settled:
                self._set_missing(button, True)
            not_found += not here
        if not not_found:
            self._stop_menu_timer()
            return
        interval = MENU_RECHECK_MS if settled else MENU_CHECK_MS
        if self._menu_timer is None or self._menu_timer_ms != interval:
            if settled:
                log.info("%d Menu button(s) have no command in this Painter", not_found)
            else:
                log.info("%d Menu button(s) not found yet; waiting for Painter to settle", not_found)
            self._stop_menu_timer()
            self._menu_timer = self.adapter.repeat(interval, self._menu_tick)
            self._menu_timer_ms = interval

    def _stop_menu_timer(self):
        timer, self._menu_timer = self._menu_timer, None
        self._menu_timer_ms = None
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
        if self.recording is not None:
            self.recording.command(action)
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

    # -- the Workflow editor (R7) ------------------------------------------------

    def new_workflow(self, group):
        """"+ → Workflow button": the editor opens empty; saving adds the Workflow at the
        end of ``group``."""
        if self.view is None:  # closed meanwhile (the "+" menu starts it a moment later)
            return
        if self.read_only:
            self.notify(READ_ONLY_MESSAGE)
            return
        self.workflow_draft = WorkflowDraft()
        self._draft_group_id = group.id
        log.info("Workflow editor: new Workflow in Group %r", group.name)
        self._render()

    def edit_workflow(self, button):
        """A double-click on a Workflow button: the editor opens with its Steps."""
        if self.view is None:
            return
        if self.read_only:
            self.notify(READ_ONLY_MESSAGE)
            return
        if not button.valid or button.kind != "workflow":
            self.notify(f"“{button.name}” cannot be edited: {button.problem or 'it is not a Workflow'}.")
            return
        self.workflow_draft = WorkflowDraft(button.raw["steps"], name=button.raw["name"], button_id=button.id)
        self._draft_group_id = None
        log.info("Workflow editor: editing %r", button.name)
        self._render()

    def draft_button(self):
        draft = self.workflow_draft
        if draft is None or draft.button_id is None:
            return None
        return next((b for g in self.layout.groups for b in g.buttons if b.id == draft.button_id), None)

    def close_workflow_editor(self):
        """Close the editor without saving."""
        self.workflow_draft = None
        self._draft_group_id = None
        self._render()

    def save_workflow(self):
        """Save the open Workflow and close the editor. Returns its Button, or ``None`` if
        it cannot be saved (the reason is shown; the editor stays open)."""
        draft = self.workflow_draft
        if draft is None:
            return None
        if draft.problem:
            self.notify(draft.problem)
            return None
        try:
            if draft.button_id is None:
                group = self.editor.group(self._draft_group_id)
                button = self.editor.add_button(group.id, len(group.buttons), draft.to_raw(), icon_png=draft.icon_png)
            else:
                button = self.draft_button()
                if button is None:
                    raise KeyError(draft.button_id)
                self.editor.update_button(button, draft.to_raw(), icon_png=draft.icon_png, reset_icon=draft.icon_reset)
        except ReadOnlyLayoutError as error:
            self.notify(str(error))
            return None
        except KeyError:
            log.exception("Saving the Workflow: its Button or Group is gone")
            self.notify("The Workflow's Button or Group is no longer there.")
            return None
        except (ValueError, OSError):
            log.exception("Saving the Workflow failed")
            self.notify("The Workflow could not be saved. See the log.")
            return None
        log.info("Saved Workflow %r (%d Step(s))", button.name, len(draft.steps))
        self.close_workflow_editor()
        return button

    def delete_workflow(self):
        """The editor's trash, after the user said Yes: the Workflow button is deleted (the
        Panel's Undo can bring it back). A new Workflow is just closed. Returns the
        ``PendingDelete``, or ``None``."""
        button = self.draft_button()
        pending = None
        if button is not None:
            try:
                pending = self.editor.delete_button(button)
            except (ReadOnlyLayoutError, KeyError, OSError):
                log.exception("Deleting the Workflow failed")
                self.notify("The Workflow could not be deleted. See the log.")
                return None
            log.info("Deleted Workflow %r", button.name)
        self.close_workflow_editor()
        return pending

    def workflow_resource_drop(self, uri_list):
        """A resource dropped onto the editor: it fills the selected incomplete Step that
        takes one; a brush otherwise adds a ``select_brush`` Step."""
        draft = self.workflow_draft
        urls = resource_urls_from_drop(uri_list)
        if draft is None or not urls:
            return
        url = urls[0]
        resource = resolve(self.adapter, url)
        step = draft.selected_step
        if step is not None and needs_resource(step) and resource is not None:
            # a brush fills only a Brush Step, and a Brush Step takes only a brush
            if step["type"] == "select_brush" and not resource.is_brush:
                self.notify(f"“{resource.gui_name}” is not a brush or tool preset.")
                return
            if step["type"] != "select_brush" and resource.is_brush:
                self.notify(f"“{resource.gui_name}” is a brush. This Step needs another kind of resource.")
                return
        if draft.fill_resource(url, resource.gui_name if resource is not None else None):
            self._render()
            return
        if resource is not None and resource.is_brush:
            draft.add({"type": "select_brush", "resource": url, "resource_name": resource.gui_name})
            self._render()
            return
        name = resource.gui_name if resource is not None else resource_name(url)
        self.notify(f"Select the Step “{name}” is for, then drop it again.")

    def dropped_resource(self, uri_list, wants_brush=False):
        """A resource dropped onto one setting: ``{"resource", "resource_name"}``, or
        ``None`` (the reason is shown). A brush setting takes only a brush, any other
        setting anything but a brush."""
        urls = resource_urls_from_drop(uri_list)
        if not urls:
            return None
        resource = resolve(self.adapter, urls[0])
        if resource is None:
            self.notify(f"Painter does not know this resource: {urls[0]}")
            return None
        if wants_brush and not resource.is_brush:
            self.notify(f"“{resource.gui_name}” is not a brush or tool preset.")
            return None
        if not wants_brush and resource.is_brush:
            self.notify(f"“{resource.gui_name}” is a brush. This setting needs another kind of resource.")
            return None
        return {"resource": urls[0], "resource_name": resource.gui_name}

    def search_resources(self, query):
        """Painter's resources matching ``query``, for the resource picker."""
        try:
            return list(self.adapter.search_resources(query))
        except Exception:
            log.exception("Searching Painter's resources for %r failed", query)
            self.notify("Painter's resources could not be searched. See the log.")
            return []

    def texture_channels(self):
        """The channels a new layer can use: the active texture set's, or the usual ones
        when Painter cannot tell (no project open)."""
        try:
            channels = self.adapter.stack_channels()
        except Exception:
            log.info("Could not read the texture set's channels", exc_info=True)
            channels = None
        return list(channels) if channels else list(DEFAULT_CHANNELS)

    def anchor_names(self):
        """The active texture set's anchor point names (offered for an anchor source), or
        none when Painter cannot tell."""
        try:
            return list(self.adapter.anchor_names())
        except Exception:
            log.info("Could not list the anchor points", exc_info=True)
            return []

    def step_action_png(self, step):
        """The icon of a ``run_action`` Step's command (PNG bytes), or ``None``."""
        if step.get("type") != "run_action" or not step.get("action"):
            return None
        try:
            action = self.adapter.find_action(step["action"])
            return None if action is None else self.adapter.action_icon_png(action)
        except Exception:
            log.exception("Could not read the icon of %r", step["action"])
            return None

    def selected_layer_name(self):
        """The name of the layer selected in Painter, or ``None``."""
        try:
            layer = self.adapter.selected_layer()
            return None if layer is None else self.adapter.layer_name(layer)
        except Exception:
            log.exception("Could not read the selected layer's name")
            return None

    # -- Recording (R8) ----------------------------------------------------------

    @property
    def recording_target(self):
        """What the Recording goes into, for the REC bar: the Group's or the Workflow's name."""
        if self.recording is None:
            return None
        if self._recording_draft is not None:
            return self._recording_draft.name
        try:
            return self.editor.group(self._recording_group_id).name
        except KeyError:
            return None

    @property
    def recording_steps(self):
        """How many Steps the Recording has captured so far."""
        return 0 if self.recording is None else len(self.recording.capture.steps)

    def start_recording(self, group):
        """"+ → Recorded Workflow": record a new Workflow for the end of ``group``."""
        if self.view is None:  # closed meanwhile (the "+" menu starts it a moment later)
            return
        if self.read_only:
            self.notify(READ_ONLY_MESSAGE)
            return
        if self._begin_recording():
            self._recording_group_id = group.id
            log.info("Recording a new Workflow for Group %r", group.name)
            self._render()

    def continue_recording(self):
        """The editor's Continue: record more Steps at the end of the open Workflow."""
        draft = self.workflow_draft
        if draft is None or self.view is None:
            return
        if self._begin_recording():
            self._recording_draft = draft
            self.workflow_draft = None  # the Groups and the REC bar show while it records
            log.info("Recording more Steps for %r", draft.name)
            self._render()

    def _begin_recording(self):
        if self.recording is not None:
            self.notify("Shelf+ is already recording.")
            return False
        self.cancel_menu_capture()
        recording = Recording(self.adapter, changed=self._render, notify=self.notify, closing=self.stop_recording)
        problem = recording.start()
        if problem:
            self.notify(problem)
            return False
        self.recording = recording
        try:  # the commands clicked name the operations; without them it still records
            self._stop_recording_watch = self.adapter.watch_actions(self.action_watcher.notify)
        except Exception:
            log.exception("Recording: could not hook Painter's commands")
        return True

    def _end_recording(self):
        """Unhook the Recording; returns its ``Capture``."""
        recording, self.recording = self.recording, None
        stop, self._stop_recording_watch = self._stop_recording_watch, None
        if stop is not None:
            try:
                stop()
            except Exception:
                log.exception("Could not unhook Painter's commands")
        return recording.stop()

    def stop_recording(self):
        """Stop: the editor opens with the captured Steps (after the Workflow's own Steps
        when continuing one). The first incomplete Step is selected, so a resource dropped
        right away fills it."""
        if self.recording is None:
            return None
        steps = self._match_smart_materials(self._end_recording().steps)
        draft, self._recording_draft = self._recording_draft, None
        if draft is None:
            draft = WorkflowDraft(steps)
            self._draft_group_id = self._recording_group_id
        else:
            draft.steps = blocks.normalized(draft.steps + steps)
        self._recording_group_id = None
        first = next((i for i, step in enumerate(draft.steps) if incomplete(step)), None)
        draft.select(first)
        self.workflow_draft = draft
        log.info("Recording stopped: %d Step(s) captured", len(steps))
        self.notify(f"Recorded {len(steps)} Step(s)." if steps else "Nothing was recorded.")
        self._render()
        return draft

    def _match_smart_materials(self, steps):
        """A recorded smart material knows only its folder's name: the one resource with
        that name is taken; with none or several the user picks (the Step stays incomplete)."""
        for step in steps:
            if step.get("type") != "add_smart" or step.get("smart") != "material" or step.get("resource"):
                continue
            name = step.get("resource_name") or ""
            found = [
                r for r in self.search_resources(name)
                if r.gui_name == name and not r.is_brush and (r.kind is None or "smart material" in r.kind.lower())
            ]
            if len(found) == 1:
                step["resource"] = found[0].url
                continue
            why = "several resources have that name" if found else "no resource has that name"
            self.notify(f"Choose the smart material for “{name}”: {why}.")
        return steps

    # -- running ---------------------------------------------------------------

    def run_button(self, button):
        """Clicking a Button: it runs as a Workflow (a Brush button as one ``select_brush``
        Step, a Smart material button as one ``add_smart`` Step, a Menu button as one
        ``run_action`` Step), so every kind has one error path."""
        if not button.valid:
            self.notify(f"“{button.name}” is invalid and cannot run: {button.problem}.")
            return
        steps = button_steps(button)
        self._cancel_running()
        log.info("Running %r (%s, %d Step(s))", button.name, button.kind, len(steps))
        reported = []

        def done(result):  # a cancelled Step never calls it, so it is always the running one
            reported.append(result)
            self._running = None
            if result.state == MISSING and button.kind in RESOURCE_KINDS and not self._can_confirm_missing():
                self.notify(LOADING_MESSAGE.format(what=LOADING_WHAT[button.kind]))
                return
            if result.state == MISSING and button.kind == "menu" and not self._menus_settled():
                self.notify(NOT_YET_MESSAGE.format(name=button.name))
                self.check_menu_buttons()  # keeps looking for it
                return
            if result.state == MISSING and button.kind in (*RESOURCE_KINDS, "menu"):
                self._set_missing(button, True)
                if button.kind == "menu":
                    self.check_menu_buttons()  # starts looking for it again
            if not result.ok:
                self.notify(result.message)

        # The handle is None when ``done`` was already called.
        name = button.name if button.kind == "workflow" else None
        self._running = run_workflow(self.adapter, steps, done, ui_steps=self.ui_steps, name=name)
        if not any(r.state == MISSING for r in reported):
            self._set_missing(button, False)  # it was found this time
        # Painter's History row comes after this returns; only a run that changed the stack has one
        if self.recording is not None and button.kind == "smart_material" and reported and reported[0].ok:
            self.recording.expect_own_smart_material(scope_label(steps), button.raw["resource"])

    def _cancel_running(self):
        running, self._running = self._running, None
        if running is not None:
            running.cancel()

    def close(self):
        self._cancel_running()
        updater, self.updater = self.updater, None
        if updater is not None:
            updater.close()
        if self.network is not None and hasattr(self.network, "close"):
            try:
                self.network.close()
            except Exception:
                log.exception("Closing the network failed")
            self.network = None
        if self.recording is not None:
            try:
                self._end_recording()
            except Exception:
                log.exception("Stopping the Recording failed")
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


class _UpdaterUi:
    """What the updater shows, passed on to the Panel view (which may be gone)."""

    def __init__(self, app):
        self.app = app

    def offer(self, offer):
        view = self.app.view
        if view is not None and hasattr(view, "offer_update"):
            view.offer_update(offer)

    def message(self, text):
        self.app.show_message(text)

    def busy(self, text):
        view = self.app.view
        if view is not None and hasattr(view, "show_busy"):
            view.show_busy(text)
