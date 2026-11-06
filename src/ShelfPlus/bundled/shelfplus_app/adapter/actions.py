"""Painter's commands (QActions), through Qt only (PRD R6). Part of the adapter layer.

Widget rules (see ``assets.py`` and ``docs/probes/``):

- Commands are found only through ``QApplication.allWidgets()`` and each widget's
  ``actions()``, never ``findChildren`` (it returns dead wrappers on 11.1). That covers
  the menus (and their submenus, which are widgets too), toolbars, and window-wide
  shortcut actions.
- Every widget and action found is kept for the plugin's lifetime (``PainterActions``
  holds them; dead ones are let go), and checked with ``shiboken6.isValid`` before use.
- The plugin's own menus (objectName ``ShelfPlus…``) are never listed or hooked.

Hooks: ``QAction.triggered`` on every command in a menu, plus ``QMenu.triggered`` on
every menu (it fires on 12.2, also for submenus). Toolbar buttons and window-wide
hotkeys are not hooked: capture mode is for commands clicked in Painter's menus. One click is usually reported more than once;
``core.menu.ActionWatcher`` drops the duplicates.
"""

import logging

from PySide6 import QtCore, QtGui, QtWidgets

from ..core.menu import MENU_PREFIX, OWN_PREFIX, MenuAction, action_id
from .assets import png_bytes, valid

log = logging.getLogger("ShelfPlus.app.actions")

RESCAN_MS = 1000  # while watching, menus created meanwhile (e.g. on project open) get hooked
MAX_MENU_DEPTH = 8


def _is_own(obj):
    try:
        return obj.objectName().startswith(OWN_PREFIX)
    except RuntimeError:
        return True


class _Scan:
    """One pass over ``allWidgets()``: every command with the widget it sits in, and the
    menu titles above each menu. Every widget and command found is put into ``keep``."""

    def __init__(self, keep):
        try:
            self.widgets = list(QtWidgets.QApplication.allWidgets())
        except Exception:
            log.exception("QApplication.allWidgets() failed")
            self.widgets = []
        self.menus = []
        self.parents = {}  # id(submenu) -> the menu it opens from
        self.entries = []  # (QAction, the widget it was found in)
        for obj in list(keep.values()):  # let go of the dead ones only
            if not valid(obj):
                keep.pop(id(obj), None)
        keep.update((id(w), w) for w in self.widgets)
        seen = set()
        for widget in self.widgets:
            try:
                if not valid(widget) or _is_own(widget):
                    continue
                if isinstance(widget, QtWidgets.QMenu):
                    self.menus.append(widget)
                actions = widget.actions()
            except RuntimeError:
                continue
            for action in actions:
                try:
                    submenu = action.menu()
                    if submenu is not None:
                        self.parents.setdefault(id(submenu), widget)
                        continue
                    if action.isSeparator() or isinstance(action, QtWidgets.QWidgetAction) or id(action) in seen:
                        continue
                except RuntimeError:
                    continue
                seen.add(id(action))
                keep[id(action)] = action
                self.entries.append((action, widget))

    def path(self, widget):
        """The titles of the menus ``widget`` sits in, outermost first (``()`` if not a menu)."""
        titles = []
        while isinstance(widget, QtWidgets.QMenu) and len(titles) < MAX_MENU_DEPTH:
            try:
                title = widget.title().replace("&&", "\0").replace("&", "").replace("\0", "&")
            except RuntimeError:
                break
            if title:
                titles.append(title)
            widget = self.parents.get(id(widget))
        return tuple(reversed(titles))


def describe(action, path=()):
    """A ``MenuAction`` for a QAction (``handle`` is the QAction, ``icon`` its QIcon)."""
    return MenuAction(action.objectName(), action.text(), path, QtGui.QIcon(action.icon()), action)


class _Watch:
    """The hooks of one ``watch()``: call it to stop; ``rescan()`` hooks new commands."""

    def __init__(self, callback, keep):
        self.callback = callback
        self._keep = keep
        self._paths = {}  # id(command) -> the titles of the menu it sits in
        self._hooked = {}  # id(obj) -> (obj, signal name, slot); also keeps obj alive
        self._timer = QtCore.QTimer()
        self._timer.setInterval(RESCAN_MS)
        self._timer.timeout.connect(self.rescan)
        self.rescan()
        self._timer.start()

    def _connect(self, obj, signal, slot):
        if id(obj) in self._hooked:
            return
        getattr(obj, signal).connect(slot)
        self._hooked[id(obj)] = (obj, signal, slot)

    def rescan(self):
        before = len(self._hooked)
        scan = _Scan(self._keep)
        for action, widget in scan.entries:
            if _is_own(action) or not isinstance(widget, QtWidgets.QMenu):
                continue
            try:
                path = scan.path(widget)
                self._paths.setdefault(id(action), path)
                self._connect(action, "triggered", lambda checked=False, a=action, p=path: self._report(a, p))
            except RuntimeError:
                continue
        for menu in scan.menus:
            try:
                # Qt reports a submenu's command through every parent menu too, so its
                # place is where it sits, not the menu reporting it.
                path = scan.path(menu)
                self._connect(menu, "triggered", lambda a, p=path: self._report(a, self._paths.get(id(a), p)))
            except RuntimeError:
                continue
        if len(self._hooked) != before:
            log.info(
                "Watching Painter's menus: %d hooks (%d new; %d widgets, %d menus)",
                len(self._hooked), len(self._hooked) - before, len(scan.widgets), len(scan.menus),
            )

    def _report(self, action, path):
        """``path``: the titles of the menu the command was run from."""
        if not valid(action):
            return
        try:
            described = describe(action, path)
        except RuntimeError:
            return
        self.callback(described)

    def __call__(self):
        self._timer.stop()
        hooked, self._hooked = self._hooked, {}
        for obj, signal, slot in hooked.values():
            if not valid(obj):
                continue
            try:
                getattr(obj, signal).disconnect(slot)
            except (RuntimeError, TypeError):
                log.debug("Could not disconnect %r", obj, exc_info=True)


class PainterActions:
    def __init__(self):
        self._keep = {}  # id -> every widget and command found, for the plugin's lifetime

    def _scan(self):
        return _Scan(self._keep)

    def kept(self):
        return list(self._keep.values())

    def all(self):
        """Every command found, each once, with the menus it sits in."""
        scan = self._scan()
        found = []
        for action, widget in scan.entries:
            try:
                found.append(describe(action, scan.path(widget)))
            except RuntimeError:
                continue
        return found

    def find(self, name):
        """The command whose ``core.menu.action_id`` is ``name``: its objectName, or
        ``menu:`` + its place in the menu. An enabled one if there are several; ``None``
        if there is none."""
        if not name:
            return None
        by_place = name.startswith(MENU_PREFIX)
        scan = self._scan()
        first = None
        for action, widget in scan.entries:
            try:
                if by_place:
                    if action.objectName() or not isinstance(widget, QtWidgets.QMenu):
                        continue
                    found = describe(action, scan.path(widget))
                    if action_id(found) != name:
                        continue
                elif action.objectName() == name:
                    found = describe(action, scan.path(widget))
                else:
                    continue
                if action.isEnabled():
                    return found
            except RuntimeError:
                continue
            first = first or found
        return first

    def trigger(self, action):
        """Run the command. ``False`` if Painter has disabled it (nothing is run)."""
        handle = action.handle
        for attempt in range(2):
            if attempt or not valid(handle):  # found again if it died (now or mid-call)
                found = self.find(action.name)
                if found is None:
                    raise RuntimeError(f"the command {action.name!r} is gone")
                handle = found.handle
            try:
                if not handle.isEnabled():
                    return False
                handle.trigger()
                return True
            except RuntimeError:
                if attempt:
                    raise
                log.info("The command %r died; finding it again", action.name)

    def icon_png(self, action):
        """The command's icon as PNG bytes, or ``None`` if it has none."""
        icon = action.icon
        if not isinstance(icon, QtGui.QIcon) or icon.isNull():
            return None
        return png_bytes(icon)

    def watch(self, callback):
        """Report every command run to ``callback(MenuAction)`` until the returned
        function is called."""
        return _Watch(callback, self._keep)
