"""The real adapter: the only place that talks to ``substance_painter``."""

import json
import logging
from urllib.parse import quote

import substance_painter.application
import substance_painter.ui

from ..core.brush import BrushResource, versionless_url
from .actions import PainterActions
from .assets import AssetsWindow

log = logging.getLogger("ShelfPlus.app.adapter")

ANCHOR_POINT_NAME = "Anchor point"


class PainterAdapter:
    def __init__(self):
        self.assets = AssetsWindow()
        self.actions = PainterActions()

    def add_dock_widget(self, widget):
        ui = substance_painter.ui
        ui_mode = getattr(getattr(ui, "UIMode", None), "Edition", None)
        if ui_mode is None:
            return ui.add_dock_widget(widget)
        return ui.add_dock_widget(widget, ui_modes=ui_mode)

    def delete_ui_element(self, handle):
        substance_painter.ui.delete_ui_element(handle)

    def painter_version(self):
        app = substance_painter.application
        if hasattr(app, "version"):
            return app.version()
        return ".".join(str(part) for part in app.version_info())

    def qt_version(self):
        import PySide6
        from PySide6 import QtCore

        return f"{QtCore.qVersion()} (PySide6 {PySide6.__version__})"

    # -- resources -----------------------------------------------------------

    def resolve_resource(self, url):
        """The brush behind a version-less ``resource://`` URL, or ``None``."""
        import substance_painter.resource as res

        for candidate in dict.fromkeys((url, quote(url, safe=":/?=&"))):
            try:
                found = res.Resource.retrieve(res.ResourceID.from_url(candidate))
            except Exception:
                log.debug("Resource.retrieve(%r) failed", candidate, exc_info=True)
                continue
            if found:
                resource = found[0]
                return BrushResource(
                    versionless_url(resource.identifier().url()), resource.gui_name(), _is_brush(res, resource), resource
                )
        return None

    def search_resources(self, query, limit=300):
        """Painter's resources matching ``query`` (Painter's own search syntax), for the
        resource picker: at most ``limit``, sorted by name."""
        import substance_painter.resource as res

        found = []
        for resource in res.search(query)[: limit * 2]:
            try:
                url = versionless_url(resource.identifier().url())
                kind = _kind_name(resource)
                found.append(BrushResource(url, resource.gui_name(), _is_brush(res, resource), resource, kind))
            except Exception:
                log.debug("Skipping a search result", exc_info=True)
        found.sort(key=lambda r: r.gui_name.lower())
        return found[:limit]

    def resources_loading(self):
        """Whether Painter is still loading resources: a shelf is crawling, or its resource
        service has not started yet (``Shelves.all()`` raises)."""
        import substance_painter.resource as res

        try:
            return any(shelf.is_crawling() for shelf in res.Shelves.all())
        except Exception:
            log.info("Shelves are not available yet", exc_info=True)
            return True

    def on_resources_loaded(self, callback):
        """Call ``callback()`` whenever a shelf finishes loading its resources. Returns a
        function that disconnects it."""
        import substance_painter.event as event

        def handler(_event):
            callback()

        event.DISPATCHER.connect(event.ShelfCrawlingEnded, handler)
        return lambda: event.DISPATCHER.disconnect(event.ShelfCrawlingEnded, handler)

    def resource_file_path(self, resource):
        """The file behind a resource (e.g. the ``.sppr``), from the legacy JavaScript API."""
        import substance_painter.js

        url = resource.handle.identifier().url() if resource.handle is not None else resource.url
        info = json.loads(substance_painter.js.evaluate(f"JSON.stringify(alg.resources.getResourceInfo({json.dumps(url)}))"))
        return (info or {}).get("filePath") or None

    def show_in_ui(self, resource):
        resource.handle.show_in_ui()

    # -- the Assets window ---------------------------------------------------

    def assets_icon_sources(self, resource):
        return self.assets.icon_sources(resource.gui_name)

    def open_assets(self):
        return self.assets.open()

    def tile_rect(self, gui_name):
        return self.assets.tile_rect(gui_name)

    def click_tile(self, rect):
        self.assets.click(rect)

    # -- Painter's commands (QActions) ----------------------------------------

    def project_open(self):
        import substance_painter.project

        return substance_painter.project.is_open()

    def list_actions(self):
        return self.actions.all()

    def find_action(self, name):
        return self.actions.find(name)

    def action_icon_png(self, action):
        return self.actions.icon_png(action)

    def watch_actions(self, callback):
        return self.actions.watch(callback)

    def trigger_action(self, action):
        return self.actions.trigger(action)

    # -- the project and its layer stack (the Workflow runner) -------------------

    def project_ready(self):
        """A project is open and in edition state (not loading, baking or closing)."""
        import substance_painter.project as project

        return project.is_open() and project.is_in_edition_state()

    def selected_layer(self):
        """The selected layer of the active texture set, or ``None``. With a mask or an
        effect selected, its layer; with several layers selected, the first."""
        import substance_painter.layerstack as ls

        selected = ls.get_selected_nodes(_active_stack())
        if not selected:
            return None
        if len(selected) > 1:
            log.info("%d nodes are selected; the Workflow starts at the first", len(selected))
        return _layer_of(ls, selected[0])

    def layer_scope(self, label):
        import substance_painter.layerstack as ls

        return ls.ScopedModification(label)

    def insert_layer(self, kind, above=None, name=None):
        import substance_painter.layerstack as ls

        insert = getattr(ls, {"fill": "insert_fill", "paint": "insert_paint", "folder": "insert_group"}[kind])
        node = insert(_position_above(ls, above))
        if name:
            node.set_name(name)
        return node

    def add_mask(self, layer, background):
        import substance_painter.layerstack as ls

        layer.add_mask({"black": ls.MaskBackground.Black, "white": ls.MaskBackground.White}[background])

    def has_mask(self, layer):
        return bool(layer.has_mask())

    def insert_effect(self, layer, target, effect, resource=None):
        """On top of the layer's mask stack (``target`` mask) or content stack (layer).
        ``effect``: generator / filter (with a ``resource`` URL), levels or anchor."""
        import substance_painter.layerstack as ls

        stack = ls.NodeStack.Mask if target == "mask" else ls.NodeStack.Content
        resource_id = self._resource_id(resource) if resource is not None else None
        position = ls.InsertPosition.inside_node(layer, stack)
        if effect == "generator":
            return ls.insert_generator_effect(position, resource_id)
        if effect == "filter":
            return ls.insert_filter_effect(position, resource_id)
        if effect == "levels":
            return ls.insert_levels_effect(position)
        if effect == "anchor":
            return ls.insert_anchor_point_effect(position, ANCHOR_POINT_NAME)
        raise ValueError(f"Shelf+ cannot add a “{effect}” effect.")

    def insert_smart_material(self, url, above=None):
        """The smart material's folder, above ``above`` in its folder or on top of the stack."""
        import substance_painter.layerstack as ls

        resource_id = self._resource_id(url)
        return ls.insert_smart_material(_position_above(ls, above), resource_id)

    def insert_smart_mask(self, layer, url):
        """Into the layer's mask stack. A layer without a mask gets a black one first, so
        only what the smart mask makes shows (Painter's own drop makes a new mask too)."""
        import substance_painter.layerstack as ls

        resource_id = self._resource_id(url)
        if not layer.has_mask():
            self.add_mask(layer, "black")
        return ls.insert_smart_mask(ls.InsertPosition.inside_node(layer, ls.NodeStack.Mask), resource_id)

    def _resource_id(self, url):
        """The ``ResourceID`` of a version-less URL; preflight has checked that it exists."""
        found = self.resolve_resource(url)
        if found is None or found.handle is None:
            raise ValueError(f"This resource is not available on this machine: {url}")
        return found.handle.identifier()

    def set_blend(self, layer, mode):
        """``mode`` is a ``BlendingMode`` name (``Multiply``), set on every channel."""
        import substance_painter.layerstack as ls

        value = _enum_member(ls.BlendingMode, mode)
        if value is None:
            raise ValueError(f"Painter has no blend mode “{mode}”.")
        channels = list(getattr(layer, "active_channels", None) or [])
        if not channels:
            layer.set_blending_mode(value)
            return
        for channel in channels:
            layer.set_blending_mode(value, channel)

    def set_opacity(self, layer, channel, percent):
        """``channel`` is a ``ChannelType`` name (``BaseColor``); ``percent`` 0–100."""
        import substance_painter.textureset as ts

        value = _enum_member(ts.ChannelType, channel)
        if value is None:
            raise ValueError(f"Painter has no channel “{channel}”.")
        layer.set_opacity(percent / 100.0, value)

    # -- a new layer's channels and content ------------------------------------------

    def stack_channels(self):
        """The ChannelType names of the active texture set's channels."""
        return [channel.name for channel in _active_stack().all_channels()]

    def set_active_channels(self, layer, channels):
        """``channels``: ChannelType names; every other channel is switched off."""
        import substance_painter.textureset as ts

        layer.active_channels = {_channel(ts, name) for name in channels}

    def set_material(self, layer, url):
        """One material (or other resource) as the Fill layer's source for every channel."""
        layer.set_material_source(self._resource_id(url))

    def set_channel_source(self, layer, channel, source):
        """A Fill layer's source for one channel: ``{"color": "#rrggbb"}``, ``{"value":
        0..1}`` (a grey) or ``{"resource": url}``."""
        import substance_painter.textureset as ts

        channel_type = _channel(ts, channel)
        if "resource" in source:
            layer.set_source(channel_type, self._resource_id(source["resource"]))
            return
        if "color" in source:
            hex_colour = source["color"].lstrip("#")
            rgb = tuple(int(hex_colour[i : i + 2], 16) / 255 for i in (0, 2, 4))
        else:
            rgb = (source["value"],) * 3
        layer.set_source(channel_type, _colour(rgb))

    def find_layers(self, name):
        """Every layer of the active texture set named exactly ``name``, folders included."""
        import substance_painter.layerstack as ls

        found = []
        pending = list(ls.get_root_layer_nodes(_active_stack()))
        while pending:
            node = pending.pop()
            if node.get_name() == name:
                found.append(node)
            if node.get_type() == ls.NodeType.GroupLayer:
                pending.extend(node.sub_layers())
        return found

    def layer_name(self, layer):
        return layer.get_name()

    def select_layer(self, layer):
        import substance_painter.layerstack as ls

        ls.set_selected_nodes([layer])

    def select_mask(self, layer):
        """Select the layer's mask, so Painter paints on it and takes a brush."""
        import substance_painter.layerstack as ls

        ls.set_selected_nodes([layer])
        ls.set_selection_type(layer, ls.SelectionType.Mask)

    def selection_paintable(self):
        """Whether Painter would paint on the selection: a mask, a Paint layer's content
        or a paint effect. ``None`` if it cannot tell (no project, nothing selected)."""
        import substance_painter.layerstack as ls
        import substance_painter.project as project

        if not project.is_open():
            return None
        selected = ls.get_selected_nodes(_active_stack())
        if not selected:
            return None
        node = selected[0]
        kind = node.get_type()
        if kind == getattr(ls.NodeType, "PaintEffect", None):
            return True
        layer = _layer_of(ls, node)
        if layer is not node:  # another effect, in the content or the mask stack
            return False
        if ls.get_selection_type(node) == ls.SelectionType.Mask:
            return True
        return kind == ls.NodeType.PaintLayer

    def save_project(self):
        import substance_painter.project as project

        project.save()

    # -- timers --------------------------------------------------------------

    def repeat(self, interval_ms, callback):
        from PySide6 import QtCore

        timer = QtCore.QTimer()
        timer.setInterval(interval_ms)
        timer.timeout.connect(callback)
        timer.start()
        return timer


def _position_above(ls, above):
    """Above ``above`` in its folder, or on top of the active stack when it is ``None``."""
    if above is None:
        return ls.InsertPosition.from_textureset_stack(_active_stack())
    return ls.InsertPosition.above_node(above)


def _active_stack():
    """The layer stack of the active texture set (``textureset``, not ``layerstack``)."""
    import substance_painter.textureset as ts

    return ts.get_active_stack()


_LAYER_TYPES = ("FillLayer", "PaintLayer", "GroupLayer", "InstanceLayer")


def _layer_of(ls, node):
    """The layer a selected node belongs to: the node itself, or the layer above its
    mask or effect."""
    layer_types = [getattr(ls.NodeType, t) for t in _LAYER_TYPES if hasattr(ls.NodeType, t)]
    while node is not None and node.get_type() not in layer_types:
        node = node.get_parent()
    return node


def _channel(ts, name):
    value = _enum_member(ts.ChannelType, name)
    if value is None:
        raise ValueError(f"Painter has no channel “{name}”.")
    return value


def _colour(rgb):
    """A uniform colour for ``set_source``. The values are what a colour picker shows
    (sRGB), so they are converted if Painter offers it."""
    from substance_painter.colormanagement import Color

    for name in ("from_srgb", "from_sRGB"):
        convert = getattr(Color, name, None)
        if convert is not None:
            return convert(*rgb)
    return Color(*rgb)


def _kind_name(resource):
    """"Smart material" from Painter's resource type, or ``None``."""
    try:
        name = resource.type().name
    except Exception:
        return None
    return name.replace("_", " ").capitalize()


def _enum_member(enum, name):
    """The member of a Painter enum called ``name`` (also ignoring case), or ``None``."""
    member = getattr(enum, name, None)
    if member is not None:
        return member
    wanted = name.replace(" ", "").lower()
    for attr in dir(enum):
        if not attr.startswith("_") and attr.lower() == wanted:
            return getattr(enum, attr)
    return None


def _is_brush(res, resource):
    """A tool preset or an ``.abr``/alpha brush. If Painter cannot tell, it is let through."""
    usage = getattr(res, "Usage", None)
    wanted = [u for u in (getattr(usage, "TOOL", None), getattr(usage, "BRUSH", None)) if u is not None]
    if not wanted:
        return True
    try:
        usages = list(resource.usages())
    except Exception:
        return True
    return any(u in usages for u in wanted)
