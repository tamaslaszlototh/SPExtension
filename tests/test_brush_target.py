"""Painter changes the brush only while something paintable is selected: a Paint layer or
a mask. With a Fill layer or folder itself selected, a click on a brush tile only highlights
the tile, and the old brush stays (found in check C of the v0.6.0-rc.1 testing guide).

So ``select_brush`` selects the layer's mask first if the selection cannot be painted on,
and stops with a message if there is no mask; and preflight refuses a Workflow whose
last layer surely has nothing to paint on."""

import pytest

from shelfplus_app.adapter.fake import FakeAdapter, FakeLayer, FakeResource
from shelfplus_app.core.brush import NOT_PAINTABLE, select_brush
from shelfplus_app.core.steps import DONE, FAILED
from shelfplus_app.core.workflow import run_workflow

HARD = "resource://starter_assets/Basic Hard"
RUST = "resource://starter_assets/Rust Coat"
EDGES = "resource://starter_assets/Edges Soft"

FILL = {"type": "add_layer", "layer": "fill"}
PAINT = {"type": "add_layer", "layer": "paint"}
FOLDER = {"type": "add_layer", "layer": "folder"}
BLACK = {"type": "add_mask", "background": "black"}
BRUSH = {"type": "select_brush", "resource": HARD}


@pytest.fixture
def adapter():
    adapter = FakeAdapter()
    adapter.project_is_open = True
    adapter.add_resource(FakeResource(HARD, "Basic Hard"))
    adapter.add_resource(FakeResource(RUST, "Rust Coat", is_brush=False))
    adapter.add_resource(FakeResource(EDGES, "Edges Soft", is_brush=False))
    adapter.tiles["Basic Hard"] = (0, 0, 10, 10)
    return adapter


def click_through(adapter, results):
    """Let the brush activation find its tile (twice in the same place) and click it."""
    for _ in range(3):
        adapter.fire_timers()
    assert len(results) == 1
    return results[0]


def run_button(adapter):
    """A Brush button: a one-Step Workflow."""
    results = []
    run_workflow(adapter, [BRUSH], results.append, ui_steps={"select_brush": select_brush})
    if results:
        return results[0]
    return click_through(adapter, results)


def run(adapter, steps):
    results = []
    run_workflow(adapter, steps, results.append, ui_steps={"select_brush": select_brush}, name="W")
    if results:
        return results[0]
    return click_through(adapter, results)


class TestBrushButton:
    def test_a_paint_layer_is_left_selected(self, adapter):
        layer = FakeLayer("Paint", "paint")
        adapter.stack.layers = [layer]
        adapter.stack.selected = layer

        assert run_button(adapter).ok
        assert adapter.clicks and adapter.stack.selected_part == "content"

    def test_a_selected_mask_is_left_selected(self, adapter):
        layer = FakeLayer("Fill", "fill")
        layer.mask = "black"
        adapter.stack.layers = [layer]
        adapter.select_mask(layer)

        assert run_button(adapter).ok
        assert adapter.stack.selected_part == "mask"

    def test_a_fill_layer_with_a_mask_gets_its_mask_selected_before_the_click(self, adapter):
        layer = FakeLayer("Fill", "fill")
        layer.mask = "black"
        adapter.stack.layers = [layer]
        adapter.stack.selected = layer
        seen = []
        adapter.click_tile = lambda rect: seen.append((adapter.stack.selected, adapter.stack.selected_part))

        assert run_button(adapter).ok
        assert seen == [(layer, "mask")]

    @pytest.mark.parametrize("kind", ["fill", "folder"])
    def test_nothing_to_paint_on_stops_it_with_a_message(self, adapter, kind):
        layer = FakeLayer("L", kind)
        adapter.stack.layers = [layer]
        adapter.stack.selected = layer

        failed = run_button(adapter)

        assert failed.state == FAILED and failed.message == NOT_PAINTABLE
        assert adapter.clicks == [] and adapter.assets_calls == []

    def test_no_project_open_does_not_stop_it(self, adapter):
        adapter.project_is_open = False

        assert run_button(adapter).ok

    def test_nothing_selected_does_not_stop_it(self, adapter):
        assert run_button(adapter).ok

    def test_an_unreadable_selection_does_not_stop_it(self, adapter, monkeypatch):
        def broken():
            raise RuntimeError("no selection API")

        monkeypatch.setattr(adapter, "selection_paintable", broken)

        assert run_button(adapter).ok


class TestWorkflow:
    def untouched(self, adapter):
        assert adapter.stack.names() == [] and adapter.stack.scopes == [] and adapter.clicks == []

    @pytest.mark.parametrize(
        "steps, index",
        [
            ([FILL, BRUSH], 2),
            ([FOLDER, BRUSH], 2),
            ([FILL, BLACK, FOLDER, BRUSH], 4),
            ([{"type": "add_smart", "smart": "material", "resource": RUST}, BRUSH], 2),
        ],
    )
    def test_preflight_refuses_a_last_layer_without_anything_to_paint_on(self, adapter, steps, index):
        failed = run(adapter, steps)

        assert failed.state == FAILED
        assert failed.message == (
            f"“W” did not start: Step {index} (Select brush) needs a Paint layer or a mask: "
            "Painter does not change the brush while a Fill layer or folder is selected. Add a mask before it."
        )
        self.untouched(adapter)

    def test_fill_layer_and_mask_then_the_brush_paints_on_the_mask(self, adapter):
        assert run(adapter, [FILL, BLACK, BRUSH]).ok

        assert adapter.stack.selected.name == "Fill layer" and adapter.stack.selected_part == "mask"
        assert len(adapter.clicks) == 1

    def test_smart_material_and_smart_mask_then_the_brush(self, adapter):
        steps = [{"type": "add_smart", "smart": "material", "resource": RUST}, {"type": "add_smart", "smart": "mask", "resource": EDGES}, BRUSH]

        assert run(adapter, steps).ok
        assert adapter.stack.selected_part == "mask"

    def test_paint_layer_then_the_brush(self, adapter):
        assert run(adapter, [PAINT, BRUSH]).ok
        assert adapter.stack.selected_part == "content"

    def test_a_picked_fill_layer_without_a_mask_is_found_at_run_time(self, adapter):
        """``select_layer`` picks a layer whose kind is known only at run time."""
        adapter.stack.layers = [FakeLayer("Base", "fill")]

        failed = run(adapter, [{"type": "select_layer", "name": "Base"}, BRUSH])

        assert failed.message == f"“W” stopped at Step 2 (Select brush): {NOT_PAINTABLE}"
        assert adapter.clicks == []
