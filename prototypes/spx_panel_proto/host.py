# PROTOTYPE – a környezet (Painter vagy önálló futtatás), amiben a Panel fut.
import os
import time
from urllib.parse import unquote

from PySide6 import QtCore, QtGui, QtWidgets

KIND_MSG = {"brush": "Brush aktiválva", "workflow": "Workflow lefutott", "menu": "Menüparancs"}


class Host:
    def __init__(self):
        self.status = lambda msg: None
        self._actions = None
        self._sizew = None
        self._last_size = None
        self._timer = QtCore.QTimer(singleShot=True, interval=700, timeout=self._flush_size)

    # --- Painter-ből (vagy szimulálva) ---
    def actions_raw(self):
        return []

    def menu_actions(self):
        if self._actions is None:
            seen, out = set(), []
            for a in self.actions_raw():
                name = a.text().replace("&&", "\0").replace("&", "").replace("\0", "&").split("\t")[0].strip()
                if not name or a.isSeparator() or a.icon().isNull() or name in seen:
                    continue
                seen.add(name)
                out.append((name, a.icon()))
            self._actions = sorted(out, key=lambda x: x[0].lower())
        return self._actions

    def pick(self, prefix):
        acts = self.menu_actions()
        for n, ic in acts:
            if n.lower() == prefix.lower():
                return n, ic
        for n, ic in acts:
            if n.lower().startswith(prefix.lower()):
                return n, ic
        return prefix, QtGui.QIcon()

    def brush_info(self, url):
        ref = unquote(url)
        name = ref.split("?")[0].rstrip("/").split("/")[-1]
        while unquote(name) != name:          # a Painter URL-je lehet kétszer kódolva
            name = unquote(name)
        return name, None, ref

    # --- visszajelzés ---
    def click(self, item):
        msg = f"{KIND_MSG[item['kind']]}: {item['name']}  (prototípus, nem történik semmi)"
        self.status(msg)
        self.log("kattintás: " + msg)

    def log(self, msg):
        print(time.strftime("%H:%M:%S"), msg)

    def log_size(self, w):
        self._sizew = w
        self._timer.start()

    def _flush_size(self):
        w = self._sizew
        if w is None:
            return
        p, dock = w.parentWidget(), None
        while p is not None:
            if isinstance(p, QtWidgets.QDockWidget):
                dock = p
                break
            p = p.parentWidget()
        where = "nincs dokk" if dock is None else ("lebeg" if dock.isFloating() else "dokkolva")
        s = (w.width(), w.height(), where)
        if s != self._last_size:
            self._last_size = s
            self.log(f"Panel mérete: {s[0]}×{s[1]} px, {where}")


class StandaloneHost(Host):
    """Painter nélkül: a menüparancsokat Qt beépített ikonjaival szimulálja."""
    FAKE = [("Save", "SP_DialogSaveButton"), ("Save as...", "SP_DriveFDIcon"),
            ("Open...", "SP_DialogOpenButton"), ("Export textures...", "SP_ArrowUp"),
            ("Bake Mesh Maps", "SP_ComputerIcon"), ("Undo", "SP_ArrowBack"), ("Redo", "SP_ArrowForward"),
            ("Fit to screen", "SP_TitleBarMaxButton"), ("Toggle 2D/3D", "SP_DesktopIcon"),
            ("Settings...", "SP_FileDialogDetailedView"), ("Reload shaders", "SP_BrowserReload")]

    def actions_raw(self):
        st = QtWidgets.QApplication.style()
        out = []
        for name, sp in self.FAKE:
            a = QtGui.QAction(st.standardIcon(getattr(QtWidgets.QStyle.StandardPixmap, sp)), name)
            out.append(a)
        self._keep = out
        return out


class PainterHost(Host):
    LOG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "spx_panel_proto")

    def __init__(self):
        super().__init__()
        os.makedirs(self.LOG_DIR, exist_ok=True)
        self.log_path = os.path.join(self.LOG_DIR, "naplo.txt")
        try:
            import substance_painter.application as app
            ver = app.version()
        except Exception as e:
            ver = f"? ({e})"
        self.log(f"=== indulás, Painter {ver} ===")

    def actions_raw(self):
        import substance_painter.ui as ui
        acts = ui.get_main_window().findChildren(QtGui.QAction)
        self.log(f"menüparancsok ikonnal: {sum(1 for a in acts if not a.icon().isNull())} / {len(acts)}")
        return acts

    def brush_info(self, url):
        name, _, ref = super().brush_info(url)
        try:
            import substance_painter.resource as res
            r = (res.Resource.retrieve(res.ResourceID.from_url(ref)) or [None])[0]
            if r is not None:
                self.log(f"behúzva: {r.gui_name()} típus={r.type()} url={ref}")
                return r.gui_name(), None, ref
            self.log(f"behúzva, de retrieve üres: {ref}")
        except Exception as e:
            self.log(f"behúzva, retrieve hiba: {e} url={ref}")
        return name, None, ref

    def log(self, msg):
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(time.strftime("%H:%M:%S ") + msg + "\n")
        except Exception:
            pass
