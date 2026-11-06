# PROTOTYPE – eldobható Painter-plugin („SPX Workflow prototípus”), nem kerül a main ágra.
# Ticket: Prototype: Workflow szerkesztő (#9, map: #1).
# Kérdés: hogyan hoz létre (rögzítéssel) és szerkeszt a felhasználó egy Workflow-t a Panelen?
#
# Telepítés: a teljes `spx_workflow_proto` mappát ide kell másolni:
#   <Documents>\Adobe\Adobe Substance 3D Painter\python\plugins\spx_workflow_proto\
# Lépések: LEPESEK.md. Napló: %APPDATA%\spx_workflow_proto\naplo.txt
# Painter nélkül: python prototypes/spx_workflow_proto/standalone.py [A|B|C]
#
# Python 3.11 (Painter 11.1) kompatibilis.

import importlib
import sys
import traceback

# A „Reload Plugins Folder” csak ezt a modult tölti újra, az almodulokat ezért kidobjuk (#13 tanulság).
for _name in [n for n in sys.modules if n.startswith(__name__ + ".")]:
    del sys.modules[_name]

_widgets = []


def start_plugin():
    import substance_painter.ui as ui
    try:
        host_mod = importlib.import_module(__name__ + ".host")
        panel_mod = importlib.import_module(__name__ + ".panel")
        host = host_mod.Host(host_mod.PainterEnv())
        w = panel_mod.PanelRoot(host)
        ui.add_dock_widget(w)
        _widgets.append(w)
    except Exception:
        print(traceback.format_exc())
        raise


def close_plugin():
    import substance_painter.ui as ui
    for w in _widgets:
        try:
            w.shutdown()
        except Exception:
            print(traceback.format_exc())
        ui.delete_ui_element(w)
    _widgets.clear()
