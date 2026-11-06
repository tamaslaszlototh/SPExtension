"""The running application: loads the Layout and panel state, and owns the Panel.

Painter-free: it uses an adapter (see ``adapter/__init__.py``) and a view factory,
so tests drive it with ``FakeAdapter`` and a fake view.
"""

import logging
import platform
from pathlib import Path

from .core.diagnostics import build_diagnostics, tail_log
from .core.editing import LayoutEditor
from .core.panel_state import TILE_SIZES, PanelStateStore
from .core.storage import LayoutStore

log = logging.getLogger("ShelfPlus.app")

# The "+" menu of each Group row: (label, handler). A ``None`` handler is shown
# disabled; the slices that add each Button kind fill in the handler.
ADD_BUTTON_KINDS = [
    ("Brush button", None),
    ("Menu button", None),
    ("Workflow button", None),
]


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
        self.add_button_kinds = list(ADD_BUTTON_KINDS)
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
        self._save_panel_state()

    def set_tile_size(self, size):
        if size not in TILE_SIZES:
            raise ValueError(f"tile size must be one of {TILE_SIZES}")
        self.panel_state["tileSize"] = size
        self._save_panel_state()

    def set_show_labels(self, show):
        self.panel_state["showLabels"] = bool(show)
        self._save_panel_state()

    def _save_panel_state(self):
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

    def run_button(self, button):
        """Clicking a Button. Running arrives with the Button kinds' own slices."""
        log.info("Clicked %r (%s); running Buttons is not available yet", button.name, button.kind)

    def close(self):
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
