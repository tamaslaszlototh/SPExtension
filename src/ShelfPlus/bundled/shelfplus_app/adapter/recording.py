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
from ..core.channels import is_colour
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


def _resource_url(source):
    """The version-less ``resource://`` URL of a Painter source, or ``None``."""
    resource_id = getattr(source, "resource_id", None)
    if callable(resource_id):
        resource_id = resource_id()
    return versionless_url(resource_id.url()) if resource_id is not None else None


def _source_url(node):
    """A generator's or filter's resource, version-less; ``None`` if it has none."""
    try:
        return _resource_url(_call(node, "get_source"))
    except Exception:
        return None


# -- a Fill's channels and content ----------------------------------------------------

_unreadable = set()  # what has been logged once: unreadable source types, and "colour"


def _value(obj, *names):
    """The first of ``obj``'s attributes or methods called ``names`` that gives something."""
    for name in names:
        value = getattr(obj, name, None)
        if callable(value):
            try:
                value = value()
            except Exception:
                value = None
        if value is not None:
            return value
    return None


def _rgb(colour, srgb):
    """``(r, g, b)`` 0..1 of a ``colormanagement.Color``: as a colour picker shows it
    (sRGB) for a colour channel, the raw value for a grey one (the runner writes a
    grey value unconverted, a colour converted from sRGB)."""
    names = ("sRGB", "srgb", "to_srgb", "value") if srgb else ("value", "linear")
    value = _value(colour, *names)
    if value is None:
        value = colour
    try:
        values = [float(v) for v in value][:3]
    except TypeError:
        values = [float(_value(colour, n)) for n in ("r", "g", "b")]
    return values if len(values) == 3 else values * 3


def _anchor_name(source):
    """The name of the anchor point a source refers to, or ``None`` if it is not an anchor
    point source. The first one read is logged with what the source offers: Painter's API
    for it could not be checked without Painter (Copy diagnostics shows the log)."""
    kind = type(source).__name__
    named_anchor = "anchor" in kind.lower()
    getters = ("get_anchor_point", "anchor_point", "get_anchor", "anchor") + (("get_node", "node") if named_anchor else ())
    anchor = _value(source, *getters)
    if anchor is None and not named_anchor:
        return None
    name = _value(anchor, "get_name", "name") if anchor is not None else None
    if "anchor" not in _unreadable:
        _unreadable.add("anchor")
        public = [a for a in dir(source) if not a.startswith("_")]
        log.info("Recording: an anchor point source (%s, offers %s) reads as %r named %r", kind, public, anchor, name)
    return str(name) if name else None


def _read_source(node, channel):
    """One channel's source (``channel`` a ChannelType; ``None`` for a mask's Fill) in a
    Step's form: ``{"resource": url}``, ``{"color": "#rrggbb"}``, ``{"value": n}`` or
    ``{"anchor": name}``; ``None`` if it cannot be read (logged once per kind of source)."""
    try:
        source = node.get_source(channel) if channel is not None else node.get_source()
    except TypeError:
        source = node.get_source(None)
    url = _resource_url(source)
    if url:
        return {"resource": url}
    anchor = _anchor_name(source)
    if anchor:
        return {"anchor": anchor}
    colour = _value(source, "get_color", "color")
    if colour is None:
        kind = type(source).__name__
        if kind not in _unreadable:
            _unreadable.add(kind)
            public = [a for a in dir(source) if not a.startswith("_")]
            log.info("Recording: cannot read a %s source (%r, offers %s); it is left out", kind, source, public)
        return None
    name = getattr(channel, "name", None)
    if "colour" not in _unreadable:  # once: how this Painter's Color reads (for Copy diagnostics)
        _unreadable.add("colour")
        log.info(
            "Recording: a uniform colour (%s) reads as value=%r sRGB=%r (%s)",
            name, _value(colour, "value"), _value(colour, "sRGB", "srgb", "to_srgb"), type(colour).__name__,
        )
    if name is not None and is_colour(name):
        r, g, b = _rgb(colour, srgb=True)
        return {"color": "#{:02x}{:02x}{:02x}".format(*(round(min(max(v, 0), 1) * 255) for v in (r, g, b)))}
    return {"value": round(_rgb(colour, srgb=False)[0], 3)}


def _active_channels(node, order):
    """The ChannelType objects switched on, in the texture set's order."""
    active = list(_value(node, "active_channels") or [])
    names = {getattr(c, "name", str(c)): c for c in active}
    ordered = [names.pop(n) for n in order if n in names]
    return ordered + [names[n] for n in sorted(names)]


def _content(node, channels, on_mask):
    """A Fill layer's or Fill effect's content in a Step's form."""
    if on_mask:
        source = _read_source(node, None)
        return {"source": source} if source else {}
    mode = _value(node, "source_mode", "get_source_mode")
    if mode is not None and "material" in str(getattr(mode, "name", mode)).lower():
        url = _resource_url(_call(node, "get_material_source"))
        return {"material": url} if url else {}
    sources = {}
    for channel in channels:
        try:
            source = _read_source(node, channel)
        except Exception:
            log.debug("Recording: the %s source could not be read", getattr(channel, "name", channel), exc_info=True)
            continue
        if source:
            sources[channel.name] = source
    return {"sources": sources}


def _fill_details(node, kind, order, on_mask=False):
    """``channels`` and ``content`` of a Fill or Paint layer or a Fill effect (only what
    it has); never raises, so a Painter that cannot tell just records less."""
    details = {}
    try:
        channels = _active_channels(node, order) if not on_mask else []
        if not on_mask:
            details["channels"] = [c.name for c in channels] or None
        if kind == "fill":
            details["content"] = _content(node, channels, on_mask)
    except Exception:
        log.debug("Recording: the channels or content of %r could not be read", node, exc_info=True)
    return details


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
    order = [c.name for c in channels]
    nodes = []

    def add_effects(layer, uid, stack_name, method):
        for effect in _call(layer, method) or []:
            kind = _kind(effect)
            entry = {
                "uid": effect.uid(), "name": effect.get_name(), "kind": kind, "parent": uid, "stack": stack_name,
                "source": _source_url(effect) if kind in ("generator", "filter") else None,
            }
            if kind == "fill":
                entry.update(_fill_details(effect, kind, order, on_mask=stack_name == "mask"))
            nodes.append(entry)

    def add_layer(layer, parent):
        uid = layer.uid()
        blend, opacity = {}, {}
        for channel in channels:
            try:
                blend[channel.name] = getattr(layer.get_blending_mode(channel), "name", None)
                opacity[channel.name] = float(layer.get_opacity(channel))
            except Exception:  # a channel this layer cannot have, or a folder without channels
                continue
        kind = _kind(layer)
        entry = {
            "uid": uid, "name": layer.get_name(), "kind": kind, "parent": parent, "stack": "layers",
            "mask": _mask(layer), "blend": blend, "opacity": opacity,
        }
        if kind in ("fill", "paint"):
            entry.update(_fill_details(layer, kind, order))
        nodes.append(entry)
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
