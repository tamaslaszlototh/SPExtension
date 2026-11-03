# SPExtension próba-plugin („SPX Probe”).
#
# Telepítés: a teljes `spx_probe` mappát ide kell másolni:
#   <Documents>\Adobe\Adobe Substance 3D Painter\python\plugins\spx_probe\
# A részletes lépéseket lásd: LEPESEK.md
#
# A panel három dolgot mér/futtat:
#   - maga a panel: megmarad-e a plugin bekapcsolt állapota és a panel helye újraindítás után
#     (minden indítás/kilépés naplózódik: %APPDATA%\spx_probe\spx_probe.log)
#   - „1. Diagnosztika” gomb: verziók, útvonalak, hálózat, menüparancsok
#   - „2. Layer stack teszt” gomb: ScopedModification próbák (eldobható projekt kell!)

import os, datetime, importlib

from PySide6 import QtWidgets, QtCore, QtGui
import substance_painter.ui as ui

from . import checks

_widgets = []
_LOG = os.path.join(checks.REPORT_DIR, "spx_probe.log")


def _log(msg):
    os.makedirs(checks.REPORT_DIR, exist_ok=True)
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")


def _dock_of(w):
    d = w.parentWidget()
    while d is not None and not isinstance(d, QtWidgets.QDockWidget):
        d = d.parentWidget()
    return d


def _geom(d):
    g = d.geometry()
    if d.isFloating():
        g = d.frameGeometry()
    screen = d.screen().name() if d.screen() else "?"
    return f"floating={d.isFloating()} visible={d.isVisible()} geom=({g.x()},{g.y()},{g.width()}x{g.height()}) screen={screen}"


def _run(w, status, fn, label):
    status.setText(f"{label} fut… (akár 30 mp)")
    QtWidgets.QApplication.processEvents()
    QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
    try:
        importlib.reload(checks)
        path = fn()
        status.setText(f"{label} kész:\n{path}")
        QtWidgets.QMessageBox.information(w, "SPX Probe", f"{label} kész.\n\nA riport itt van:\n{path}")
    except Exception as e:
        status.setText(f"{label} HIBA: {e}")
        QtWidgets.QMessageBox.warning(w, "SPX Probe", f"{label} hiba:\n{e}")
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()


def start_plugin():
    w = QtWidgets.QWidget()
    w.setObjectName("spx_probe_panel")
    w.setWindowTitle("SPX Probe")
    lay = QtWidgets.QVBoxLayout(w)
    status = QtWidgets.QLabel("Kész. A gombokat a LEPESEK.md szerinti sorrendben használd.")
    status.setWordWrap(True)

    b1 = QtWidgets.QPushButton("1. Diagnosztika futtatása")
    b1.clicked.connect(lambda: _run(w, status, checks.run_diagnostics, "Diagnosztika"))
    b2 = QtWidgets.QPushButton("2. Layer stack teszt (eldobható projekt kell!)")
    b2.clicked.connect(lambda: _run(w, status, checks.run_layerstack, "Layer stack teszt"))
    b3 = QtWidgets.QPushButton("Riport mappa megnyitása")

    def open_dir():
        os.makedirs(checks.REPORT_DIR, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(checks.REPORT_DIR))

    b3.clicked.connect(open_dir)
    for b in (b1, b2, b3):
        lay.addWidget(b)
    lay.addWidget(status)
    lay.addStretch(1)

    ui.add_dock_widget(w)
    _widgets.append(w)

    def report():
        d = _dock_of(w)
        _log("START " + (_geom(d) if d else "dock nem található"))

    QtCore.QTimer.singleShot(3000, report)  # a Painter addigra visszaállítja az elrendezést


def close_plugin():
    for w in _widgets:
        d = _dock_of(w)
        if d is not None:
            _log("CLOSE " + _geom(d))
        ui.delete_ui_element(w)
    _widgets.clear()
