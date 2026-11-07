"""An in-memory adapter for tests. Records what the App asked Painter to do."""

from contextlib import contextmanager

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


class FakeLayer:
    """A layer of the fake stack. ``children`` (top first) only for a folder."""

    def __init__(self, name, kind="paint", children=None):
        self.name = name
        self.kind = kind
        self.children = list(children or [])
        self.mask = None
        self.effects = []  # (target, effect, resource url or None), oldest first
        self.effect_nodes = []  # the FakeEffect of each, in the same order
        self.blend = "Normal"
        self.opacity = {}
        self.channels = None  # the active channels; None: Painter's default
        self.material = None  # a Fill layer's material (URL)
        self.sources = {}  # a Fill layer's channel -> source

    def __repr__(self):
        return f"FakeLayer({self.name!r}, {self.kind!r})"


class FakeEffect:
    """An effect inside a layer (insert_effect's result); a Fill one has content."""

    def __init__(self, target, effect):
        self.target, self.effect = target, effect
        self.channels = None
        self.material = None
        self.sources = {}
        self.source = None  # a Fill on a mask: its one source


class FakeLayerStack:
    """Painter's layer stack of the active texture set, as far as the runner sees it.

    Like Painter, it refuses a selection change inside a ``ScopedModification``, and every
    change outside one is an error here (Painter would make it a separate undo entry).
    ``fail_on`` = an operation name (``"add_mask"``…) that raises, for mid-run failures.
    """

    def __init__(self, layers=None):
        self.layers = list(layers or [])  # top of the stack first
        self.selected = None
        self.selected_part = "content"  # or "mask": which part of the selected layer
        self.scopes = []  # the labels of every scope opened
        self.in_scope = False
        self.fail_on = None
        self.changes = 0

    def walk(self, layers=None):
        for layer in self.layers if layers is None else layers:
            yield layer
            yield from self.walk(layer.children)

    def siblings(self, layer):
        if layer in self.layers:
            return self.layers
        return next(p.children for p in self.walk() if layer in p.children)

    def insert(self, layer, above=None):
        """Put ``layer`` above ``above`` in its folder, or on top of the stack."""
        siblings = self.layers if above is None else self.siblings(above)
        siblings.insert(0 if above is None else siblings.index(above), layer)
        return layer

    def names(self, layers=None):
        """The stack as nested names, e.g. ``["Fill", ("Folder", ["Paint"])]``."""
        layers = self.layers if layers is None else layers
        return [(layer.name, self.names(layer.children)) if layer.kind == "folder" else layer.name for layer in layers]

    def change(self, op):
        if not self.in_scope:
            raise AssertionError(f"{op} outside a ScopedModification")
        if self.fail_on == op:
            raise RuntimeError(f"{op} failed")
        self.changes += 1


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
        self.project_is_open = False
        self.watch_error = None

        # The project and its layer stack (the Workflow runner).
        self.edition = True  # the open project is in edition state
        self.stack = FakeLayerStack()
        self.texture_channels = None  # the active texture set's channels; None: unknown
        self.saves = 0
        self.save_error = None

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

    def project_open(self):
        return self.project_is_open

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

    # -- the project and its layer stack ----------------------------------------

    def project_ready(self):
        return self.project_is_open and self.edition

    def selected_layer(self):
        return self.stack.selected

    @contextmanager
    def layer_scope(self, label):
        stack = self.stack
        assert not stack.in_scope, "scopes do not nest"
        stack.scopes.append(label)
        stack.in_scope = True
        try:
            yield
        finally:
            stack.in_scope = False

    def insert_layer(self, kind, above=None, name=None):
        stack = self.stack
        stack.change("insert_layer")
        layer = FakeLayer(name or {"fill": "Fill layer", "paint": "Layer", "folder": "Folder"}[kind], kind)
        return stack.insert(layer, above)

    def add_mask(self, layer, background):
        self.stack.change("add_mask")
        layer.mask = background

    def has_mask(self, layer):
        return layer.mask is not None

    def _resource(self, url):
        if url not in self.resources:  # preflight checks this; Painter would raise
            raise ValueError(f"No resource {url}")
        return self.resources[url]

    def insert_effect(self, layer, target, effect, resource=None):
        self.stack.change("insert_effect")
        if target == "mask" and layer.mask is None:
            raise RuntimeError("The layer has no mask")
        if resource is not None:
            self._resource(resource)
        layer.effects.append((target, effect, resource))
        node = FakeEffect(target, effect)
        layer.effect_nodes.append(node)
        return node

    def insert_smart_material(self, url, above=None):
        stack = self.stack
        stack.change("insert_smart_material")
        return stack.insert(FakeLayer(self._resource(url).gui_name, "folder"), above)

    def insert_smart_mask(self, layer, url):
        """Into the layer's mask; a layer without one gets a black mask first."""
        self.stack.change("insert_smart_mask")
        self._resource(url)
        if layer.mask is None:
            layer.mask = "black"
        layer.effects.append(("mask", "smart mask", url))

    def set_blend(self, layer, mode):
        self.stack.change("set_blend")
        layer.blend = mode

    def set_opacity(self, layer, channel, percent):
        self.stack.change("set_opacity")
        layer.opacity[channel] = percent

    def set_active_channels(self, layer, channels):
        self.stack.change("set_active_channels")
        layer.channels = list(channels)

    def set_material(self, layer, url):
        self.stack.change("set_material")
        self._resource(url)
        layer.material = url

    def set_channel_source(self, layer, channel, source):
        self.stack.change("set_channel_source")
        if "resource" in source:
            self._resource(source["resource"])
        source = {k: v for k, v in source.items() if k != "resource_name"}
        if channel is None:  # a Fill on a mask
            layer.source = source
        else:
            layer.sources[channel] = source

    def stack_channels(self):
        return self.texture_channels

    def search_resources(self, query):
        words = query.lower().split()
        return [r for r in self.resources.values() if all(w in r.gui_name.lower() for w in words)]

    def find_layers(self, name):
        return [layer for layer in self.stack.walk() if layer.name == name]

    def layer_name(self, layer):
        return layer.name

    def select_layer(self, layer):
        if self.stack.in_scope:
            raise RuntimeError("The selection cannot change inside a ScopedModification")
        self.stack.selected = layer
        self.stack.selected_part = "content"

    def select_mask(self, layer):
        if self.stack.in_scope:
            raise RuntimeError("The selection cannot change inside a ScopedModification")
        assert layer.mask is not None, "the layer has no mask"
        self.stack.selected = layer
        self.stack.selected_part = "mask"

    def selection_paintable(self):
        """Like Painter: a Paint layer's content or any mask; ``None`` if it cannot tell."""
        layer = self.stack.selected
        if not self.project_ready() or layer is None:
            return None
        return self.stack.selected_part == "mask" or layer.kind == "paint"

    def save_project(self):
        if self.save_error is not None:
            raise self.save_error
        self.saves += 1

    # -- timers --------------------------------------------------------------

    def repeat(self, interval_ms, callback):
        timer = FakeTimer(interval_ms, callback)
        self.timers.append(timer)
        return timer

    def fire_timers(self):
        for timer in list(self.timers):
            if timer.active:
                timer.callback()
