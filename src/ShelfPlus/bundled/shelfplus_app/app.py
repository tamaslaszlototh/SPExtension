"""The running application: loads the Layout and panel state, and owns the Panel.

Painter-free: it uses an adapter (see ``adapter/__init__.py``) and a view factory,
so tests drive it with ``FakeAdapter`` and a fake view.
"""

import logging
import platform
from pathlib import Path

from .core.brush import MISSING, brush_button, brush_icon, resolve, resource_urls_from_drop, select_brush
from .core.diagnostics import build_diagnostics, tail_log
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

# The UI Steps the App can run so far: Step type -> function(adapter, step, done).
UI_STEPS = {"select_brush": select_brush}


def button_steps(button):
    """The Steps a Button runs. A Brush button is a one-Step Workflow. ``None``: this
    Button kind cannot run yet."""
    if button.kind == "brush":
        return [{"type": "select_brush", "resource": button.raw["resource"]}]
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
        handlers = {"Brush button": self.explain_brush_drop}
        self.add_button_kinds = [(label, handlers.get(label, handler)) for label, handler in ADD_BUTTON_KINDS]
        self.missing = set()  # ids of Brush buttons whose preset is not on this machine
        self._running = None  # the Step in progress (its handle has ``cancel()``)
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
        self.check_brushes()

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

    def check_brushes(self):
        """Mark every Brush button whose preset cannot be found (at load)."""
        for group in self.layout.groups:
            for button in group.buttons:
                if button.valid and button.kind == "brush":
                    self._set_missing(button, resolve(self.adapter, button.raw["resource"]) is None)
        if self.missing:
            log.info("%d Brush button(s) have no preset on this machine", len(self.missing))

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
            if result.state == MISSING:
                self._set_missing(button, True)
            if not result.ok:
                self.notify(result.message)

        # The handle is None when ``done`` was already called.
        self._running = UI_STEPS[step["type"]](self.adapter, step, done)
        if not any(r.state == MISSING for r in reported):
            self._set_missing(button, False)  # it was found this time

    def _cancel_running(self):
        running, self._running = self._running, None
        if running is not None:
            running.cancel()

    def close(self):
        self._cancel_running()
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
