"""The content of a Fill inside a layer (Painter's "Add fill"): on the layer, like a Fill
layer (channels, one material or per-channel sources); on the mask, one grey value or one
resource."""

import pytest

from shelfplus_app.adapter.fake import FakeAdapter, FakeLayer, FakeResource
from shelfplus_app.core.layout import step_problem
from shelfplus_app.core.workflow import run_workflow
from shelfplus_app.core.workflow_draft import auto_name, incomplete

CLOUDS = "resource://starter_assets/Clouds 1"
RUST = "resource://starter_assets/Rust"


def fill_on(target, **extra):
    return {"type": "add_effect", "effect": "fill", "target": target, **extra}


class TestValidation:
    def test_a_fill_on_the_layer_takes_what_a_fill_layer_takes(self):
        step = fill_on("layer", channels=["BaseColor", "Height"], sources={"BaseColor": {"color": "#ff0000"}, "Height": {"value": -0.5}})

        assert step_problem(step) is None
        assert step_problem(fill_on("layer", material={"resource": RUST})) is None

    def test_a_fill_on_the_mask_takes_one_value_or_one_resource(self):
        assert step_problem(fill_on("mask", source={"value": 0.3})) is None
        assert step_problem(fill_on("mask", source={"resource": CLOUDS, "resource_name": "Clouds 1"})) is None

    @pytest.mark.parametrize(
        "step, problem",
        [
            (fill_on("mask", source={"value": 1.5}), "Step 'add_effect' has an invalid 'source'"),
            (fill_on("mask", source={"color": "#ffffff"}), "Step 'add_effect' has an invalid 'source'"),
            (fill_on("mask", material={"resource": RUST}), "Step 'add_effect' on the mask takes only 'source'"),
            (fill_on("layer", source={"value": 0.3}), "Step 'add_effect' on the layer cannot have 'source'"),
            (
                {"type": "add_effect", "effect": "paint", "target": "layer", "material": {"resource": RUST}},
                "Step 'add_effect' (paint) has no content",
            ),
        ],
    )
    def test_problems(self, step, problem):
        assert step_problem(step) == problem

    def test_a_fill_waiting_for_its_resource_is_incomplete_and_a_material_names_it(self):
        assert incomplete(fill_on("mask", source={"resource": ""})) == "⚠ choose resource"
        named = fill_on("layer", material={"resource": RUST, "resource_name": "Rust"})
        assert auto_name([{"type": "add_layer", "layer": "fill"}, named]) == "Fill layer + Fill: Rust"


@pytest.fixture
def adapter():
    adapter = FakeAdapter()
    adapter.project_is_open = True
    base = FakeLayer("Base")
    base.mask = "black"
    adapter.stack.layers = [base]
    adapter.stack.selected = base
    adapter.add_resource(FakeResource(CLOUDS, "Clouds 1", is_brush=False))
    return adapter


def run(adapter, steps):
    results = []
    run_workflow(adapter, steps, results.append, name="W")
    return results[0]


class TestRunning:
    def test_a_fill_on_the_layer_gets_channels_and_sources(self, adapter):
        step = fill_on("layer", channels=["BaseColor"], sources={"BaseColor": {"color": "#ff0000"}})

        assert run(adapter, [step]).ok

        node = adapter.stack.layers[0].effect_nodes[0]
        assert (node.channels, node.sources) == (["BaseColor"], {"BaseColor": {"color": "#ff0000"}})

    def test_a_fill_on_the_layer_without_chosen_channels_gets_every_channel(self, adapter):
        adapter.texture_channels = ["BaseColor", "Roughness"]

        assert run(adapter, [fill_on("layer")]).ok

        assert adapter.stack.layers[0].effect_nodes[0].channels == ["BaseColor", "Roughness"]

    def test_a_fill_on_the_mask_gets_its_one_source(self, adapter):
        assert run(adapter, [fill_on("mask", source={"resource": CLOUDS})]).ok

        node = adapter.stack.layers[0].effect_nodes[0]
        assert node.source == {"resource": CLOUDS} and node.channels is None

    def test_a_missing_resource_in_a_fill_stops_it_before_anything_changes(self, adapter):
        failed = run(adapter, [fill_on("mask", source={"resource": "resource://a/Gone"})])

        assert not failed.ok and adapter.stack.scopes == []

    def test_switching_on_channels_by_default_does_not_stop_the_workflow_if_painter_refuses(self, adapter, monkeypatch):
        adapter.texture_channels = ["BaseColor"]

        def refuse(node, channels):
            raise AttributeError("no active_channels on a fill effect")

        monkeypatch.setattr(adapter, "set_active_channels", refuse)

        assert run(adapter, [fill_on("layer")]).ok
