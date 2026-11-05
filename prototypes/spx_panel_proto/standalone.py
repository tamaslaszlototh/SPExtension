# PROTOTYPE – a Panel kipróbálása Painter nélkül (macOS/Windows), Qt-ban szimulált Painter-ablakkal.
#   pip install PySide6
#   python prototypes/spx_panel_proto/standalone.py [A|B|C]
# Bal oldalon egy szimulált „Assets” ablak: innen húzhatsz brusht a Panelre.
# A Panel egy dokkolható ablak: lebegtetheted (dupla klikk a címsoron), és bármelyik szélre dokkolhatod.

import os
import sys
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402
from spx_panel_proto import panel, host  # noqa: E402

Qt = QtCore.Qt


class FakeAssets(QtWidgets.QListWidget):
    BRUSHES = ["Basic Soft", "Concrete Spots", "Dust Puff", "Rust Edge", "Leak Drip", "Fabric Weave",
               "Spray Paint", "Wood Grain"]

    def __init__(self):
        super().__init__()
        self.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.setIconSize(QtCore.QSize(48, 48))
        self.setGridSize(QtCore.QSize(72, 76))
        self.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.setDragEnabled(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragOnly)
        for n in self.BRUSHES:
            it = QtWidgets.QListWidgetItem(panel.glyph("brush", n), n, self)
            it.setToolTip(n)

    def mimeData(self, items):
        md = QtCore.QMimeData()
        # ugyanaz a forma, mint a Painterben (#13): text/uri-list, URL-kódolt resource:// URL
        md.setData("text/uri-list", "\r\n".join(quote(f"resource://starter_assets/{i.text()}?version=1", safe="")
                                               for i in items).encode())
        return md


def dark(app):
    app.setStyle("Fusion")
    p = QtGui.QPalette()
    for role, c in [("Window", "#2b2b2b"), ("WindowText", "#d6d6d6"), ("Base", "#232323"),
                    ("AlternateBase", "#2f2f2f"), ("Text", "#d6d6d6"), ("Button", "#353535"),
                    ("ButtonText", "#d6d6d6"), ("Highlight", "#3d6fb0"), ("ToolTipBase", "#1e1e1e"),
                    ("ToolTipText", "#e6e6e6")]:
        p.setColor(getattr(QtGui.QPalette.ColorRole, role), QtGui.QColor(c))
    app.setPalette(p)


def main():
    app = QtWidgets.QApplication(sys.argv)
    dark(app)
    win = QtWidgets.QMainWindow()
    win.setWindowTitle("Szimulált Painter – SPX Panel prototípus")
    vp = QtWidgets.QLabel("3D viewport\n(szimulált)")
    vp.setAlignment(Qt.AlignmentFlag.AlignCenter)
    vp.setStyleSheet("background: #1b1b1b; color: #555; font-size: 22px;")
    win.setCentralWidget(vp)
    assets = QtWidgets.QDockWidget("Assets (szimulált)")
    assets.setObjectName("assets")
    assets.setWidget(FakeAssets())
    win.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, assets)
    start = sys.argv[1] if len(sys.argv) > 1 else "A"
    root = panel.PanelRoot(host.StandaloneHost(), start)
    dock = QtWidgets.QDockWidget("SPX Panel")
    dock.setObjectName("spx_panel_dock")
    dock.setWidget(root)
    win.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
    win.resize(1100, 650)
    win.resizeDocks([assets, dock], [220, 200], Qt.Orientation.Horizontal)
    win.show()
    if os.environ.get("SPX_SHOT"):           # képernyőkép a fejlesztőnek: SPX_SHOT=out.png
        def shot():
            win.grab().save(os.environ["SPX_SHOT"])
            app.quit()
        QtCore.QTimer.singleShot(600, shot)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
