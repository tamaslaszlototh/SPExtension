"""Anchor points (#35): the anchor point Step's name, and an anchor point as a Fill
channel's source, referred to by name: the schema, preflight and replay."""

import pytest

from shelfplus_app.adapter.fake import FakeAdapter, FakeEffect, FakeLayer
from shelfplus_app.core.layout import step_problem
from shelfplus_app.core.steps import FAILED
from shelfplus_app.core.workflow import ANCHOR_POINT_NAME, run_workflow

EDGES = {"anchor": "Edges"}


def anchor(name=None, target="layer"):
    step = {"type": "add_effect", "effect": "anchor", "target": target}
    if name is not None:
        step["name"] = name
    return step


def fill_layer(**extra):
    return {"type": "add_layer", "layer": "fill", **extra}


def with_anchor(layer, name):
    node = FakeEffect("layer", "anchor", name=name)
    layer.effects.append(("layer", "anchor", None))
    layer.effect_nodes.append(node)
    return node


@pytest.fixture
def adapter():
    adapter = FakeAdapter()
    adapter.project_is_open = True
    base = FakeLayer("Base")
    adapter.stack.layers = [base]
    adapter.stack.selected = base
    return adapter


def run(adapter, steps):
    results = []
    run_workflow(adapter, steps, results.append, name="Anchors")
    (result,) = results
    return result


class TestSchema:
    def test_an_anchor_step_may_have_a_name(self):
        assert step_problem(anchor("Edges")) is None
        assert step_problem(anchor()) is None
        assert step_problem(anchor("")) == "Step 'add_effect' has an invalid 'name'"

    def test_only_an_anchor_point_has_a_name(self):
        step = {"type": "add_effect", "effect": "levels", "target": "mask", "name": "Edges"}

        assert step_problem(step) == "Step 'add_effect' (levels) cannot have 'name'"

    def test_an_anchor_is_a_source_of_a_fill_layer_a_fill_effect_and_a_mask_fill(self):
        assert step_problem(fill_layer(sources={"Height": EDGES})) is None
        assert step_problem({"type": "add_effect", "effect": "fill", "target": "layer", "sources": {"BaseColor": EDGES}}) is None
        assert step_problem({"type": "add_effect", "effect": "fill", "target": "mask", "source": EDGES}) is None

    @pytest.mark.parametrize("source", [{"anchor": ""}, {"anchor": 3}, {"anchor": "Edges", "value": 1}])
    def test_an_anchor_source_needs_a_name_and_nothing_else(self, source):
        assert step_problem(fill_layer(sources={"Height": source})) == "Step 'add_layer' has an invalid 'sources'"


class TestAnchorStep:
    def test_replay_names_the_anchor(self, adapter):
        assert run(adapter, [anchor("Edges")]).ok

        (node,) = adapter.stack.layers[0].effect_nodes
        assert node.name == "Edges"

    def test_without_a_name_it_is_painters_default(self, adapter):
        assert run(adapter, [anchor()]).ok

        assert adapter.stack.layers[0].effect_nodes[0].name == ANCHOR_POINT_NAME

    def test_preflight_refuses_a_name_already_in_the_stack(self, adapter):
        other = FakeLayer("Other")
        adapter.stack.layers.append(other)
        with_anchor(other, "Edges")

        result = run(adapter, [anchor("Edges")])

        assert result.state == FAILED
        assert result.message == "“Anchors” did not start: Step 1 (Add anchor point to the layer): An anchor point named “Edges” already exists."
        assert adapter.stack.scopes == []

    def test_preflight_refuses_the_same_name_twice_in_one_workflow(self, adapter):
        result = run(adapter, [anchor("Edges"), {"type": "add_mask", "background": "black"}, anchor("Edges", "mask")])

        assert result.state == FAILED and "Step 3" in result.message and "already exists" in result.message


class TestAnchorSource:
    def test_replay_finds_the_anchor_by_name_anywhere_in_the_stack(self, adapter):
        folder = FakeLayer("Folder", "folder", [FakeLayer("Inside")])
        adapter.stack.layers.append(folder)
        with_anchor(folder.children[0], "Edges")

        assert run(adapter, [fill_layer(channels=["Height"], sources={"Height": EDGES})]).ok

        assert adapter.stack.layers[0].sources == {"Height": EDGES}

    def test_a_mask_fill_takes_an_anchor(self, adapter):
        with_anchor(adapter.stack.layers[0], "Edges")
        steps = [
            {"type": "add_mask", "background": "black"},
            {"type": "add_effect", "effect": "fill", "target": "mask", "source": EDGES},
        ]

        assert run(adapter, steps).ok

        assert adapter.stack.layers[0].effect_nodes[-1].source == EDGES

    def test_preflight_refuses_a_missing_anchor(self, adapter):
        result = run(adapter, [fill_layer(sources={"Height": EDGES})])

        assert result.state == FAILED
        assert result.message == "“Anchors” did not start: Step 1 (Add Fill layer): No anchor point named “Edges”."
        assert adapter.stack.scopes == []

    def test_preflight_refuses_several_anchors_with_the_name(self, adapter):
        with_anchor(adapter.stack.layers[0], "Edges")
        other = FakeLayer("Other")
        adapter.stack.layers.append(other)
        with_anchor(other, "Edges")

        result = run(adapter, [fill_layer(sources={"Height": EDGES})])

        assert result.state == FAILED and result.message.endswith("Several anchor points named “Edges”.")

    def test_an_anchor_made_earlier_in_the_workflow_counts_as_found(self, adapter):
        steps = [anchor("Edges"), fill_layer(channels=["Height"], sources={"Height": EDGES})]

        assert run(adapter, steps).ok

        assert adapter.stack.layers[0].sources == {"Height": EDGES}

    def test_an_anchor_made_later_in_the_workflow_does_not_count(self, adapter):
        steps = [fill_layer(sources={"Height": EDGES}), anchor("Edges")]

        assert run(adapter, steps).message.endswith("No anchor point named “Edges”.")

    def test_the_default_name_of_an_earlier_anchor_counts(self, adapter):
        steps = [anchor(), fill_layer(channels=["Height"], sources={"Height": {"anchor": ANCHOR_POINT_NAME}})]

        assert run(adapter, steps).ok
