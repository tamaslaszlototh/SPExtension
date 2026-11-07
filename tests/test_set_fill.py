"""``set_fill`` ("Fill content", #35): the channels and content of an existing layer, the
Current layer: the schema, preflight and replay."""

import pytest

from shelfplus_app.adapter.fake import FakeAdapter, FakeEffect, FakeLayer, FakeResource
from shelfplus_app.core.layout import step_problem
from shelfplus_app.core.steps import FAILED
from shelfplus_app.core.workflow import run_workflow, step_label

RUST = "resource://starter_assets/Rust"
EDGES = {"anchor": "Edges"}


def set_fill(**extra):
    return {"type": "set_fill", **extra}


@pytest.fixture
def adapter():
    adapter = FakeAdapter()
    adapter.project_is_open = True
    layer = FakeLayer("Old fill", "fill")
    layer.channels = ["BaseColor", "Roughness"]
    layer.sources = {"BaseColor": {"color": "#808080"}, "Roughness": {"value": 0.3}}
    adapter.stack.layers = [layer, FakeLayer("Paint", "paint")]
    adapter.stack.selected = layer
    adapter.add_resource(FakeResource(RUST, "Rust", is_brush=False))
    return adapter


def run(adapter, steps):
    results = []
    run_workflow(adapter, steps, results.append, name="Fill")
    (result,) = results
    return result


class TestSchema:
    def test_valid_forms(self):
        assert step_problem(set_fill(channels_on=["Height"], channels_off=["Roughness"])) is None
        assert step_problem(set_fill(sources={"BaseColor": EDGES, "Height": {"value": 0.5}})) is None
        assert step_problem(set_fill(material={"resource": RUST, "resource_name": "Rust"})) is None

    @pytest.mark.parametrize(
        "extra, problem",
        [
            ({}, "Step 'set_fill' changes nothing"),
            ({"channels_on": []}, "Step 'set_fill' has an invalid 'channels_on'"),
            ({"channels_on": ["Height"], "channels_off": ["Height"]}, "Step 'set_fill' switches 'Height' both on and off"),
            ({"material": {"resource": RUST}, "sources": {"Height": {"value": 0}}}, "Step 'set_fill' has both 'material' and 'sources'"),
            ({"channels_off": ["Height"], "sources": {"Height": {"value": 0}}}, "Step 'set_fill' sets 'Height', which it switches off"),
            ({"source": {"value": 1}}, "Step 'set_fill' cannot have 'source'"),
        ],
    )
    def test_problems(self, extra, problem):
        assert step_problem(set_fill(**extra)) == problem

    def test_its_label(self):
        assert step_label(set_fill(channels_on=["Height"])) == "Set Fill content"


class TestReplay:
    def test_it_sets_sources_on_the_current_fill_layer(self, adapter):
        assert run(adapter, [set_fill(sources={"BaseColor": {"color": "#ff0000"}})]).ok

        layer = adapter.stack.layers[0]
        assert layer.sources == {"BaseColor": {"color": "#ff0000"}, "Roughness": {"value": 0.3}}
        assert layer.channels == ["BaseColor", "Roughness"]
        assert adapter.stack.scopes == ["Shelf+: Fill"]

    def test_it_sets_one_material(self, adapter):
        assert run(adapter, [set_fill(material={"resource": RUST})]).ok

        assert adapter.stack.layers[0].material == RUST

    def test_it_switches_only_the_channels_it_names(self, adapter):
        assert run(adapter, [set_fill(channels_on=["Height"], channels_off=["Roughness"])]).ok

        assert adapter.stack.layers[0].channels == ["BaseColor", "Height"]

    def test_a_source_on_a_channel_that_is_off_switches_it_on(self, adapter):
        assert run(adapter, [set_fill(sources={"Metallic": {"value": 1}})]).ok

        layer = adapter.stack.layers[0]
        assert layer.channels == ["BaseColor", "Roughness", "Metallic"]
        assert layer.sources["Metallic"] == {"value": 1}

    def test_switching_channels_works_on_a_paint_layer(self, adapter):
        paint = adapter.stack.layers[1]
        paint.channels = ["BaseColor"]
        adapter.stack.selected = paint

        assert run(adapter, [set_fill(channels_on=["Height"])]).ok

        assert paint.channels == ["BaseColor", "Height"]

    def test_a_source_on_a_paint_layer_stops_the_step(self, adapter):
        adapter.stack.selected = adapter.stack.layers[1]

        result = run(adapter, [set_fill(sources={"Height": {"value": 1}})])

        assert result.state == FAILED
        assert result.message == "“Fill” stopped at Step 1 (Set Fill content): needs a Fill layer."

    def test_switching_channels_on_a_folder_stops_the_step(self, adapter):
        folder = FakeLayer("Folder", "folder")
        adapter.stack.layers.append(folder)
        adapter.stack.selected = folder

        result = run(adapter, [set_fill(channels_on=["Height"])])

        assert result.message.endswith("needs a Fill or Paint layer.")

    def test_it_needs_a_selected_layer(self, adapter):
        adapter.stack.selected = None

        result = run(adapter, [set_fill(channels_on=["Height"])])

        assert result.message == "“Fill” did not start: Step 1 (Set Fill content) needs a selected layer."

    def test_an_anchor_source(self, adapter):
        node = FakeEffect("layer", "anchor", name="Edges")
        adapter.stack.layers[1].effect_nodes.append(node)

        assert run(adapter, [set_fill(sources={"BaseColor": EDGES})]).ok

        assert adapter.stack.layers[0].sources["BaseColor"] == EDGES


class TestPreflight:
    def test_a_source_after_a_new_paint_layer_does_not_start(self, adapter):
        steps = [{"type": "add_layer", "layer": "paint"}, set_fill(sources={"Height": {"value": 1}})]

        result = run(adapter, steps)

        assert result.message == "“Fill” did not start: Step 2 (Set Fill content) needs a Fill layer."
        assert adapter.stack.scopes == []

    def test_channels_after_a_new_folder_do_not_start(self, adapter):
        steps = [{"type": "add_layer", "layer": "folder"}, set_fill(channels_on=["Height"])]

        assert run(adapter, steps).message.endswith("Step 2 (Set Fill content) needs a Fill or Paint layer.")

    def test_channels_after_a_new_paint_layer_are_fine(self, adapter):
        steps = [{"type": "add_layer", "layer": "paint"}, set_fill(channels_on=["Height"])]

        assert run(adapter, steps).ok

    def test_after_select_layer_it_is_checked_when_it_runs(self, adapter):
        steps = [{"type": "select_layer", "name": "Paint"}, set_fill(sources={"Height": {"value": 1}})]

        assert run(adapter, steps).message.endswith("stopped at Step 2 (Set Fill content): needs a Fill layer.")

    def test_a_channel_the_texture_set_does_not_have(self, adapter):
        adapter.texture_channels = ["BaseColor", "Roughness"]

        result = run(adapter, [set_fill(channels_on=["Height"])])

        assert result.message.endswith("uses the Height channel, which this texture set does not have.")
