"""One Recording over the fake adapter: History signals, undo/redo, the debounced layer
stack event, texture set switches, a locked project, names from commands and drops."""

import pytest

from shelfplus_app.adapter.fake import FakeAdapter, FakeEffect, FakeLayer
from shelfplus_app.core.menu import MenuAction
from shelfplus_app.core.recording import (
    DEBOUNCE_MS,
    NO_PROJECT,
    OTHER_STACK,
    OWN_WORKFLOW,
    RETRY_MS,
    UNREADABLE,
    Recording,
)

DIRT = "resource://starter_assets/Dirt"


class Clock:
    def __init__(self):
        self.ms = 0

    def __call__(self):
        return self.ms


@pytest.fixture
def adapter():
    adapter = FakeAdapter()
    adapter.project_is_open = True
    adapter.stack.layers = [FakeLayer("Base")]
    adapter.stack.selected = adapter.stack.layers[0]
    adapter.history = ["Open project"]
    adapter.history_index = 1
    return adapter


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def events():
    return {"changed": 0, "notices": [], "closing": 0}


@pytest.fixture
def recording(adapter, clock, events):
    def changed():
        events["changed"] += 1

    def closing():
        events["closing"] += 1

    rec = Recording(adapter, changed=changed, notify=events["notices"].append, closing=closing, now=clock)
    assert rec.start() is None
    return rec


def add_fill(adapter, label="Add fill layer"):
    stack = adapter.stack
    layer = FakeLayer("Fill layer 1", "fill")
    stack.layers.insert(stack.layers.index(stack.selected) if stack.selected in stack.layers else 0, layer)
    stack.selected = layer
    adapter.push_history(label)
    return layer


def add_mask(adapter, layer, background="black", label="Add black mask"):
    layer.mask = background
    adapter.push_history(label)


def test_it_needs_an_open_project(adapter):
    adapter.project_is_open = False

    assert Recording(adapter).start() == NO_PROJECT
    assert adapter.history_watchers == []


def test_each_history_row_is_diffed_into_steps(adapter, recording, events):
    layer = add_fill(adapter)
    add_mask(adapter, layer)

    assert recording.capture.steps == [{"type": "add_layer", "layer": "fill"}, {"type": "add_mask", "background": "black"}]
    assert events["changed"] == 2


def test_undo_leaves_a_step_out_and_redo_brings_it_back(adapter, recording):
    layer = add_fill(adapter)
    add_mask(adapter, layer)

    layer.mask = None
    adapter.undo_history()
    assert recording.capture.steps == [{"type": "add_layer", "layer": "fill"}]

    layer.mask = "black"
    adapter.redo_history()
    assert recording.capture.steps[-1] == {"type": "add_mask", "background": "black"}


def test_a_new_operation_with_the_undone_label_is_not_a_redo(adapter, recording):
    """Undo "Add fill layer", then add another fill: the History looks exactly as before
    the undo, but the new layer has a new uid."""
    first = add_fill(adapter)
    adapter.stack.layers.remove(first)
    adapter.stack.selected = adapter.stack.layers[0]
    adapter.undo_history()
    assert recording.capture.steps == []

    second = add_fill(adapter)

    assert second.uid != first.uid
    assert recording.capture.steps == [{"type": "add_layer", "layer": "fill"}]
    assert recording.ops[0].changes[0].uid == second.uid


def test_stop_returns_the_steps_and_unhooks(adapter, recording):
    add_fill(adapter)

    capture = recording.stop()

    assert capture.steps == [{"type": "add_layer", "layer": "fill"}]
    assert adapter.history_watchers == [] and adapter.stack_watchers == []
    assert adapter.closing_watchers == [] and adapter.drop_watchers == []
    adapter.push_history("Add fill layer")  # nothing listens any more


def test_a_change_without_a_history_row_yet_is_taken_at_stop(adapter, recording):
    layer = add_fill(adapter)
    layer.opacity = {"BaseColor": 50}  # still dragging: no History row

    assert recording.stop().steps[-1] == {"type": "set_opacity", "opacity": {"BaseColor": 50}}


def test_the_layer_selected_at_stop_is_a_select_layer_step(adapter):
    old = FakeLayer("Old layer", "fill")
    adapter.stack.layers.append(old)
    recording = Recording(adapter)
    recording.start()

    adapter.stack.selected = old

    assert recording.stop().steps == [{"type": "select_layer", "name": "Old layer"}]


def test_a_painting_stroke_gives_nothing(adapter, recording, events):
    adapter.push_history("Add stroke")

    assert recording.capture.steps == [] and events["notices"] == []


def test_an_unknown_operation_is_noticed_once(adapter, recording, events):
    adapter.push_history("Set property")
    adapter.push_history("Set property")

    assert events["notices"] == ["“Set property” cannot be recorded, so it was skipped."]


def test_shelf_plus_own_workflow_runs_are_skipped(adapter, recording, events):
    add_fill(adapter, label="Shelf+: Fill layer + Black mask")

    assert recording.capture.steps == [] and events["notices"] == [OWN_WORKFLOW]


def test_the_command_clicked_names_the_operation(adapter, recording, clock):
    """Painter's API says only "it has a mask"; the command clicked says which."""
    layer = add_fill(adapter)
    recording.command(MenuAction("", "Add white mask\n\nHold Alt…"))
    clock.ms += 100
    add_mask(adapter, layer, background="on", label="Add mask")

    assert recording.capture.steps[-1] == {"type": "add_mask", "background": "white"}


def test_a_command_from_long_ago_or_a_window_command_names_nothing(adapter, recording, clock):
    layer = add_fill(adapter)
    recording.command(MenuAction("", "Add white mask"))
    clock.ms += 10_000
    recording.command(MenuAction("smart_masks_action", "Smart masks"))
    add_mask(adapter, layer, background="on", label="Add mask")

    assert recording.capture.steps[-1] == {"type": "add_mask", "background": "black"}


def test_a_smart_material_dropped_onto_painter_takes_the_dropped_resource(adapter, recording):
    rust = "resource://starter_assets/Rust Iron"
    adapter.drop_on_painter([rust])
    folder = FakeLayer("Rust Iron", "folder", children=[FakeLayer("Rust", "fill")])
    adapter.stack.layers.insert(0, folder)
    adapter.push_history("Drop layer preset")

    assert recording.capture.steps == [
        {"type": "add_smart", "smart": "material", "resource": rust, "resource_name": "Rust Iron"}
    ]


def test_a_generator_source_set_later_updates_its_step(adapter, recording):
    layer = add_fill(adapter)
    add_mask(adapter, layer)
    generator = FakeEffect("mask", "generator", name="Generator (empty)")
    layer.effect_nodes.append(generator)
    adapter.push_history("Add generator")
    generator.name, generator.source = "Dirt", DIRT
    adapter.push_history("Set generator")

    assert recording.capture.steps[-1] == {
        "type": "add_effect", "effect": "generator", "target": "mask", "resource": DIRT, "resource_name": "Dirt",
    }
    assert len(recording.capture.steps) == 3


# -- the layer stack event and texture sets ---------------------------------------------


def test_the_layer_stack_event_is_debounced(adapter, recording):
    calls = []
    real = adapter.snapshot
    adapter.snapshot = lambda: calls.append(1) or real()
    for _ in range(5):
        adapter.layer_stack_changed()

    pending = [t for t in adapter.timers if t.active]
    assert len(pending) == 1 and pending[0].interval_ms == DEBOUNCE_MS
    adapter.fire_timers()
    assert len(calls) == 1


def test_work_in_another_texture_set_is_skipped_and_switching_takes_a_new_base(adapter, recording, events):
    coat = adapter.stack
    boots = type(coat)([FakeLayer("Boots base")])
    boots.selected = boots.layers[0]

    adapter.switch_texture_set("boots", boots)
    adapter.fire_timers()
    add_fill(adapter)
    assert recording.capture.steps == [] and OTHER_STACK in events["notices"]

    adapter.switch_texture_set("coat", coat)
    adapter.fire_timers()
    add_fill(adapter)
    assert recording.capture.steps == [{"type": "add_layer", "layer": "fill"}]


# -- robustness ------------------------------------------------------------------------


def test_a_locked_project_is_retried(adapter, recording):
    adapter.snapshot_errors = [RuntimeError("The project is locked."), RuntimeError("The project is locked.")]
    add_fill(adapter)
    assert recording.capture.steps == []

    retry = [t for t in adapter.timers if t.active]
    assert retry and retry[0].interval_ms == RETRY_MS
    adapter.fire_timers()
    adapter.fire_timers()

    assert recording.capture.steps == [{"type": "add_layer", "layer": "fill"}]


def test_a_stack_that_stays_unreadable_is_noticed(adapter, recording, events):
    adapter.snapshot_errors = [RuntimeError("The project is locked.")] * 100
    add_fill(adapter)
    for _ in range(100):
        adapter.fire_timers()

    assert UNREADABLE in events["notices"]


def test_the_project_closing_asks_the_app_to_stop(adapter, recording, events):
    adapter.close_project()

    assert events["closing"] == 1


def test_a_full_history_dropping_its_oldest_rows_keeps_their_steps(adapter, recording):
    """Painter's undo limit: each new row pushes the oldest one out."""
    layer = add_fill(adapter)

    def push_full(label):
        adapter.history = adapter.history[1:] + [label]
        adapter._history_changed()

    layer.mask = "black"
    push_full("Add black mask")
    layer.blend = "Multiply"
    push_full("set blending mode")  # now the "Add fill layer" row is gone too

    assert recording.capture.steps == [
        {"type": "add_layer", "layer": "fill"},
        {"type": "add_mask", "background": "black"},
        {"type": "set_blend", "blend": "Multiply"},
    ]
    layer.blend = "Normal"
    adapter.undo_history()
    assert recording.capture.steps[-1] == {"type": "add_mask", "background": "black"}


def test_the_layer_stack_event_also_handles_a_reading_left_waiting(adapter, recording):
    adapter.snapshot_errors = [RuntimeError("The project is locked.")]
    add_fill(adapter)
    assert recording.capture.steps == []

    adapter.layer_stack_changed()
    debounce = [t for t in adapter.timers if t.active and t.interval_ms == DEBOUNCE_MS]
    debounce[0].active = False
    debounce[0].callback()

    assert recording.capture.steps == [{"type": "add_layer", "layer": "fill"}]


def test_stop_uses_the_last_good_snapshot_when_the_project_cannot_be_read(adapter, recording):
    layer = add_fill(adapter)
    layer.opacity = {"BaseColor": 50}
    adapter.layer_stack_changed()
    adapter.fire_timers()  # the debounced event read the stack
    adapter.snapshot_errors = [RuntimeError("The project is closing.")]

    assert recording.stop().steps[-1] == {"type": "set_opacity", "opacity": {"BaseColor": 50}}
