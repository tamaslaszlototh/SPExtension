"""SPX Assets Probe v1.0 - eldobható mérőszkript a Research #20-hoz (Assets ablak megnyitása pluginból).

Telepítés: ezt az EGY fájlt másold ide:
    Documents\\Adobe\\Adobe Substance 3D Painter\\python\\plugins\\spx_assets_probe.py
majd indítsd újra a Paintert, és a Python menüben kapcsold be: spx_assets_probe.
Riport: %APPDATA%\\spx_assets_probe\\report.txt  (ezt kell visszaküldeni)

A lépésenkénti teendők: research/open-assets-window.md, "Mérési protokoll" szakasz.
"""
import ctypes
import datetime
import os
import time
import urllib.parse

from PySide6 import QtCore, QtGui, QtWidgets
import substance_painter.resource as sp_res
import substance_painter.ui as sp_ui

try:
    import shiboken6
except ImportError:  # pragma: no cover
    from PySide6 import shiboken6

VERSION = "1.0"
REPORT = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "spx_assets_probe", "report.txt")
ASSETS_OBJECT_NAME = "NewShelf"          # #13/#15 mérése: 11.1.0 és 12.2.0
LIST_VIEW_CLASS = "Alg::ResourceListView"
TIMEOUT_MS = 5000
POLL_MS = 15

_panel = None


# --------------------------------------------------------------------------- napló

def log(msg):
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    line = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3] + "  " + msg
    print(line)
    with open(REPORT, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def ptr(o):
    try:
        return shiboken6.getCppPointer(o)[0]
    except Exception:
        return id(o)


# --------------------------------------------------------------------------- keresés (csak allWidgets, findChildren soha)

def live_widgets():
    for w in QtWidgets.QApplication.allWidgets():
        try:
            if shiboken6.isValid(w):
                w.objectName()
                yield w
        except RuntimeError:
            continue


def assets_dock():
    for w in live_widgets():
        if isinstance(w, QtWidgets.QDockWidget) and w.objectName() == ASSETS_OBJECT_NAME:
            return w
    return None


def inside(w, ancestor):
    target = ptr(ancestor)
    p = w
    while p is not None:
        if ptr(p) == target:
            return True
        p = p.parentWidget()
    return False


def list_view(dock):
    best = None
    for w in live_widgets():
        if w.metaObject().className() == LIST_VIEW_CLASS and inside(w, dock):
            if w.isVisible():
                return w
            best = best or w
    return best


def find_index(view, name):
    m = view.model()
    if m is None or m.rowCount() == 0:
        return None
    hits = m.match(m.index(0, 0), QtCore.Qt.DisplayRole, name, 1,
                   QtCore.Qt.MatchExactly | QtCore.Qt.MatchRecursive)
    return hits[0] if hits else None


def window_menu_actions():
    """(útvonal, QAction) párok a főmenü második szintjéig (pl. Window / Views / Assets)."""
    out = []
    mw = sp_ui.get_main_window()
    for top in mw.menuBar().actions():
        m = top.menu()
        if m is None:
            continue
        for a in m.actions():
            sub = a.menu()
            if sub is None:
                continue
            for b in sub.actions():
                out.append((f"{top.text()}/{a.text()}/{b.text()}".replace("&", ""), b))
    return out


def views_assets_action(dock):
    tva = dock.toggleViewAction()
    title = dock.windowTitle().strip()
    for path, a in window_menu_actions():
        if ptr(a) == ptr(tva):
            return path + " [= dock.toggleViewAction()]", a
    for path, a in window_menu_actions():
        if a.text().replace("&", "").strip() == title:
            return path + " [saját QAction]", a
    return None, None


def dock_state(d):
    if d is None:
        return "Assets dock: NINCS"
    mw = sp_ui.get_main_window()
    try:
        tabs = [t.windowTitle().strip() for t in mw.tabifiedDockWidgets(d)]
    except Exception as e:
        tabs = f"hiba: {e}"
    g = d.frameGeometry()
    win = d.window()
    return (f"hidden={d.isHidden()} visible={d.isVisible()} region_empty={d.visibleRegion().isEmpty()} "
            f"floating={d.isFloating()} area={mw.dockWidgetArea(d)} tabs_with={tabs} "
            f"toggle_checked={d.toggleViewAction().isChecked()} geo=({g.x()},{g.y()} {g.width()}x{g.height()}) "
            f"window={win.metaObject().className()}:{win.objectName()!r} parent="
            f"{d.parentWidget().metaObject().className() if d.parentWidget() else None}")


def diagnostics():
    log(f"=== DIAGNOSZTIKA (probe v{VERSION}) Qt={QtCore.qVersion()}")
    d = assets_dock()
    log("  Assets: " + dock_state(d))
    if d is None:
        log("  dockok: " + str([(w.objectName(), w.windowTitle()) for w in live_widgets()
                               if isinstance(w, QtWidgets.QDockWidget)]))
        return
    tva = d.toggleViewAction()
    log(f"  toggleViewAction: text={tva.text()!r} checked={tva.isChecked()} enabled={tva.isEnabled()}")
    acts = window_menu_actions()
    log(f"  főmenü 2. szintű actionök: {len(acts)}")
    for path, a in acts:
        if path.lower().startswith("window"):
            same = " [= Assets toggleViewAction]" if ptr(a) == ptr(tva) else ""
            log(f"    {path} checkable={a.isCheckable()} checked={a.isChecked()}{same}")
    path, _ = views_assets_action(d)
    log(f"  Window→Views→Assets action: {path}")
    for w in live_widgets():
        if isinstance(w, QtWidgets.QToolBar):
            hits = [a.text() for a in w.actions() if ptr(a) == ptr(tva) or "assets" in a.text().lower()]
            if hits:
                log(f"  toolbar {w.objectName()!r} ({w.windowTitle()!r}) Assets-actionök: {hits}")
    try:
        layout = sp_ui.get_layout(sp_ui.UIMode.Edition)
        log(f"  ui.get_layout(Edition): {len(layout)} bájt")
    except Exception as e:
        log(f"  ui.get_layout hiba: {e}")


# --------------------------------------------------------------------------- megnyitási módszerek

def m1_show_raise(d):
    d.show()
    d.raise_()
    if d.isFloating():
        d.activateWindow()


def m2_toggle_action(d):
    a = d.toggleViewAction()
    if not a.isChecked():          # bepipált actiont trigger() BEZÁRNÁ
        a.trigger()
    d.raise_()


def m3_menu_action(d):
    path, a = views_assets_action(d)
    if a is None:
        log("  Window→Views→Assets action nem található (nyisd le egyszer a Window menüt, és próbáld újra)")
        return
    log(f"  menü action: {path} checked={a.isChecked()}")
    if not (a.isCheckable() and a.isChecked()):
        a.trigger()
    d.raise_()


def m4_nothing(d):
    pass  # csak a show_in_ui() fut (minden módszer után is lefut)


METHODS = (("M1  show() + raise_()", m1_show_raise),
           ("M2  dock.toggleViewAction()", m2_toggle_action),
           ("M3  Window → Views → Assets", m3_menu_action),
           ("M4  csak show_in_ui()", m4_nothing))


# --------------------------------------------------------------------------- kattintás

def qt_click(view, idx):
    vp = view.viewport()
    c = view.visualRect(idx).center()
    lp, gp = QtCore.QPointF(c), QtCore.QPointF(vp.mapToGlobal(c))
    for t in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease):
        btns = QtCore.Qt.NoButton if t == QtCore.QEvent.MouseButtonRelease else QtCore.Qt.LeftButton
        QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(t, lp, gp, QtCore.Qt.LeftButton, btns,
                                                               QtCore.Qt.NoModifier))


def win_click(view, idx):
    from ctypes import wintypes
    vp = view.viewport()
    gp = vp.mapToGlobal(view.visualRect(idx).center())
    scr = QtGui.QGuiApplication.screenAt(gp) or QtGui.QGuiApplication.primaryScreen()
    g, dpr = scr.geometry(), scr.devicePixelRatio()
    x, y = int(round(g.x() + (gp.x() - g.x()) * dpr)), int(round(g.y() + (gp.y() - g.y()) * dpr))
    u = ctypes.windll.user32
    old = wintypes.POINT()
    u.GetCursorPos(ctypes.byref(old))
    u.SetCursorPos(x, y)
    u.mouse_event(0x0002, 0, 0, 0, 0)
    u.mouse_event(0x0004, 0, 0, 0, 0)
    QtCore.QTimer.singleShot(150, lambda: u.SetCursorPos(old.x, old.y))
    log(f"  Windows-kattintás: logikai {gp.x()},{gp.y()} -> fizikai {x},{y} (dpr={dpr})")


# --------------------------------------------------------------------------- mérés

class Run:
    def __init__(self, label, fn, resource, click):
        self.label, self.fn, self.r, self.click = label, fn, resource, click
        self.marks, self.last_rect, self.scrolled = {}, None, False

    def start(self):
        d = assets_dock()
        log(f"=== {self.label} | preset: {self.r.gui_name()} | kattint: {self.click}")
        log("  előtte: " + dock_state(d))
        self.t0 = time.perf_counter()
        if d is not None:
            try:
                self.fn(d)
            except Exception as e:
                log(f"  módszer hiba: {e!r}")
        self.r.show_in_ui()
        log(f"  módszer + show_in_ui() visszatért: {self.ms():.0f} ms")
        QtCore.QTimer.singleShot(0, self.poll)

    def ms(self):
        return (time.perf_counter() - self.t0) * 1000

    def poll(self):
        el = self.ms()
        try:
            d = assets_dock()
            if d is not None and not d.isHidden() and not d.visibleRegion().isEmpty():
                self.marks.setdefault("dock_látható", el)
            v = list_view(d) if d is not None else None
            if v is not None and v.isVisible() and not v.visibleRegion().isEmpty():
                self.marks.setdefault("nézet_látható", el)
            idx = find_index(v, self.r.gui_name()) if v is not None else None
            if idx is not None:
                self.marks.setdefault("elem_a_modellben", el)
                rect = v.visualRect(idx)
                inview = rect.isValid() and v.viewport().rect().contains(rect.center())
                if not inview and not self.scrolled:
                    v.scrollTo(idx)
                    self.scrolled = True
                    self.marks["scrollTo_kellett"] = el
                if inview and "nézet_látható" in self.marks:
                    if rect == self.last_rect:          # két egymást követő mérésben ugyanott: stabil
                        self.marks["kattintható"] = el
                        return self.finish(d, v, idx)
                    self.last_rect = rect
        except RuntimeError as e:
            log(f"  poll hiba: {e}")
        if el > TIMEOUT_MS:
            return self.finish(assets_dock(), None, None)
        QtCore.QTimer.singleShot(POLL_MS, self.poll)

    def finish(self, d, v, idx):
        log("  időbélyegek (ms): " + ", ".join(f"{k}={t:.0f}" for k, t in self.marks.items()))
        if idx is None:
            log(f"  NEM lett kattintható {TIMEOUT_MS} ms alatt")
        log("  utána: " + dock_state(d))
        if idx is not None and self.click:
            qt_click(v, idx)
            log("  Qt-kattintás elküldve (nézd meg: aktív lett-e a brush)")
        if _panel is not None:
            _panel.last = (v, idx)
            _panel.status.setText(f"Kész: {self.label}. Írd be a megjegyzést, ha valami furcsa volt.")


# --------------------------------------------------------------------------- panel

class Panel(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("spx_assets_probe")
        self.setWindowTitle(f"SPX Assets Probe v{VERSION}")
        self.setAcceptDrops(True)
        self.url, self.last = None, (None, None)
        lay = QtWidgets.QVBoxLayout(self)
        self.drop = QtWidgets.QLabel("1. Húzz ide egy brush presetet az Assets ablakból")
        self.drop.setWordWrap(True)
        lay.addWidget(self.drop)
        self.state = QtWidgets.QLineEdit()
        self.state.setPlaceholderText("Állapot kódja (pl. S3) – a protokoll szerint")
        lay.addWidget(self.state)
        self.click = QtWidgets.QCheckBox("Utána kattintson is (Qt esemény)")
        self.click.setChecked(True)
        lay.addWidget(self.click)
        for label, fn in METHODS:
            b = QtWidgets.QPushButton(label)
            b.clicked.connect(lambda _=False, label=label, fn=fn: self.run(label, fn))
            lay.addWidget(b)
        b = QtWidgets.QPushButton("Kattintás Windows-egérrel (ha a Qt-kattintás nem aktivált)")
        b.clicked.connect(self.win)
        lay.addWidget(b)
        self.note = QtWidgets.QLineEdit()
        self.note.setPlaceholderText("Megjegyzés (pl. 'elrendezés rendben', 'rossz helyen nyílt ki') + Enter")
        self.note.returnPressed.connect(self.save_note)
        lay.addWidget(self.note)
        b = QtWidgets.QPushButton("Diagnosztika")
        b.clicked.connect(diagnostics)
        lay.addWidget(b)
        b = QtWidgets.QPushButton("Riport mappa megnyitása")
        b.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(os.path.dirname(REPORT))))
        lay.addWidget(b)
        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        lay.addStretch(1)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        md = e.mimeData()
        url = md.urls()[0].toString() if md.hasUrls() else md.text().strip()
        r = self.resource(url)
        if r is None:
            log(f"  behúzás: nem található resource: {url}")
            return
        self.url = url
        self.drop.setText(f"Preset: {r.gui_name()}")
        log(f"=== preset kiválasztva: {r.gui_name()} ({url})")
        e.acceptProposedAction()

    def resource(self, url=None):
        url = url or self.url
        if not url:
            return None
        for u in (url, urllib.parse.unquote(url)):
            try:
                found = sp_res.Resource.retrieve(sp_res.ResourceID.from_url(u))
                if found:
                    return found[0]
            except Exception:
                continue
        return None

    def run(self, label, fn):
        r = self.resource()
        if r is None:
            self.status.setText("Előbb húzz be egy presetet!")
            return
        self.status.setText("Mér…")
        Run(f"[{self.state.text().strip() or '?'}] {label}", fn, r, self.click.isChecked()).start()

    def win(self):
        v, idx = self.last
        if v is None or idx is None:
            self.status.setText("Nincs utolsó elem; előbb futtass egy módszert.")
            return
        win_click(v, idx)

    def save_note(self):
        log(f"  MEGJEGYZÉS [{self.state.text().strip()}]: {self.note.text()}")
        self.note.clear()


def start_plugin():
    global _panel
    _panel = Panel()
    sp_ui.add_dock_widget(_panel)
    log(f"##### SPX Assets Probe v{VERSION} indul")
    diagnostics()


def close_plugin():
    global _panel
    if _panel is not None:
        sp_ui.delete_ui_element(_panel)
        _panel = None


if __name__ == "__main__":
    start_plugin()
