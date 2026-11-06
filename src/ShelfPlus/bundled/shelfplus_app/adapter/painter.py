"""The real adapter: the only place that talks to ``substance_painter``."""

import json
import logging
from urllib.parse import quote

import substance_painter.application
import substance_painter.ui

from ..core.brush import BrushResource, versionless_url
from .assets import AssetsWindow

log = logging.getLogger("ShelfPlus.app.adapter")


class PainterAdapter:
    def __init__(self):
        self.assets = AssetsWindow()

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

    # -- timers --------------------------------------------------------------

    def repeat(self, interval_ms, callback):
        from PySide6 import QtCore

        timer = QtCore.QTimer()
        timer.setInterval(interval_ms)
        timer.timeout.connect(callback)
        timer.start()
        return timer


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
