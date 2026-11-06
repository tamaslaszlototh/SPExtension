"""Changes the Panel makes to the Layout (PRD R2.5). Every change is exactly one auto-save.

Buttons are passed as the ``Button`` objects of ``editor.layout`` (an invalid Button
may have no id); Groups are passed by id.
"""

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .layout import Button, Group, new_id
from .storage import READ_ONLY_MESSAGE, ReadOnlyLayoutError

log = logging.getLogger("ShelfPlus.app.editing")


@dataclass
class PendingDelete:
    """A deleted Button that can still be brought back with Undo."""

    button: Button
    group_id: str
    group_name: str
    group_extra: dict
    group_index: int
    index: int

    @property
    def name(self):
        return self.button.name


class LayoutEditor:
    def __init__(self, layout, save, data_dir, read_only=False):
        self.layout = layout
        self._save = save
        self.data_dir = Path(data_dir)
        self.read_only = read_only
        self.pending_delete = None

    def _check_writable(self):
        if self.read_only:
            raise ReadOnlyLayoutError(READ_ONLY_MESSAGE)

    @contextmanager
    def _change(self):
        """One change: refused when read-only, saved once at the end, and undone in
        memory if anything fails (so the Layout shown stays the one on disk)."""
        self._check_writable()
        groups = list(self.layout.groups)
        group_state = [(g, g.name, list(g.buttons)) for g in groups]
        names = [(b, b.raw["name"]) for g in groups for b in g.buttons if b.valid]
        try:
            yield
            self._save(self.layout)
        except BaseException:
            self.layout.groups[:] = groups
            for group, name, buttons in group_state:
                group.name = name
                group.buttons[:] = buttons
            for button, name in names:
                button.raw["name"] = name
            raise

    # -- lookups -------------------------------------------------------------

    def group(self, group_id):
        for group in self.layout.groups:
            if group.id == group_id:
                return group
        raise KeyError(group_id)

    def locate(self, button):
        """(Group, index) of a Button of this Layout."""
        for group in self.layout.groups:
            for index, candidate in enumerate(group.buttons):
                if candidate is button:
                    return group, index
        raise KeyError("the Button is not in the Layout")

    # -- Buttons -------------------------------------------------------------

    def move_button(self, button, group_id, index):
        """Move ``button`` so it lands before position ``index`` of the Group as it is now
        (``index`` counts the moved Button too, as a drop position does). Returns whether
        anything changed."""
        self._check_writable()
        source, old = self.locate(button)
        target = self.group(group_id)
        index = max(0, min(index, len(target.buttons)))
        if target is source:
            if index in (old, old + 1):
                return False
            if index > old:
                index -= 1
        with self._change():
            del source.buttons[old]
            target.buttons.insert(index, button)
        return True

    def rename_button(self, button, name):
        self._check_writable()
        if not button.valid:
            raise ValueError("an invalid Button cannot be renamed")
        name = _clean_name(name)
        self.locate(button)
        with self._change():
            button.raw["name"] = name

    def delete_button(self, button):
        """Remove ``button``; it can come back with ``undo_delete`` until ``expire_delete``.
        A new delete ends the Undo of the previous one."""
        self._check_writable()
        group, index = self.locate(button)
        with self._change():
            del group.buttons[index]
        self.expire_delete()
        self.pending_delete = PendingDelete(
            button, group.id, group.name, dict(group.extra), self.layout.groups.index(group), index
        )
        return self.pending_delete

    def undo_delete(self):
        """Bring back the last deleted Button where it was. Returns whether there was one."""
        pending = self.pending_delete
        if pending is None:
            return False
        with self._change():
            try:
                group = self.group(pending.group_id)
            except KeyError:
                group = Group(pending.group_id, pending.group_name, [], pending.group_extra)
                self.layout.groups.insert(min(pending.group_index, len(self.layout.groups)), group)
            group.buttons.insert(min(pending.index, len(group.buttons)), pending.button)
        self.pending_delete = None
        return True

    def expire_delete(self):
        """The Undo time is over: the deleted Button's icon file is removed now."""
        pending, self.pending_delete = self.pending_delete, None
        if pending is not None:
            self._delete_icon(pending.button)

    def _delete_icon(self, button):
        icon = button.icon
        if icon is None:
            return
        icons = (self.data_dir / "icons").resolve()
        path = (self.data_dir / icon).resolve()
        if path.parent != icons:
            log.warning("Not deleting icon outside the icons folder: %s", icon)
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            log.exception("Could not delete icon %s", path)

    # -- Groups --------------------------------------------------------------

    def add_group(self, name, index=None):
        """A new, empty Group at ``index`` (last by default)."""
        self._check_writable()
        name = _clean_name(name)
        taken = {g.id for g in self.layout.groups}
        group_id = new_id()
        while group_id in taken:
            group_id = new_id()
        group = Group(group_id, name)
        if index is None:
            index = len(self.layout.groups)
        with self._change():
            self.layout.groups.insert(max(0, min(index, len(self.layout.groups))), group)
        return group

    def rename_group(self, group_id, name):
        self._check_writable()
        name = _clean_name(name)
        group = self.group(group_id)
        with self._change():
            group.name = name

    def move_group(self, group_id, index):
        """Move a Group to position ``index`` (0 = first). Returns whether anything changed."""
        self._check_writable()
        group = self.group(group_id)
        old = self.layout.groups.index(group)
        if index == old or not 0 <= index < len(self.layout.groups):
            return False
        with self._change():
            del self.layout.groups[old]
            self.layout.groups.insert(index, group)
        return True

    def delete_group(self, group_id):
        """Delete an empty Group."""
        self._check_writable()
        group = self.group(group_id)
        if group.buttons:
            raise ValueError(f"Group {group.name!r} is not empty")
        with self._change():
            self.layout.groups.remove(group)


def _clean_name(name):
    name = (name or "").strip()
    if not name:
        raise ValueError("a name cannot be empty")
    return name
