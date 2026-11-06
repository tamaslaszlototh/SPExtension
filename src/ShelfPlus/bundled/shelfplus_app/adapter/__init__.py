"""The adapter layer: everything Painter-specific lives behind it.

The core and the App never import ``substance_painter``. They talk to an adapter
with this interface:

- ``add_dock_widget(widget) -> handle``: dock the Panel in Painter's Edition mode.
- ``delete_ui_element(handle)``: remove a UI element added earlier.
- ``painter_version() -> str``
- ``qt_version() -> str``

``painter.PainterAdapter`` is the real one; ``fake.FakeAdapter`` is used by tests.
"""
