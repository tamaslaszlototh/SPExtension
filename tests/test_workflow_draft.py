"""The Workflow being edited (PRD R7.3–R7.6), without Qt: name, incomplete Steps,
selection, filling a Step from a dropped resource, and the JSON that is saved."""

from shelfplus_app.core.layout import button_problem
from shelfplus_app.core.workflow_draft import CATALOG, WorkflowDraft, auto_name, incomplete, template

FILL = {"type": "add_layer", "layer": "fill"}
BLACK = {"type": "add_mask", "background": "black"}
DIRT = {"type": "add_effect", "effect": "generator", "target": "mask", "resource": "resource://starter_assets/Dirt"}
OPACITY = {"type": "set_opacity", "opacity": {"BaseColor": 50}}
SAVE = {"type": "save"}


def test_the_automatic_name_lists_the_steps():
    assert auto_name([FILL, BLACK, DIRT, OPACITY]) == "Fill layer + Black mask + Dirt + Opacity 50%"
    assert auto_name([SAVE]) == "Save"
    assert auto_name([]) == "New Workflow"


def test_the_name_follows_the_steps_until_the_user_types_one():
    draft = WorkflowDraft()
    draft.add(dict(FILL))
    draft.add(dict(BLACK))
    assert draft.name == "Fill layer + Black mask"

    draft.set_name("My fill")
    draft.add(dict(DIRT))
    assert draft.name == "My fill"

    draft.set_name("  ")  # cleared: automatic again
    assert draft.name == "Fill layer + Black mask + Dirt"


def test_an_existing_workflow_keeps_its_own_name_but_an_automatic_one_stays_automatic():
    assert WorkflowDraft([FILL], name="Mine").name_is_automatic is False
    draft = WorkflowDraft([FILL], name="Fill layer")
    draft.add(dict(BLACK))
    assert draft.name == "Fill layer + Black mask"


def test_every_catalog_entry_is_a_step_and_the_ones_needing_a_choice_are_incomplete():
    labels = [label for _, label in CATALOG]
    assert "Fill layer" in labels and "Smart mask" in labels and "Save" in labels
    assert incomplete(template("Smart mask")) == "⚠ choose resource"
    assert incomplete(template("Select layer by name")) == "⚠ enter a name"
    assert incomplete(template("Black mask")) is None


def test_incomplete_steps_block_saving():
    draft = WorkflowDraft()
    assert draft.problem == "Add a Step first."

    draft.add(dict(FILL))
    draft.add(template("Smart mask"))
    assert draft.problem == "Step 2 (Add smart mask) is incomplete: ⚠ choose resource"

    draft.set_step(1, {"type": "add_smart", "smart": "mask", "resource": "resource://a/Edges"})
    assert draft.problem is None


def test_a_dropped_resource_fills_the_selected_incomplete_step():
    draft = WorkflowDraft([dict(FILL)])
    draft.add(template("Smart mask"))
    assert draft.selected == 1

    assert draft.fill_resource("resource://a/Edges") is True
    assert draft.steps[1] == {"type": "add_smart", "smart": "mask", "resource": "resource://a/Edges"}
    assert draft.fill_resource("resource://a/Other") is False  # complete now: not filled again


def test_a_dropped_resource_does_not_fill_a_step_that_takes_none():
    draft = WorkflowDraft()
    draft.add(template("Select layer by name"))

    assert draft.fill_resource("resource://a/Edges") is False


def test_the_moved_step_stays_selected_and_a_snapped_back_drop_changes_nothing():
    draft = WorkflowDraft([dict(FILL), dict(BLACK), dict(SAVE)])
    draft.select(1)

    assert draft.move_up(1) is True
    assert draft.steps == [BLACK, FILL, SAVE] and draft.selected == 0
    assert draft.drop(2, 0) is False  # Save above the layer Steps
    assert draft.steps == [BLACK, FILL, SAVE]


def test_the_selected_row_decides_where_an_acting_step_goes():
    draft = WorkflowDraft([dict(FILL), {"type": "add_layer", "layer": "paint"}])
    draft.select(0)
    draft.add(dict(BLACK))

    assert [s["type"] for s in draft.steps] == ["add_layer", "add_mask", "add_layer"]
    assert draft.selected == 1


def test_deleting_clears_the_selection():
    draft = WorkflowDraft([dict(FILL), dict(BLACK)])
    draft.select(1)
    draft.delete(0)

    assert draft.steps == [] and draft.selected is None


def test_the_saved_json_is_the_flat_list_the_runner_reads():
    draft = WorkflowDraft()
    for step in (FILL, BLACK, DIRT, SAVE, OPACITY):
        draft.add(dict(step))

    raw = draft.to_raw()

    assert raw == {
        "kind": "workflow",
        "name": "Fill layer + Black mask + Dirt + Opacity 50% + Save",
        "steps": [FILL, BLACK, DIRT, OPACITY, SAVE],
    }
    assert button_problem({"id": "x", **raw}) is None


def test_a_layer_whose_material_or_channel_resource_is_not_chosen_yet_is_incomplete():
    waiting = {"type": "add_layer", "layer": "fill", "material": {"resource": ""}}
    channel = {"type": "add_layer", "layer": "fill", "channels": ["Height"], "sources": {"Height": {"resource": ""}}}

    assert incomplete(waiting) == "⚠ choose resource"
    assert incomplete(channel) == "⚠ choose resource"


def test_a_fill_layer_with_a_material_is_named_after_it():
    rust = {"type": "add_layer", "layer": "fill", "material": {"resource": "resource://a/Rust_v2", "resource_name": "Rust"}}

    assert auto_name([rust, BLACK]) == "Fill layer: Rust + Black mask"


def test_paint_and_fill_effects_are_in_the_catalog():
    assert template("Paint on layer") == {"type": "add_effect", "effect": "paint", "target": "layer"}
    assert template("Fill on mask") == {"type": "add_effect", "effect": "fill", "target": "mask"}
    assert incomplete(template("Paint on layer")) is None
    assert auto_name([FILL, template("Paint on layer")]) == "Fill layer + Paint"


def test_a_rows_detail_says_what_the_step_applies_to():
    from shelfplus_app.core.workflow_draft import row_detail

    def effect(kind, target, **extra):
        return {"type": "add_effect", "effect": kind, "target": target, **extra}

    assert row_detail(effect("fill", "mask")) == "on mask"
    assert row_detail(effect("paint", "layer")) == "on layer"
    assert row_detail(effect("generator", "mask", resource="resource://a/Dirt", resource_name="Dirt")) == "generator on mask"
    assert row_detail(effect("generator", "mask")) == "on mask"  # no resource yet: the name says generator
    assert row_detail(effect("fill", "mask", source={"value": 0.3})) == "on mask, value 0.3"
    assert row_detail(effect("fill", "layer", sources={"BaseColor": {"color": "#0000ff"}})) == "on layer, per channel"
    assert row_detail({"type": "add_smart", "smart": "material", "resource": "resource://a/Rust"}) == "smart material"
    assert row_detail({"type": "add_smart", "smart": "mask"}) is None  # "Smart mask" says it already
    assert row_detail(OPACITY) == "BaseColor"
    assert row_detail({"type": "set_opacity", "opacity": {"BaseColor": 50, "Height": 50}}) == "2 channels"
    assert row_detail({"type": "select_layer", "name": "Base"}) == "select layer"
    assert row_detail({"type": "select_brush", "resource": "resource://a/Hard"}) == "brush"
    assert row_detail({"type": "run_action", "action": "SAVE_PROJECT"}) == "menu command"
    assert row_detail(FILL) is None and row_detail(BLACK) is None and row_detail(SAVE) is None
    named = {"type": "add_layer", "layer": "paint", "name": "Dirt pass", "channels": ["BaseColor", "Roughness"]}
    assert row_detail(named) == "Paint layer, 2 channels"


# -- anchor points and Fill content (#35) ----------------------------------------------

EDGES = {"anchor": "Edges"}


def test_fill_content_is_a_setting_in_the_catalog_and_starts_incomplete():
    assert ("Setting", "Fill content") in CATALOG
    step = template("Fill content")

    assert step == {"type": "set_fill"}
    assert incomplete(step) == "⚠ choose what to change"


def test_an_anchor_source_without_a_name_is_incomplete():
    step = {"type": "add_layer", "layer": "fill", "sources": {"Height": {"anchor": ""}}}

    assert incomplete(step) == "⚠ enter an anchor point name"
    assert incomplete({"type": "set_fill", "sources": {"Height": {"anchor": ""}}}) == "⚠ enter an anchor point name"


def test_rows_show_anchor_names():
    from shelfplus_app.core.workflow_draft import row_detail, short_name

    anchor = {"type": "add_effect", "effect": "anchor", "target": "mask"}
    assert short_name(anchor) == "Anchor point"
    assert short_name({**anchor, "name": "Anchor point"}) == "Anchor point"
    assert short_name({**anchor, "name": "Edges"}) == "Anchor point “Edges”"
    assert row_detail({"type": "add_effect", "effect": "fill", "target": "mask", "source": EDGES}) == "on mask, anchor “Edges”"
    assert row_detail({"type": "add_layer", "layer": "fill", "sources": {"Height": EDGES}}) == "per channel, anchor “Edges”"


def test_a_fill_content_row_says_what_it_changes():
    from shelfplus_app.core.workflow_draft import row_detail, short_name

    assert short_name({"type": "set_fill"}) == "Fill content"
    assert row_detail({"type": "set_fill", "sources": {"BaseColor": EDGES}}) == "BaseColor anchor “Edges”"
    assert row_detail({"type": "set_fill", "sources": {"BaseColor": {"color": "#ff0000"}, "Height": {"value": 0.5}}}) == "2 channels set"
    assert row_detail({"type": "set_fill", "material": {"resource": "resource://a/Rust"}}) == "material Rust"
    assert row_detail({"type": "set_fill", "channels_on": ["Height"], "channels_off": ["Roughness", "Metallic"]}) == "Height on, 2 channels off"
