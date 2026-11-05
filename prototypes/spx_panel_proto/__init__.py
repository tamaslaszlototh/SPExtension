# PROTOTYPE – eldobható Painter-plugin („SPX Panel prototípus”), nem kerül a main ágra.
# Kérdés: hogyan nézzen ki a Panel, és hogyan működjön a Layout szerkesztése? (lásd panel.py fejléc)
#
# Telepítés: a teljes `spx_panel_proto` mappát ide kell másolni:
#   <Documents>\Adobe\Adobe Substance 3D Painter\python\plugins\spx_panel_proto\
# Lépések: LEPESEK.md. Napló: %APPDATA%\spx_panel_proto\naplo.txt
# Painter nélkül: python standalone.py

import sys
import importlib

# A „Reload Plugins Folder” csak ezt a modult tölti újra, az almodulokat ezért kidobjuk (lásd #13 tanulság).
for _name in [n for n in sys.modules if n.startswith(__name__ + ".")]:
    del sys.modules[_name]

_widgets = []


def start_plugin():
    import substance_painter.ui as ui
    panel = importlib.import_module(__name__ + ".panel")
    host = importlib.import_module(__name__ + ".host")
    w = panel.PanelRoot(host.PainterHost())
    ui.add_dock_widget(w)
    _widgets.append(w)


def close_plugin():
    import substance_painter.ui as ui
    for w in _widgets:
        ui.delete_ui_element(w)
    _widgets.clear()
