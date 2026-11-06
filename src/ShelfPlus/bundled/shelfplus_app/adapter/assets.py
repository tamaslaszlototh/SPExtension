"""Painter's Assets window, driven through Qt only (PRD R5.2). Part of the adapter layer.

Widget rules (measured on Painter 11.1, see ``docs/probes/second-round.md``):

- Painter widgets are found only through ``QApplication.allWidgets()``, never
  ``findChildren`` (it returns dead wrappers on 11.1), and never by walking up with
  ``parentWidget()``/``window()``: dropping such a wrapper invalidates its descendants'.
- Every reference found is kept (the dock, the view, its viewport and model, and the
  ``allWidgets()`` list it came from), checked with ``shiboken6.isValid`` before use,
  and found again when invalid.
"""

import logging

from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid

log = logging.getLogger("ShelfPlus.app.assets")

DOCK_NAME = "NewShelf"
VIEW_CLASS = "Alg::ResourceListView"
ICON_SIZE = 256  # the largest size asked of a DecorationRole icon


def _valid(obj):
    try:
        return obj is not None and isValid(obj)
    except Exception:
        return False


class AssetsWindow:
    def __init__(self, dock_name=DOCK_NAME, view_class=VIEW_CLASS):
        self.dock_name = dock_name
        self.view_class = view_class
        self._held = []  # the allWidgets() list of the last lookup
        self._dock = None
        self._view = None
        self._viewport = None
        self._model = None

    # -- finding -------------------------------------------------------------

    def _all_widgets(self):
        try:
            widgets = QtWidgets.QApplication.allWidgets()
        except Exception:
            log.exception("QApplication.allWidgets() failed")
            return []
        self._held = widgets
        return widgets

    def dock(self):
        """The Assets dock, or ``None``."""
        if _valid(self._dock):
            return self._dock
        self._dock = self._view = self._viewport = self._model = None
        for widget in self._all_widgets():
            try:
                if isinstance(widget, QtWidgets.QDockWidget) and _valid(widget) and widget.objectName() == self.dock_name:
                    self._dock = widget
                    break
            except RuntimeError:
                continue
        if self._dock is None:
            log.warning("The Assets window (%s) was not found", self.dock_name)
        return self._dock

    def view(self):
        """The Assets window's resource list (a visible one if there is one), or ``None``."""
        dock = self.dock()
        if dock is None:
            return None
        if _valid(self._view) and _valid(self._viewport) and self._view.isVisible():
            return self._view
        found = None
        for widget in self._all_widgets():
            try:
                if not (isinstance(widget, QtWidgets.QAbstractItemView) and _valid(widget)):
                    continue
                if widget.metaObject().className() != self.view_class or not dock.isAncestorOf(widget):
                    continue
            except RuntimeError:
                continue
            found = widget
            if widget.isVisible():
                break
        self._view = found
        self._viewport = found.viewport() if found is not None else None
        return found

    def _index(self, view, gui_name):
        model = view.model()
        self._model = model
        if model is None or model.rowCount() == 0:
            return None
        flags = QtCore.Qt.MatchFlag.MatchExactly | QtCore.Qt.MatchFlag.MatchRecursive
        hits = model.match(model.index(0, 0), QtCore.Qt.ItemDataRole.DisplayRole, gui_name, 1, flags)
        return hits[0] if hits else None

    # -- the steps of activating -------------------------------------------------

    def open(self):
        """Open the Assets window and bring it to the front (also out from behind a tab)."""
        dock = self.dock()
        if dock is None:
            return False
        if dock.isHidden():
            dock.show()
        dock.raise_()
        return True

    def tile_rect(self, gui_name):
        """The tile's rectangle in the view's viewport, once it is on screen; else ``None``.
        A tile in the model but scrolled out of sight is scrolled to."""
        view = self.view()
        if view is None or not view.isVisible() or view.visibleRegion().isEmpty():
            return None
        index = self._index(view, gui_name)
        if index is None:
            return None
        rect = view.visualRect(index)
        if not rect.isValid() or not self._viewport.rect().contains(rect.center()):
            view.scrollTo(index)
            return None
        return (rect.x(), rect.y(), rect.width(), rect.height())

    def click(self, rect):
        """A left click (press and release) at the centre of ``rect``, sent as Qt events to
        the view's viewport. ``rect`` belongs to that viewport: if it is gone, nothing is
        clicked (a view found again could have its tiles elsewhere)."""
        if not _valid(self._viewport):
            raise RuntimeError("the Assets view is gone")
        viewport = self._viewport
        centre = QtCore.QRect(*rect).center()
        local = QtCore.QPointF(centre)
        global_pos = QtCore.QPointF(viewport.mapToGlobal(centre))
        left = QtCore.Qt.MouseButton.LeftButton
        for kind, buttons in (
            (QtCore.QEvent.Type.MouseButtonPress, left),
            (QtCore.QEvent.Type.MouseButtonRelease, QtCore.Qt.MouseButton.NoButton),
        ):
            event = QtGui.QMouseEvent(kind, local, global_pos, left, buttons, QtCore.Qt.KeyboardModifier.NoModifier)
            QtWidgets.QApplication.sendEvent(viewport, event)

    # -- the icon --------------------------------------------------------------

    def icon_sources(self, gui_name):
        """``(tooltip HTML, DecorationRole image as PNG bytes)`` of the tile, each maybe ``None``."""
        view = self.view()
        index = self._index(view, gui_name) if view is not None else None
        if index is None:
            log.info("No Assets tile named %r for the icon", gui_name)
            return None, None
        tooltip = index.data(QtCore.Qt.ItemDataRole.ToolTipRole)
        decoration = _png_bytes(index.data(QtCore.Qt.ItemDataRole.DecorationRole))
        return (tooltip if isinstance(tooltip, str) else None), decoration


def _png_bytes(value):
    """A ``QIcon``/``QPixmap``/``QImage`` as PNG bytes, or ``None``."""
    if isinstance(value, QtGui.QIcon):
        sizes = value.availableSizes()
        size = max(sizes, key=lambda s: s.width() * s.height()) if sizes else QtCore.QSize(ICON_SIZE, ICON_SIZE)
        value = value.pixmap(size)
    if isinstance(value, QtGui.QPixmap):
        value = value.toImage()
    if not isinstance(value, QtGui.QImage) or value.isNull():
        return None
    data = QtCore.QByteArray()
    buffer = QtCore.QBuffer(data)
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    ok = value.save(buffer, "PNG")
    buffer.close()
    return bytes(data) if ok else None
