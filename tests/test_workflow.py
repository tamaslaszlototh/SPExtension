"""The Workflow runner (PRD R4) against a fake layer stack: preflight, one outer
ScopedModification, the Current layer, the final selection, then the UI Steps."""

import pytest

from shelfplus_app.adapter.fake import FakeAdapter, FakeLayer, FakeResource
from shelfplus_app.core.menu import MenuAction
from shelfplus_app.core.steps import DONE, FAILED, MISSING, StepResult
from shelfplus_app.core.workflow import run_workflow, step_label

FILL = {"type": "add_layer", "layer": "fill"}
PAINT = {"type": "add_layer", "layer": "paint"}
FOLDER = {"type": "add_layer", "layer": "folder"}
BLACK = {"type": "add_mask", "background": "black"}
WHITE = {"type": "add_mask", "background": "white"}
SAVE = {"type": "save"}


def select(name):
    return {"type": "select_layer", "name": name}


@pytest.fixture
def base():
    return FakeLayer("Base")


@pytest.fixture
def inner():
    return FakeLayer("Inner")


@pytest.fixture
def folder(inner):
    return FakeLayer("Folder", "folder", [inner])


@pytest.fixture
def adapter(base, folder):
    adapter = FakeAdapter()
    adapter.project_is_open = True
    adapter.stack.layers = [folder, base]
    return adapter


def run(adapter, steps, name=None, ui_steps=None):
    results = []
    handle = run_workflow(adapter, steps, results.append, ui_steps=ui_steps, name=name)
    return results, handle


def result(adapter, steps, **kwargs):
    results, _ = run(adapter, steps, **kwargs)
    assert len(results) == 1
    return results[0]


class TestInsertionPosition:
    def test_above_the_selected_layer(self, adapter, base):
        adapter.stack.selected = base

        assert result(adapter, [FILL]).ok
        assert adapter.stack.names() == [("Folder", ["Inner"]), "Fill layer", "Base"]

    def test_above_a_selected_layer_inside_a_folder_stays_in_the_folder(self, adapter, inner):
        adapter.stack.selected = inner

        assert result(adapter, [PAINT]).ok
        assert adapter.stack.names() == [("Folder", ["Layer", "Inner"]), "Base"]

    def test_above_a_selected_folder_not_inside_it(self, adapter, folder):
        adapter.stack.selected = folder

        assert result(adapter, [FILL]).ok
        assert adapter.stack.names() == ["Fill layer", ("Folder", ["Inner"]), "Base"]

    def test_on_top_of_the_stack_with_nothing_selected(self, adapter):
        assert result(adapter, [FILL]).ok
        assert adapter.stack.names() == ["Fill layer", ("Folder", ["Inner"]), "Base"]

    def test_on_an_empty_stack(self, adapter):
        adapter.stack.layers = []

        assert result(adapter, [FOLDER]).ok
        assert adapter.stack.names() == [("Folder", [])]

    def test_optional_name(self, adapter):
        assert result(adapter, [{"type": "add_layer", "layer": "paint", "name": "Dirt"}]).ok
        assert adapter.stack.layers[0].name == "Dirt"


class TestCurrentLayer:
    def test_a_new_layer_becomes_the_current_layer(self, adapter, base):
        adapter.stack.selected = base

        assert result(adapter, [FILL, BLACK, PAINT, WHITE]).ok

        assert adapter.stack.names() == [("Folder", ["Inner"]), "Layer", "Fill layer", "Base"]
        paint, fill = adapter.stack.layers[1], adapter.stack.layers[2]
        assert (fill.mask, paint.mask, base.mask) == ("black", "white", None)

    def test_acting_steps_act_on_the_selected_layer(self, adapter, base):
        adapter.stack.selected = base
        steps = [
            BLACK,
            {"type": "set_blend", "blend": "Multiply"},
            {"type": "set_opacity", "opacity": {"BaseColor": 40, "Roughness": 100}},
        ]

        assert result(adapter, steps).ok
        assert (base.mask, base.blend, base.opacity) == ("black", "Multiply", {"BaseColor": 40, "Roughness": 100})

    def test_select_layer_moves_the_current_layer(self, adapter, base, inner):
        adapter.stack.selected = base

        assert result(adapter, [select("Inner"), BLACK, FILL]).ok
        assert inner.mask == "black" and base.mask is None
        assert adapter.stack.names() == [("Folder", ["Fill layer", "Inner"]), "Base"]

    def test_select_layer_finds_folders(self, adapter, folder):
        assert result(adapter, [select("Folder"), BLACK]).ok
        assert folder.mask == "black"


class TestOneUndo:
    def test_all_layer_steps_in_one_scope(self, adapter, base):
        adapter.stack.selected = base

        assert result(adapter, [FILL, BLACK, PAINT], name="Setup").ok
        assert adapter.stack.scopes == ["Shelf+: Setup"]
        assert adapter.stack.changes == 3

    def test_no_scope_without_layer_steps(self, adapter):
        assert result(adapter, [SAVE]).ok
        assert adapter.stack.scopes == []

    def test_the_selection_never_changes_inside_the_scope(self, adapter, base):
        """The fake raises like Painter on a selection change inside the scope."""
        adapter.stack.selected = base

        assert result(adapter, [FILL, select("Base"), PAINT, select("Inner"), BLACK]).ok


class TestFinalSelection:
    def test_the_new_layer_is_selected_after_the_scope(self, adapter, base):
        adapter.stack.selected = base

        result(adapter, [FILL, BLACK])

        assert adapter.stack.selected is adapter.stack.layers[1]
        assert adapter.stack.selected.name == "Fill layer"

    def test_the_layer_picked_by_name_is_selected(self, adapter, base, inner):
        adapter.stack.selected = base

        result(adapter, [select("Inner"), BLACK])

        assert adapter.stack.selected is inner

    def test_the_selection_is_left_alone_when_only_acting_on_it(self, adapter, base, monkeypatch):
        """Painter may have the layer's mask selected; re-selecting the layer would move it."""
        adapter.stack.selected = base
        selects = []
        monkeypatch.setattr(adapter, "select_layer", selects.append)

        assert result(adapter, [BLACK]).ok
        assert selects == []

    def test_a_failed_select_after_the_scope_does_not_fail_the_workflow(self, adapter, base, monkeypatch):
        adapter.stack.selected = base

        def refuse(layer):
            raise RuntimeError("no")

        monkeypatch.setattr(adapter, "select_layer", refuse)

        assert result(adapter, [FILL]).ok


class TestSelectLayer:
    def test_one_match(self, adapter, base):
        assert result(adapter, [select("Base"), BLACK]).ok
        assert base.mask == "black"

    def test_no_match_fails_naming_the_step(self, adapter):
        failed = result(adapter, [FILL, select("Dirt"), BLACK], name="Dirt mask")

        assert failed.state == FAILED
        assert failed.message == "“Dirt mask” stopped at Step 2 (Select layer “Dirt”): No layer named “Dirt”."

    def test_several_matches_fail(self, adapter, base):
        adapter.stack.layers.append(FakeLayer("Base"))

        failed = result(adapter, [select("Base"), BLACK], name="W")

        assert failed.state == FAILED
        assert failed.message == "“W” stopped at Step 1 (Select layer “Base”): Several layers named “Base”."
        assert base.mask is None

    def test_exact_match_only(self, adapter):
        failed = result(adapter, [select("base")])

        assert failed.state == FAILED and "No layer named “base”" in failed.message


class TestMidRunFailure:
    def test_stops_at_the_failing_step_and_keeps_earlier_changes(self, adapter, base):
        adapter.stack.selected = base
        adapter.stack.fail_on = "add_mask"
        saved = []

        failed = result(adapter, [FILL, BLACK, PAINT, SAVE], name="W", ui_steps={"save": lambda a, s, d: saved.append(s)})

        assert failed.state == FAILED
        assert failed.message.startswith("“W” stopped at Step 2 (Add black mask): ")
        assert adapter.stack.names() == [("Folder", ["Inner"]), "Fill layer", "Base"]
        assert adapter.stack.scopes == ["Shelf+: W"] and not adapter.stack.in_scope
        assert saved == []

    def test_the_current_layer_so_far_is_selected(self, adapter, base):
        adapter.stack.selected = base
        adapter.stack.fail_on = "add_mask"

        result(adapter, [FILL, BLACK])

        assert adapter.stack.selected.name == "Fill layer"

    def test_a_failing_ui_step_stops_the_rest(self, adapter):
        adapter.actions = [MenuAction("x", "X")]
        calls = []

        def fail(a, step, done):
            calls.append("fail")
            done(StepResult(FAILED, "Painter said no."))

        def ok(a, step, done):
            calls.append("ok")
            done(StepResult(DONE))

        failed = result(
            adapter,
            [{"type": "run_action", "action": "x"}, SAVE],
            name="W",
            ui_steps={"run_action": fail, "save": ok},
        )

        assert calls == ["fail"]
        assert failed.message == "“W” stopped at Step 1 (Run menu command): Painter said no."

    def test_a_failing_save(self, adapter):
        adapter.save_error = RuntimeError("The project is locked.")

        failed = result(adapter, [SAVE], name="Save")

        assert failed.state == FAILED
        assert failed.message == "“Save” stopped at Step 1 (Save): The project is locked."


class TestPreflight:
    """On any failure nothing changes, and the message names the Step and what is missing."""

    def untouched(self, adapter, before):
        assert adapter.stack.names() == before
        assert adapter.stack.scopes == [] and adapter.stack.changes == 0 and adapter.saves == 0

    def test_no_project(self, adapter):
        adapter.project_is_open = False
        before = adapter.stack.names()

        failed = result(adapter, [FILL, SAVE], name="W")

        assert failed.state == FAILED
        assert failed.message == "“W” did not start: open a project first."
        self.untouched(adapter, before)

    def test_project_not_in_edition_state(self, adapter):
        adapter.edition = False

        failed = result(adapter, [SAVE], name="W")

        assert failed.state == FAILED and "did not start" in failed.message

    def test_the_first_block_needs_a_selected_layer(self, adapter):
        before = adapter.stack.names()

        failed = result(adapter, [BLACK, FILL], name="W")

        assert failed.message == "“W” did not start: Step 1 (Add black mask) needs a selected layer."
        self.untouched(adapter, before)

    def test_an_unreadable_selection_stops_it(self, adapter, monkeypatch):
        """Not read as "nothing selected", which would put the layer on top of the stack."""
        before = adapter.stack.names()

        def broken():
            raise AttributeError("no get_active_stack")

        monkeypatch.setattr(adapter, "selected_layer", broken)

        failed = result(adapter, [FILL, BLACK], name="W")

        assert failed.message == "“W” did not start: Painter's selected layer could not be read. See the log."
        self.untouched(adapter, before)

    def test_no_selection_needed_when_a_layer_is_created_first(self, adapter):
        assert result(adapter, [FILL, BLACK]).ok

    def test_no_selection_needed_after_select_layer(self, adapter):
        assert result(adapter, [select("Base"), BLACK]).ok

    def test_missing_resource(self, adapter, base):
        adapter.stack.selected = base
        before = adapter.stack.names()
        steps = [FILL, {"type": "select_brush", "resource": "resource://a/Gone"}]

        failed = result(adapter, steps, name="W", ui_steps={"select_brush": lambda a, s, d: d(StepResult(DONE))})

        assert failed.state == MISSING
        assert failed.message == (
            "“W” did not start: Step 2 (Select brush): This brush is not available on this machine: resource://a/Gone"
        )
        self.untouched(adapter, before)

    def test_found_resource(self, adapter):
        adapter.add_resource(FakeResource("resource://a/Hard", "Hard"))
        steps = [{"type": "select_brush", "resource": "resource://a/Hard"}]

        assert result(adapter, steps, ui_steps={"select_brush": lambda a, s, d: d(StepResult(DONE))}).ok

    def test_missing_menu_command(self, adapter):
        before = adapter.stack.names()
        steps = [FILL, {"type": "run_action", "action": "bake_all"}]

        failed = result(adapter, steps, name="W", ui_steps={"run_action": lambda a, s, d: d(StepResult(DONE))})

        assert failed.state == MISSING
        assert "Step 2 (Run menu command)" in failed.message and "bake_all" in failed.message
        self.untouched(adapter, before)

    def test_a_layer_step_after_a_ui_step(self, adapter):
        before = adapter.stack.names()

        failed = result(adapter, [SAVE, FILL], name="W")

        assert failed.message == (
            "“W” did not start: Step 2 (Add Fill layer) must come before the brush, menu and save Steps."
        )
        self.untouched(adapter, before)

    def test_a_step_this_version_cannot_run(self, adapter):
        before = adapter.stack.names()
        steps = [FILL, {"type": "add_sticker"}]

        failed = result(adapter, steps, name="W")

        assert failed.message == "“W” did not start: Step 2 (add_sticker) is not available in this version of Shelf+."
        self.untouched(adapter, before)

    def test_a_single_step_button_shows_the_step_message_alone(self, adapter):
        """A Brush or Menu button is a one-Step Workflow: its message has no Step prefix."""
        steps = [{"type": "run_action", "action": "bake_all"}]

        failed = result(adapter, steps, ui_steps={"run_action": lambda a, s, d: d(StepResult(DONE))})

        assert failed.message == "This menu command is not available in this Painter version: bake_all"

    def test_ui_steps_without_a_project_need_none(self, adapter):
        adapter.project_is_open = False
        ran = []

        steps = [{"type": "run_action", "action": "x"}]
        adapter.actions = [MenuAction("x", "X")]

        assert result(adapter, steps, ui_steps={"run_action": lambda a, s, d: (ran.append(s), d(StepResult(DONE)))}).ok
        assert ran == steps


class TestUiSteps:
    def test_run_after_the_selection(self, adapter, base):
        adapter.stack.selected = base
        seen = []

        def save(a, step, done):
            seen.append((a.stack.in_scope, a.stack.selected.name))
            done(StepResult(DONE))

        assert result(adapter, [FILL, SAVE], ui_steps={"save": save}).ok
        assert seen == [(False, "Fill layer")]

    def test_the_default_save_step_saves(self, adapter):
        assert result(adapter, [SAVE]).ok
        assert adapter.saves == 1

    def test_asynchronous_steps_chain_and_can_be_cancelled(self, adapter):
        pending = []

        class Handle:
            cancelled = False

            def cancel(self):
                self.cancelled = True

        def later(a, step, done):
            pending.append(done)
            return Handle()

        results, handle = run(adapter, [SAVE, SAVE], ui_steps={"save": later})

        assert results == [] and len(pending) == 1
        pending[0](StepResult(DONE))
        assert results == [] and len(pending) == 2
        pending[1](StepResult(DONE))
        assert [r.state for r in results] == [DONE]

        results, handle = run(adapter, [SAVE], ui_steps={"save": later})
        handle.cancel()
        assert results == []

    def test_synchronous_runs_return_no_handle(self, adapter):
        results, handle = run(adapter, [SAVE])

        assert handle is None and results[0].ok


def test_step_labels():
    assert step_label(FILL) == "Add Fill layer"
    assert step_label(PAINT) == "Add Paint layer"
    assert step_label(FOLDER) == "Add folder"
    assert step_label(WHITE) == "Add white mask"
    assert step_label({"type": "set_blend", "blend": "Multiply"}) == "Set blend mode to Multiply"
    assert step_label({"type": "set_opacity", "opacity": {"BaseColor": 50}}) == "Set opacity"
    assert step_label(select("Dirt")) == "Select layer “Dirt”"
    assert step_label(SAVE) == "Save"
    assert step_label({"type": "explode"}) == "explode"
