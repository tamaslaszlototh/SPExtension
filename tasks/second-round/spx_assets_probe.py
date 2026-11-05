"""SPX Assets Probe v1.1 - eldobható mérőszkript (#21, ismétlés 11.1.0-n).

Mér: (B) .abr brush ikonja és aktiválása, (D) az Assets ablak megnyitása és a brush aktiválása,
valamint indításkor egyszer: mi teszi érvénytelenné ("already deleted") a widget-hivatkozásokat 11.1-en.

Telepítés: ezt az EGY fájlt másold ide:
    Documents\\Adobe\\Adobe Substance 3D Painter\\python\\plugins\\spx_assets_probe.py
majd indítsd újra a Paintert, és a Python menüben kapcsold be: spx_assets_probe.
Riport: %APPDATA%\\spx_assets_probe\\report.txt  (+ a mentett ikonképek ugyanott)

Lépések: tasks/second-round/LEPESEK-11.1.md

v1.1 változások a v1.0-hoz képest:
- a Run objektumok megmaradnak (v1.0-ban a Python eltakarította őket, ezért a poll sosem futott),
- minden widget-hivatkozás a plugin élete végéig megmarad (_KEEP), és használat előtt újrakeressük,
- a mérés során nem hívjuk a sp_ui.get_main_window()-t (a főablakot allWidgets()-ből keressük),
- indításkor wrapper-érvénytelenítési teszt (melyik lépés után lesz "already deleted"),
- behúzáskor ikon-kiolvasás (tooltip-PNG, DecorationRole) és megjelenítés,
- minden mérés után Igen/Nem kérdések; ha a Qt-kattintás nem aktivált, Windows-egér magától,
- a megjegyzés Enter nélkül is mentődik (mező elhagyásakor).
"""
import base64
import ctypes
import datetime
import gc
import os
import re
import time
import urllib.parse

from PySide6 import QtCore, QtGui, QtWidgets
import substance_painter.resource as sp_res
import substance_painter.ui as sp_ui

try:
    import shiboken6
except ImportError:  # pragma: no cover
    from PySide6 import shiboken6

VERSION = "1.1"
REPORT_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "spx_assets_probe")
REPORT = os.path.join(REPORT_DIR, "report.txt")
ASSETS_OBJECT_NAME = "NewShelf"          # #13/#15 mérése: 11.1.0 és 12.2.0
LIST_VIEW_CLASS = "Alg::ResourceListView"
TIMEOUT_MS = 5000
POLL_MS = 15

Qt = QtCore.Qt
DISPLAY = Qt.ItemDataRole.DisplayRole
DECORATION = Qt.ItemDataRole.DecorationRole
TOOLTIP = Qt.ItemDataRole.ToolTipRole

_panel = None
_KEEP = {}        # minden wrapper, amit valaha megfogtunk: soha ne dobjuk el (11.1 érvénytelenítés)
_RUNS = []        # a futó/lefutott mérések (különben a Python eltakarítja őket)


# --------------------------------------------------------------------------- napló

def log(msg):
    os.makedirs(REPORT_DIR, exist_ok=True)
    line = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3] + "  " + msg
    print(line)
    with open(REPORT, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def keep(o):
    """Megtartja a wrappert (listánál az elemeit), pointer szerint egyedileg."""
    if o is None:
        return o
    for x in (o if isinstance(o, (list, tuple)) else (o,)):
        try:
            _KEEP[ptr(x)] = x
        except Exception:
            pass
    return o


def valid(o):
    if o is None:
        return False
    try:
        if not shiboken6.isValid(o):
            return False
        o.objectName()
        return True
    except Exception:
        return False


def ptr(o):
    try:
        return shiboken6.getCppPointer(o)[0]
    except Exception:
        return id(o)


# --------------------------------------------------------------------------- keresés (csak allWidgets)

def live_widgets(hold=True):
    ws = QtWidgets.QApplication.allWidgets()
    if hold:
        keep(ws)
    out = []
    for w in ws:
        try:
            if shiboken6.isValid(w):
                w.objectName()
                out.append(w)
        except RuntimeError:
            continue
    return out


def main_window(hold=True):
    for w in live_widgets(hold):
        if isinstance(w, QtWidgets.QMainWindow) and w.objectName() == "S4MainWindow":
            return keep(w) if hold else w
    for w in live_widgets(hold):
        if isinstance(w, QtWidgets.QMainWindow) and w.parentWidget() is None:
            return keep(w) if hold else w
    return None


def assets_dock(hold=True):
    for w in live_widgets(hold):
        if isinstance(w, QtWidgets.QDockWidget) and w.objectName() == ASSETS_OBJECT_NAME:
            return keep(w) if hold else w
    return None


def inside(w, ancestor):
    target = ptr(ancestor)
    p = w
    while p is not None:
        if ptr(p) == target:
            return True
        p = p.parentWidget()
    return False


def list_view(dock, hold=True):
    if dock is None:
        return None
    best = None
    for w in live_widgets(hold):
        if w.metaObject().className() == LIST_VIEW_CLASS and inside(w, dock):
            if w.isVisible():
                return keep(w) if hold else w
            best = best or w
    return keep(best) if hold else best


def find_index(view, name):
    m = view.model()
    if m is None or m.rowCount() == 0:
        return None
    keep(m)
    hits = m.match(m.index(0, 0), DISPLAY, name, 1, Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive)
    return hits[0] if hits else None


def window_menu_actions():
    """(útvonal, QAction) párok a főmenü második szintjéig (pl. Window / Views / Assets)."""
    mw = main_window()
    out = []
    if mw is None or mw.menuBar() is None:
        return out
    for a in mw.menuBar().actions():
        m = a.menu()
        if m is None:
            continue
        top = a.text().replace("&", "")
        for b in m.actions():
            keep(b)
            out.append((f"{top} / {b.text().replace('&', '')}", b))
            sm = b.menu()
            if sm is not None:
                for c in sm.actions():
                    keep(c)
                    out.append((f"{top} / {b.text().replace('&', '')} / {c.text().replace('&', '')}", c))
    return out


def views_assets_action(dock):
    tva = keep(dock.toggleViewAction())
    for path, a in window_menu_actions():
        if ptr(a) == ptr(tva):
            return path + " [= dock.toggleViewAction()]", a
    for path, a in window_menu_actions():
        if path.lower().endswith("/ assets"):
            return path, a
    return None, None


def dock_state(d):
    if not valid(d):
        return "Assets dock: NINCS / érvénytelen"
    mw = main_window()
    try:
        tabs = [t.windowTitle().strip() for t in keep(mw.tabifiedDockWidgets(d))] if mw is not None else "nincs főablak"
    except Exception as e:
        tabs = f"hiba: {e}"
    try:
        g = d.frameGeometry()
        win = keep(d.window())
        par = keep(d.parentWidget())
        return (f"hidden={d.isHidden()} visible={d.isVisible()} region_empty={d.visibleRegion().isEmpty()} "
                f"floating={d.isFloating()} area={mw.dockWidgetArea(d) if mw is not None else '?'} tabs_with={tabs} "
                f"toggle_checked={keep(d.toggleViewAction()).isChecked()} "
                f"geo=({g.x()},{g.y()} {g.width()}x{g.height()}) "
                f"window={win.metaObject().className()}:{win.objectName()!r} "
                f"parent={par.metaObject().className() if par is not None else None}")
    except Exception as e:
        return f"dock_state hiba: {e!r}"


def diagnostics():
    log(f"=== DIAGNOSZTIKA (probe v{VERSION}) Qt={QtCore.qVersion()} PySide6={_pyside_version()}")
    log("  Assets: " + dock_state(assets_dock()))


def _pyside_version():
    try:
        import PySide6
        return PySide6.__version__
    except Exception:
        return "?"


# --------------------------------------------------------------------------- wrapper-érvénytelenítési teszt

def wrapper_tests():
    """Indításkor, MÉG A _KEEP feltöltése előtt: melyik lépés után lesz "already deleted" egy élő widget?
    Minden lépésnél friss nézet-hivatkozással indulunk, és csak azt ellenőrizzük."""
    log("=== WRAPPER-TESZT (melyik lépés után lesz érvénytelen egy élő widget-hivatkozás)")

    def fresh_view():
        d = assets_dock(hold=False)
        v = list_view(d, hold=False)
        return d, v

    def report(name, v, d=None):
        gc.collect()
        log(f"  {name}: nézet érvényes={valid(v)}" + (f", dock érvényes={valid(d)}" if d is not None else ""))

    try:
        d, v = fresh_view()
        if v is None:
            log("  nem található Assets lista-nézet (legyen nyitva az Assets ablak); a teszt kimarad")
            return
        report("T0 kiinduló állapot", v, d)

        mw = sp_ui.get_main_window()
        log(f"  T1 sp_ui.get_main_window() -> {type(mw).__name__} érvényes={valid(mw)}")
        del mw
        report("T1 get_main_window() eredményének eldobása után", v, d)

        d, v = fresh_view()
        del d
        report("T2 a dock-hivatkozás eldobása után", v)

        d, v = fresh_view()
        ws = QtWidgets.QApplication.allWidgets()
        del ws
        report("T3 egy allWidgets() lista eldobása után", v, d)

        d, v = fresh_view()
        w = d.window()
        p = d.parentWidget()
        del w, p
        report("T4 d.window() / d.parentWidget() eldobása után", v, d)

        d, v = fresh_view()
        mw2 = main_window(hold=False)
        tabs = mw2.tabifiedDockWidgets(d) if mw2 is not None else []
        del tabs, mw2
        report("T5 tabifiedDockWidgets() + allWidgets-főablak eldobása után", v, d)

        d, v = fresh_view()
        m = v.model()
        del m
        report("T6 a modell-hivatkozás eldobása után", v, d)

        d, v = fresh_view()
        keep([d, v])
        QtCore.QTimer.singleShot(1000, lambda: log(f"  T7 1 s eseménykezelés után (megtartva): "
                                                   f"nézet érvényes={valid(v)}, dock érvényes={valid(d)}"))
    except Exception as e:
        log(f"  wrapper-teszt hiba: {e!r}")


# --------------------------------------------------------------------------- módszerek (Assets megnyitása)

def m1_show_raise(d):
    d.show()
    d.raise_()
    if d.isFloating():
        d.activateWindow()


def m2_toggle_action(d):
    a = keep(d.toggleViewAction())
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


# --------------------------------------------------------------------------- kattintás (mindig friss kereséssel)

def locate(name):
    """Friss keresés: (nézet, index) vagy (None, None)."""
    d = assets_dock()
    v = list_view(d) if valid(d) else None
    if not valid(v):
        return None, None
    idx = find_index(v, name)
    return (v, idx) if idx is not None else (v, None)


def qt_click(name):
    v, idx = locate(name)
    if idx is None:
        log("  Qt-kattintás: az elem nem található")
        return False
    vp = keep(v.viewport())
    c = v.visualRect(idx).center()
    lp, gp = QtCore.QPointF(c), QtCore.QPointF(vp.mapToGlobal(c))
    for t in (QtCore.QEvent.Type.MouseButtonPress, QtCore.QEvent.Type.MouseButtonRelease):
        btns = Qt.MouseButton.NoButton if t == QtCore.QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
        QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(t, lp, gp, Qt.MouseButton.LeftButton, btns,
                                                               Qt.KeyboardModifier.NoModifier))
    log(f"  Qt-kattintás elküldve (nézet érvényes utána: {valid(v)})")
    return True


def win_click(name):
    from ctypes import wintypes
    v, idx = locate(name)
    if idx is None:
        log("  Windows-kattintás: az elem nem található")
        return False
    vp = keep(v.viewport())
    gp = vp.mapToGlobal(v.visualRect(idx).center())
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
    return True


# --------------------------------------------------------------------------- kérdések

def ask(question, options=("Igen", "Nem", "Nem tudom")):
    box = QtWidgets.QMessageBox(_panel)
    box.setWindowTitle("SPX Assets Probe")
    box.setText(question)
    buttons = [box.addButton(o, QtWidgets.QMessageBox.ButtonRole.AcceptRole) for o in options]
    box.exec()
    clicked = box.clickedButton()
    answer = next((o for o, b in zip(options, buttons) if b is clicked), "?")
    log(f"  >> KÉRDÉS: {question}")
    log(f"  >> VÁLASZ: {answer}")
    return answer


def ask_text(question):
    text, ok = QtWidgets.QInputDialog.getText(_panel, "SPX Assets Probe", question)
    if ok and text.strip():
        log(f"  >> {question} {text.strip()}")


# --------------------------------------------------------------------------- ikon

def save_icon(name, tag):
    """Az Assets csempe ikonja: tooltip-PNG és DecorationRole. Visszaad: a legjobb kép útvonala."""
    v, idx = locate(name)
    if idx is None:
        log(f"  ikon [{tag}]: „{name}” nincs az Assets modellben")
        return None
    best = None
    safe = re.sub(r"[^\w.-]+", "_", name)
    tip = idx.data(TOOLTIP)
    if isinstance(tip, str) and "data:image/" in tip:
        m = re.search(r"data:image/(\w+);base64,([A-Za-z0-9+/=]+)", tip)
        if m:
            data = base64.b64decode(m.group(2))
            img = QtGui.QImage.fromData(data)
            path = os.path.join(REPORT_DIR, f"icon_{tag}_{safe}_tooltip.{m.group(1)}")
            with open(path, "wb") as f:
                f.write(data)
            log(f"  ikon [{tag}] tooltip-kép: {m.group(1)} {len(data)} bájt {img.width()}x{img.height()} -> {path}")
            best = path
    else:
        log(f"  ikon [{tag}] tooltip: nincs beágyazott kép ({type(tip).__name__}: {str(tip)[:120]!r})")
    deco = idx.data(DECORATION)
    pm = None
    if isinstance(deco, QtGui.QIcon):
        pm = deco.pixmap(QtCore.QSize(256, 256))
    elif isinstance(deco, QtGui.QPixmap):
        pm = deco
    elif isinstance(deco, QtGui.QImage):
        pm = QtGui.QPixmap.fromImage(deco)
    if pm is not None and not pm.isNull():
        path = os.path.join(REPORT_DIR, f"icon_{tag}_{safe}_decoration.png")
        pm.save(path)
        log(f"  ikon [{tag}] DecorationRole: {pm.width()}x{pm.height()} -> {path}")
        best = best or path
    else:
        log(f"  ikon [{tag}] DecorationRole: nincs ({type(deco).__name__})")
    return best


# --------------------------------------------------------------------------- mérés

class Run:
    """Egy módszer: módszer + show_in_ui(), aszinkron várakozás, kattintás, kérdések."""

    def __init__(self, label, fn, resource, click):
        self.label, self.fn, self.r, self.click = label, fn, resource, click
        self.name = resource.gui_name()
        self.marks, self.last_rect, self.scrolled, self.done = {}, None, False, False
        _RUNS.append(self)

    def start(self):
        d = assets_dock()
        log(f"=== {self.label} | preset: {self.name} | kattint: {self.click}")
        log("  előtte: " + dock_state(d))
        self.t0 = time.perf_counter()
        if valid(d):
            try:
                self.fn(d)
            except Exception as e:
                log(f"  módszer hiba: {e!r}")
        else:
            log("  az Assets dock nem található / érvénytelen")
        try:
            self.r.show_in_ui()
        except Exception as e:
            log(f"  show_in_ui hiba: {e!r}")
        log(f"  módszer + show_in_ui() visszatért: {self.ms():.0f} ms")
        QtCore.QTimer.singleShot(0, self.poll)

    def ms(self):
        return (time.perf_counter() - self.t0) * 1000

    def poll(self):
        if self.done:
            return
        el = self.ms()
        try:
            d = assets_dock()
            if valid(d) and not d.isHidden() and not d.visibleRegion().isEmpty():
                self.marks.setdefault("dock_látható", el)
            v = list_view(d) if valid(d) else None
            if valid(v) and v.isVisible() and not v.visibleRegion().isEmpty():
                self.marks.setdefault("nézet_látható", el)
            idx = find_index(v, self.name) if valid(v) else None
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
                        return self.finish(True)
                    self.last_rect = rect
        except Exception as e:
            log(f"  poll hiba: {e!r}")
        if el > TIMEOUT_MS:
            return self.finish(False)
        QtCore.QTimer.singleShot(POLL_MS, self.poll)

    def finish(self, clickable):
        self.done = True
        log("  időbélyegek (ms): " + ", ".join(f"{k}={t:.0f}" for k, t in self.marks.items()))
        if not clickable:
            log(f"  NEM lett kattintható {TIMEOUT_MS} ms alatt")
        log("  utána: " + dock_state(assets_dock()))
        if _panel is not None:
            _panel.status.setText(f"Kérdések jönnek: {self.label}")
        QtCore.QTimer.singleShot(300, lambda: self.after(clickable))

    def after(self, clickable):
        ask("Látszik most az Assets ablak (kinyílt / előtérbe jött)?")
        if clickable and self.click:
            qt_click(self.name)
            QtCore.QTimer.singleShot(800, self.ask_active)
        else:
            self.ask_layout()

    def ask_active(self):
        a = ask(f"Qt-kattintás után: a(z) „{self.name}” lett az aktív brush?\n"
                "(Nézd meg a Properties ablakban, vagy fess egy vonást.)")
        if a != "Igen":
            log("  Qt-kattintás nem aktivált -> Windows-egér")
            win_click(self.name)
            QtCore.QTimer.singleShot(800, self.ask_active_win)
        else:
            self.ask_layout()

    def ask_active_win(self):
        ask(f"Windows-egeres kattintás után: a(z) „{self.name}” lett az aktív brush?")
        self.ask_layout()

    def ask_layout(self):
        ask_text("Megjegyzés ehhez a méréshez (hol van az Assets ablak, furcsaság) – üresen is mehet:")
        if _panel is not None:
            _panel.status.setText(f"Kész: {self.label}. Jöhet a következő.")


# --------------------------------------------------------------------------- panel

class Panel(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("spx_assets_probe")
        self.setWindowTitle(f"SPX Assets Probe v{VERSION}")
        self.setAcceptDrops(True)
        self.url = None
        lay = QtWidgets.QVBoxLayout(self)
        self.drop = QtWidgets.QLabel("Húzz ide egy brusht az Assets ablakból")
        self.drop.setWordWrap(True)
        self.drop.setMinimumHeight(40)
        self.drop.setStyleSheet("border: 2px dashed gray; padding: 6px;")
        lay.addWidget(self.drop)
        self.icon = QtWidgets.QLabel("")
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon.setMinimumHeight(128)
        lay.addWidget(self.icon)
        self.state = QtWidgets.QLineEdit()
        self.state.setPlaceholderText("Állapot kódja (B, S1, S2, S3, S4) – a lépések szerint")
        lay.addWidget(self.state)
        self.click = QtWidgets.QCheckBox("Utána kattintson is a brushra")
        self.click.setChecked(True)
        lay.addWidget(self.click)
        for label, fn in METHODS:
            b = QtWidgets.QPushButton(label)
            b.clicked.connect(lambda _=False, label=label, fn=fn: self.run(label, fn))
            lay.addWidget(b)
        self.note = QtWidgets.QLineEdit()
        self.note.setPlaceholderText("Megjegyzés (Enter vagy kattints máshova = mentés)")
        self.note.editingFinished.connect(self.save_note)
        lay.addWidget(self.note)
        b = QtWidgets.QPushButton("Diagnosztika")
        b.clicked.connect(diagnostics)
        lay.addWidget(b)
        b = QtWidgets.QPushButton("Riport mappa megnyitása")
        b.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(REPORT_DIR)))
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
        e.acceptProposedAction()
        r = self.resource(url)
        if r is None:
            log(f"  behúzás: nem található resource: {url}")
            self.status.setText("Ezt nem ismertem fel brushként, próbáld újra.")
            return
        self.url = url
        name = r.gui_name()
        self.drop.setText(f"Brush: {name}")
        log(f"=== brush behúzva: {name} ({url})")
        try:
            log(f"  típus={r.type()} usages={list(r.usages())}")
        except Exception as ex:
            log(f"  típus/usages hiba: {ex!r}")
        QtCore.QTimer.singleShot(0, lambda: self.show_icon(name))

    def show_icon(self, name):
        path = save_icon(name, "drop")
        if path:
            pm = QtGui.QPixmap(path)
            self.icon.setPixmap(pm.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))
        else:
            self.icon.setText("(nincs ikon)")
        ask(f"Megjelent a panelen a(z) „{name}” brush képe? Az a brush, és éles?",
            ("Igen, éles", "Igen, de homályos/kicsi", "Nem / más kép", "Nincs kép"))

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
        self.save_note()
        r = self.resource()
        if r is None:
            self.status.setText("Előbb húzz be egy brusht!")
            return
        self.status.setText("Mér…")
        Run(f"[{self.state.text().strip() or '?'}] {label}", fn, r, self.click.isChecked()).start()

    def save_note(self):
        text = self.note.text().strip()
        if text:
            log(f"  MEGJEGYZÉS [{self.state.text().strip()}]: {text}")
            self.note.clear()


def start_plugin():
    global _panel
    log(f"##### SPX Assets Probe v{VERSION} indul")
    QtCore.QTimer.singleShot(2000, wrapper_tests)       # a _KEEP feltöltése ELŐTT
    QtCore.QTimer.singleShot(4000, _create_panel)


def _create_panel():
    global _panel
    _panel = Panel()
    sp_ui.add_dock_widget(_panel)
    diagnostics()


def close_plugin():
    global _panel
    if _panel is not None:
        sp_ui.delete_ui_element(_panel)
        _panel = None
    _RUNS.clear()
    _KEEP.clear()
