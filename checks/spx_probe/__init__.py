# SPExtension próba-plugin: plugin-bekapcsolás és Panel-pozíció megmaradásának ellenőrzése.
#
# Telepítés: a teljes `spx_probe` mappát másold ide:
#   <Documents>\Adobe\Adobe Substance 3D Painter\python\plugins\spx_probe\
# (a pontos útvonalat a spx_check.py 2. pontja kiírja).
#
# Teszt:
#   1. Painter -> Python menü -> kapcsold be a "spx_probe"-ot. Megjelenik egy "SPX Probe" panel.
#   2. Tedd lebegővé, húzd egy jól felismerhető helyre (ha van második monitor, oda).
#   3. Lépj ki a Painterből, indítsd újra.
#   4. Figyeld meg: magától betöltődött-e a plugin, és ugyanott van-e a panel.
#   Minden indítás naplózódik ide: %APPDATA%\spx_probe.log (a spx_check.py is kiírja).

import os, datetime

from PySide6 import QtWidgets
import substance_painter.ui as ui

_widgets = []
_LOG = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "spx_probe.log")


def _log(msg):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")


def start_plugin():
    w = QtWidgets.QWidget()
    w.setObjectName("spx_probe_panel")
    w.setWindowTitle("SPX Probe")
    lay = QtWidgets.QVBoxLayout(w)
    lay.addWidget(QtWidgets.QLabel("SPX Probe – húzz arrébb, majd indítsd újra a Paintert"))
    ui.add_dock_widget(w)
    _widgets.append(w)

    def report():
        d = w.parentWidget()
        while d is not None and not isinstance(d, QtWidgets.QDockWidget):
            d = d.parentWidget()
        if d is None:
            _log("start: dock nem található")
            return
        g = d.geometry()
        screen = d.screen().name() if d.screen() else "?"
        _log(f"start: floating={d.isFloating()} visible={d.isVisible()} "
             f"geom=({g.x()},{g.y()},{g.width()}x{g.height()}) screen={screen} dock_objectName={d.objectName()!r}")

    from PySide6 import QtCore
    QtCore.QTimer.singleShot(3000, report)  # a Painter addigra visszaállítja az elrendezést


def close_plugin():
    for w in _widgets:
        d = w.parentWidget()
        while d is not None and not isinstance(d, QtWidgets.QDockWidget):
            d = d.parentWidget()
        if d is not None:
            g = d.geometry()
            _log(f"close: floating={d.isFloating()} geom=({g.x()},{g.y()},{g.width()}x{g.height()})")
        ui.delete_ui_element(w)
    _widgets.clear()
