"""The real adapter's layer-stack calls against stand-in ``substance_painter`` modules that
have only the names the real API has where they live (``get_active_stack`` is in
``textureset``, not ``layerstack``: v0.5.0 failed on Painter 11.1 because of that)."""

import sys
import types

import pytest


class Node:
    def __init__(self, name, kind="FillLayer", children=(), parent=None):
        self.name, self.kind, self.children, self.parent = name, kind, list(children), parent
        self.mask = None
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

    def has_mask(self):
        return self.mask is not None

    def add_mask(self, background):
        self.mask = background


class Resource:
    """``substance_painter.resource.Resource`` as far as the adapter uses it."""

    def __init__(self, url, name):
        self.url, self.name = url, name

    def identifier(self):
        return types.SimpleNamespace(url=lambda: self.url)

    def gui_name(self):
        return self.name


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
    ls.InsertPosition.inside_node = lambda node, stack: ("inside", node, stack)
    ls.NodeStack = types.SimpleNamespace(Content="Content", Mask="Mask", Substack="Substack")
    ls.MaskBackground = types.SimpleNamespace(Black="Black", White="White")
    ls.SelectionType = types.SimpleNamespace(Content="Content", Mask="Mask", Properties="Properties")
    ls.NodeType.PaintEffect = "PaintEffect"
    selection = {"nodes": [mask], "types": {}}
    ls.get_selected_nodes = lambda stack: stack_only(stack) and selection["nodes"]
    ls.get_selection_type = lambda node: selection["types"].get(id(node), "Content")
    ls.set_selected_nodes = lambda nodes: selection.update(nodes=list(nodes))
    ls.set_selection_type = lambda node, kind: selection["types"].__setitem__(id(node), kind)
    project = types.ModuleType("substance_painter.project")
    project.is_open = lambda: True

    def effect(kind):
        return lambda position, *args: (calls.append((kind, position, *args)), Node(kind, kind))[1]

    ls.insert_generator_effect = effect("generator")
    ls.insert_filter_effect = effect("filter")
    ls.insert_levels_effect = effect("levels")
    ls.insert_anchor_point_effect = effect("anchor")
    ls.insert_smart_mask = effect("smart mask")
    ls.insert_smart_material = lambda position, resource_id: (
        calls.append(("smart material", position, resource_id)),
        Node("Rust", "GroupLayer"),
    )[1]
    res = types.ModuleType("substance_painter.resource")
    resources = {"resource://starter_assets/Dirt": Resource("resource://starter_assets/Dirt?version=1", "Dirt")}
    res.ResourceID = types.SimpleNamespace(from_url=lambda url: url)
    res.Resource = types.SimpleNamespace(retrieve=lambda rid: [resources[rid]] if rid in resources else [])
    ts = types.ModuleType("substance_painter.textureset")
    ts.get_active_stack = lambda: STACK
    package = types.ModuleType("substance_painter")
    for name, module in (("layerstack", ls), ("textureset", ts), ("resource", res), ("project", project), ("application", types.ModuleType("a")), ("ui", types.ModuleType("u"))):
        setattr(package, name, module)
        monkeypatch.setitem(sys.modules, f"substance_painter.{name}", module)
    monkeypatch.setitem(sys.modules, "substance_painter", package)
    monkeypatch.delitem(sys.modules, "shelfplus_app.adapter.painter", raising=False)
    from shelfplus_app.adapter.painter import PainterAdapter

    adapter = PainterAdapter.__new__(PainterAdapter)  # no Assets window or QActions needed
    adapter.selection = selection  # for the tests: what Painter has selected
    return adapter, calls, {"inner": inner, "folder": folder, "base": base, "mask": mask}


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


DIRT = "resource://starter_assets/Dirt"


def test_effect_on_the_mask_goes_inside_the_mask_stack(painter):
    adapter, calls, nodes = painter
    base = nodes["base"]
    base.mask = "Black"

    assert adapter.has_mask(base)
    adapter.insert_effect(base, "mask", "generator", resource=DIRT)
    adapter.insert_effect(base, "mask", "levels")

    (kind, position, rid), levels = calls
    assert (kind, position) == ("generator", ("inside", base, "Mask"))
    assert rid.url() == "resource://starter_assets/Dirt?version=1"
    assert levels == ("levels", ("inside", base, "Mask"))


def test_effect_on_the_layer_goes_inside_the_content_stack(painter):
    adapter, calls, nodes = painter
    base = nodes["base"]

    adapter.insert_effect(base, "layer", "filter", resource=DIRT)
    adapter.insert_effect(base, "layer", "anchor")

    assert calls[0][:2] == ("filter", ("inside", base, "Content"))
    assert calls[1] == ("anchor", ("inside", base, "Content"), "Anchor point")


def test_an_unknown_resource_at_run_time(painter):
    adapter, calls, nodes = painter

    with pytest.raises(ValueError, match="not available on this machine"):
        adapter.insert_effect(nodes["base"], "layer", "filter", resource="resource://x/Gone")
    assert calls == []


def test_smart_material_above_a_layer_or_on_top(painter):
    adapter, calls, nodes = painter

    adapter.insert_smart_material(DIRT, above=nodes["base"])
    adapter.insert_smart_material(DIRT)

    assert [c[:2] for c in calls] == [("smart material", ("above", nodes["base"])), ("smart material", ("top", STACK))]


def test_smart_mask_adds_a_black_mask_only_if_there_is_none(painter):
    adapter, calls, nodes = painter
    base, inner = nodes["base"], nodes["inner"]
    inner.mask = "White"

    adapter.insert_smart_mask(base, DIRT)
    adapter.insert_smart_mask(inner, DIRT)

    assert base.mask == "Black" and inner.mask == "White"
    assert [c[:2] for c in calls] == [("smart mask", ("inside", base, "Mask")), ("smart mask", ("inside", inner, "Mask"))]


def select(adapter, node, part="Content"):
    adapter.selection["nodes"] = [node]
    adapter.selection["types"][id(node)] = part


def test_a_fill_layer_or_folder_itself_cannot_be_painted_on(painter):
    adapter, _, nodes = painter
    for name in ("base", "folder"):
        select(adapter, nodes[name])
        assert adapter.selection_paintable() is False


def test_a_paint_layer_or_a_mask_can_be_painted_on(painter):
    adapter, _, nodes = painter
    select(adapter, Node("Paint", "PaintLayer"))
    assert adapter.selection_paintable() is True
    select(adapter, nodes["base"], "Mask")
    assert adapter.selection_paintable() is True
    select(adapter, Node("Paint effect", "PaintEffect"))
    assert adapter.selection_paintable() is True


def test_another_effect_cannot_be_painted_on(painter):
    adapter, _, _ = painter  # the fixture selects a "Mask"-typed effect node under Base

    assert adapter.selection_paintable() is False


def test_nothing_selected_cannot_tell(painter):
    adapter, _, _ = painter
    adapter.selection["nodes"] = []

    assert adapter.selection_paintable() is None


def test_select_mask_selects_the_layer_and_its_mask(painter):
    adapter, _, nodes = painter

    adapter.select_mask(nodes["base"])

    assert adapter.selection["nodes"] == [nodes["base"]] and adapter.selection_paintable() is True
