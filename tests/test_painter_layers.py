"""The real adapter's layer-stack calls against stand-in ``substance_painter`` modules that
have only the names the real API has where they live (``get_active_stack`` is in
``textureset``, not ``layerstack``: v0.5.0 failed on Painter 11.1 because of that)."""

import sys
import types

import pytest


class Node:
    def __init__(self, name, kind="FillLayer", children=(), parent=None):
        self.name, self.kind, self.children, self.parent = name, kind, list(children), parent
        for child in self.children:
            child.parent = self

    def get_name(self):
        return self.name

    def get_type(self):
        return self.kind

    def get_parent(self):
        return self.parent

    def sub_layers(self):
        return self.children


STACK = object()


@pytest.fixture
def painter(monkeypatch):
    inner = Node("Inner")
    folder = Node("Folder", "GroupLayer", [inner])
    mask = Node("mask", "Mask")
    base = Node("Base", children=[])
    mask.parent = base
    calls = []

    def stack_only(stack):
        assert stack is STACK
        return stack

    ls = types.ModuleType("substance_painter.layerstack")
    ls.NodeType = types.SimpleNamespace(FillLayer="FillLayer", PaintLayer="PaintLayer", GroupLayer="GroupLayer")
    ls.get_selected_nodes = lambda stack: [stack_only(stack) and mask]
    ls.get_root_layer_nodes = lambda stack: [stack_only(stack) and folder, base]
    ls.InsertPosition = types.SimpleNamespace(
        from_textureset_stack=lambda stack: ("top", stack_only(stack)),
        above_node=lambda node: ("above", node),
    )
    ls.insert_fill = lambda position: (calls.append(position), Node("Fill"))[1]
    ls.insert_paint = lambda position: (calls.append(position), Node("Paint", "PaintLayer"))[1]
    ls.insert_group = lambda position: (calls.append(position), Node("Folder", "GroupLayer"))[1]
    ts = types.ModuleType("substance_painter.textureset")
    ts.get_active_stack = lambda: STACK
    package = types.ModuleType("substance_painter")
    for name, module in (("layerstack", ls), ("textureset", ts), ("application", types.ModuleType("a")), ("ui", types.ModuleType("u"))):
        setattr(package, name, module)
        monkeypatch.setitem(sys.modules, f"substance_painter.{name}", module)
    monkeypatch.setitem(sys.modules, "substance_painter", package)
    monkeypatch.delitem(sys.modules, "shelfplus_app.adapter.painter", raising=False)
    from shelfplus_app.adapter.painter import PainterAdapter

    adapter = PainterAdapter.__new__(PainterAdapter)  # no Assets window or QActions needed
    return adapter, calls, {"inner": inner, "folder": folder, "base": base}


def test_selected_mask_means_its_layer(painter):
    adapter, _, nodes = painter

    assert adapter.selected_layer() is nodes["base"]


def test_insert_on_top_of_the_active_stack(painter):
    adapter, calls, _ = painter

    adapter.insert_layer("fill")

    assert calls == [("top", STACK)]


def test_find_layers_includes_folder_contents(painter):
    adapter, _, nodes = painter

    assert adapter.find_layers("Inner") == [nodes["inner"]]
    assert adapter.find_layers("Folder") == [nodes["folder"]]
