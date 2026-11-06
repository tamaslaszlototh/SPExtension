"""The real adapter: the only place that talks to ``substance_painter`` (this slice's part of it)."""

import substance_painter.application
import substance_painter.ui


class PainterAdapter:
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
