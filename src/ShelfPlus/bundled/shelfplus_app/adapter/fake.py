"""An in-memory adapter for tests. Records what the App asked Painter to do."""

from ..core.brush import BrushResource
from ..core.menu import action_id, same_action


def FakeResource(url, gui_name, is_brush=True):
    return BrushResource(url, gui_name, is_brush)


class FakeTimer:
    def __init__(self, interval_ms, callback):
        self.interval_ms = interval_ms
        self.callback = callback
        self.active = True

    def stop(self):
        self.active = False


class FakeAdapter:
    def __init__(self, painter_version="11.1.0", qt_version="6.5.8", fail_on_dock=False):
        self._painter_version = painter_version
        self._qt_version = qt_version
        self.fail_on_dock = fail_on_dock
        self.docks = []
        self.deleted = []

        # Resources: url -> BrushResource, and what the Assets window shows for them.
        self.resources = {}
        self.resource_error = None
        self.tooltips = {}  # url -> tooltip HTML
        self.decorations = {}  # url -> PNG bytes
        self.preset_files = {}  # url -> file path

        # The Assets window.
        self.assets_window = True
        self.assets_calls = []
        self.tiles = {}  # gui_name -> (x, y, w, h) or None
        self.tile_error = None
        self.click_error = None
        self.clicks = []

        self.timers = []

        # Painter loading its resources (shelf crawling).
        self.loading = False
        self.loaded_callbacks = []

        # Painter's commands (QActions): MenuActions, their icons, and the hooks.
        self.actions = []
        self.action_icons = {}  # objectName -> PNG bytes
        self.action_error = None
        self.trigger_error = None
        self.disabled = set()  # objectNames Painter has disabled right now
        self.triggered = []  # objectNames, in the order they were triggered
        self.hooks = []  # the callbacks of watch_actions()
        self.watch_error = None

    def add_dock_widget(self, widget):
        if self.fail_on_dock:
            raise RuntimeError("add_dock_widget failed")
        self.docks.append(widget)
        return widget

    def delete_ui_element(self, handle):
        self.deleted.append(handle)

    def painter_version(self):
        return self._painter_version

    def qt_version(self):
        return self._qt_version

    # -- resources -----------------------------------------------------------

    def add_resource(self, resource, tooltip=None, decoration=None, preset_file=None):
        self.resources[resource.url] = resource
        self.tooltips[resource.url] = tooltip
        self.decorations[resource.url] = decoration
        self.preset_files[resource.url] = preset_file

    def resolve_resource(self, url):
        if self.resource_error is not None:
            raise self.resource_error
        return self.resources.get(url)

    def resources_loading(self):
        return self.loading

    def on_resources_loaded(self, callback):
        self.loaded_callbacks.append(callback)
        return lambda: self.loaded_callbacks.remove(callback)

    def finish_loading(self):
        self.loading = False
        for callback in list(self.loaded_callbacks):
            callback()

    def assets_icon_sources(self, resource):
        return self.tooltips.get(resource.url), self.decorations.get(resource.url)

    def resource_file_path(self, resource):
        return self.preset_files.get(resource.url)

    # -- the Assets window ---------------------------------------------------

    def open_assets(self):
        self.assets_calls.append("open")
        return self.assets_window

    def show_in_ui(self, resource):
        self.assets_calls.append(f"show_in_ui {resource.url}")

    def tile_rect(self, gui_name):
        if self.tile_error is not None:
            raise self.tile_error
        return self.tiles.get(gui_name)

    def click_tile(self, rect):
        if self.click_error is not None:
            raise self.click_error
        self.clicks.append(rect)

    # -- Painter's commands (QActions) ----------------------------------------

    def list_actions(self):
        if self.action_error is not None:
            raise self.action_error
        return list(self.actions)

    def find_action(self, name):
        if self.action_error is not None:
            raise self.action_error
        return next((a for a in self.actions if same_action(action_id(a), name)), None)

    def action_icon_png(self, action):
        return self.action_icons.get(action.name)

    def watch_actions(self, callback):
        if self.watch_error is not None:
            raise self.watch_error
        self.hooks.append(callback)
        return lambda: self.hooks.remove(callback)

    def click_command(self, action, hook_calls=2):
        """The user runs ``action`` from Painter's menu: like Qt, every hook reports it
        (``QAction.triggered`` and ``QMenu.triggered``)."""
        self.triggered.append(action.name)
        self._report(action, hook_calls)

    def trigger_action(self, action):
        if self.trigger_error is not None:
            raise self.trigger_error
        if action.name in self.disabled:
            return False
        self.click_command(action)
        return True

    def _report(self, action, hook_calls):
        for _ in range(hook_calls):
            for callback in list(self.hooks):
                callback(action)

    # -- timers --------------------------------------------------------------

    def repeat(self, interval_ms, callback):
        timer = FakeTimer(interval_ms, callback)
        self.timers.append(timer)
        return timer

    def fire_timers(self):
        for timer in list(self.timers):
            if timer.active:
                timer.callback()
