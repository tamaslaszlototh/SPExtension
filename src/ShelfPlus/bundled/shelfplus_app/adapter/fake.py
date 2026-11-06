"""An in-memory adapter for tests. Records what the App asked Painter to do."""


class FakeAdapter:
    def __init__(self, painter_version="11.1.0", qt_version="6.5.8", fail_on_dock=False):
        self._painter_version = painter_version
        self._qt_version = qt_version
        self.fail_on_dock = fail_on_dock
        self.docks = []
        self.deleted = []

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
