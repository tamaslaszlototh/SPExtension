"""Menu buttons in the App (PRD R6) against the fake adapter: capture mode, the list,
clicking, and the "unavailable" badge."""

import json
import shutil
from pathlib import Path

import pytest

from shelfplus_app.adapter.fake import FakeAdapter
from shelfplus_app.app import App
from shelfplus_app.core.menu import MenuAction
from shelfplus_app.core.storage import READ_ONLY_MESSAGE

BUNDLED = Path(__file__).parents[1] / "src" / "ShelfPlus" / "bundled"
PNG = b"\x89PNG\r\n\x1a\n" + b"save" + b"IEND\xaeB`\x82"

SAVE = MenuAction("SAVE_PROJECT", "&Save", ("File",))
LOG = MenuAction("show_log", "Log", ("Window", "Views"))
EXPORT = MenuAction("export_textures", "Export textures...", ("File",))
ADD_LAYER = MenuAction("", "Add layer\n\nHold Alt to enable all channels")


class FakeView:
    def __init__(self, app):
        self.app = app
        self.widget = object()
        self.renders = 0
        self.notes = []

    def render(self):
        self.renders += 1

    def notify(self, text):
        self.notes.append(text)

    def dispose(self):
        pass


def menu(bid, action, name):
    return {"id": bid, "kind": "menu", "name": name, "action": action, "icon": None}


LAYOUT = {
    "schemaVersion": 1,
    "groups": [
        {"id": "g1", "name": "Commands", "buttons": [menu("m1", "SAVE_PROJECT", "Save"), menu("m2", "bake_all", "Bake")]},
        {"id": "g2", "name": "Empty", "buttons": []},
    ],
}


@pytest.fixture
def adapter():
    adapter = FakeAdapter()
    adapter.actions = [SAVE, LOG, EXPORT, ADD_LAYER]
    adapter.action_icons = {"SAVE_PROJECT": PNG}
    return adapter


@pytest.fixture
def env(tmp_path):
    version_dir = tmp_path / "versions" / "0.4.0"
    version_dir.mkdir(parents=True)
    shutil.copy(BUNDLED / "default_layout.json", version_dir / "default_layout.json")
    (tmp_path / "layout.json").write_text(json.dumps(LAYOUT), encoding="utf-8")
    return {"version": "0.4.0", "version_dir": str(version_dir), "data_dir": str(tmp_path), "loader_version": 1}


def start(env, adapter):
    app = App(env, adapter, FakeView)
    app.start()
    return app


def saved(env):
    return json.loads((Path(env["data_dir"]) / "layout.json").read_text(encoding="utf-8"))


def group(app, group_id):
    return app.editor.group(group_id)


def add_menu_handler(app):
    handlers = dict(app.add_button_kinds)
    return handlers["Menu button"]


class TestCapture:
    def test_the_plus_menus_menu_button_entry_starts_capture_mode(self, env, adapter):
        app = start(env, adapter)
        renders = app.view.renders

        add_menu_handler(app)(group(app, "g2"))

        assert app.capturing is group(app, "g2")
        assert len(adapter.hooks) == 1
        assert app.view.renders > renders  # the Panel shows the capture bar

    def test_the_next_command_clicked_becomes_a_menu_button_at_the_end_of_the_group(self, env, adapter):
        app = start(env, adapter)
        app.start_menu_capture(group(app, "g1"))

        adapter.click_command(SAVE)

        buttons = saved(env)["groups"][0]["buttons"]
        assert [b["name"] for b in buttons] == ["Save", "Bake", "Save"]
        new = buttons[-1]
        assert new == {"id": new["id"], "kind": "menu", "name": "Save", "action": "SAVE_PROJECT", "icon": f"icons/{new['id']}.png"}
        assert (Path(env["data_dir"]) / new["icon"]).read_bytes() == PNG
        assert app.capturing is None
        assert adapter.hooks == []
        assert app.view.notes[-1] == "Added “Save” to “Commands”."

    def test_a_command_without_an_icon_gets_the_generic_icon(self, env, adapter):
        app = start(env, adapter)
        app.start_menu_capture(group(app, "g2"))

        adapter.click_command(LOG)

        (raw,) = saved(env)["groups"][1]["buttons"]
        assert raw["action"] == "show_log" and raw["icon"] is None

    def test_one_click_reported_by_every_hook_adds_one_button(self, env, adapter):
        app = start(env, adapter)
        app.start_menu_capture(group(app, "g2"))

        adapter.click_command(LOG, hook_calls=4)

        assert [b["action"] for b in saved(env)["groups"][1]["buttons"]] == ["show_log"]

    def test_a_command_without_an_object_name_is_refused_and_capture_goes_on(self, env, adapter):
        app = start(env, adapter)
        app.start_menu_capture(group(app, "g2"))

        adapter.click_command(ADD_LAYER)

        assert saved(env)["groups"][1]["buttons"] == []
        assert app.capturing is group(app, "g2")
        assert "is in none of Painter's menus" in app.view.notes[-1]
        adapter.click_command(EXPORT)
        assert [b["action"] for b in saved(env)["groups"][1]["buttons"]] == ["export_textures"]

    def test_a_command_without_an_object_name_is_stored_by_its_menu_place_and_runs(self, env, adapter):
        settings = MenuAction("", "Settings...", ("Edit",))
        adapter.actions.append(settings)
        app = start(env, adapter)
        app.start_menu_capture(group(app, "g2"))

        adapter.click_command(settings)
        (raw,) = saved(env)["groups"][1]["buttons"]
        adapter.triggered.clear()
        app.run_button(group(app, "g2").buttons[0])

        assert raw["action"] == "menu:Edit › Settings..." and raw["name"] == "Settings..."
        assert adapter.triggered == [""] and not app.is_missing(group(app, "g2").buttons[0])

    def test_a_refusal_is_shown_in_the_capture_bar_until_the_next_command(self, env, adapter):
        app = start(env, adapter)
        app.start_menu_capture(group(app, "g2"))

        adapter.click_command(ADD_LAYER)
        assert "is in none of Painter's menus" in app.capture_note
        adapter.click_command(LOG)

        assert app.capture_note is None

    def test_cancelling_ends_capture_mode_without_adding_anything(self, env, adapter):
        app = start(env, adapter)
        app.start_menu_capture(group(app, "g2"))

        app.cancel_menu_capture()
        adapter.click_command(SAVE)

        assert app.capturing is None
        assert adapter.hooks == []
        assert saved(env)["groups"][1]["buttons"] == []

    def test_cancelling_when_not_capturing_does_nothing(self, env, adapter):
        app = start(env, adapter)
        renders = app.view.renders

        app.cancel_menu_capture()

        assert app.view.renders == renders

    def test_starting_again_moves_capture_to_the_other_group_with_one_set_of_hooks(self, env, adapter):
        app = start(env, adapter)
        app.start_menu_capture(group(app, "g1"))

        app.start_menu_capture(group(app, "g2"))
        adapter.click_command(SAVE)

        assert len(saved(env)["groups"][0]["buttons"]) == 2
        assert [b["action"] for b in saved(env)["groups"][1]["buttons"]] == ["SAVE_PROJECT"]
        assert adapter.hooks == []

    def test_clicking_a_menu_button_while_capturing_runs_it_and_is_not_captured(self, env, adapter):
        app = start(env, adapter)
        app.start_menu_capture(group(app, "g2"))

        app.run_button(group(app, "g1").buttons[0])

        assert adapter.triggered == ["SAVE_PROJECT"]
        assert saved(env)["groups"][1]["buttons"] == []
        assert app.capturing is group(app, "g2")

    def test_if_painters_menus_cannot_be_watched_capture_does_not_start(self, env, adapter):
        adapter.watch_error = RuntimeError("no main window")
        app = start(env, adapter)

        app.start_menu_capture(group(app, "g2"))

        assert app.capturing is None
        assert app.view.notes[-1] == "Painter's menu cannot be watched. Use “Choose from list…” instead."

    def test_a_read_only_layout_cannot_capture(self, env, adapter):
        data = dict(LAYOUT, schemaVersion=99)
        (Path(env["data_dir"]) / "layout.json").write_text(json.dumps(data), encoding="utf-8")
        app = start(env, adapter)

        app.start_menu_capture(group(app, "g2"))

        assert app.capturing is None and adapter.hooks == []
        assert app.view.notes[-1] == READ_ONLY_MESSAGE

    def test_a_group_deleted_while_capturing_ends_capture_without_adding(self, env, adapter):
        app = start(env, adapter)
        app.start_menu_capture(group(app, "g2"))
        app.editor.delete_group("g2")

        adapter.click_command(SAVE)

        assert app.capturing is None and adapter.hooks == []
        assert [g["id"] for g in saved(env)["groups"]] == ["g1"]

    def test_closing_the_panel_stops_watching_painters_menu(self, env, adapter):
        app = start(env, adapter)
        app.start_menu_capture(group(app, "g2"))

        app.close()

        assert adapter.hooks == [] and app.capturing is None


class TestList:
    def test_the_list_offers_painters_named_commands_filtered_by_the_search(self, env, adapter):
        app = start(env, adapter)

        assert [a.name for a in app.menu_actions("")] == ["export_textures", "SAVE_PROJECT", "show_log"]
        assert [a.name for a in app.menu_actions("views")] == ["show_log"]

    def test_if_the_commands_cannot_be_read_the_list_is_empty_and_says_so(self, env, adapter):
        adapter.action_error = RuntimeError("no main window")
        app = start(env, adapter)

        assert app.menu_actions("") == []
        assert app.view.notes[-1] == "Painter's commands could not be read. See the log."

    def test_a_command_picked_from_the_list_is_added_and_ends_capture_mode(self, env, adapter):
        app = start(env, adapter)
        app.start_menu_capture(group(app, "g2"))

        button = app.add_menu_button("g2", EXPORT)

        assert button.name == "Export textures..."
        assert [b["action"] for b in saved(env)["groups"][1]["buttons"]] == ["export_textures"]
        assert app.capturing is None and adapter.hooks == []


class TestRunning:
    def test_a_click_triggers_the_command_once(self, env, adapter):
        app = start(env, adapter)

        app.run_button(group(app, "g1").buttons[0])

        assert adapter.triggered == ["SAVE_PROJECT"]
        assert app.view.notes == []

    def test_a_command_missing_from_this_painter_version_gets_the_unavailable_badge_at_start(self, env, adapter):
        app = start(env, adapter)
        save, bake = group(app, "g1").buttons

        assert not app.is_missing(save)
        assert app.is_missing(bake)

    def test_clicking_an_unavailable_button_says_so_and_runs_nothing(self, env, adapter):
        app = start(env, adapter)

        app.run_button(group(app, "g1").buttons[1])

        assert adapter.triggered == []
        assert app.view.notes == ["This menu command is not available in this Painter version: bake_all"]

    def test_a_command_that_appears_later_loses_its_badge(self, env, adapter):
        # Some commands are created only when a project is opened.
        app = start(env, adapter)
        bake = group(app, "g1").buttons[1]
        adapter.actions.append(MenuAction("bake_all", "Bake all"))

        adapter.fire_timers()

        assert not app.is_missing(bake)
        assert not any(t.active for t in adapter.timers)

    def test_a_click_on_a_badged_button_whose_command_now_exists_runs_it_and_clears_the_badge(self, env, adapter):
        app = start(env, adapter)
        bake = group(app, "g1").buttons[1]
        adapter.actions.append(MenuAction("bake_all", "Bake all"))

        app.run_button(bake)

        assert adapter.triggered == ["bake_all"]
        assert not app.is_missing(bake)

    def test_a_command_gone_by_the_time_of_a_click_is_badged_and_looked_for_again(self, env, adapter):
        app = start(env, adapter)
        save = group(app, "g1").buttons[0]
        app.editor.delete_button(group(app, "g1").buttons[1])  # only Save is left to check
        app.check_menu_buttons()
        assert not any(t.active for t in adapter.timers)
        adapter.actions.remove(SAVE)

        app.run_button(save)
        assert app.is_missing(save)
        adapter.actions.append(SAVE)
        adapter.fire_timers()

        assert not app.is_missing(save)

    def test_a_menu_button_added_for_a_missing_command_is_badged(self, env, adapter):
        app = start(env, adapter)

        button = app.add_menu_button("g2", MenuAction("gone", "Gone"))

        assert app.is_missing(button)
