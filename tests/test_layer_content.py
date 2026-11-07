"""What a new Fill or Paint layer is set up with (``add_layer``): its active channels, and
a Fill layer's content: one material, or per channel a colour, a value or a resource."""

import pytest

from shelfplus_app.adapter.fake import FakeAdapter, FakeLayer, FakeResource
from shelfplus_app.core.layout import step_problem
from shelfplus_app.core.steps import FAILED, MISSING
from shelfplus_app.core.workflow import run_workflow

RUST = "resource://starter_assets/Rust"
NOISE = "resource://starter_assets/Clouds 1"


def fill(**extra):
    return {"type": "add_layer", "layer": "fill", **extra}


class TestValidation:
    def test_channels_and_sources_are_valid(self):
        step = fill(
            channels=["BaseColor", "Height", "Normal"],
            sources={
                "BaseColor": {"color": "#c08040"},
                "Height": {"value": 0.25},
                "Normal": {"resource": NOISE, "resource_name": "Clouds 1"},
            },
        )

        assert step_problem(step) is None
        assert step_problem(fill(material={"resource": RUST, "resource_name": "Rust"})) is None
        assert step_problem({"type": "add_layer", "layer": "paint", "channels": ["BaseColor"]}) is None

    @pytest.mark.parametrize(
        "extra, problem",
        [
            ({"channels": []}, "Step 'add_layer' has an invalid 'channels'"),
            ({"sources": {"Height": {"value": 2}}}, "Step 'add_layer' has an invalid 'sources'"),
            ({"sources": {"BaseColor": {"color": "red"}}}, "Step 'add_layer' has an invalid 'sources'"),
            ({"sources": {"BaseColor": {"resource": "x"}}}, "Step 'add_layer' has an invalid 'sources'"),
            ({"material": {"resource": ""}}, "Step 'add_layer' has an invalid 'material'"),
            (
                {"material": {"resource": RUST}, "sources": {"Height": {"value": 0}}},
                "Step 'add_layer' has both 'material' and 'sources'",
            ),
            (
                {"channels": ["BaseColor"], "sources": {"Height": {"value": 0}}},
                "Step 'add_layer' sets 'Height', which is not one of its channels",
            ),
        ],
    )
    def test_problems(self, extra, problem):
        assert step_problem(fill(**extra)) == problem

    def test_only_a_fill_layer_has_content(self):
        paint = {"type": "add_layer", "layer": "paint", "material": {"resource": RUST}}

        assert step_problem(paint) == "Step 'add_layer' (paint) cannot have 'material' or 'sources'"


@pytest.fixture
def adapter():
    adapter = FakeAdapter()
    adapter.project_is_open = True
    adapter.stack.layers = [FakeLayer("Base")]
    adapter.add_resource(FakeResource(RUST, "Rust", is_brush=False))
    adapter.add_resource(FakeResource(NOISE, "Clouds 1", is_brush=False))
    return adapter


def run(adapter, steps):
    results = []
    run_workflow(adapter, steps, results.append, name="W")
    return results[0]


class TestRunning:
    def test_channels_and_per_channel_sources_are_set_on_the_new_layer(self, adapter):
        step = fill(
            channels=["BaseColor", "Height"],
            sources={"BaseColor": {"color": "#c08040"}, "Height": {"resource": NOISE}},
        )

        assert run(adapter, [step]).ok

        layer = adapter.stack.layers[0]
        assert layer.channels == ["BaseColor", "Height"]
        assert layer.sources == {"BaseColor": {"color": "#c08040"}, "Height": {"resource": NOISE}}
        assert adapter.stack.scopes == ["Shelf+: W"]  # still one undo

    def test_a_material_fills_the_layer(self, adapter):
        assert run(adapter, [fill(material={"resource": RUST, "resource_name": "Rust"})]).ok

        assert adapter.stack.layers[0].material == RUST

    def test_a_paint_layer_gets_its_channels(self, adapter):
        assert run(adapter, [{"type": "add_layer", "layer": "paint", "channels": ["Roughness"]}]).ok

        assert adapter.stack.layers[0].channels == ["Roughness"]

    def test_without_chosen_channels_every_channel_of_the_texture_set_is_switched_on(self, adapter):
        """What the editor shows as "all ticked". A layer made through Painter's Python
        API starts with no channel switched on, unlike one made in Painter's own UI."""
        adapter.texture_channels = ["BaseColor", "Height", "Roughness"]

        assert run(adapter, [fill(), {"type": "add_layer", "layer": "paint"}]).ok

        paint, filled = adapter.stack.layers[:2]
        assert filled.channels == ["BaseColor", "Height", "Roughness"]
        assert paint.channels == ["BaseColor", "Height", "Roughness"]

    def test_a_folder_gets_no_channels(self, adapter):
        adapter.texture_channels = ["BaseColor"]

        assert run(adapter, [{"type": "add_layer", "layer": "folder"}]).ok

        assert adapter.stack.layers[0].channels is None

    def test_when_painter_cannot_list_the_channels_they_are_left_alone(self, adapter):
        assert run(adapter, [fill()]).ok

        layer = adapter.stack.layers[0]
        assert (layer.channels, layer.material, layer.sources) == (None, None, {})


class TestPreflight:
    def test_a_missing_material_stops_it_before_anything_changes(self, adapter):
        failed = run(adapter, [fill(material={"resource": "resource://a/Gone"})])

        assert failed.state == MISSING
        assert failed.message == (
            "“W” did not start: Step 1 (Add Fill layer): This resource is not available on this machine: resource://a/Gone"
        )
        assert adapter.stack.scopes == []

    def test_a_missing_channel_source_stops_it(self, adapter):
        failed = run(adapter, [fill(channels=["Height"], sources={"Height": {"resource": "resource://a/Gone"}})])

        assert failed.state == MISSING and adapter.stack.scopes == []

    def test_a_channel_the_texture_set_does_not_have_stops_it(self, adapter):
        adapter.texture_channels = ["BaseColor", "Roughness"]

        failed = run(adapter, [fill(channels=["BaseColor", "Height"])])

        assert failed.state == FAILED
        assert failed.message == "“W” did not start: Step 1 (Add Fill layer) uses the Height channel, which this texture set does not have."
        assert adapter.stack.scopes == []
