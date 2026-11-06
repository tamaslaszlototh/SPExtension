"""Icons drawn at run time, so the release needs no image files."""

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


def automatic_icon(button):
    """The icon of a Button whose ``icon`` is ``null``: its kind's colour and its initials."""
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
