"""The Workflow editor's layer-block tree (PRD R7.2, R7.3): the flat ``steps[]`` the
runner reads, drawn and edited as blocks. Pure functions, no Qt."""

from shelfplus_app.core import blocks

FILL = {"type": "add_layer", "layer": "fill"}
PAINT = {"type": "add_layer", "layer": "paint"}
BLACK = {"type": "add_mask", "background": "black"}
DIRT = {"type": "add_effect", "effect": "generator", "target": "mask", "resource": "resource://starter_assets/Dirt"}
OPACITY = {"type": "set_opacity", "opacity": {"BaseColor": 50}}
PICK = {"type": "select_layer", "name": "Base"}
SAVE = {"type": "save"}
BRUSH = {"type": "select_brush", "resource": "resource://starter_assets/Basic Hard"}


def shape(rows):
    """Rows as short text: ``start``, ``end``, ``H:<type>``, ``  <type>``."""
    out = []
    for row in rows:
        if row.kind in (blocks.START, blocks.END):
            out.append(row.kind)
        elif row.kind == blocks.HEADER:
            out.append(f"H{row.index}")
        else:
            out.append(f"  {row.index}")
    return out


# -- flat list -> block tree -----------------------------------------------------


def test_steps_are_grouped_under_the_layer_they_create_or_pick():
    steps = [FILL, BLACK, DIRT, PICK, OPACITY, SAVE]

    assert shape(blocks.rows(steps)) == ["H0", "  1", "  2", "H3", "  4", "end", "  5"]


def test_the_start_block_is_shown_only_when_it_has_steps_or_while_dragging():
    assert shape(blocks.rows([FILL, BLACK])) == ["H0", "  1", "end"]
    assert shape(blocks.rows([FILL, BLACK], dragging=True)) == ["start", "H0", "  1", "end"]
    assert shape(blocks.rows([OPACITY, FILL])) == ["start", "  0", "H1", "end"]


def test_a_smart_material_is_a_header_but_a_smart_mask_acts_on_the_current_layer():
    material = {"type": "add_smart", "smart": "material", "resource": "resource://a/M"}
    mask = {"type": "add_smart", "smart": "mask", "resource": "resource://a/S"}

    assert shape(blocks.rows([material, mask])) == ["H0", "  1", "end"]


def test_a_ui_step_written_among_the_layer_steps_is_drawn_in_the_end_section():
    assert shape(blocks.rows([FILL, SAVE, BLACK])) == ["H0", "  2", "end", "  1"]
    assert blocks.normalized([FILL, SAVE, BLACK]) == [FILL, BLACK, SAVE]


# -- deleting --------------------------------------------------------------------


def test_deleting_a_step_removes_only_it():
    assert blocks.delete([FILL, BLACK, DIRT], 1) == [FILL, DIRT]


def test_deleting_a_header_removes_its_whole_block():
    steps = [OPACITY, FILL, BLACK, DIRT, PAINT, SAVE]

    assert blocks.delete(steps, 1) == [OPACITY, PAINT, SAVE]
    assert blocks.block_size(steps, 1) == 2
    assert blocks.block_size(steps, 4) == 0
    assert blocks.block_size(steps, 2) == 0  # not a header


# -- moving with up / down ---------------------------------------------------------


def test_up_and_down_move_an_acting_step_within_and_across_blocks():
    steps = [FILL, BLACK, DIRT, PAINT, OPACITY, SAVE]

    assert blocks.move_up(steps, 2) == [FILL, DIRT, BLACK, PAINT, OPACITY, SAVE]
    assert blocks.move_down(steps, 2) == [FILL, BLACK, PAINT, DIRT, OPACITY, SAVE]  # into the next block
    assert blocks.move_up(steps, 4) == [FILL, BLACK, DIRT, OPACITY, PAINT, SAVE]  # into the block above
    assert blocks.move_up([FILL, BLACK], 1) == [BLACK, FILL]  # into the Start block


def test_an_acting_step_cannot_move_into_the_end_section_or_above_the_start():
    assert blocks.move_down([FILL, BLACK, SAVE], 1) is None
    assert blocks.move_up([BLACK, FILL], 0) is None


def test_up_and_down_on_a_header_move_its_whole_block():
    steps = [OPACITY, FILL, BLACK, PAINT, DIRT, SAVE]

    assert blocks.move_up(steps, 3) == [OPACITY, PAINT, DIRT, FILL, BLACK, SAVE]
    assert blocks.move_down(steps, 1) == [OPACITY, PAINT, DIRT, FILL, BLACK, SAVE]
    assert blocks.move_up(steps, 1) is None  # the first block; the Start block stays first
    assert blocks.move_down(steps, 3) is None


def test_ui_steps_move_only_within_the_end_section():
    steps = [FILL, BRUSH, SAVE]

    assert blocks.move_down(steps, 1) == [FILL, SAVE, BRUSH]
    assert blocks.move_up(steps, 1) is None
    assert blocks.move_down(steps, 2) is None


# -- dragging ----------------------------------------------------------------------
#
# A drop lands in a gap of the rows drawn while dragging (the Start block is shown):
# gap g is above row g; gap len(rows) is below the last row.


def gap_above(steps, wanted):
    """The gap above the row drawn as ``wanted`` (see ``shape``) while dragging."""
    return shape(blocks.rows(steps, dragging=True)).index(wanted)


def test_dropping_a_step_into_another_block_retargets_it():
    steps = [FILL, BLACK, PAINT, OPACITY, SAVE]
    # rows: start, H0, 1, H2, 3, end, 4

    assert blocks.drop(steps, 1, gap_above(steps, "  3")) == [FILL, PAINT, BLACK, OPACITY, SAVE]
    assert blocks.drop(steps, 3, gap_above(steps, "H2")) == [FILL, BLACK, OPACITY, PAINT, SAVE]


def test_dropping_a_step_into_the_empty_start_block():
    steps = [FILL, BLACK]
    # rows: start, H0, 1, end

    assert blocks.drop(steps, 1, gap_above(steps, "H0")) == [BLACK, FILL]
    assert blocks.drop(steps, 1, 0) == [BLACK, FILL]  # above the Start block's title


def test_dragging_a_header_moves_its_whole_block_between_blocks():
    steps = [OPACITY, FILL, BLACK, PAINT, DIRT, SAVE]
    # rows: start, 0, H1, 2, H3, 4, end, 5

    assert blocks.drop(steps, 3, gap_above(steps, "H1")) == [OPACITY, PAINT, DIRT, FILL, BLACK, SAVE]
    assert blocks.drop(steps, 1, gap_above(steps, "end")) == [OPACITY, PAINT, DIRT, FILL, BLACK, SAVE]
    assert blocks.drop(steps, 1, gap_above(steps, "H3")) == steps  # where it already is


def test_a_header_dropped_inside_a_block_snaps_back():
    steps = [OPACITY, FILL, BLACK, PAINT, DIRT, SAVE]

    assert blocks.drop(steps, 3, gap_above(steps, "  2")) is None  # blocks cannot nest
    assert blocks.drop(steps, 3, gap_above(steps, "  0")) is None  # would take the Start block's Steps
    assert blocks.drop(steps, 1, gap_above(steps, "  5")) is None  # into the end section


def test_a_step_dropped_into_the_end_section_snaps_back():
    steps = [FILL, BLACK, SAVE]

    assert blocks.drop(steps, 1, gap_above(steps, "  2")) is None
    assert blocks.drop(steps, 1, len(blocks.rows(steps, dragging=True))) is None


def test_a_ui_step_dragged_out_of_the_end_section_snaps_back():
    steps = [FILL, BLACK, BRUSH, SAVE]

    assert blocks.drop(steps, 3, gap_above(steps, "  1")) is None
    assert blocks.drop(steps, 3, gap_above(steps, "  2")) == [FILL, BLACK, SAVE, BRUSH]
    assert blocks.drop(steps, 2, len(blocks.rows(steps, dragging=True))) == [FILL, BLACK, SAVE, BRUSH]


# -- adding by hand (R7.3) ---------------------------------------------------------


def test_a_creating_step_becomes_a_new_block_after_the_last_one():
    steps, index = blocks.insert([FILL, BLACK, SAVE], PAINT, selected=1)

    assert (steps, index) == ([FILL, BLACK, PAINT, SAVE], 2)


def test_an_acting_step_goes_to_the_end_of_the_selected_rows_block():
    steps = [FILL, BLACK, PAINT, SAVE]

    assert blocks.insert(steps, DIRT, selected=0) == ([FILL, BLACK, DIRT, PAINT, SAVE], 2)
    assert blocks.insert(steps, DIRT, selected=1) == ([FILL, BLACK, DIRT, PAINT, SAVE], 2)


def test_an_acting_step_goes_to_the_last_block_when_nothing_or_a_ui_step_is_selected():
    steps = [FILL, BLACK, PAINT, SAVE]

    assert blocks.insert(steps, DIRT) == ([FILL, BLACK, PAINT, DIRT, SAVE], 3)
    assert blocks.insert(steps, DIRT, selected=3) == ([FILL, BLACK, PAINT, DIRT, SAVE], 3)
    assert blocks.insert([SAVE], BLACK) == ([BLACK, SAVE], 0)  # no block: the Start block


def test_an_acting_step_with_the_start_block_selected_stays_there():
    assert blocks.insert([OPACITY, FILL], BLACK, selected=0) == ([OPACITY, BLACK, FILL], 1)


def test_a_ui_step_goes_to_the_end_section():
    assert blocks.insert([FILL, SAVE], BRUSH, selected=0) == ([FILL, SAVE, BRUSH], 2)
