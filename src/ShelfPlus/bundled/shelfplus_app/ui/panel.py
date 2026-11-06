"""The Panel shell (PRD R2.1, R2.7). This slice lists the Layout as plain text."""

import logging

from PySide6 import QtCore, QtGui, QtWidgets

from shiboken6 import isValid

log = logging.getLogger("ShelfPlus.app.panel")

OBJECT_NAME = "ShelfPlusPanel"
STATUS_MS = 3000


def make_icon():
    """The Panel's windowIcon, drawn at run time so no image file is needed."""
    pixmap = QtGui.QPixmap(64, 64)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor("#d9822b"))
    painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
    painter.setBrush(QtGui.QColor("#ffffff"))
    painter.drawRect(28, 16, 8, 32)
    painter.drawRect(16, 28, 32, 8)
    painter.end()
    return QtGui.QIcon(pixmap)


class QtPanelView:
    """The Panel widget. ``app`` provides ``version`` and ``diagnostics_text()``."""

    def __init__(self, app):
        self.app = app
        widget = QtWidgets.QWidget()
        widget.setObjectName(OBJECT_NAME)
        widget.setWindowTitle("Shelf+")
        widget.setWindowIcon(make_icon())
        self.widget = widget

        root = QtWidgets.QVBoxLayout(widget)
        root.setContentsMargins(6, 6, 6, 6)

        bar = QtWidgets.QHBoxLayout()
        self.status = QtWidgets.QLabel()
        self.status.setObjectName(OBJECT_NAME + "Status")
        bar.addWidget(self.status, 1)
        self.panel_menu_tool = QtWidgets.QToolButton()
        self.panel_menu_tool.setObjectName(OBJECT_NAME + "Menu")
        self.panel_menu_tool.setText("☰")
        self.panel_menu_tool.setToolTip("Shelf+ menu")
        self.panel_menu_tool.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.menu = QtWidgets.QMenu(self.panel_menu_tool)
        version_action = self.menu.addAction(f"Shelf+ v{app.version}")
        version_action.setEnabled(False)
        self.menu.addSeparator()
        self.copy_action = self.menu.addAction("Copy diagnostics")
        self.copy_action.triggered.connect(self.copy_diagnostics)
        self.panel_menu_tool.setMenu(self.menu)
        bar.addWidget(self.panel_menu_tool)
        root.addLayout(bar)

        self.messages = QtWidgets.QLabel()
        self.messages.setObjectName(OBJECT_NAME + "Messages")
        self.messages.setWordWrap(True)
        self.messages.setTextFormat(QtCore.Qt.PlainText)
        self.messages.hide()
        root.addWidget(self.messages)

        self.listing = QtWidgets.QLabel()
        self.listing.setObjectName(OBJECT_NAME + "Layout")
        self.listing.setTextFormat(QtCore.Qt.PlainText)
        self.listing.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.listing.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidget(self.listing)
        root.addWidget(scroll, 1)

        # Parented to the widget, so it cannot fire after the Panel is gone.
        self.status_timer = QtCore.QTimer(widget)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self.status.clear)

    def show_layout(self, lines, read_only, messages):
        self.listing.setText("\n".join(lines) if lines else "(The Layout is empty.)")
        self.messages.setText("\n".join(messages))
        self.messages.setVisible(bool(messages))

    def copy_diagnostics(self):
        text = self.app.diagnostics_text()
        QtGui.QGuiApplication.clipboard().setText(text)
        log.info("Diagnostics copied to the clipboard")
        self.status.setText("Diagnostics copied.")
        self.status_timer.start(STATUS_MS)

    def dispose(self):
        widget, self.widget = self.widget, None
        if widget is not None and isValid(widget):
            self.status_timer.stop()
            widget.deleteLater()
