"""What Recording (``core/recording.py``) needs from Painter. Part of the adapter layer.

- ``snapshot(...)``: the active layer stack as plain dicts, nodes by uid (stable across
  undo and redo). Painter raises ``ProjectError('The project is locked.')`` while it
  saves; the error is passed on and the core retries.
- ``HistoryWatch``: Painter's History, the ``QUndoView`` with objectName ``history``
  (readable even while its dock is hidden). Every signal of its model, its selection
  and its undo stack is coalesced into one reading (labels, index) after the current
  event, so the reading never sees a half-updated model.
- ``DropWatch``: resources dropped anywhere in Painter (an application event filter
  that only looks, never takes the drop).
- Painter's ``LayerStacksModelDataChanged`` and ``ProjectAboutToClose`` events.

Widget rules as everywhere (see ``docs/probes/``): the History view is found only
through ``QApplication.allWidgets()``, every wrapper is kept while the watch lives and
checked with ``shiboken6.isValid`` before use.
"""

import logging

from PySide6 import QtCore, QtWidgets

from ..core.brush import resource_urls_from_drop, versionless_url
from ..core.menu import OWN_PREFIX
from .assets import valid

log = logging.getLogger("ShelfPlus.app.recording")

HISTORY_NAME = "history"

_LAYER_KINDS = {"FillLayer": "fill", "PaintLayer": "paint", "GroupLayer": "folder", "InstanceLayer": "instance"}
_EFFECT_KINDS = {
    "FillEffect": "fill", "PaintEffect": "paint", "LevelsEffect": "levels", "FilterEffect": "filter",
    "GeneratorEffect": "generator", "AnchorPointEffect": "anchor", "CompareMaskEffect": "compare_mask",
    "ColorSelectionEffect": "color_selection",
}


# -- the layer stack snapshot -----------------------------------------------------------


def _kind(node):
    name = getattr(node.get_type(), "name", str(node.get_type()))
    return _LAYER_KINDS.get(name) or _EFFECT_KINDS.get(name) or name


def _call(obj, method, *args):
    """``obj.method(*args)``, or ``None`` if this Painter has no such method."""
    function = getattr(obj, method, None)
    return None if function is None else function(*args)


def _source_url(node):
    """A generator's or filter's resource, version-less; ``None`` if it has none."""
    try:
        source = _call(node, "get_source")
        resource_id = getattr(source, "resource_id", None)
        if callable(resource_id):
            resource_id = resource_id()
        return versionless_url(resource_id.url()) if resource_id is not None else None
    except Exception:
        return None


def _mask(layer):
    """``None`` without a mask; ``"black"`` / ``"white"`` if this Painter tells its
    background, else ``"on"`` (the core then goes by the command clicked)."""
    if not _call(layer, "has_mask"):
        return None
    try:
        background = _call(layer, "get_mask_background")
    except Exception:
        background = None
    name = str(getattr(background, "name", background or "")).lower()
    return name if name in ("black", "white") else "on"


def _stack_id(stack):
    try:
        return f"{stack.material().name()}/{stack.name()}"
    except Exception:
        return str(stack)


def snapshot(ls, stack, layer_of):
    """The stack as ``core/recording.py`` reads it. ``layer_of(node)``: the layer a
    selected mask or effect belongs to."""
    try:
        channels = list(stack.all_channels())
    except Exception:
        channels = []
    nodes = []

    def add_effects(layer, uid, stack_name, method):
        for effect in _call(layer, method) or []:
            nodes.append({
                "uid": effect.uid(), "name": effect.get_name(), "kind": _kind(effect), "parent": uid,
                "stack": stack_name, "source": _source_url(effect),
            })

    def add_layer(layer, parent):
        uid = layer.uid()
        blend, opacity = {}, {}
        for channel in channels:
            try:
                blend[channel.name] = getattr(layer.get_blending_mode(channel), "name", None)
                opacity[channel.name] = float(layer.get_opacity(channel))
            except Exception:  # a channel this layer cannot have, or a folder without channels
                continue
        nodes.append({
            "uid": uid, "name": layer.get_name(), "kind": _kind(layer), "parent": parent, "stack": "layers",
            "mask": _mask(layer), "blend": blend, "opacity": opacity,
        })
        add_effects(layer, uid, "content", "content_effects")
        add_effects(layer, uid, "mask", "mask_effects")
        for child in _call(layer, "sub_layers") or []:
            add_layer(child, uid)

    for layer in ls.get_root_layer_nodes(stack):
        add_layer(layer, None)
    selected = ls.get_selected_nodes(stack)
    layer = layer_of(selected[0]) if selected else None
    return {"stack": _stack_id(stack), "selected": layer.uid() if layer is not None else None, "nodes": nodes}


# -- Painter's History -------------------------------------------------------------------


class HistoryWatch:
    """Calls ``callback(labels, index)`` at once and after every change of the History.
    Call it to stop. Raises ``LookupError`` if there is no History view."""

    def __init__(self, callback):
        self.callback = callback
        self._keep = []  # every wrapper found, for as long as the watch lives
        self._hooked = []  # (signal, slot)
        self.view = self._find()
        if self.view is None:
            raise LookupError("Painter's History view (objectName 'history') was not found")
        self._timer = QtCore.QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._report)
        self._hook()
        self._report()

    def _find(self):
        try:
            widgets = list(QtWidgets.QApplication.allWidgets())
        except Exception:
            log.exception("QApplication.allWidgets() failed")
            return None
        self._keep.append(widgets)
        for widget in widgets:
            try:
                if isinstance(widget, QtWidgets.QUndoView) and widget.objectName() == HISTORY_NAME:
                    return widget
            except RuntimeError:
                continue
        return None

    def _connect(self, signal, slot):
        signal.connect(slot)
        self._hooked.append((signal, slot))

    def _hook(self):
        view = self.view
        model = view.model()
        self._keep.append(model)
        later = self._timer.start
        for name in ("modelReset", "rowsInserted", "rowsRemoved", "dataChanged", "layoutChanged"):
            self._connect(getattr(model, name), lambda *args: later())
        selection = view.selectionModel()
        if selection is not None:
            self._keep.append(selection)
            self._connect(selection.currentChanged, lambda *args: later())
        stack = self._undo_stack()
        if stack is not None:
            self._keep.append(stack)
            self._connect(stack.indexChanged, lambda *args: later())
        group = _call(view, "group")
        if group is not None:
            self._keep.append(group)
            self._connect(group.indexChanged, lambda *args: later())
            self._connect(group.activeStackChanged, lambda *args: later())
        log.info("Watching Painter's History (%s)", "its undo stack" if stack is not None else "its rows")

    def _undo_stack(self):
        stack = _call(self.view, "stack")
        if stack is None:
            group = _call(self.view, "group")
            stack = _call(group, "activeStack") if group is not None else None
        return stack

    def read(self):
        """``(labels, index)``: the commands' texts, oldest first, and how many are done."""
        if not valid(self.view):
            self.view = self._find()
            if self.view is None:
                raise LookupError("Painter's History view is gone")
        stack = self._undo_stack()
        if stack is not None:
            return [stack.text(i) for i in range(stack.count())], stack.index()
        # Qt's QUndoModel: row 0 is "<empty>", row n the n-th command; the current row
        # is how many are done.
        model = self.view.model()
        rows = model.rowCount()
        labels = [str(model.index(row, 0).data() or "") for row in range(1, rows)]
        current = self.view.currentIndex().row()
        return labels, current if current >= 0 else len(labels)

    def _report(self):
        try:
            labels, index = self.read()
        except Exception:
            log.exception("Reading Painter's History failed")
            return
        self.callback(labels, index)

    def __call__(self):
        self._timer.stop()
        for signal, slot in self._hooked:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                log.debug("Could not disconnect a History signal", exc_info=True)
        self._hooked = []
        self._keep = []


# -- drops onto Painter --------------------------------------------------------------------


class DropWatch(QtCore.QObject):
    """Calls ``callback(urls)`` for every drop of resources onto Painter (not onto the
    Panel). Call it to stop."""

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self._app = QtWidgets.QApplication.instance()
        if self._app is not None:
            self._app.installEventFilter(self)

    def eventFilter(self, obj, event):
        try:
            if event.type() == QtCore.QEvent.Type.Drop and not obj.objectName().startswith(OWN_PREFIX):
                mime = event.mimeData()
                if mime is not None and mime.hasFormat("text/uri-list"):
                    urls = resource_urls_from_drop(bytes(mime.data("text/uri-list")).decode("utf-8", "replace"))
                    if urls:
                        log.debug("Dropped onto Painter: %s", urls)
                        self.callback(urls)
        except Exception:
            log.exception("Reading a drop onto Painter failed")
        return False

    def __call__(self):
        if self._app is not None:
            self._app.removeEventFilter(self)
            self._app = None
