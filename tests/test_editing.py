"""Layout operations used by the Panel (PRD R2.5): each change is exactly one auto-save."""

import pytest

from shelfplus_app.core.editing import LayoutEditor
from shelfplus_app.core.layout import Layout
from shelfplus_app.core.storage import ReadOnlyLayoutError


def button(bid, name=None, icon=None):
    return {"id": bid, "kind": "workflow", "name": name or bid.upper(), "icon": icon, "steps": [{"type": "save"}]}


def doc():
    return {
        "schemaVersion": 1,
        "groups": [
            {"id": "g1", "name": "General", "buttons": [button("a"), button("b"), button("c")]},
            {"id": "g2", "name": "Layers", "buttons": [button("d")]},
            {"id": "g3", "name": "Empty", "buttons": []},
        ],
    }


class SpyStore:
    def __init__(self):
        self.saved = []

    def save(self, layout):
        self.saved.append(layout.to_json())


@pytest.fixture
def store():
    return SpyStore()


def make(store, tmp_path, read_only=False, data=None):
    return LayoutEditor(Layout.from_json(data or doc()), store.save, tmp_path, read_only=read_only)


def contents(saved):
    return [(g["name"], [b["id"] for b in g["buttons"]]) for g in saved["groups"]]


def find(editor, bid):
    return next(b for g in editor.layout.groups for b in g.buttons if b.id == bid)


class TestMoveButton:
    def test_within_a_group_inserts_before_the_given_position(self, store, tmp_path):
        editor = make(store, tmp_path)

        editor.move_button(find(editor, "a"), "g1", 3)

        assert len(store.saved) == 1
        assert contents(store.saved[0])[0] == ("General", ["b", "c", "a"])

    def test_moving_backwards_within_a_group(self, store, tmp_path):
        editor = make(store, tmp_path)

        editor.move_button(find(editor, "c"), "g1", 0)

        assert contents(store.saved[0])[0] == ("General", ["c", "a", "b"])

    def test_between_groups(self, store, tmp_path):
        editor = make(store, tmp_path)

        editor.move_button(find(editor, "b"), "g2", 0)

        assert len(store.saved) == 1
        assert contents(store.saved[0])[:2] == [("General", ["a", "c"]), ("Layers", ["b", "d"])]

    def test_to_the_same_place_saves_nothing(self, store, tmp_path):
        editor = make(store, tmp_path)

        assert editor.move_button(find(editor, "a"), "g1", 1) is False
        assert editor.move_button(find(editor, "a"), "g1", 0) is False
        assert store.saved == []

    def test_an_invalid_button_can_be_moved_and_stays_unchanged(self, store, tmp_path):
        data = doc()
        broken = {"kind": "teleport", "colour": "red"}
        data["groups"][0]["buttons"].append(broken)
        editor = make(store, tmp_path, data=data)
        invalid = editor.layout.groups[0].buttons[-1]

        editor.move_button(invalid, "g3", 0)

        assert store.saved[0]["groups"][2]["buttons"] == [broken]


class TestDeleteAndUndo:
    def test_delete_saves_once(self, store, tmp_path):
        editor = make(store, tmp_path)

        pending = editor.delete_button(find(editor, "b"))

        assert pending.name == "B"
        assert len(store.saved) == 1
        assert contents(store.saved[0])[0] == ("General", ["a", "c"])

    def test_undo_puts_the_button_back_where_it_was_with_one_save(self, store, tmp_path):
        editor = make(store, tmp_path)
        editor.delete_button(find(editor, "b"))

        assert editor.undo_delete() is True

        assert len(store.saved) == 2
        assert contents(store.saved[1]) == contents(doc())

    def test_undo_twice_does_nothing(self, store, tmp_path):
        editor = make(store, tmp_path)
        editor.delete_button(find(editor, "b"))
        editor.undo_delete()

        assert editor.undo_delete() is False
        assert len(store.saved) == 2

    def test_the_icon_is_kept_until_undo_expires(self, store, tmp_path):
        data = doc()
        data["groups"][1]["buttons"][0]["icon"] = "icons/d.png"
        icon = tmp_path / "icons" / "d.png"
        icon.parent.mkdir()
        icon.write_bytes(b"png")
        editor = make(store, tmp_path, data=data)

        editor.delete_button(find(editor, "d"))
        assert icon.exists()
        editor.expire_delete()

        assert not icon.exists()
        assert editor.undo_delete() is False
        assert len(store.saved) == 1

    def test_undone_delete_keeps_the_icon(self, store, tmp_path):
        data = doc()
        data["groups"][1]["buttons"][0]["icon"] = "icons/d.png"
        icon = tmp_path / "icons" / "d.png"
        icon.parent.mkdir()
        icon.write_bytes(b"png")
        editor = make(store, tmp_path, data=data)

        editor.delete_button(find(editor, "d"))
        editor.undo_delete()
        editor.expire_delete()

        assert icon.exists()

    def test_icons_outside_the_icons_folder_are_never_deleted(self, store, tmp_path):
        data = doc()
        data["groups"][1]["buttons"][0]["icon"] = "../outside.png"
        outside = tmp_path.parent / "outside.png"
        outside.write_bytes(b"png")
        editor = make(store, tmp_path, data=data)

        editor.delete_button(find(editor, "d"))
        editor.expire_delete()

        assert outside.exists()

    def test_a_second_delete_ends_the_undo_of_the_first(self, store, tmp_path):
        data = doc()
        data["groups"][0]["buttons"][0]["icon"] = "icons/a.png"
        icon = tmp_path / "icons" / "a.png"
        icon.parent.mkdir()
        icon.write_bytes(b"png")
        editor = make(store, tmp_path, data=data)

        editor.delete_button(find(editor, "a"))
        editor.delete_button(find(editor, "b"))
        editor.undo_delete()

        assert not icon.exists()
        assert contents(store.saved[-1])[0] == ("General", ["b", "c"])

    def test_undo_recreates_a_group_deleted_in_the_meantime(self, store, tmp_path):
        editor = make(store, tmp_path)
        editor.delete_button(find(editor, "d"))
        editor.delete_group("g2")

        editor.undo_delete()

        assert contents(store.saved[-1])[1] == ("Layers", ["d"])
        assert store.saved[-1]["groups"][1]["id"] == "g2"

    def test_an_invalid_button_can_be_deleted(self, store, tmp_path):
        data = doc()
        data["groups"][2]["buttons"].append(["not", "an", "object"])
        editor = make(store, tmp_path, data=data)

        pending = editor.delete_button(editor.layout.groups[2].buttons[0])
        editor.expire_delete()

        assert pending.name == "(invalid)"
        assert store.saved[-1]["groups"][2]["buttons"] == []


class TestRenameButton:
    def test_saves_once_with_the_new_name(self, store, tmp_path):
        editor = make(store, tmp_path)

        editor.rename_button(find(editor, "a"), "  Quick save ")

        assert len(store.saved) == 1
        assert store.saved[0]["groups"][0]["buttons"][0]["name"] == "Quick save"

    def test_an_empty_name_is_refused(self, store, tmp_path):
        editor = make(store, tmp_path)

        with pytest.raises(ValueError):
            editor.rename_button(find(editor, "a"), "   ")
        assert store.saved == []

    def test_an_invalid_button_cannot_be_renamed(self, store, tmp_path):
        data = doc()
        data["groups"][2]["buttons"].append({"id": "x", "kind": "teleport", "name": "Old"})
        editor = make(store, tmp_path, data=data)

        with pytest.raises(ValueError):
            editor.rename_button(editor.layout.groups[2].buttons[0], "New")
        assert store.saved == []


class TestGroups:
    def test_new_group_is_inserted_at_the_position_with_a_fresh_id(self, store, tmp_path):
        editor = make(store, tmp_path)

        group = editor.add_group("Masks", 1)

        assert len(store.saved) == 1
        assert [g["name"] for g in store.saved[0]["groups"]] == ["General", "Masks", "Layers", "Empty"]
        assert store.saved[0]["groups"][1] == {"id": group.id, "name": "Masks", "buttons": []}
        assert group.id not in ("g1", "g2", "g3") and group.id

    def test_new_group_goes_last_by_default(self, store, tmp_path):
        editor = make(store, tmp_path)

        editor.add_group("Masks")

        assert store.saved[0]["groups"][-1]["name"] == "Masks"

    def test_rename_saves_once(self, store, tmp_path):
        editor = make(store, tmp_path)

        editor.rename_group("g2", "Fills")

        assert len(store.saved) == 1
        assert store.saved[0]["groups"][1]["name"] == "Fills"

    def test_rename_to_an_empty_name_is_refused(self, store, tmp_path):
        editor = make(store, tmp_path)

        with pytest.raises(ValueError):
            editor.rename_group("g2", "")
        assert store.saved == []

    def test_reorder_moves_the_group_to_a_new_position(self, store, tmp_path):
        editor = make(store, tmp_path)

        editor.move_group("g3", 0)

        assert len(store.saved) == 1
        assert [g["id"] for g in store.saved[0]["groups"]] == ["g3", "g1", "g2"]

    def test_reorder_past_the_ends_is_a_no_op(self, store, tmp_path):
        editor = make(store, tmp_path)

        assert editor.move_group("g1", -1) is False
        assert editor.move_group("g3", 3) is False
        assert store.saved == []

    def test_delete_an_empty_group_saves_once(self, store, tmp_path):
        editor = make(store, tmp_path)

        editor.delete_group("g3")

        assert len(store.saved) == 1
        assert [g["id"] for g in store.saved[0]["groups"]] == ["g1", "g2"]

    def test_a_group_with_buttons_cannot_be_deleted(self, store, tmp_path):
        editor = make(store, tmp_path)

        with pytest.raises(ValueError):
            editor.delete_group("g1")
        assert store.saved == []


class TestReadOnly:
    def test_every_change_is_refused_and_nothing_is_saved(self, store, tmp_path):
        editor = make(store, tmp_path, read_only=True)
        a = find(editor, "a")

        for change in (
            lambda: editor.move_button(a, "g2", 0),
            lambda: editor.delete_button(a),
            lambda: editor.rename_button(a, "X"),
            lambda: editor.add_group("X"),
            lambda: editor.rename_group("g1", "X"),
            lambda: editor.move_group("g1", 1),
            lambda: editor.delete_group("g3"),
        ):
            with pytest.raises(ReadOnlyLayoutError):
                change()
        assert store.saved == []


class TestFailedSave:
    """If the save fails, the Layout in memory stays as it is on disk."""

    @pytest.fixture
    def failing(self, tmp_path):
        def save(layout):
            raise OSError("disk full")

        return LayoutEditor(Layout.from_json(doc()), save, tmp_path)

    def test_every_change_is_rolled_back(self, failing):
        a = find(failing, "a")
        for change in (
            lambda: failing.move_button(a, "g2", 0),
            lambda: failing.delete_button(a),
            lambda: failing.rename_button(a, "X"),
            lambda: failing.add_group("X", 0),
            lambda: failing.rename_group("g1", "X"),
            lambda: failing.move_group("g1", 1),
            lambda: failing.delete_group("g3"),
        ):
            with pytest.raises(OSError):
                change()
            assert contents(failing.layout.to_json()) == contents(doc())
            assert [g.name for g in failing.layout.groups] == ["General", "Layers", "Empty"]
            assert a.name == "A"
        assert failing.pending_delete is None

    def test_a_failed_undo_keeps_the_undo_available(self, store, tmp_path):
        editor = make(store, tmp_path)
        editor.delete_button(find(editor, "b"))
        editor._save = lambda layout: (_ for _ in ()).throw(OSError("disk full"))

        with pytest.raises(OSError):
            editor.undo_delete()

        assert contents(editor.layout.to_json())[0] == ("General", ["a", "c"])
        assert editor.pending_delete is not None
