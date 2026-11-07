"""The real adapter's Recording parts: the layer stack snapshot against a stand-in
``layerstack``, and the History watch against a real ``QUndoView`` (offscreen)."""

import os
import types

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6 import QtCore, QtGui  # noqa: E402

from shelfplus_app.adapter.recording import DropWatch, HistoryWatch, snapshot  # noqa: E402
from shelfplus_app.core.recording import diff, MASK  # noqa: E402

_uids = iter(range(100, 1000))


class Enum:
    def __init__(self, name):
        self.name = name


class Node:
    def __init__(self, name, kind="FillLayer", children=(), content=(), mask=(), has_mask=False, source=None):
        self._uid = next(_uids)
        self.name, self.kind = name, Enum(kind)
        self.children, self.content, self.masks = list(children), list(content), list(mask)
        self.mask_on, self.source = has_mask, source
        self.blend = {"BaseColor": "Normal", "Roughness": "Normal"}
        self.opacity = {"BaseColor": 1.0, "Roughness": 1.0}

    def uid(self):
        return self._uid

    def get_name(self):
        return self.name

    def get_type(self):
        return self.kind

    def has_mask(self):
        return self.mask_on

    def sub_layers(self):
        return self.children

    def content_effects(self):
        return self.content

    def mask_effects(self):
        return self.masks

    def get_blending_mode(self, channel):
        return Enum(self.blend[channel.name])

    def get_opacity(self, channel):
        return self.opacity[channel.name]

    def get_source(self):
        if self.source is None:
            return None
        return types.SimpleNamespace(resource_id=types.SimpleNamespace(url=lambda: self.source + "?version=abc"))


class Stack:
    def all_channels(self):
        return {Enum("BaseColor"): None, Enum("Roughness"): None}

    def material(self):
        return types.SimpleNamespace(name=lambda: "coat")

    def name(self):
        return ""


def painter(layers, selected):
    ls = types.SimpleNamespace(get_root_layer_nodes=lambda stack: layers, get_selected_nodes=lambda stack: selected)
    return ls


def test_the_snapshot_lists_layers_effects_and_their_settings():
    dirt = Node("Dirt", "GeneratorEffect", source="resource://starter_assets/Dirt")
    levels = Node("Levels", "LevelsEffect")
    fill = Node("Fill layer 1", content=[levels], mask=[dirt], has_mask=True)
    fill.opacity["BaseColor"] = 0.5
    inner = Node("Inner", "PaintLayer")
    folder = Node("Folder", "GroupLayer", children=[inner])
    ls = painter([fill, folder], [dirt])

    snap = snapshot(ls, Stack(), lambda node: fill)

    assert snap["stack"] == "coat/" and snap["selected"] == fill.uid()
    by_name = {n["name"]: n for n in snap["nodes"]}
    assert [n["name"] for n in snap["nodes"]] == ["Fill layer 1", "Levels", "Dirt", "Folder", "Inner"]
    assert {k: v for k, v in by_name["Fill layer 1"].items() if k not in ("channels", "content")} == {
        "uid": fill.uid(), "name": "Fill layer 1", "kind": "fill", "parent": None, "stack": "layers", "mask": "on",
        "blend": {"BaseColor": "Normal", "Roughness": "Normal"}, "opacity": {"BaseColor": 0.5, "Roughness": 1.0},
    }
    assert by_name["Dirt"]["stack"] == "mask" and by_name["Dirt"]["source"] == "resource://starter_assets/Dirt"
    assert by_name["Levels"]["stack"] == "content" and by_name["Levels"]["kind"] == "levels"
    assert by_name["Inner"]["parent"] == folder.uid() and by_name["Folder"]["kind"] == "folder"


def test_two_snapshots_diff_into_the_change_made():
    fill = Node("Fill layer 1")
    ls = painter([fill], [])
    before = snapshot(ls, Stack(), lambda node: node)
    fill.mask_on = True

    (change,) = diff(before, snapshot(ls, Stack(), lambda node: node))

    assert change.what == MASK and change.new == "on"


# -- the History ---------------------------------------------------------------------


@pytest.fixture
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def history(qt_app):
    stack = QtGui.QUndoStack()
    view = QtWidgets.QUndoView(stack)
    view.setObjectName("history")
    yield stack
    view.setObjectName("")  # deleteLater() alone may leave it in allWidgets() for the next test
    view.deleteLater()
    qt_app.processEvents()


def command(text):
    cmd = QtGui.QUndoCommand(text)
    return cmd


def test_the_history_watch_reports_rows_and_index_once_per_change(qt_app, history):
    readings = []
    history.push(command("Open project"))

    stop = HistoryWatch(lambda labels, index: readings.append((tuple(labels), index)))
    assert readings == [(("Open project",), 1)]

    history.push(command("Add fill layer"))
    qt_app.processEvents()
    history.undo()
    qt_app.processEvents()

    assert readings[1:] == [(("Open project", "Add fill layer"), 2), (("Open project", "Add fill layer"), 1)]
    stop()
    history.redo()
    qt_app.processEvents()
    assert len(readings) == 3


def test_without_a_history_view_the_watch_cannot_start(qt_app):
    with pytest.raises(LookupError):
        HistoryWatch(lambda labels, index: None)


# -- drops ----------------------------------------------------------------------------


def test_a_resource_dropped_onto_painter_is_reported(qt_app):
    """The filter itself: Qt delivers a real drop only at the end of a real drag."""
    target = QtWidgets.QWidget()
    target.setObjectName("LayerStack")
    own = QtWidgets.QWidget()
    own.setObjectName("ShelfPlusPanel")
    seen = []
    watch = DropWatch(seen.append)
    mime = QtCore.QMimeData()
    mime.setData("text/uri-list", b"resource://starter_assets/Rust%20Iron?version=abc\r\n")
    event = QtGui.QDropEvent(QtCore.QPointF(1, 1), QtCore.Qt.DropAction.CopyAction, mime,
                             QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)

    assert watch.eventFilter(target, event) is False  # it only looks
    watch.eventFilter(own, event)
    watch()

    assert seen == [["resource://starter_assets/Rust Iron"]]
    target.deleteLater()
    own.deleteLater()


# -- a Fill's channels and content --------------------------------------------------------


class Colour:
    """``colormanagement.Color`` as far as the snapshot reads it."""

    def __init__(self, linear, srgb=None):
        self.value = tuple(linear)
        if srgb is not None:
            self.sRGB = tuple(srgb)


class Uniform:
    def __init__(self, colour):
        self._colour = colour

    def get_color(self):
        return self._colour


class Texture:
    def __init__(self, url):
        self.resource_id = types.SimpleNamespace(url=lambda: url + "?version=1")


class FillNode(Node):
    def __init__(self, name, kind="FillLayer", sources=None, material=None, mask_source=None, **kw):
        super().__init__(name, kind, **kw)
        self.active_channels = {Enum("Roughness"), Enum("BaseColor")}
        self.sources, self.material, self.mask_source = sources or {}, material, mask_source
        self.source_mode = Enum("Material" if material else "Split")

    def get_source(self, channel=None):
        if channel is None:
            return self.mask_source
        return self.sources[channel.name]

    def get_material_source(self):
        return Texture(self.material)


def test_a_fill_layers_channels_and_sources_are_read_in_the_texture_sets_order():
    fill = FillNode("Fill layer 1", sources={
        "BaseColor": Uniform(Colour((0.7, 0.01, 0.01), srgb=(0.878, 0.063, 0.063))),
        "Roughness": Uniform(Colour((0.9, 0.9, 0.9))),
    })

    (node,) = snapshot(painter([fill], []), Stack(), lambda n: n)["nodes"]

    assert node["channels"] == ["BaseColor", "Roughness"]
    assert node["content"] == {"sources": {"BaseColor": {"color": "#e01010"}, "Roughness": {"value": 0.9}}}


def test_a_fill_layer_with_one_material_and_a_texture_channel():
    material = FillNode("Fill layer 1", material="resource://starter_assets/Rust Iron")
    texture = FillNode("Fill layer 2", sources={
        "BaseColor": Texture("resource://starter_assets/Clouds 1"),
        "Roughness": object(),  # a kind of source the snapshot cannot read: left out
    })

    nodes = snapshot(painter([material, texture], []), Stack(), lambda n: n)["nodes"]

    assert nodes[0]["content"] == {"material": "resource://starter_assets/Rust Iron"}
    assert nodes[1]["content"] == {"sources": {"BaseColor": {"resource": "resource://starter_assets/Clouds 1"}}}


def test_a_paint_layer_has_channels_only_and_a_mask_fill_its_grey_value():
    mask_fill = FillNode("Fill", "FillEffect", mask_source=Uniform(Colour((0.3, 0.3, 0.3))))
    paint = FillNode("Layer 1", "PaintLayer", mask=[mask_fill], has_mask=True)

    nodes = snapshot(painter([paint], []), Stack(), lambda n: n)["nodes"]

    assert nodes[0]["channels"] == ["BaseColor", "Roughness"] and "content" not in nodes[0]
    assert nodes[1]["content"] == {"source": {"value": 0.3}} and nodes[1]["source"] is None
