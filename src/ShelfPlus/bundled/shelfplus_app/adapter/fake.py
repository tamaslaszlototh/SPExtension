"""An in-memory adapter for tests. Records what the App asked Painter to do."""

from ..core.brush import BrushResource


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

    # -- timers --------------------------------------------------------------

    def repeat(self, interval_ms, callback):
        timer = FakeTimer(interval_ms, callback)
        self.timers.append(timer)
        return timer

    def fire_timers(self):
        for timer in list(self.timers):
            if timer.active:
                timer.callback()
