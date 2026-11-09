"""Smart material buttons (issue #47), without Qt or Painter.

A Smart material button is created like a Brush button, by a drop from the Assets window
(``core/brush.py`` reads the drop and the icon). Clicked, it runs as a Workflow with one
``add_smart`` Step (``smart_material_step``). Dragged out of the Panel onto Painter's
Layers window, it carries the same ``text/uri-list`` as the Assets window's drag
(``drag_uri_list``), and Painter handles the drop itself.
"""

from urllib.parse import quote

SMART_MATERIAL = "smart material"  # Painter's resource type for people, lower case


def is_smart_material(resource):
    """Whether a resolved resource is a smart material (Painter tells it by its type)."""
    return not resource.is_brush and (resource.kind or "").lower() == SMART_MATERIAL


def smart_material_button(resource):
    """The Layout's JSON for a new Smart material button, without ``id`` and ``icon``."""
    return {"kind": "smart_material", "name": resource.gui_name, "resource": resource.url}


def smart_material_step(button):
    """The one ``add_smart`` Step a Smart material button runs."""
    raw = button.raw
    return {"type": "add_smart", "smart": "material", "resource": raw["resource"], "resource_name": raw["name"]}


def drag_uri_list(url):
    """The ``text/uri-list`` of a Smart material button dragged onto Painter: its URL,
    percent-encoded as in the Assets window's drag."""
    return quote(url, safe=":/?=&") + "\r\n"


def missing_message(url):
    return f"This smart material is not available on this machine: {url}"
