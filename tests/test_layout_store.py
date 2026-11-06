"""Layout storage (PRD R3): load, save and backup, recovery, invalid Buttons, newer schema, migrations."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from shelfplus_app.core.layout import Layout
from shelfplus_app.core.storage import LayoutStore, ReadOnlyLayoutError

BUNDLED_DEFAULT = Path(__file__).parents[1] / "src" / "ShelfPlus" / "bundled" / "default_layout.json"

NOW = datetime(2026, 11, 6, 14, 30, 5)


def layout_doc(*buttons, schema=1, group_extra=None):
    group = {"id": "g1", "name": "General", "buttons": list(buttons)}
    group.update(group_extra or {})
    return {"schemaVersion": schema, "groups": [group]}


SAVE = {"id": "b1", "kind": "workflow", "name": "Save", "icon": None, "steps": [{"type": "save"}]}
BRUSH = {
    "id": "b2",
    "kind": "brush",
    "name": "Basic Hard",
    "resource": "resource://starter_assets/Basic Hard",
    "icon": "icons/b2.png",
}
MENU = {"id": "b3", "kind": "menu", "name": "Bake", "action": "bake_action"}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data)
    path.write_text(text, encoding="utf-8")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path / "ShelfPlus"


def store(data_dir, **kw):
    kw.setdefault("default_layout_path", BUNDLED_DEFAULT)
    kw.setdefault("now", lambda: NOW)
    return LayoutStore(data_dir, **kw)


def names(layout):
    return [(g.name, [b.name for b in g.buttons]) for g in layout.groups]


class TestDefaultLayout:
    def test_bundled_default_is_general_with_save_and_fill_black_mask(self):
        layout = Layout.from_json(read(BUNDLED_DEFAULT))

        assert names(layout) == [("General", ["Save", "Fill layer + Black mask"])]
        assert all(b.valid and b.kind == "workflow" for b in layout.groups[0].buttons)
        assert [s["type"] for s in layout.groups[0].buttons[0].raw["steps"]] == ["save"]
        assert layout.groups[0].buttons[1].raw["steps"] == [
            {"type": "add_layer", "layer": "fill"},
            {"type": "add_mask", "background": "black"},
        ]

    def test_first_start_copies_the_default_layout_in(self, data_dir):
        result = store(data_dir).load()

        assert (data_dir / "layout.json").read_bytes() == BUNDLED_DEFAULT.read_bytes()
        assert names(result.layout) == [("General", ["Save", "Fill layer + Black mask"])]
        assert result.messages == []
        assert not result.read_only

    def test_an_existing_layout_is_never_replaced_by_the_default(self, data_dir):
        write(data_dir / "layout.json", layout_doc(MENU))

        result = store(data_dir).load()

        assert names(result.layout) == [("General", ["Bake"])]
        assert read(data_dir / "layout.json") == layout_doc(MENU)


class TestSave:
    def test_save_writes_utf8_two_space_indent_without_ascii_escapes(self, data_dir):
        s = store(data_dir)
        layout = s.load().layout
        layout.groups[0].name = "Általános"

        s.save(layout)

        text = (data_dir / "layout.json").read_text(encoding="utf-8")
        assert "Általános" in text
        assert '\n  "groups": [' in text
        assert text.endswith("\n")

    def test_previous_file_becomes_the_backup(self, data_dir):
        write(data_dir / "layout.json", layout_doc(MENU))
        before = (data_dir / "layout.json").read_bytes()
        s = store(data_dir)
        layout = s.load().layout
        layout.groups[0].name = "Renamed"

        s.save(layout)

        assert (data_dir / "layout.bak.json").read_bytes() == before
        assert read(data_dir / "layout.json")["groups"][0]["name"] == "Renamed"

    def test_backup_follows_each_save(self, data_dir):
        s = store(data_dir)
        layout = s.load().layout
        layout.groups[0].name = "One"
        s.save(layout)
        layout.groups[0].name = "Two"
        s.save(layout)

        assert read(data_dir / "layout.bak.json")["groups"][0]["name"] == "One"
        assert read(data_dir / "layout.json")["groups"][0]["name"] == "Two"

    def test_no_temporary_files_are_left_behind(self, data_dir):
        s = store(data_dir)
        s.save(s.load().layout)

        assert sorted(p.name for p in data_dir.iterdir()) == ["layout.bak.json", "layout.json"]

    def test_load_then_save_round_trips_the_document(self, data_dir):
        doc = layout_doc(SAVE, BRUSH, MENU, group_extra={"futureGroupKey": 7})
        doc["groups"][0]["buttons"][0]["futureKey"] = {"kept": True}
        write(data_dir / "layout.json", doc)
        s = store(data_dir)

        s.save(s.load().layout)

        assert read(data_dir / "layout.json") == doc


class TestInvalidButtons:
    INVALID = [
        {"id": "x1", "kind": "teleport", "name": "Unknown kind"},
        {"id": "x2", "kind": "workflow", "name": "Unknown step", "icon": None, "steps": [{"type": "explode"}]},
        {"id": "x3", "kind": "brush", "name": "No resource", "icon": None},
        {"id": "x4", "kind": "menu", "name": "Bad action", "action": ""},
        {"kind": "menu", "name": "No id", "action": "a"},
        {"id": "x6", "kind": "workflow", "name": "Bad param", "icon": None, "steps": [{"type": "add_layer", "layer": "stone"}]},
        "not even an object",
    ]

    def test_every_other_button_still_loads(self, data_dir):
        write(data_dir / "layout.json", layout_doc(SAVE, *self.INVALID, MENU))

        layout = store(data_dir).load().layout

        buttons = layout.groups[0].buttons
        assert [b.valid for b in buttons] == [True] + [False] * len(self.INVALID) + [True]
        assert all(b.problem for b in buttons if not b.valid)

    def test_invalid_buttons_are_written_back_unchanged(self, data_dir):
        doc = layout_doc(SAVE, *self.INVALID, MENU)
        write(data_dir / "layout.json", doc)
        s = store(data_dir)

        s.save(s.load().layout)

        assert read(data_dir / "layout.json") == doc

    def test_invalid_buttons_have_a_display_name(self, data_dir):
        write(data_dir / "layout.json", layout_doc(*self.INVALID))

        buttons = store(data_dir).load().layout.groups[0].buttons

        assert buttons[0].name == "Unknown kind"
        assert buttons[-1].name == "(invalid)"


class TestBrokenFileRecovery:
    def test_unreadable_file_is_kept_and_the_backup_is_loaded(self, data_dir):
        write(data_dir / "layout.json", "{ this is not json")
        write(data_dir / "layout.bak.json", layout_doc(MENU))

        result = store(data_dir).load()

        assert names(result.layout) == [("General", ["Bake"])]
        broken = data_dir / "layout.broken-20261106-143005.json"
        assert broken.read_text(encoding="utf-8") == "{ this is not json"
        assert result.messages == [
            "layout.json could not be read. It was kept as layout.broken-20261106-143005.json, "
            "and the backup was loaded."
        ]
        # The recovered Layout is the current one again, so the next start does not reset it.
        assert read(data_dir / "layout.json") == layout_doc(MENU)

    @pytest.mark.parametrize(
        "content",
        [
            json.dumps({"groups": []}),
            json.dumps({"schemaVersion": 1, "groups": {}}),
            json.dumps({"schemaVersion": 1, "groups": [{"id": "g1", "buttons": []}]}),
            json.dumps([1, 2]),
            json.dumps({"schemaVersion": "1", "groups": []}),
        ],
    )
    def test_a_file_with_the_wrong_structure_counts_as_unreadable(self, data_dir, content):
        write(data_dir / "layout.json", content)
        write(data_dir / "layout.bak.json", layout_doc(MENU))

        result = store(data_dir).load()

        assert names(result.layout) == [("General", ["Bake"])]

    def test_when_the_backup_is_broken_too_the_default_is_loaded(self, data_dir):
        write(data_dir / "layout.json", "broken main")
        write(data_dir / "layout.bak.json", "broken backup")

        result = store(data_dir).load()

        assert names(result.layout) == [("General", ["Save", "Fill layer + Black mask"])]
        kept = sorted(p.read_text(encoding="utf-8") for p in data_dir.glob("layout.broken-*.json"))
        assert kept == ["broken backup", "broken main"]
        assert not (data_dir / "layout.bak.json").exists()
        assert len(result.messages) == 1
        assert result.messages[0].endswith("The default Layout was loaded.")

    def test_broken_main_without_backup_loads_the_default(self, data_dir):
        write(data_dir / "layout.json", "broken main")

        result = store(data_dir).load()

        assert names(result.layout) == [("General", ["Save", "Fill layer + Black mask"])]
        assert result.messages[0].endswith("The default Layout was loaded.")

    def test_broken_files_are_never_overwritten(self, data_dir):
        old = data_dir / "layout.broken-20261106-143005.json"
        write(old, "older broken file")
        write(data_dir / "layout.json", "new broken file")

        store(data_dir).load()

        assert old.read_text(encoding="utf-8") == "older broken file"
        assert (data_dir / "layout.broken-20261106-143005-2.json").read_text(encoding="utf-8") == "new broken file"

    def test_saving_after_recovery_does_not_overwrite_kept_files(self, data_dir):
        write(data_dir / "layout.json", "broken main")
        write(data_dir / "layout.bak.json", "broken backup")
        s = store(data_dir)
        layout = s.load().layout

        s.save(layout)
        s.save(layout)

        kept = sorted(p.read_text(encoding="utf-8") for p in data_dir.glob("layout.broken-*.json"))
        assert kept == ["broken backup", "broken main"]


class TestNewerSchema:
    def test_newer_schema_is_read_only_and_never_written(self, data_dir):
        doc = layout_doc(MENU, schema=2)
        write(data_dir / "layout.json", doc)
        before = (data_dir / "layout.json").read_bytes()
        s = store(data_dir)

        result = s.load()

        assert result.read_only
        assert result.messages == ["This Layout was saved by a newer Shelf+. Update Shelf+ to edit this Layout."]
        with pytest.raises(ReadOnlyLayoutError):
            s.save(result.layout)
        assert (data_dir / "layout.json").read_bytes() == before
        assert not (data_dir / "layout.bak.json").exists()

    def test_newer_schema_shows_its_groups_as_far_as_they_can_be_read(self, data_dir):
        write(data_dir / "layout.json", layout_doc(MENU, {"id": "n", "kind": "future", "name": "New"}, schema=2))

        layout = store(data_dir).load().layout

        assert names(layout) == [("General", ["Bake", "New"])]

    def test_after_a_rollback_the_backup_matching_this_schema_is_shown(self, data_dir):
        write(data_dir / "layout.json", layout_doc(MENU, schema=2))
        write(data_dir / "layout.v1.bak.json", layout_doc(SAVE))

        result = store(data_dir).load()

        assert result.read_only
        assert names(result.layout) == [("General", ["Save"])]


def rename_groups(doc):
    for group in doc["groups"]:
        group["name"] = group["name"] + " (v2)"
    return doc


def add_marker(doc):
    doc["marker"] = "v3"
    return doc


class TestMigrations:
    def test_migrations_run_stepwise_and_the_old_file_is_kept(self, data_dir):
        write(data_dir / "layout.json", layout_doc(MENU))
        before = (data_dir / "layout.json").read_bytes()
        s = store(data_dir, schema_version=3, migrations={1: rename_groups, 2: add_marker})

        result = s.load()

        assert names(result.layout) == [("General (v2)", ["Bake"])]
        assert result.layout.schema_version == 3
        assert (data_dir / "layout.v1.bak.json").read_bytes() == before
        saved = read(data_dir / "layout.json")
        assert saved["schemaVersion"] == 3
        assert saved["marker"] == "v3"
        assert not result.read_only

    def test_a_version_without_a_migration_path_counts_as_unreadable(self, data_dir):
        write(data_dir / "layout.json", layout_doc(MENU, schema=0))

        result = store(data_dir).load()

        assert names(result.layout) == [("General", ["Save", "Fill layer + Black mask"])]
        assert list(data_dir.glob("layout.broken-*.json"))

    def test_current_schema_needs_no_migration(self, data_dir):
        write(data_dir / "layout.json", layout_doc(MENU))

        store(data_dir).load()

        assert not list(data_dir.glob("layout.v*.bak.json"))
