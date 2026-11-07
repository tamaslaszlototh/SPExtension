"""The effect and smart Steps (PRD R4.2) against the fake layer stack: ``add_effect`` on the
mask or the layer, ``add_smart`` material and mask, their preflight and runtime errors."""

import pytest

from shelfplus_app.adapter.fake import FakeAdapter, FakeLayer, FakeResource
from shelfplus_app.core.steps import DONE, FAILED, MISSING, StepResult
from shelfplus_app.core.workflow import run_workflow, step_label

DIRT = "resource://starter_assets/mg_dirt/mg_dirt"
BLUR = "resource://starter_assets/Blur"
RUST = "resource://starter_assets/Rust Coat"
EDGES = "resource://starter_assets/Edges Soft"
HARD = "resource://starter_assets/Basic Hard"

FILL = {"type": "add_layer", "layer": "fill"}
FOLDER = {"type": "add_layer", "layer": "folder"}
BLACK = {"type": "add_mask", "background": "black"}
SAVE = {"type": "save"}


def effect(kind, target="mask", resource=None):
    step = {"type": "add_effect", "effect": kind, "target": target}
    if resource is not None:
        step["resource"] = resource
    return step


def smart(kind, resource):
    return {"type": "add_smart", "smart": kind, "resource": resource}


@pytest.fixture
def base():
    return FakeLayer("Base")


@pytest.fixture
def adapter(base):
    adapter = FakeAdapter()
    adapter.project_is_open = True
    adapter.stack.layers = [base]
    for url, name in ((DIRT, "Dirt"), (BLUR, "Blur"), (RUST, "Rust Coat"), (EDGES, "Edges Soft"), (HARD, "Basic Hard")):
        adapter.add_resource(FakeResource(url, name, is_brush=url == HARD))
    return adapter


def result(adapter, steps, name="W", ui_steps=None):
    results = []
    run_workflow(adapter, steps, results.append, ui_steps=ui_steps, name=name)
    assert len(results) == 1
    return results[0]


def untouched(adapter, before):
    assert adapter.stack.names() == before
    assert adapter.stack.scopes == [] and adapter.stack.changes == 0


class TestAddEffect:
    def test_fill_black_mask_dirt_generator_and_levels_on_the_mask(self, adapter):
        """Manual checklist item 1, in one ScopedModification."""
        steps = [FILL, BLACK, effect("generator", resource=DIRT), effect("levels")]

        assert result(adapter, steps).ok

        fill = adapter.stack.layers[0]
        assert fill.name == "Fill layer" and fill.mask == "black"
        assert fill.effects == [("mask", "generator", DIRT), ("mask", "levels", None)]
        assert adapter.stack.scopes == ["Shelf+: W"]
        assert adapter.stack.selected is fill

    def test_on_the_layer_content(self, adapter, base):
        adapter.stack.selected = base

        assert result(adapter, [effect("filter", "layer", BLUR), effect("anchor", "layer")]).ok

        assert base.effects == [("layer", "filter", BLUR), ("layer", "anchor", None)]

    def test_acts_on_the_current_layer_not_the_start_layer(self, adapter, base):
        adapter.stack.selected = base

        assert result(adapter, [FILL, effect("levels", "layer")]).ok

        assert base.effects == [] and adapter.stack.layers[0].effects == [("layer", "levels", None)]

    def test_on_the_mask_of_a_layer_without_one_stops_the_workflow(self, adapter, base):
        adapter.stack.selected = base

        failed = result(adapter, [FILL, effect("generator", resource=DIRT), SAVE])

        assert failed.state == FAILED
        assert failed.message == (
            "“W” stopped at Step 2 (Add generator to the mask): The Current layer has no mask. Add a mask before this Step."
        )
        assert adapter.stack.names() == ["Fill layer", "Base"]  # no rollback (R4.7)
        assert adapter.saves == 0

    def test_on_a_folder_content_is_refused_by_painter(self, adapter):
        failed = result(adapter, [FOLDER, effect("levels", "layer")])

        assert failed.state == FAILED
        assert failed.message.startswith("“W” stopped at Step 2 (Add levels to the layer): ")

    @pytest.mark.parametrize("kind, label", [("levels", "Add levels to the mask"), ("anchor", "Add anchor point to the mask")])
    def test_painter_refusing_levels_or_anchor_stops_the_workflow(self, adapter, kind, label):
        adapter.stack.fail_on = "insert_effect"

        failed = result(adapter, [FILL, BLACK, effect(kind), SAVE])

        assert failed.message == f"“W” stopped at Step 3 ({label}): insert_effect failed"
        assert adapter.stack.layers[0].mask == "black" and adapter.saves == 0

    def test_preflight_catches_a_missing_generator(self, adapter, base):
        adapter.stack.selected = base
        before = adapter.stack.names()
        gone = "resource://starter_assets/Gone"

        failed = result(adapter, [FILL, BLACK, effect("generator", resource=gone)])

        assert failed.state == MISSING
        assert failed.message == (
            f"“W” did not start: Step 3 (Add generator to the mask): This resource is not available on this machine: {gone}"
        )
        untouched(adapter, before)

    def test_preflight_catches_a_missing_filter(self, adapter, base):
        adapter.stack.selected = base
        before = adapter.stack.names()

        failed = result(adapter, [effect("filter", "layer", "resource://x/Gone")])

        assert failed.state == MISSING and "Step 1 (Add filter to the layer)" in failed.message
        untouched(adapter, before)

    def test_the_first_block_needs_a_selected_layer(self, adapter):
        before = adapter.stack.names()

        failed = result(adapter, [effect("levels", "layer")])

        assert failed.message == "“W” did not start: Step 1 (Add levels to the layer) needs a selected layer."
        untouched(adapter, before)


class TestSmartMaterial:
    def test_inserted_above_the_current_layer_and_becomes_it(self, adapter, base):
        adapter.stack.selected = base

        assert result(adapter, [smart("material", RUST), BLACK]).ok

        material = adapter.stack.layers[0]
        assert adapter.stack.names() == [("Rust Coat", []), "Base"]
        assert material.mask == "black" and base.mask is None
        assert adapter.stack.selected is material

    def test_on_top_of_the_stack_with_nothing_selected(self, adapter):
        assert result(adapter, [smart("material", RUST)]).ok

        assert adapter.stack.names() == [("Rust Coat", []), "Base"]

    def test_a_mask_on_it_needs_no_selected_layer(self, adapter):
        assert result(adapter, [smart("material", RUST), BLACK]).ok

        assert adapter.stack.layers[0].mask == "black"

    def test_preflight_catches_a_missing_material(self, adapter, base):
        adapter.stack.selected = base
        before = adapter.stack.names()

        failed = result(adapter, [FILL, smart("material", "resource://x/Gone")])

        assert failed.state == MISSING and "Step 2 (Add smart material)" in failed.message
        untouched(adapter, before)

    def test_painter_refusing_it_stops_the_workflow(self, adapter):
        adapter.stack.fail_on = "insert_smart_material"

        failed = result(adapter, [smart("material", RUST)])

        assert failed.message == "“W” stopped at Step 1 (Add smart material): insert_smart_material failed"


class TestSmartMask:
    def test_smart_material_then_smart_mask_on_it(self, adapter):
        """Manual checklist item 2."""
        assert result(adapter, [smart("material", RUST), smart("mask", EDGES)]).ok

        material = adapter.stack.layers[0]
        assert material.name == "Rust Coat" and material.mask == "black"
        assert material.effects == [("mask", "smart mask", EDGES)]
        assert adapter.stack.selected is material

    def test_goes_into_an_existing_mask(self, adapter, base):
        adapter.stack.selected = base
        base.mask = "white"

        assert result(adapter, [smart("mask", EDGES)]).ok

        assert base.mask == "white" and base.effects == [("mask", "smart mask", EDGES)]

    def test_needs_a_selected_layer_when_it_comes_first(self, adapter):
        failed = result(adapter, [smart("mask", EDGES)])

        assert failed.message == "“W” did not start: Step 1 (Add smart mask) needs a selected layer."

    def test_preflight_catches_a_missing_mask(self, adapter, base):
        adapter.stack.selected = base
        before = adapter.stack.names()

        failed = result(adapter, [FILL, smart("mask", "resource://x/Gone")])

        assert failed.state == MISSING and "Step 2 (Add smart mask)" in failed.message
        untouched(adapter, before)

    def test_painter_refusing_it_keeps_the_earlier_steps(self, adapter, base):
        adapter.stack.selected = base
        adapter.stack.fail_on = "insert_smart_mask"

        failed = result(adapter, [FILL, smart("mask", EDGES)])

        assert failed.message == "“W” stopped at Step 2 (Add smart mask): insert_smart_mask failed"
        assert adapter.stack.names() == ["Fill layer", "Base"]


class TestEndSteps:
    def test_fill_layer_then_a_brush(self, adapter, base):
        """Manual checklist item 3: the brush is chosen after the scope closes and the
        Fill layer is selected."""
        adapter.stack.selected = base
        seen = []

        def select_brush(a, step, done):
            seen.append((step["resource"], a.stack.in_scope, a.stack.selected.name))
            done(StepResult(DONE))

        steps = [FILL, {"type": "select_brush", "resource": HARD}]

        assert result(adapter, steps, ui_steps={"select_brush": select_brush}).ok
        assert seen == [(HARD, False, "Fill layer")]

    def test_a_renamed_preset_stops_it_before_anything_changes(self, adapter, base):
        """Manual checklist item 4."""
        adapter.stack.selected = base
        before = adapter.stack.names()
        renamed = "resource://starter_assets/Basic Hard Renamed"
        steps = [FILL, BLACK, {"type": "select_brush", "resource": renamed}]

        failed = result(adapter, steps, ui_steps={"select_brush": lambda a, s, d: d(StepResult(DONE))})

        assert failed.state == MISSING
        assert failed.message == (
            f"“W” did not start: Step 3 (Select brush): This brush is not available on this machine: {renamed}"
        )
        untouched(adapter, before)


def test_step_labels():
    assert step_label(effect("generator", resource=DIRT)) == "Add generator to the mask"
    assert step_label(effect("filter", "layer", BLUR)) == "Add filter to the layer"
    assert step_label(effect("levels")) == "Add levels to the mask"
    assert step_label(effect("anchor", "layer")) == "Add anchor point to the layer"
    assert step_label(smart("material", RUST)) == "Add smart material"
    assert step_label(smart("mask", EDGES)) == "Add smart mask"
