"""Icons drawn at run time, so the release needs no image files."""

import math

from PySide6 import QtCore, QtGui

KIND_COLOURS = {
    "brush": "#3d8fd1",
    "menu": "#8a63c9",
    "workflow": "#3fa66a",
}
INVALID_COLOUR = "#c0392b"

_SIZE = 64


def _canvas():
    pixmap = QtGui.QPixmap(_SIZE, _SIZE)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    return pixmap, painter


def panel_icon():
    """The Panel's windowIcon: an orange tile with a plus."""
    pixmap, painter = _canvas()
    painter.setBrush(QtGui.QColor("#d9822b"))
    painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
    painter.setBrush(QtGui.QColor("#ffffff"))
    painter.drawRect(28, 16, 8, 32)
    painter.drawRect(16, 28, 32, 8)
    painter.end()
    return QtGui.QIcon(pixmap)


def initials(name):
    """Up to two letters for the automatic icon: "Fill layer + Black mask" -> "FL"."""
    words = [w for w in name.split() if w[:1].isalnum()]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def brush_icon():
    """The generic Brush button icon (no image could be read from the Assets window):
    a brush on the Brush button colour."""
    pixmap, painter = _canvas()
    painter.setBrush(QtGui.QColor(KIND_COLOURS["brush"]))
    painter.drawRoundedRect(2, 2, 60, 60, 10, 10)
    painter.translate(32, 32)
    painter.rotate(45)
    painter.setBrush(QtGui.QColor("#f0d9b5"))
    painter.drawRoundedRect(-4, -4, 8, 26, 3, 3)  # handle
    painter.setBrush(QtGui.QColor("#c8c8c8"))
    painter.drawRect(-6, -10, 12, 7)  # ferrule
    painter.setBrush(QtGui.QColor("#ffffff"))
    painter.drawRoundedRect(-7, -24, 14, 15, 6, 6)  # bristles
    painter.end()
    return QtGui.QIcon(pixmap)


def menu_icon():
    """The generic Menu button icon (the command has no icon of its own): a drop-down
    menu with a highlighted line, on the Menu button colour."""
    pixmap, painter = _canvas()
    painter.setBrush(QtGui.QColor(KIND_COLOURS["menu"]))
    painter.drawRoundedRect(2, 2, 60, 60, 10, 10)
    painter.setBrush(QtGui.QColor("#ffffff"))
    painter.drawRoundedRect(12, 10, 40, 10, 3, 3)  # the menu title
    painter.setBrush(QtGui.QColor("#e6dcf5"))
    painter.drawRect(16, 22, 32, 32)  # the open menu
    painter.setBrush(QtGui.QColor("#5b3d91"))
    for y in (27, 43):
        painter.drawRect(20, y, 24, 4)
    painter.setBrush(QtGui.QColor("#d9822b"))
    painter.drawRect(18, 34, 28, 7)  # the line being clicked
    painter.end()
    return QtGui.QIcon(pixmap)


def with_warning_badge(icon):
    """``icon`` with a small warning triangle in its bottom-right corner (a missing preset)."""
    pixmap = icon.pixmap(_SIZE, _SIZE)
    if pixmap.isNull():
        pixmap = QtGui.QPixmap(_SIZE, _SIZE)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    scale = pixmap.width() / _SIZE
    painter.scale(scale, scale)
    triangle = QtGui.QPolygonF([QtCore.QPointF(48, 32), QtCore.QPointF(64, 62), QtCore.QPointF(32, 62)])
    painter.setPen(QtGui.QPen(QtGui.QColor("#202020"), 2))
    painter.setBrush(QtGui.QColor("#f2b01e"))
    painter.drawPolygon(triangle)
    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    painter.setBrush(QtGui.QColor("#202020"))
    painter.drawRect(QtCore.QRectF(46.5, 40, 3, 12))
    painter.drawRect(QtCore.QRectF(46.5, 55, 3, 3))
    painter.end()
    return QtGui.QIcon(pixmap)


def automatic_icon(button):
    """The icon of a Button whose ``icon`` is ``null``: its kind's colour and its initials
    (a Brush or Menu button: the generic brush or menu icon)."""
    if button.valid and button.kind == "brush":
        return brush_icon()
    if button.valid and button.kind == "menu":
        return menu_icon()
    colour = KIND_COLOURS.get(button.kind, INVALID_COLOUR) if button.valid else INVALID_COLOUR
    text = initials(button.name) if button.valid else "!"
    pixmap, painter = _canvas()
    painter.setBrush(QtGui.QColor(colour))
    painter.drawRoundedRect(2, 2, 60, 60, 10, 10)
    font = painter.font()
    font.setBold(True)
    font.setPixelSize(26)
    painter.setFont(font)
    painter.setPen(QtGui.QColor("#ffffff"))
    painter.drawText(QtCore.QRect(0, 0, _SIZE, _SIZE), QtCore.Qt.AlignmentFlag.AlignCenter, text)
    painter.end()
    return QtGui.QIcon(pixmap)


def trash_icon():
    """A bin, drawn here: ``style().standardIcon`` cannot be used, because on Painter 11.1
    the Python wrapper of the application style is already deleted."""
    pixmap, painter = _canvas()
    colour = QtGui.QColor("#d0d0d0")
    painter.setBrush(colour)
    painter.drawRoundedRect(14, 12, 36, 6, 2, 2)  # lid
    painter.drawRect(26, 6, 12, 6)  # handle
    painter.drawRoundedRect(18, 22, 28, 36, 4, 4)  # body
    painter.setBrush(QtGui.QColor("#5a5a5a"))
    for x in (25, 31, 37):
        painter.drawRect(x, 28, 3, 24)  # slats
    painter.end()
    return QtGui.QIcon(pixmap)


def plus_icon():
    """The "+" of a Group row: thick light bars, so it stands out on Painter's dark theme
    (the font's "+" was hard to see)."""
    pixmap, painter = _canvas()
    painter.setBrush(QtGui.QColor("#e6e6e6"))
    painter.drawRoundedRect(27, 8, 10, 48, 4, 4)
    painter.drawRoundedRect(8, 27, 48, 10, 4, 4)
    painter.end()
    return QtGui.QIcon(pixmap)


# -- the Step icon set (PRD R7.6) ----------------------------------------------------
#
# One colour per kind of Step: layers blue-grey, masks grey, effects teal, settings amber,
# saving green. A Workflow without its own icon shows its first Step's icon.

STEP_COLOURS = {
    "layer": "#4a6d8c",
    "mask": "#5f5f5f",
    "effect": "#2f8f8a",
    "setting": "#b07d1f",
    "save": "#3fa66a",
}


def _tile(colour):
    pixmap, painter = _canvas()
    painter.setBrush(QtGui.QColor(colour))
    painter.drawRoundedRect(2, 2, 60, 60, 10, 10)
    return pixmap, painter


def _layers(painter, top_colour="#ffffff"):
    """Three stacked layer slabs; the top one in ``top_colour``."""
    for y, colour in ((40, "#9fb6c9"), (30, "#c9d8e4"), (20, top_colour)):
        painter.setBrush(QtGui.QColor(colour))
        painter.drawPolygon(QtGui.QPolygonF([
            QtCore.QPointF(32, y - 8), QtCore.QPointF(54, y), QtCore.QPointF(32, y + 8), QtCore.QPointF(10, y),
        ]))


def _star(painter, cx, cy, r, colour="#ffffff"):
    points = []
    for i in range(8):
        radius = r if i % 2 == 0 else r * 0.38
        angle = i * math.pi / 4
        points.append(QtCore.QPointF(cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    painter.setBrush(QtGui.QColor(colour))
    painter.drawPolygon(QtGui.QPolygonF(points))


def _mask(painter, background="black"):
    """A square split white / black, the mask's background bigger."""
    painter.setBrush(QtGui.QColor("#ffffff"))
    painter.drawRect(14, 14, 36, 36)
    painter.setBrush(QtGui.QColor("#101010"))
    if background == "black":
        painter.drawRect(14, 14, 36, 36)
        painter.setBrush(QtGui.QColor("#ffffff"))
        painter.drawEllipse(24, 24, 16, 16)
    else:
        painter.drawEllipse(24, 24, 16, 16)


def step_icon(step, action_png=None):
    """The bundled icon of a Step; ``select_brush`` gets the brush icon and ``run_action``
    its command's icon (``action_png``) or the generic menu icon."""
    kind = step.get("type")
    if kind == "select_brush":
        return brush_icon()
    if kind == "run_action":
        if action_png:
            pixmap = QtGui.QPixmap()
            if pixmap.loadFromData(action_png):
                return QtGui.QIcon(pixmap)
        return menu_icon()
    if kind == "add_layer":
        pixmap, painter = _tile(STEP_COLOURS["layer"])
        top = {"fill": "#7fc4f0", "paint": "#ffffff", "folder": "#f0c96a"}.get(step.get("layer"), "#ffffff")
        _layers(painter, top)
    elif kind == "select_layer":
        pixmap, painter = _tile(STEP_COLOURS["layer"])
        _layers(painter)
        painter.setBrush(QtGui.QColor("#d9822b"))  # a pointer on the top layer
        painter.drawPolygon(QtGui.QPolygonF([
            QtCore.QPointF(36, 26), QtCore.QPointF(56, 40), QtCore.QPointF(47, 42), QtCore.QPointF(52, 54),
            QtCore.QPointF(47, 56), QtCore.QPointF(42, 44), QtCore.QPointF(36, 50),
        ]))
    elif kind == "add_smart" and step.get("smart") == "material":
        pixmap, painter = _tile(STEP_COLOURS["layer"])
        _layers(painter, "#f0c96a")
        _star(painter, 46, 46, 12, "#d9822b")
    elif kind == "add_mask":
        pixmap, painter = _tile(STEP_COLOURS["mask"])
        _mask(painter, step.get("background"))
    elif kind == "add_smart":
        pixmap, painter = _tile(STEP_COLOURS["mask"])
        _mask(painter)
        _star(painter, 46, 46, 12, "#d9822b")
    elif kind == "add_effect":
        pixmap, painter = _tile(STEP_COLOURS["effect"])
        effect = step.get("effect")
        painter.setBrush(QtGui.QColor("#ffffff"))
        if effect == "generator":
            _star(painter, 32, 32, 22)
        elif effect == "filter":
            painter.drawPolygon(QtGui.QPolygonF([
                QtCore.QPointF(12, 14), QtCore.QPointF(52, 14), QtCore.QPointF(36, 34),
                QtCore.QPointF(36, 52), QtCore.QPointF(28, 48), QtCore.QPointF(28, 34),
            ]))
        elif effect == "fill":  # a filled square
            painter.drawRoundedRect(14, 14, 36, 36, 4, 4)
        elif effect == "paint":  # a brush stroke
            painter.save()
            painter.translate(32, 32)
            painter.rotate(-35)
            painter.drawRoundedRect(-22, -7, 44, 14, 7, 7)
            painter.restore()
        elif effect == "levels":
            for x, h in ((14, 14), (24, 30), (34, 22), (44, 38)):
                painter.drawRect(x, 52 - h, 7, h)
        else:  # the anchor point
            painter.drawEllipse(26, 10, 12, 12)
            painter.drawRect(30, 20, 4, 30)
            painter.drawRect(18, 28, 28, 4)
            painter.drawPie(14, 30, 36, 24, 180 * 16, 180 * 16)
            painter.setBrush(QtGui.QColor(STEP_COLOURS["effect"]))
            painter.drawPie(20, 30, 24, 16, 180 * 16, 180 * 16)
        if step.get("target") == "mask":
            painter.setBrush(QtGui.QColor("#101010"))  # a small mask badge
            painter.drawRect(44, 44, 14, 14)
    elif kind == "set_blend":
        pixmap, painter = _tile(STEP_COLOURS["setting"])
        painter.setBrush(QtGui.QColor(255, 255, 255, 200))
        painter.drawEllipse(10, 16, 30, 30)
        painter.setBrush(QtGui.QColor(32, 32, 32, 160))
        painter.drawEllipse(24, 16, 30, 30)
    elif kind == "set_opacity":
        pixmap, painter = _tile(STEP_COLOURS["setting"])
        for row in range(4):  # a checkerboard fading out
            for col in range(4):
                if (row + col) % 2 == 0:
                    painter.setBrush(QtGui.QColor(255, 255, 255, 60 + 60 * col))
                    painter.drawRect(12 + col * 10, 12 + row * 10, 10, 10)
    elif kind == "set_fill":  # a filled square, half of it changed
        pixmap, painter = _tile(STEP_COLOURS["setting"])
        painter.setBrush(QtGui.QColor(255, 255, 255, 200))
        painter.drawRoundedRect(14, 14, 36, 36, 4, 4)
        painter.setBrush(QtGui.QColor(32, 32, 32, 160))
        painter.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(50, 14), QtCore.QPointF(50, 50), QtCore.QPointF(14, 50)]))
    elif kind == "save":
        pixmap, painter = _tile(STEP_COLOURS["save"])
        painter.setBrush(QtGui.QColor("#ffffff"))  # a floppy disk
        painter.drawRoundedRect(14, 14, 36, 36, 4, 4)
        painter.setBrush(QtGui.QColor(STEP_COLOURS["save"]))
        painter.drawRect(22, 14, 18, 12)
        painter.drawRect(20, 34, 24, 14)
    else:
        pixmap, painter = _tile(INVALID_COLOUR)
    painter.end()
    return QtGui.QIcon(pixmap)
