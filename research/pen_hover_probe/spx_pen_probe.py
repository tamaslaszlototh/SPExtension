"""SPExtension - pen hover / tooltip probe (throwaway, see research/pen-hover-tooltip.md).

Install: copy this file to
    Documents\\Adobe\\Adobe Substance 3D Painter\\python\\plugins\\
then in Painter: Python menu -> spx_pen_probe (enable it).
A dock "SPX pen probe" appears. Follow the steps written in the dock,
then press "Save report" and send the saved .txt file back.
"""

import os
import time

from PySide6 import QtCore, QtGui, QtWidgets

try:
    import substance_painter.ui as spui
except ImportError:  # allows a quick standalone smoke test outside Painter
    spui = None

E = QtCore.QEvent
Qt = QtCore.Qt

WATCH = {
    E.Enter, E.Leave, E.HoverEnter, E.HoverMove, E.HoverLeave,
    E.MouseMove, E.ToolTip,
    E.TabletMove, E.TabletPress, E.TabletRelease,
    E.TabletEnterProximity, E.TabletLeaveProximity,
}
PROXIMITY = {E.TabletEnterProximity, E.TabletLeaveProximity}
DWELL_MS = 600
MAX_SAMPLES_PER_KEY = 5


def _ename(t):
    return getattr(t, "name", str(t))


def _describe(ev):
    """Short, crash-safe description of a mouse / tablet event."""
    parts = []
    for attr in ("buttons",):
        try:
            parts.append("buttons=%s" % getattr(ev, attr)())
        except Exception:
            pass
    try:
        dev = ev.device()
        parts.append("dev=%s/%s" % (_ename(dev.type()), dev.name()))
    except Exception:
        pass
    try:
        parts.append("ptr=%s" % _ename(ev.pointerType()))
    except Exception:
        pass
    try:
        parts.append("source=%s" % _ename(ev.source()))
    except Exception:
        pass
    try:
        parts.append("pressure=%.2f" % ev.pressure())
    except Exception:
        pass
    try:
        parts.append("accepted=%s" % ev.isAccepted())
    except Exception:
        pass
    return " ".join(parts)


class Recorder:
    def __init__(self):
        self.counts = {}
        self.samples = []
        self._per_key = {}
        self.t0 = time.time()

    def hit(self, layer, target, ev):
        key = (layer, target, _ename(ev.type()))
        self.counts[key] = self.counts.get(key, 0) + 1
        n = self._per_key.get(key, 0)
        if n < MAX_SAMPLES_PER_KEY:
            self._per_key[key] = n + 1
            self.samples.append("%7.2fs %-4s %-10s %-22s %s" % (
                time.time() - self.t0, layer, target, _ename(ev.type()), _describe(ev)))

    def note(self, text):
        self.samples.append("%7.2fs NOTE %s" % (time.time() - self.t0, text))

    def reset(self):
        self.__init__()


class Probe(QtCore.QObject):
    """Event filter. layer='app' when installed on QApplication, 'obj' on the buttons."""

    def __init__(self, layer, targets, rec, on_app_tablet=None):
        super().__init__()
        self.layer = layer
        self.targets = targets
        self.rec = rec
        self.on_app_tablet = on_app_tablet

    def eventFilter(self, obj, ev):
        try:
            t = ev.type()
            if t not in WATCH:
                return False
            name = self.targets.get(obj)
            if name is None:
                if t in PROXIMITY and self.layer == "app":
                    self.rec.hit(self.layer, "QApplication", ev)
                return False
            self.rec.hit(self.layer, name, ev)
            if self.on_app_tablet and t == E.TabletMove:
                self.on_app_tablet(obj, ev)
        except Exception as exc:  # never break Painter's event loop
            self.rec.note("filter error: %r" % exc)
        return False  # observe only, never consume


class DwellTip(QtCore.QObject):
    """Shows QToolTip.showText after the pointer rests on a widget; hides when it leaves.
    Uses QCursor.pos() polling for leave detection, so it needs no Leave/MouseMove events."""

    def __init__(self, rec, label):
        super().__init__()
        self.rec = rec
        self.label = label
        self.widget = None
        self.shown = False
        self.dwell = QtCore.QTimer(self, singleShot=True, interval=DWELL_MS)
        self.dwell.timeout.connect(self._show)
        self.watch = QtCore.QTimer(self, interval=100)
        self.watch.timeout.connect(self._check_leave)

    def pointer_over(self, widget):
        if widget is not self.widget:
            self.widget = widget
            self.shown = False
            self.dwell.start()
            self.watch.start()

    def _inside(self):
        w = self.widget
        return w is not None and w.isVisible() and w.rect().contains(w.mapFromGlobal(QtGui.QCursor.pos()))

    def _show(self):
        if self._inside():
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), self.widget.toolTip(), self.widget)
            self.shown = True
            self.rec.note("%s: custom tooltip shown" % self.label)

    def _check_leave(self):
        if not self._inside():
            if self.shown:
                QtWidgets.QToolTip.hideText()
            self.widget = None
            self.shown = False
            self.dwell.stop()
            self.watch.stop()


class TabletTipButton(QtWidgets.QToolButton):
    """Variant B: widget-level tablet tracking + own tooltip from tabletEvent."""

    def __init__(self, text, tip, rec):
        super().__init__()
        self.setText(text)
        self.setToolTip(tip)
        self.setTabletTracking(True)
        self.rec = rec
        self.dwell = DwellTip(rec, "B")

    def tabletEvent(self, ev):
        self.rec.hit("hndl", "B", ev)
        if ev.type() == E.TabletMove and ev.buttons() == Qt.NoButton:
            self.dwell.pointer_over(self)
        ev.ignore()  # keep Qt's mouse synthesis possible


INSTRUCTIONS = (
    "Lepesek (mindegyiknel kb. 3 mp-ig tartsd a kurzort a gomb folott, ne kattints):\n"
    "1. Reset. EGERREL: A, B, C, D gomb. Latszik a tooltip?\n"
    "2. Reset. TOLLAL lebegtetve (nem erinti a tablat): A, B, C, D gomb.\n"
    "3. Tollal egy Painter-sajat gomb/ikon folott (pl. felso toolbar). Van tooltip?\n"
    "4. Ird be a megfigyeleseket a lenti mezobe, majd 'Save report'.\n"
    "Ha van ido: ismeteld a 2. lepest ugy is, hogy a tablameghajtoban\n"
    "a Windows Ink KI van kapcsolva (Painter ujrainditas kell), majd vissza BE."
)


class ProbeDock(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("spx_pen_probe_dock")
        self.setWindowTitle("SPX pen probe")
        self.rec = Recorder()

        self.btn_a = QtWidgets.QToolButton(text="A: Qt tooltip")
        self.btn_a.setToolTip("A - beepitett QToolTip (setToolTip)")
        self.btn_b = TabletTipButton("B: tabletEvent", "B - sajat tooltip a widget tabletEvent-jebol", self.rec)
        self.btn_c = QtWidgets.QToolButton(text="C: app filter")
        self.btn_c.setToolTip("C - sajat tooltip az alkalmazas-szintu eventFilterbol")
        self.btn_d = QtWidgets.QToolButton(text="D: cursor poll")
        self.btn_d.setToolTip("D - sajat tooltip QCursor.pos() lekerdezesbol (esemenyfuggetlen)")
        for b in (self.btn_a, self.btn_b, self.btn_c, self.btn_d):
            b.setMinimumSize(110, 48)
            b.setAttribute(Qt.WA_Hover, True)
            b.setStyleSheet("QToolButton:hover { background: #3a6; }")

        self.targets = {self.btn_a: "A", self.btn_b: "B", self.btn_c: "C", self.btn_d: "D"}
        self.tip_c = DwellTip(self.rec, "C")
        self.tip_d = DwellTip(self.rec, "D")

        self.obj_probe = Probe("obj", self.targets, self.rec)
        for b in self.targets:
            b.installEventFilter(self.obj_probe)
        # Installed last on QApplication -> runs before Painter's own app-level filters.
        self.app_probe = Probe("app", self.targets, self.rec, on_app_tablet=self._app_tablet)
        QtWidgets.QApplication.instance().installEventFilter(self.app_probe)

        self.poll = QtCore.QTimer(self, interval=100)
        self.poll.timeout.connect(self._poll_cursor)
        self.poll.start()

        self.notes = QtWidgets.QPlainTextEdit()
        self.notes.setPlaceholderText("Megfigyelesek: pl. 'egér: A ok, B ok... toll: A nincs, D ok, Painter gomb: nincs'")
        btn_reset = QtWidgets.QPushButton("Reset")
        btn_reset.clicked.connect(self._reset)
        btn_save = QtWidgets.QPushButton("Save report")
        btn_save.clicked.connect(self._save)
        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)

        grid = QtWidgets.QGridLayout()
        grid.addWidget(self.btn_a, 0, 0)
        grid.addWidget(self.btn_b, 0, 1)
        grid.addWidget(self.btn_c, 1, 0)
        grid.addWidget(self.btn_d, 1, 1)
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(INSTRUCTIONS)
        info.setWordWrap(True)
        lay.addWidget(info)
        lay.addLayout(grid)
        lay.addWidget(self.notes)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(btn_reset)
        row.addWidget(btn_save)
        lay.addLayout(row)
        lay.addWidget(self.status)

    def _app_tablet(self, obj, ev):
        if obj is self.btn_c and ev.buttons() == Qt.NoButton:
            self.tip_c.pointer_over(self.btn_c)

    def _poll_cursor(self):
        w = QtWidgets.QApplication.widgetAt(QtGui.QCursor.pos())
        if w is self.btn_d:
            self.tip_d.pointer_over(self.btn_d)

    def _reset(self):
        self.rec.reset()
        self.status.setText("Reset kesz.")

    def _env(self):
        app = QtWidgets.QApplication.instance()
        lines = []
        try:
            import PySide6
            lines.append("PySide6 %s, Qt runtime %s" % (PySide6.__version__, QtCore.qVersion()))
        except Exception as exc:
            lines.append("version error %r" % exc)
        try:
            import substance_painter as sp
            lines.append("Painter %s" % (sp.application.version(),))
        except Exception as exc:
            lines.append("Painter version n/a (%r)" % exc)
        lines.append("platform=%s" % QtGui.QGuiApplication.platformName())
        for attr in ("AA_SynthesizeMouseForUnhandledTabletEvents", "AA_CompressHighFrequencyEvents",
                     "AA_CompressTabletEvents", "AA_SynthesizeMouseForUnhandledTouchEvents"):
            a = getattr(Qt, attr, None)
            if a is not None:
                lines.append("%s=%s" % (attr, app.testAttribute(a)))
        lines.append("QT_QPA_PLATFORM=%r" % os.environ.get("QT_QPA_PLATFORM"))
        lines.append("arguments=%r" % (app.arguments(),))
        try:
            lines.append("input devices: %s" % ", ".join(
                "%s(%s)" % (d.name(), _ename(d.type())) for d in QtGui.QInputDevice.devices()))
        except Exception as exc:
            lines.append("devices n/a %r" % exc)
        lines.append("toolTipWakeUp style hint ms=%s" % self.style().styleHint(QtWidgets.QStyle.SH_ToolTip_WakeUpDelay))
        lines.append("dock window active=%s, isWindow(top)=%s" % (self.isActiveWindow(), self.window().objectName()))
        return lines

    def _save(self):
        base = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "SPExtension")
        os.makedirs(base, exist_ok=True)
        path = os.path.join(base, "pen_probe_%s.txt" % time.strftime("%Y%m%d_%H%M%S"))
        out = ["# SPX pen probe report", ""]
        out += self._env()
        out += ["", "## Observations", self.notes.toPlainText(), "", "## Counts (layer target event: n)"]
        for (layer, target, ev), n in sorted(self.rec.counts.items()):
            out.append("%s %s %s: %d" % (layer, target, ev, n))
        out += ["", "## First samples"] + self.rec.samples
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out))
        self.status.setText("Mentve: %s" % path)

    def teardown(self):
        self.poll.stop()
        QtWidgets.QApplication.instance().removeEventFilter(self.app_probe)


_DOCK = None


def start_plugin():
    global _DOCK
    _DOCK = ProbeDock()
    if spui is not None:
        spui.add_dock_widget(_DOCK)
    else:
        _DOCK.show()


def close_plugin():
    global _DOCK
    if _DOCK is not None:
        _DOCK.teardown()
        if spui is not None:
            spui.delete_ui_element(_DOCK)
        _DOCK = None


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    start_plugin()
    app.exec()
