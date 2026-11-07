"""Recording (PRD R8), the pure part: the layer stack diff, reading Painter's History, and
turning a sequence of operations into Steps (merging, filtering, selection rules).

The snapshot sequences follow the probe runs in ``docs/probes/``: the History labels
(``Add fill layer``, ``set blending opacity``, ``Set generator``, ``Drop resource on new
mask``, ``Add stroke``…) and what the diff showed for each operation."""

from shelfplus_app.core.recording import (
    ADDED,
    BLEND,
    MASK,
    MOVED,
    NAME,
    OPACITY,
    REDO,
    REMOVED,
    RESET,
    SOURCE,
    UNDO,
    NOTHING,
    PUSH,
    Op,
    derive,
    diff,
    history_event,
    is_window_action,
)
from shelfplus_app.core.menu import MenuAction

DIRT = "resource://starter_assets/Dirt"
RUST = "resource://starter_assets/Rust Iron"


# -- building snapshots ---------------------------------------------------------------


def layer(uid, name, kind="paint", parent=None, mask=None, blend="Normal", opacity=1.0):
    return {
        "uid": uid, "name": name, "kind": kind, "parent": parent, "stack": "layers",
        "mask": mask, "blend": {"BaseColor": blend, "Roughness": blend},
        "opacity": {"BaseColor": opacity, "Roughness": opacity},
    }


def effect(uid, name, kind, parent, stack="mask", source=None):
    return {"uid": uid, "name": name, "kind": kind, "parent": parent, "stack": stack, "source": source}


def snap(*nodes, selected=None, stack="coat"):
    """Nodes top first, as Painter lists them."""
    return {"stack": stack, "selected": selected, "nodes": [dict(n) for n in nodes]}


def changed(node, **fields):
    return {**node, **fields}


BASE = layer(1, "Base")
OLD = layer(9, "Old layer", kind="fill")


def op(label, before, after, **kw):
    return Op(label, diff(before, after), before, after, **kw)


def capture(base, *ops, final=None):
    return derive(base, list(ops), final)


# -- diff ---------------------------------------------------------------------------


def test_a_new_layer_is_one_added_change():
    before = snap(BASE, selected=1)
    after = snap(layer(2, "Fill layer 1", "fill"), BASE, selected=2)

    (change,) = diff(before, after)

    assert change.what == ADDED and change.uid == 2 and change.new["kind"] == "fill"


def test_a_folder_added_with_its_content_is_one_change():
    """A smart material arrives as one folder with everything inside it in one diff."""
    before = snap(BASE)
    after = snap(
        layer(5, "Rust Iron", "folder"), layer(6, "Rust", "fill", parent=5), layer(7, "Dirt", "fill", parent=5),
        effect(8, "Mask Editor", "generator", parent=6), BASE,
    )

    (change,) = diff(before, after)

    assert change.what == ADDED and change.uid == 5 and change.size == 3


def test_a_parameter_change_shows_only_the_channels_that_changed():
    before = snap(layer(2, "Layer 3"))
    after = snap(layer(2, "Layer 3") | {"opacity": {"BaseColor": 0.5, "Roughness": 1.0}})

    (change,) = diff(before, after)

    assert change.what == OPACITY and change.old == {"BaseColor": 1.0} and change.new == {"BaseColor": 0.5}


def test_blend_mask_source_and_name_changes():
    before = snap(layer(2, "Fill layer 1", "fill"), effect(3, "Generator (empty)", "generator", 2))
    after = snap(
        changed(layer(2, "Grime", "fill", mask="black", blend="Multiply")),
        effect(3, "Dirt", "generator", 2, source=DIRT),
    )

    whats = {(c.what, c.uid) for c in diff(before, after)}

    assert whats == {(NAME, 2), (MASK, 2), (BLEND, 2), (SOURCE, 3), (NAME, 3)}


def test_a_removed_layer_takes_its_effects_with_it():
    before = snap(layer(2, "Fill", "fill", mask="black"), effect(3, "Levels", "levels", 2), BASE)
    after = snap(BASE)

    (change,) = diff(before, after)

    assert change.what == REMOVED and change.uid == 2


def test_inserting_a_layer_does_not_move_the_others_but_reordering_does():
    before = snap(layer(2, "A"), layer(3, "B"), BASE)
    inserted = snap(layer(2, "A"), layer(4, "New"), layer(3, "B"), BASE)
    reordered = snap(layer(3, "B"), layer(2, "A"), BASE)

    assert [c.what for c in diff(before, inserted)] == [ADDED]
    assert MOVED in [c.what for c in diff(before, reordered)]


def test_a_layer_moved_into_a_folder_is_moved():
    before = snap(layer(2, "Folder", "folder"), layer(3, "A"))
    after = snap(layer(2, "Folder", "folder"), layer(3, "A", parent=2))

    assert [c.what for c in diff(before, after)] == [MOVED]


def test_the_same_snapshot_has_no_changes():
    assert diff(snap(BASE, selected=1), snap(BASE, selected=1)) == []


# -- History ---------------------------------------------------------------------------


def test_a_new_row_is_an_operation():
    assert history_event((("Add fill layer",), 1), (("Add fill layer", "Add black mask"), 2)) == (PUSH, 1, 0)


def test_the_index_going_down_is_undo_and_up_without_a_new_row_is_redo():
    rows = ("Add fill layer", "set blending mode")
    assert history_event((rows, 2), (rows, 1)) == (UNDO, None, 0)
    assert history_event((rows, 1), (rows, 2)) == (REDO, None, 0)
    assert history_event((rows, 2), (rows, 2)) == (NOTHING, None, 0)


def test_a_new_operation_after_an_undo_replaces_the_undone_rows():
    before = (("Add fill layer", "set blending mode"), 1)
    assert history_event(before, (("Add fill layer", "Add black mask"), 2)) == (PUSH, 1, 0)


def test_a_full_history_dropping_its_oldest_row_is_still_a_new_operation():
    before = (("a", "b", "c"), 3)
    assert history_event(before, (("b", "c", "d"), 3)) == (PUSH, 2, 1)


def test_a_cleared_history_is_a_reset():
    assert history_event((("a", "b"), 2), ((), 0)) == (RESET, None, 0)


# -- the friend's first checklist run (issue #31) ------------------------------------


def checklist_ops():
    """Add fill → black mask → Dirt generator → layer opacity dragged to 50% → blend
    Multiply. The fill goes above the selected Base layer."""
    s0 = snap(BASE, selected=1)
    s1 = snap(layer(2, "Fill layer 1", "fill"), BASE, selected=2)
    s2 = snap(layer(2, "Fill layer 1", "fill", mask="black"), BASE, selected=2)
    s3 = snap(layer(2, "Fill layer 1", "fill", mask="black"), effect(3, "Generator (empty)", "generator", 2), BASE, selected=3)
    s4 = snap(layer(2, "Fill layer 1", "fill", mask="black"), effect(3, "Dirt", "generator", 2, source=DIRT), BASE, selected=3)
    fill = layer(2, "Fill layer 1", "fill", mask="black")
    s5 = snap(fill | {"opacity": {"BaseColor": 0.5, "Roughness": 1.0}}, effect(3, "Dirt", "generator", 2, source=DIRT), BASE)
    s6 = snap(
        fill | {"opacity": {"BaseColor": 0.5, "Roughness": 1.0}, "blend": {"BaseColor": "Multiply", "Roughness": "Multiply"}},
        effect(3, "Dirt", "generator", 2, source=DIRT), BASE,
    )
    return s0, [
        op("Add fill layer", s0, s1),
        op("Add black mask", s1, s2),
        op("Add generator", s2, s3),
        op("Set generator", s3, s4),
        op("set blending opacity", s4, s5),
        op("set blending mode", s5, s6),
    ]


def test_the_checklist_recording_gives_four_steps_with_opacity_at_exactly_50():
    base, ops = checklist_ops()

    result = capture(base, *ops[:5])  # the blend was undone (Ctrl+Z)

    assert result.steps == [
        {"type": "add_layer", "layer": "fill"},
        {"type": "add_mask", "background": "black"},
        {"type": "add_effect", "effect": "generator", "target": "mask", "resource": DIRT, "resource_name": "Dirt"},
        {"type": "set_opacity", "opacity": {"BaseColor": 50}},
    ]
    assert result.notices == []


def test_with_the_blend_kept_it_is_five_steps():
    base, ops = checklist_ops()

    steps = capture(base, *ops).steps

    assert steps[-1] == {"type": "set_blend", "blend": "Multiply"}


# -- merging and filtering --------------------------------------------------------------


def opacity_op(before_value, after_value, uid=2, label="set blending opacity"):
    before = snap(layer(uid, "Fill layer 1", "fill", opacity=before_value), BASE)
    after = snap(layer(uid, "Fill layer 1", "fill", opacity=before_value) | {"opacity": {"BaseColor": after_value, "Roughness": before_value}}, BASE)
    return op(label, before, after)


def new_fill():
    s0 = snap(BASE, selected=1)
    return s0, op("Add fill layer", s0, snap(layer(2, "Fill layer 1", "fill"), BASE, selected=2))


def test_a_parameter_that_keeps_changing_updates_one_step():
    base, add = new_fill()

    steps = capture(base, add, opacity_op(1.0, 0.3), opacity_op(0.3, 0.5)).steps

    assert steps == [{"type": "add_layer", "layer": "fill"}, {"type": "set_opacity", "opacity": {"BaseColor": 50}}]


def test_opacity_is_stored_per_channel():
    base, add = new_fill()
    rough_before = snap(layer(2, "Fill layer 1", "fill") | {"opacity": {"BaseColor": 0.5, "Roughness": 1.0}}, BASE)
    rough_after = snap(layer(2, "Fill layer 1", "fill") | {"opacity": {"BaseColor": 0.5, "Roughness": 0.25}}, BASE)

    steps = capture(base, add, opacity_op(1.0, 0.5), op("set blending opacity", rough_before, rough_after)).steps

    assert steps[-1] == {"type": "set_opacity", "opacity": {"BaseColor": 50, "Roughness": 25}}


def test_an_opacity_dragged_back_to_where_it_was_is_dropped():
    """Probe round 2, C: the user dragged back to 1.0, so the net change was 0."""
    base, add = new_fill()

    steps = capture(base, add, opacity_op(1.0, 0.4), opacity_op(0.4, 1.0)).steps

    assert steps == [{"type": "add_layer", "layer": "fill"}]


def test_a_blend_set_back_is_dropped():
    base, add = new_fill()
    normal = snap(layer(2, "Fill layer 1", "fill"), BASE)
    multiply = snap(layer(2, "Fill layer 1", "fill", blend="Multiply"), BASE)

    steps = capture(base, add, op("set blending mode", normal, multiply), op("set blending mode", multiply, normal)).steps

    assert steps == [{"type": "add_layer", "layer": "fill"}]


def test_opacity_values_are_rounded_to_what_painter_shows():
    base, add = new_fill()

    steps = capture(base, add, opacity_op(1.0, 0.49999)).steps

    assert steps[-1] == {"type": "set_opacity", "opacity": {"BaseColor": 50}}


def test_painting_is_not_a_step_and_not_reported():
    """Probe problem 8: strokes show only as ``Add stroke`` rows, with no diff."""
    base = snap(layer(2, "Layer 1"), selected=2)

    result = capture(base, op("Add stroke", base, base), op("Add stroke", base, base))

    assert result.steps == [] and result.notices == []


def test_an_operation_outside_the_catalog_is_skipped_with_a_notice():
    base = snap(layer(2, "Layer 1"), selected=2)

    result = capture(base, op("Set property", base, base))

    assert result.steps == []
    assert result.notices == ["“Set property” cannot be recorded, so it was skipped."]


def test_deleting_an_existing_layer_is_skipped_with_a_notice():
    before = snap(OLD, BASE, selected=9)
    after = snap(BASE, selected=1)

    result = capture(before, op("Remove layer(s)", before, after))

    assert result.steps == [] and len(result.notices) == 1


def test_a_layer_created_and_deleted_again_leaves_nothing():
    base, add = new_fill()
    with_mask = snap(layer(2, "Fill layer 1", "fill", mask="black"), BASE, selected=2)

    steps = capture(
        base, add, op("Add black mask", add.after, with_mask), op("Remove layer(s)", with_mask, snap(BASE, selected=1))
    ).steps

    assert steps == []


def test_moving_layers_is_skipped_with_a_notice():
    before = snap(layer(2, "A"), BASE, selected=2)
    after = snap(BASE, layer(2, "A"), selected=2)

    result = capture(before, op("Move layer(s)", before, after))

    assert result.steps == [] and result.notices == ["Moving layers cannot be recorded, so it was skipped."]


def test_renaming_a_new_layer_names_its_step():
    base, add = new_fill()
    renamed = snap(layer(2, "Grime", "fill"), BASE, selected=2)

    steps = capture(base, add, op("label", add.after, renamed)).steps

    assert steps == [{"type": "add_layer", "layer": "fill", "name": "Grime"}]


def test_renaming_an_existing_layer_is_skipped_with_a_notice():
    before = snap(BASE, selected=1)
    after = snap(layer(1, "Renamed"), selected=1)

    result = capture(before, op("label", before, after))

    assert result.steps == [] and len(result.notices) == 1


def test_a_white_mask_is_told_apart_by_the_command_name():
    """Painter's API says only that a layer has a mask; the command clicked says which."""
    base, add = new_fill()
    masked = snap(layer(2, "Fill layer 1", "fill", mask="on"), BASE, selected=2)

    white = capture(base, add, op("Add mask", add.after, masked, name="Add white mask")).steps
    black = capture(base, add, op("Add mask", add.after, masked, name="Add black mask")).steps

    assert white[-1] == {"type": "add_mask", "background": "white"}
    assert black[-1] == {"type": "add_mask", "background": "black"}


def test_effects_on_the_layer_and_unknown_effect_kinds():
    base, add = new_fill()
    with_levels = snap(layer(2, "Fill layer 1", "fill"), effect(3, "Levels", "levels", 2, stack="content"), BASE)
    with_compare = snap(
        layer(2, "Fill layer 1", "fill"), effect(3, "Levels", "levels", 2, stack="content"),
        effect(4, "Compare mask", "compare_mask", 2, stack="content"), BASE,
    )

    result = capture(base, add, op("Add levels", add.after, with_levels), op("Add compare mask", with_levels, with_compare))

    assert result.steps[-1] == {"type": "add_effect", "effect": "levels", "target": "layer"}
    assert result.notices == ["“Add compare mask” cannot be recorded, so it was skipped."]


def test_a_generator_without_its_source_yet_is_left_for_the_user():
    base, add = new_fill()
    masked = snap(layer(2, "Fill layer 1", "fill", mask="black"), BASE)
    empty = snap(layer(2, "Fill layer 1", "fill", mask="black"), effect(3, "Generator (empty)", "generator", 2), BASE)

    steps = capture(base, add, op("Add black mask", add.after, masked), op("Add generator", masked, empty)).steps

    assert steps[-1] == {"type": "add_effect", "effect": "generator", "target": "mask"}


def test_changing_an_existing_effect_is_skipped_with_a_notice():
    before = snap(layer(1, "Base", mask="black"), effect(3, "Dirt", "generator", 1, source=DIRT), selected=1)
    after = snap(layer(1, "Base", mask="black"), effect(3, "Rust", "generator", 1, source=RUST), selected=1)

    result = capture(before, op("Set generator", before, after))

    assert result.steps == [] and len(result.notices) == 1


def test_shelf_plus_own_workflows_are_skipped():
    before = snap(BASE, selected=1)
    after = snap(layer(2, "Fill layer 1", "fill"), BASE, selected=2)

    result = capture(before, Op("Shelf+: Fill layer", [], before, after, skipped="Shelf+'s own Workflows are not recorded."))

    assert result.steps == [] and result.notices == ["Shelf+'s own Workflows are not recorded."]


# -- what cannot be recorded fully --------------------------------------------------------


def test_a_smart_mask_is_added_without_its_resource():
    """Probe problem 3: only a Mask Editor generator (plus the new mask) shows."""
    base, add = new_fill()
    dropped = snap(layer(2, "Fill layer 1", "fill", mask="on"), effect(3, "Mask Editor", "generator", 2), BASE)

    steps = capture(base, add, op("Drop resource on new mask", add.after, dropped)).steps

    assert steps == [{"type": "add_layer", "layer": "fill"}, {"type": "add_smart", "smart": "mask"}]


def test_a_smart_material_is_named_after_its_folder():
    before = snap(BASE, selected=1)
    after = snap(layer(5, "Rust Iron", "folder"), layer(6, "Rust", "fill", parent=5), BASE, selected=5)

    (step,) = capture(before, op("Drop layer preset", before, after)).steps

    assert step == {"type": "add_smart", "smart": "material", "resource": "", "resource_name": "Rust Iron"}


def test_a_smart_material_dropped_just_before_takes_the_dropped_resource():
    before = snap(BASE, selected=1)
    after = snap(layer(5, "Rust Iron", "folder"), layer(6, "Rust", "fill", parent=5), BASE, selected=5)

    (step,) = capture(before, op("Drop layer preset", before, after, drops=(DIRT, RUST))).steps

    assert step["resource"] == RUST


# -- selection (R8.6) -------------------------------------------------------------------


def test_steps_on_another_existing_layer_get_a_select_layer_step():
    before = snap(OLD, BASE, selected=1)
    after = snap(changed(OLD, mask="black"), BASE, selected=9)

    steps = capture(before, op("Add black mask", before, after)).steps

    assert steps == [{"type": "select_layer", "name": "Old layer"}, {"type": "add_mask", "background": "black"}]


def test_steps_on_the_start_layer_join_the_start_block():
    """After a new layer, going back to the start layer: no select_layer, the Step acts on
    the layer selected when the Workflow starts."""
    base, add = new_fill()
    on_base = snap(layer(2, "Fill layer 1", "fill"), changed(BASE, mask="black"), selected=1)

    steps = capture(base, add, op("Add black mask", add.after, on_base)).steps

    assert steps == [{"type": "add_mask", "background": "black"}, {"type": "add_layer", "layer": "fill"}]


def test_steps_on_an_earlier_new_layer_join_its_block():
    s0 = snap(BASE, selected=1)
    s1 = snap(layer(2, "Fill layer 1", "fill"), BASE, selected=2)
    s2 = snap(layer(3, "Layer 1", "paint"), layer(2, "Fill layer 1", "fill"), BASE, selected=3)
    s3 = snap(layer(3, "Layer 1", "paint"), layer(2, "Fill layer 1", "fill", mask="black"), BASE, selected=2)

    steps = capture(s0, op("Add fill layer", s0, s1), op("Add layer", s1, s2), op("Add black mask", s2, s3)).steps

    assert steps == [
        {"type": "add_layer", "layer": "fill"},
        {"type": "add_mask", "background": "black"},
        {"type": "add_layer", "layer": "paint"},
    ]


def test_a_new_layer_above_another_existing_layer_selects_it_first():
    before = snap(BASE, OLD, selected=9)
    after = snap(BASE, layer(2, "Fill layer 1", "fill"), OLD, selected=2)

    steps = capture(snap(BASE, OLD, selected=1), op("Add fill layer", before, after)).steps

    assert steps == [{"type": "select_layer", "name": "Old layer"}, {"type": "add_layer", "layer": "fill"}]


def test_an_existing_layer_selected_at_the_end_is_a_select_layer_step():
    base = snap(OLD, BASE, selected=1)

    steps = capture(base, final=snap(OLD, BASE, selected=9)).steps

    assert steps == [{"type": "select_layer", "name": "Old layer"}]


def test_ending_on_the_start_layer_or_a_new_one_adds_nothing():
    base, add = new_fill()

    assert capture(base, add, final=add.after).steps == [{"type": "add_layer", "layer": "fill"}]
    assert capture(base, final=base).steps == []


def test_a_layer_name_used_twice_is_mentioned():
    twin = layer(8, "Old layer", kind="fill")
    before = snap(OLD, twin, BASE, selected=1)
    after = snap(changed(OLD, mask="black"), twin, BASE, selected=9)

    result = capture(before, op("Add black mask", before, after))

    assert result.steps[0] == {"type": "select_layer", "name": "Old layer"}
    assert any("Several layers are named “Old layer”" in n for n in result.notices)


# -- window and Assets-view commands ------------------------------------------------------


def test_commands_that_only_open_windows_are_not_names():
    assert is_window_action(MenuAction("smart_masks_action", "Smart masks"))
    assert is_window_action(MenuAction("", "Log", ("Window", "Views")))
    assert not is_window_action(MenuAction("", "Add black mask"))
    assert not is_window_action(MenuAction("save_action", "Save", ("File",)))


def test_a_new_layer_above_the_start_layer_runs_first_so_later_ones_go_above_it():
    """Fill A above the start layer, the start layer selected again, Fill B: Painter has
    A, B, start. Replayed, B's block comes first, so A goes above it."""
    s0 = snap(BASE, selected=1)
    s1 = snap(layer(2, "A", "fill"), BASE, selected=2)
    s2 = snap(layer(2, "A", "fill"), layer(3, "B", "paint"), BASE, selected=3)

    steps = capture(s0, op("Add fill layer", s0, s1), op("Add layer", s1, s2)).steps

    assert steps == [{"type": "add_layer", "layer": "paint"}, {"type": "add_layer", "layer": "fill"}]


def test_a_new_layer_above_an_earlier_new_layer_runs_right_after_it():
    s0 = snap(BASE, selected=1)
    s1 = snap(layer(2, "A", "fill"), BASE, selected=2)
    s2 = snap(layer(3, "C", "folder"), layer(2, "A", "fill"), BASE, selected=3)
    s3 = snap(layer(3, "C", "folder"), layer(4, "B", "paint"), layer(2, "A", "fill"), BASE, selected=4)

    steps = capture(s0, op("Add fill layer", s0, s1), op("Add group", s1, s2), op("Add layer", s2, s3)).steps

    assert [s["layer"] for s in steps] == ["fill", "paint", "folder"]


def test_only_the_last_rows_text_changing_is_a_merge():
    from shelfplus_app.core.recording import MERGE

    before = (("Add fill layer", "set blending opacity"), 2)
    assert history_event(before, (("Add fill layer", "set blending opacity 50%"), 2)) == (MERGE, None, 0)
