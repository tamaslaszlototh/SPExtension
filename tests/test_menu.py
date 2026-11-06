"""Menu buttons without Painter (PRD R6): naming, the hook watcher, capture, the list, run_action."""

import pytest

from shelfplus_app.adapter.fake import FakeAdapter
from shelfplus_app.core.menu import (
    DEDUPE_MS,
    ActionWatcher,
    MenuAction,
    action_label,
    capture_problem,
    menu_button,
    run_action,
    search_actions,
)
from shelfplus_app.core.steps import DONE, FAILED, MISSING

SAVE = MenuAction("SAVE_PROJECT", "&Save", ("File",))
LOG = MenuAction("show_log", "Log", ("Window", "Views"))
ADD_LAYER = MenuAction("", "Add layer\n\nHold Alt to enable all channels")


class Clock:
    def __init__(self):
        self.ms = 0

    def __call__(self):
        return self.ms


# -- naming ---------------------------------------------------------------------


class TestNaming:
    @pytest.mark.parametrize(
        "text, label",
        [
            ("&Save", "Save"),
            ("Save &As...", "Save As..."),
            ("Fish && Chips", "Fish & Chips"),
            ("Add fill layer\n\nHold Alt to enable all channels", "Add fill layer"),
            ("Translate tool (<b>W</b>)", "Translate tool (W)"),
            ("  Bake   mesh maps ", "Bake mesh maps"),
            ("", ""),
        ],
    )
    def test_the_label_is_the_first_line_without_mnemonics_or_markup(self, text, label):
        assert action_label(text) == label

    def test_a_menu_button_stores_the_object_name_and_the_label(self):
        assert menu_button(SAVE) == {"kind": "menu", "name": "Save", "action": "SAVE_PROJECT"}

    def test_a_command_without_text_is_named_after_its_object_name(self):
        assert menu_button(MenuAction("export_textures", ""))["name"] == "export_textures"


# -- the hook watcher -----------------------------------------------------------


class TestActionWatcher:
    def test_each_hook_call_reaches_the_listener(self):
        seen = []
        watcher = ActionWatcher(seen.append)

        watcher.notify(SAVE)
        watcher.notify(LOG)

        assert seen == [SAVE, LOG]

    def test_one_click_reported_by_several_hooks_counts_once(self):
        # QAction.triggered and QMenu.triggered for the same click; on 12.2 also a
        # second menu (Views/Log + Window/Log).
        clock = Clock()
        seen = []
        watcher = ActionWatcher(seen.append, now=clock)

        watcher.notify(LOG)
        clock.ms += 5
        watcher.notify(MenuAction("show_log", "Log", ("View",)))
        watcher.notify(LOG)

        assert seen == [LOG]

    def test_the_same_command_again_after_the_window_counts_again(self):
        clock = Clock()
        seen = []
        watcher = ActionWatcher(seen.append, now=clock)

        watcher.notify(SAVE)
        clock.ms += DEDUPE_MS + 1
        watcher.notify(SAVE)

        assert seen == [SAVE, SAVE]

    def test_a_burst_of_duplicates_does_not_stretch_the_window(self):
        clock = Clock()
        seen = []
        watcher = ActionWatcher(seen.append, now=clock)

        watcher.notify(SAVE)
        for _ in range(3):
            clock.ms += DEDUPE_MS // 2
            watcher.notify(SAVE)

        assert seen == [SAVE, SAVE]  # the last call is a new click, past the first's window

    def test_different_commands_in_quick_succession_both_count(self):
        seen = []
        watcher = ActionWatcher(seen.append, now=Clock())

        watcher.notify(SAVE)
        watcher.notify(LOG)

        assert seen == [SAVE, LOG]

    def test_commands_without_an_object_name_are_told_apart_by_their_text(self):
        seen = []
        watcher = ActionWatcher(seen.append, now=Clock())

        watcher.notify(ADD_LAYER)
        watcher.notify(MenuAction("", "Add fill layer"))
        watcher.notify(ADD_LAYER)

        assert seen == [ADD_LAYER, MenuAction("", "Add fill layer")]

    def test_the_plugins_own_triggers_are_ignored(self):
        seen = []
        watcher = ActionWatcher(seen.append)

        with watcher.replaying():
            watcher.notify(SAVE)
            watcher.notify(SAVE)
        watcher.notify(LOG)

        assert seen == [LOG]

    def test_an_own_trigger_does_not_swallow_the_users_next_click(self):
        clock = Clock()
        seen = []
        watcher = ActionWatcher(seen.append, now=clock)

        with watcher.replaying():
            watcher.notify(SAVE)
        clock.ms += 1
        watcher.notify(SAVE)

        assert seen == [SAVE]

    def test_replaying_ends_even_if_the_trigger_raises(self):
        seen = []
        watcher = ActionWatcher(seen.append)

        with pytest.raises(RuntimeError), watcher.replaying():
            raise RuntimeError("trigger failed")
        watcher.notify(SAVE)

        assert seen == [SAVE]

    def test_without_a_listener_nothing_happens(self):
        ActionWatcher().notify(SAVE)

    def test_a_failing_listener_does_not_reach_painters_signal(self):
        def listener(action):
            raise ValueError("boom")

        ActionWatcher(listener).notify(SAVE)


# -- capture ----------------------------------------------------------------------


class TestCaptureProblem:
    def test_a_named_command_can_be_captured(self):
        assert capture_problem(SAVE) is None

    def test_a_command_without_an_object_name_cannot_be_found_again(self):
        assert capture_problem(ADD_LAYER) == (
            "“Add layer” cannot be a Menu button: Painter gives it no name to find it by. Try another command."
        )


# -- the searchable list ----------------------------------------------------------

ACTIONS = [
    LOG,
    SAVE,
    MenuAction("SAVE_PROJECT_AS", "Save &As...", ("File",)),
    ADD_LAYER,
    MenuAction("ShelfPlusCopyDiagnostics", "Copy diagnostics"),
    MenuAction("export_textures", "Export textures...", ("File",)),
    MenuAction("SAVE_PROJECT", "Save", ("Toolbar",)),  # the same command in another place
]


class TestSearch:
    def test_without_a_query_every_usable_command_is_listed_once_sorted_by_place_and_label(self):
        found = search_actions(ACTIONS, "")

        assert [(a.name, a.path) for a in found] == [
            ("export_textures", ("File",)),
            ("SAVE_PROJECT", ("File",)),
            ("SAVE_PROJECT_AS", ("File",)),
            ("show_log", ("Window", "Views")),
        ]

    def test_every_word_must_match_the_label_the_object_name_or_the_place(self):
        assert [a.name for a in search_actions(ACTIONS, "save")] == ["SAVE_PROJECT", "SAVE_PROJECT_AS"]
        assert [a.name for a in search_actions(ACTIONS, "file AS")] == ["SAVE_PROJECT_AS"]
        assert [a.name for a in search_actions(ACTIONS, "views")] == ["show_log"]
        assert [a.name for a in search_actions(ACTIONS, "show_log")] == ["show_log"]
        assert search_actions(ACTIONS, "bake") == []

    def test_mnemonic_ampersands_do_not_stop_a_match(self):
        assert [a.name for a in search_actions(ACTIONS, "save as")] == ["SAVE_PROJECT_AS"]


# -- the run_action Step ----------------------------------------------------------


def step(name):
    return {"type": "run_action", "action": name}


class TestRunAction:
    def test_the_command_is_triggered_once_and_reported_done(self):
        adapter = FakeAdapter()
        adapter.actions = [SAVE]
        results = []

        handle = run_action(adapter, step("SAVE_PROJECT"), results.append)

        assert handle is None
        assert adapter.triggered == ["SAVE_PROJECT"]
        assert [(r.state, r.message) for r in results] == [(DONE, None)]

    def test_a_command_missing_from_this_painter_version_is_not_run(self):
        adapter = FakeAdapter()
        results = []

        run_action(adapter, step("bake_everything"), results.append)

        assert adapter.triggered == []
        assert [(r.state, r.message) for r in results] == [
            (MISSING, "This menu command is not available in this Painter version: bake_everything")
        ]

    def test_a_lookup_that_fails_counts_as_missing(self):
        adapter = FakeAdapter()
        adapter.action_error = RuntimeError("main window is gone")
        results = []

        run_action(adapter, step("SAVE_PROJECT"), results.append)

        assert [r.state for r in results] == [MISSING]

    def test_a_trigger_that_raises_is_reported_as_failed(self):
        adapter = FakeAdapter()
        adapter.actions = [SAVE]
        adapter.trigger_error = RuntimeError("Internal C++ object already deleted")
        results = []

        run_action(adapter, step("SAVE_PROJECT"), results.append)

        assert [(r.state, r.message) for r in results] == [(FAILED, "“Save” could not be run. See the log.")]

    def test_a_command_painter_has_disabled_right_now_is_reported(self):
        adapter = FakeAdapter()
        adapter.actions = [SAVE]
        adapter.disabled = {"SAVE_PROJECT"}
        results = []

        run_action(adapter, step("SAVE_PROJECT"), results.append)

        assert adapter.triggered == []
        assert [(r.state, r.message) for r in results] == [(FAILED, "“Save” cannot be used right now in Painter.")]

    def test_its_own_trigger_is_not_seen_by_the_watcher(self):
        adapter = FakeAdapter()
        adapter.actions = [SAVE]
        seen = []
        watcher = ActionWatcher(seen.append)
        adapter.watch_actions(watcher.notify)

        run_action(adapter, step("SAVE_PROJECT"), lambda result: None, watcher=watcher)

        assert adapter.triggered == ["SAVE_PROJECT"] and seen == []
