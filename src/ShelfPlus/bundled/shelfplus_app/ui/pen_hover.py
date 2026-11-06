"""Hover names for the pen (PRD R2.6).

Qt's own tooltip does not appear with a pen in Painter. While the Panel is visible,
this helper polls ``QCursor.pos()`` + ``widgetAt`` every ~100 ms, and after ~600 ms
over one Panel element shows that element's ``toolTip()`` with ``QToolTip.showText``.
The mouse keeps Qt's normal tooltip; hover highlight is untouched.
"""

from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid

from ..core.hover import SHOW, HoverTracker

POLL_MS = 100
DELAY_MS = 600


class PenHover(QtCore.QObject):
    def __init__(self, root, paused=lambda: False):
        super().__init__(root)  # parented: it cannot outlive the Panel
        self.root = root
        self.paused = paused
        self.tracker = HoverTracker(DELAY_MS)
        self.clock = QtCore.QElapsedTimer()
        self.clock.start()
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.tick)
        root.installEventFilter(self)
        if root.isVisible():
            self.timer.start()

    def eventFilter(self, obj, event):
        if obj is self.root:
            if event.type() == QtCore.QEvent.Type.Show:
                self.timer.start()
            elif event.type() == QtCore.QEvent.Type.Hide:
                self.timer.stop()
                self._apply(self.tracker.tick(self.clock.elapsed(), None, ""), None)
        return False

    def stop(self):
        self.timer.stop()

    def named_element(self, widget):
        """The nearest widget at or above ``widget`` inside the Panel that has a name."""
        root = self.root
        if widget is None or not (widget is root or root.isAncestorOf(widget)):
            return None, ""
        while widget is not None:
            text = widget.toolTip()
            if text:
                return widget, text
            if widget is root:
                break
            widget = widget.parentWidget()
        return None, ""

    def tick(self):
        if not isValid(self.root) or not self.root.isVisible():
            return
        if self.paused():
            target, text = None, ""
            pos = None
        else:
            pos = QtGui.QCursor.pos()
            target, text = self.named_element(QtWidgets.QApplication.widgetAt(pos))
        showing = QtWidgets.QToolTip.isVisible()
        self._apply(self.tracker.tick(self.clock.elapsed(), target, text, showing), pos)

    def _apply(self, action, pos):
        if action is None:
            return
        if action[0] == SHOW:
            QtWidgets.QToolTip.showText(pos, action[1], self.root)
        else:
            QtWidgets.QToolTip.hideText()
