"""The adapter layer: everything Painter-specific lives behind it.

The core and the App never import ``substance_painter``. They talk to an adapter
with this interface:

- ``add_dock_widget(widget) -> handle``: dock the Panel in Painter's Edition mode.
- ``delete_ui_element(handle)``: remove a UI element added earlier.
- ``painter_version() -> str``
- ``qt_version() -> str``

Brush buttons (``core/brush.py``):

- ``resolve_resource(url) -> core.brush.BrushResource | None``: look up a version-less
  ``resource://`` URL.
- ``resources_loading() -> bool``: Painter is still loading resources (shelf crawling).
- ``on_resources_loaded(callback) -> disconnect``: ``callback()`` when a shelf finishes loading.
- ``resource_file_path(resource) -> str | None``: the file behind it (e.g. the ``.sppr``).
- ``assets_icon_sources(resource) -> (tooltip HTML, DecorationRole PNG bytes)``.
- ``open_assets() -> bool``, ``show_in_ui(resource)``, ``tile_rect(gui_name)`` and
  ``click_tile(rect)``: the Assets window automation (``assets.AssetsWindow``).
- ``repeat(interval_ms, callback) -> timer``: a repeating timer with ``stop()``.

Menu buttons (``core/menu.py``), Painter's commands as ``core.menu.MenuAction``:

- ``list_actions() -> [MenuAction]``: every command found (``actions.PainterActions``).
- ``project_open() -> bool``: a project is open (many menus exist only then).
- ``find_action(name) -> MenuAction | None``: the command with that ``objectName``.
- ``action_icon_png(action) -> bytes | None``: its icon, or ``None`` if it has none.
- ``trigger_action(action) -> bool``: run it; ``False`` if Painter has disabled it.
- ``watch_actions(callback) -> stop``: ``callback(action)`` for every hook call
  (``QAction.triggered``, ``QMenu.triggered``) until ``stop()``; duplicates included.

``painter.PainterAdapter`` is the real one; ``fake.FakeAdapter`` is used by tests.
"""
