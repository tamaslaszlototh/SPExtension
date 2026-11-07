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

        if above is None:
            position = ls.InsertPosition.from_textureset_stack(_active_stack())
        else:
            position = ls.InsertPosition.above_node(above)
        insert = getattr(ls, {"fill": "insert_fill", "paint": "insert_paint", "folder": "insert_group"}[kind])
        node = insert(position)
        if name:
            node.set_name(name)
        return node

    def add_mask(self, layer, background):
        import substance_painter.layerstack as ls

        layer.add_mask({"black": ls.MaskBackground.Black, "white": ls.MaskBackground.White}[background])

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

    def select_layer(self, layer):
        import substance_painter.layerstack as ls

        ls.set_selected_nodes([layer])

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
