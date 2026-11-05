# PROTOTYPE – eldobható próba-plugin („SPX Brush Probe”), nem kerül a main ágra.
# Kérdés: hogyan tud egy Brush button ténylegesen aktiválni egy brush presetet, és honnan veszi az ikonját?
#
# Telepítés: a teljes `spx_brush_probe` mappát ide kell másolni:
#   <Documents>\Adobe\Adobe Substance 3D Painter\python\plugins\spx_brush_probe\
# Lépések: LEPESEK.md. Riportok: %APPDATA%\spx_brush_probe\

import os, sys, importlib

from PySide6 import QtWidgets, QtCore, QtGui
import substance_painter.ui as ui

PROBE_VERSION = "v3.3"

# A „Reload Plugins Folder” csak ezt a modult tölti újra, az almodulokat nem:
# a régi checks a sys.modules-ban maradna. Ezért kidobjuk, és frissen töltjük be.
# (A `from . import checks` itt nem jó: ha a csomagon már ott a régi `checks` attribútum, azt adja vissza.)
for _name in [n for n in sys.modules if n.startswith(__name__ + ".")]:
    del sys.modules[_name]
checks = importlib.import_module(__name__ + ".checks")

_widgets = []


def start_plugin():
    w = QtWidgets.QWidget()
    w.setObjectName("spx_brush_probe_panel")
    w.setWindowTitle(f"SPX Brush Probe {PROBE_VERSION}")
    lay = QtWidgets.QVBoxLayout(w)

    combo = QtWidgets.QComboBox()
    combo.setMinimumContentsLength(30)
    combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    status = QtWidgets.QLabel(f"SPX Brush Probe {PROBE_VERSION} (checks {checks.PROBE_VERSION}). "
                              "Kezdd a „0. Presetek betöltése” gombbal (lásd LEPESEK.md).")
    status.setWordWrap(True)
    presets = []

    def current():
        i = combo.currentIndex()
        return presets[i][1] if 0 <= i < len(presets) else None

    def run(label, fn, needs_preset=True):
        def handler():
            r = current()  # nincs reload: a JS-felderítés és a fájlindex a gombok között megmarad
            if needs_preset and r is None:
                QtWidgets.QMessageBox.warning(w, "SPX Brush Probe", "Előbb válassz presetet a listából.")
                return
            status.setText(f"{label} fut…")
            QtWidgets.QApplication.processEvents()
            try:
                path = fn(w, r) if needs_preset else fn()
                status.setText(f"{label} kész. Riport: {path}")
            except Exception as e:
                checks.log("!! KIVÉTEL:", repr(e))
                import traceback
                checks.log(traceback.format_exc())
                path = checks.flush()
                status.setText(f"{label} HIBA: {e}\nRiport: {path}")
                QtWidgets.QMessageBox.warning(w, "SPX Brush Probe", f"{label} hiba:\n{e}\n\nA riportba bekerült.")
        return handler

    def load():
        presets[:] = checks.guard(checks.list_presets) or []
        checks.flush()
        combo.clear()
        combo.addItems([label for label, _ in presets])
        status.setText(f"{len(presets)} preset betöltve. Válassz egy tool presetet (pl. egy alap festő brusht).")

    b0 = QtWidgets.QPushButton("0. Presetek betöltése")
    b0.clicked.connect(load)
    b1 = QtWidgets.QPushButton("1. Felderítés (JS API, doksi, UI-fa) – kb. 1 perc")
    b1.clicked.connect(run("Felderítés", checks.run_discovery, needs_preset=False))
    b2 = QtWidgets.QPushButton("2. A: kijelölés az Assets ablakban")
    b2.clicked.connect(run("A próba", checks.try_show_in_ui))
    b4 = QtWidgets.QPushButton("3. C: kattintás szimulálása")
    b4.clicked.connect(run("C próba", checks.try_qt_click))
    b5 = QtWidgets.QPushButton("4. Ikon próbák")
    b5.clicked.connect(run("Ikon próba", checks.try_icons))
    b6 = QtWidgets.QPushButton("Riport mappa megnyitása")

    def open_dir():
        os.makedirs(checks.REPORT_DIR, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(checks.REPORT_DIR))

    b6.clicked.connect(open_dir)

    class DropZone(QtWidgets.QLabel):
        def __init__(self):
            super().__init__("⬇ Húzz ide egy brusht az Assets ablakból ⬇")
            self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.setMinimumHeight(50)
            self.setStyleSheet("border: 2px dashed #888; padding: 6px;")
            self.setAcceptDrops(True)
            self._entered = False

        def dragEnterEvent(self, e):
            if not self._entered:  # elég egyszer naplózni, ha a drop nem engedélyezett
                self._entered = True
                checks.guard(checks.log_drop, e.mimeData(), "dragEnter")
                checks.flush()
            e.acceptProposedAction()

        def dropEvent(self, e):
            urls = checks.guard(checks.log_drop, e.mimeData(), "drop") or []
            path = checks.flush()
            e.acceptProposedAction()
            hit = None
            for u in urls:
                base = u.split("?")[0]
                for i, (label, _) in enumerate(presets):
                    if base in label:
                        hit = i
                        break
                if hit is not None:
                    break
            if hit is not None:
                combo.setCurrentIndex(hit)
                self.setText(f"Behúzva és kiválasztva: {presets[hit][0].split('  ')[0]}")
            else:
                self.setText("Behúzás naplózva (a listában nem találtam).")
            status.setText(f"Behúzás naplózva: {path}")

    drop = DropZone()
    lay.addWidget(b0)
    lay.addWidget(combo)
    lay.addWidget(drop)
    for b in (b1, b2, b4, b5, b6):
        lay.addWidget(b)
    lay.addWidget(status)
    lay.addStretch(1)

    ui.add_dock_widget(w)
    _widgets.append(w)


def close_plugin():
    for w in _widgets:
        ui.delete_ui_element(w)
    _widgets.clear()
