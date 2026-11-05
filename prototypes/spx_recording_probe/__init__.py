# PROTOTYPE – eldobható mérő-plugin („SPX Recording Probe”), nem kerül a main ágra.
# Ticket: #18 „Prototype: Recording mérése a layer stack eseményekkel mindkét gépen” (map: #1).
# Kérdés: működik-e a Recording „snapshot + diff, eseményre ébresztve” módszerrel 11.1.0-n és 12.2.0-n?
#
# Telepítés: a teljes `spx_recording_probe` mappát ide kell másolni:
#   <Documents>\Adobe\Adobe Substance 3D Painter\python\plugins\spx_recording_probe\
# Lépések: LEPESEK.md. Riport: %APPDATA%\spx_recording_probe\rec_<verzió>.txt
#
# Python 3.11 (Painter 11.1) kompatibilis: nincs 3.12-es f-string szintaxis.

import datetime
import json
import os
import sys
import time
import traceback
import urllib.parse
from functools import partial

from PySide6 import QtCore, QtGui, QtWidgets
import substance_painter as sp
import substance_painter.application  # noqa: F401  (explicit almodul-importok)
import substance_painter.event  # noqa: F401
import substance_painter.layerstack  # noqa: F401
import substance_painter.project  # noqa: F401
import substance_painter.resource  # noqa: F401
import substance_painter.textureset  # noqa: F401
import substance_painter.ui as sp_ui

try:
    import shiboken6
except ImportError:  # pragma: no cover
    from PySide6 import shiboken6

PROBE_VERSION = "v1.0"
LS = sp.layerstack
DEBOUNCE_MS = 150
POLL_MS = 1000
SETTLE_MS = 800

# --------------------------------------------------------------------------- lépések
# (kód, rövid név, utasítás a barátnak, jelzők)
# jelzők: "drop" = előbb a resource-t a probe mezőjébe kell húzni; "note" = jegyzetet kérünk
STEPS = [
    ("S00", "Előkészítés",
     "Nyiss meg egy ELDOBHATÓ projektet (File → New, egyszerű mesh). Nyisd ki a History ablakot: "
     "Window → Views → History. Legyen látható a Layers ablak is. Ha kész, nyomd meg a „Kész” gombot.", ""),
    ("S01", "Nyugalom",
     "Ne csinálj SEMMIT kb. 5 másodpercig (ne mozgasd az egeret a Painter fölött). Utána „Kész”.", ""),
    ("S02", "Kijelölés",
     "Kattints a Layers ablakban egy MÁSIK layerre (csak kijelölés). Ha csak egy layer van, előbb adj hozzá "
     "egy Fill layert, és akkor arra kattints vissza a régire.", ""),
    ("S03", "Fill layer",
     "A Layers ablak tetején lévő gombbal adj hozzá egy Fill layert.", ""),
    ("S04", "Paint layer",
     "Adj hozzá egy Paint layert (ugyanott, a gombsorban).", ""),
    ("S05", "Folder",
     "Adj hozzá egy Foldert (mappa ikon).", ""),
    ("S06", "Fekete maszk",
     "Kattints a Paint layerre, majd jobb klikk → Add black mask.", ""),
    ("S07", "Generator",
     "A maszkon jobb klikk → Add generator, majd a megjelenő generatornál válassz ki egyet (pl. Dirt). "
     "📝 Írd be a jegyzetbe, melyiket választottad.", "note"),
    ("S08", "Filter",
     "A maszkon jobb klikk → Add filter, majd válassz egyet (pl. Blur). 📝 Írd be, melyiket.", "note"),
    ("S09", "Levels",
     "A maszkon jobb klikk → Add levels.", ""),
    ("S10", "Anchor point",
     "A maszkon jobb klikk → Add anchor point.", ""),
    ("S11", "Opacity húzása",
     "Kattints a Paint layerre. Fogd meg az opacity csúszkáját (a layer sorában vagy a Properties-ben), "
     "és LASSAN húzd kb. 3 másodpercig ide-oda, ELENGEDÉS NÉLKÜL. Utána engedd el, és nyomd a „Kész”-t.", ""),
    ("S12", "Blend mode",
     "A Paint layer blend mode-ját állítsd Multiply-re (a layer sorában a „Norm” feliratra kattintva).", ""),
    ("S13", "Átnevezés",
     "Dupla kattintással nevezd át a Paint layert erre: Proba (Enter).", ""),
    ("S14", "Smart material",
     "ELŐSZÖR: húzz egy smart materialt az Assets ablakból a probe panel szaggatott mezőjébe "
     "(a felirat kiírja a nevét). UTÁNA húzd be ugyanazt a smart materialt a Layers ablakba.", "drop"),
    ("S15", "Smart mask",
     "ELŐSZÖR: húzz egy smart maskot az Assets ablakból a probe panel szaggatott mezőjébe. "
     "UTÁNA húzd rá ugyanazt a Layers ablakban egy layerre (pl. a Fill layerre).", "drop"),
    ("S16", "Festés",
     "Kattints a Paint layerre (Proba), válaszd a Paint eszközt, és fess PONTOSAN 3 vonást a modellre.", ""),
    ("S17", "Új Fill az undo-hoz",
     "Adj hozzá még egy Fill layert. (A következő lépésben ezt vonjuk vissza.)", ""),
    ("S18", "Ctrl+Z",
     "Nyomd meg EGYSZER a Ctrl+Z-t (billentyűvel). Az előbbi Fill layernek el kell tűnnie.", ""),
    ("S19", "Ctrl+Y",
     "Nyomd meg EGYSZER a Ctrl+Y-t (redo). Ha nem jön vissza a layer, próbáld a Ctrl+Shift+Z-t. "
     "📝 Írd be, melyik működött.", "note"),
    ("S20", "Undo/Redo menüből",
     "Az Edit menüben kattints az Undo-ra, majd az Edit menüben a Redo-ra. "
     "📝 Ha nincs ilyen menüpont, írd be.", "note"),
    ("S21", "Undo a History-ból",
     "A History ablakban kattints 2 sorral feljebb (2 lépés vissza), majd az utolsó sorra (vissza előre).", ""),
    ("S22", "Toolváltás",
     "A bal oldali eszköztáron kattints sorban: Eraser, Projection, Paint. Utána ugyanezt billentyűvel, "
     "ha tudod a gyorsbillentyűt. 📝 Írd be, milyen billentyűket nyomtál.", "note"),
    ("S23", "Brush váltás",
     "Az Assets ablakban kattints egy másik brushra (a Paint eszköz legyen aktív). 📝 Írd be a nevét.", "note"),
    ("S24", "Texture set váltás",
     "Ha a projektben több texture set van: a Texture Set List-ben kattints egy másikra, majd vissza. "
     "Ha csak egy van, nyomd a „Kihagyom” gombot.", ""),
    ("S25", "File → Save (menüből)",
     "File → Save (menüből kattintva). Ha mentési ablak jön, mentsd el valahova (pl. Asztal), "
     "ez eldobható projekt.", ""),
    ("S26", "Ctrl+S",
     "Fess egy vonást (hogy legyen mit menteni), aztán nyomd meg a Ctrl+S-t.", ""),
    ("S27", "Almenü parancs",
     "Window → Views → Log: kapcsold BE, majd ugyanott kapcsold KI.", ""),
    ("S28", "Törlés",
     "Jelölj ki egy layert (pl. a Foldert), és töröld (Delete billentyű vagy a kuka ikon).", ""),
    ("S29", "Átrendezés",
     "A Layers ablakban húzással cserélj fel két layert.", ""),
    ("S30", "Projekt bezárása",
     "File → Close (mentés nélkül, ha kérdezi). Utána „Kész”. Ezzel vége a mérésnek.", ""),
]

_probe = None


# --------------------------------------------------------------------------- segédek

def _safe(f, default=None):
    try:
        return f()
    except Exception as e:  # noqa
        return default if default is not None else "ERR:%s" % type(e).__name__


def ptr(o):
    try:
        return shiboken6.getCppPointer(o)[0]
    except Exception:
        return id(o)


def alive(o):
    try:
        return shiboken6.isValid(o)
    except Exception:
        return False


def live_widgets():
    for w in QtWidgets.QApplication.allWidgets():
        try:
            if shiboken6.isValid(w):
                w.objectName()
                yield w
        except RuntimeError:
            continue


def inside(w, ancestor):
    target = ptr(ancestor)
    p = w
    while p is not None:
        if ptr(p) == target:
            return True
        p = p.parentWidget()
    return False


def painter_version():
    v = _safe(sp.application.version)
    if isinstance(v, str) and not v.startswith("ERR"):
        return v
    vi = _safe(sp.application.version_info)
    return ".".join(str(x) for x in vi) if isinstance(vi, tuple) else "unknown"


# --------------------------------------------------------------------------- snapshot / diff

def _node_rec(n, parent_uid, idx, in_mask, channels):
    t = n.get_type()
    r = {"uid": n.uid(), "type": t.name, "name": _safe(n.get_name), "parent": parent_uid,
         "idx": idx, "mask_stack": in_mask, "visible": _safe(n.is_visible)}
    if _safe(n.has_blending, False) is True:
        if in_mask:
            r["blend"] = _safe(lambda: n.get_blending_mode().name)
            r["opacity"] = _safe(lambda: round(n.get_opacity(), 4))
        else:
            r["blend"] = {c.name: _safe(lambda c=c: n.get_blending_mode(c).name) for c in channels}
            r["opacity"] = {c.name: _safe(lambda c=c: round(n.get_opacity(c), 4)) for c in channels}
    if t in (LS.NodeType.GeneratorEffect, LS.NodeType.FilterEffect):
        src = _safe(n.get_source)
        if src is None:
            r["source"] = None
        elif isinstance(src, str):
            r["source"] = src
        else:
            r["source"] = _safe(lambda: src.resource_id.url())
    return r


def snapshot():
    if not sp.project.is_open() or not sp.project.is_in_edition_state():
        return None
    stack = sp.textureset.get_active_stack()
    channels = list(stack.all_channels().keys())
    nodes = {}

    def walk_layers(layers, parent_uid):
        for i, n in enumerate(layers):
            r = _node_rec(n, parent_uid, i, False, channels)
            r["has_mask"] = _safe(n.has_mask)
            if r["has_mask"] is True:
                r["mask_bg"] = _safe(lambda: n.get_mask_background().name)
            nodes[r["uid"]] = r
            for j, e in enumerate(_safe(n.content_effects, []) or []):
                nodes[e.uid()] = _node_rec(e, n.uid(), j, False, channels)
            for j, e in enumerate(_safe(n.mask_effects, []) or []):
                nodes[e.uid()] = _node_rec(e, n.uid(), j, True, channels)
            if n.get_type() == LS.NodeType.GroupLayer:
                walk_layers(n.sub_layers(), n.uid())

    walk_layers(LS.get_root_layer_nodes(stack), None)
    sel = [n.uid() for n in (_safe(lambda: LS.get_selected_nodes(stack), []) or [])]
    key = "%s/%s" % (_safe(lambda: stack.material().name()), _safe(stack.name))
    return {"stack": key, "nodes": nodes, "selection": sel}


# --------------------------------------------------------------------------- lépés-statisztika

class StepStats:
    def __init__(self, code, name):
        self.code, self.name = code, name
        self.t0 = time.perf_counter()
        self.lsm_times = []          # LayerStacksModelDataChanged időpontok (s, lépés elejétől)
        self.other_events = {}       # egyéb esemény -> darab
        self.diffs_event = 0
        self.diffs_poll = 0
        self.actions = []
        self.menus = []
        self.keys = []
        self.dock_titles = []
        self.added = []
        self.removed = []
        self.changed = []
        self.uid_notes = []
        self.dropped = None
        self.note = ""
        self.skipped = False

    def rel(self):
        return time.perf_counter() - self.t0


# --------------------------------------------------------------------------- a mérő

class Probe(QtCore.QObject):
    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.t0 = time.perf_counter()
        self.version = painter_version()
        d = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "spx_recording_probe")
        os.makedirs(d, exist_ok=True)
        self.report_dir = d
        self.report = os.path.join(d, "rec_%s.txt" % self.version.replace(" ", "_"))
        self.last = None
        self.seen = {}               # uid -> utolsó ismert rekord (minden valaha látott node)
        self.removed = {}            # uid -> rekord (eltűnt node-ok)
        self.ev_conns = []
        self.qt_conns = {}           # ptr -> (obj, signal-név, slot)
        self.stats = None
        self.all_stats = []
        self.thread_checked = False
        self.history_logged = False
        self.last_key_ts = None

        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(DEBOUNCE_MS)
        self.timer.timeout.connect(lambda: self.process("event"))
        self.poll = QtCore.QTimer(self)
        self.poll.setInterval(POLL_MS)
        self.poll.timeout.connect(self._poll)

        self.log("#" * 70)
        self.log("SPX Recording Probe %s indul | %s" % (PROBE_VERSION, datetime.datetime.now().isoformat()))
        self.log("Painter %s | Python %s | Qt %s | PySide %s" % (
            self.version, sys.version.split()[0], QtCore.qVersion(),
            _safe(lambda: __import__("PySide6").__version__)))
        for name in ("LayerStacksModelDataChanged", "TextureStateEvent", "ProjectEditionEntered",
                     "ProjectEditionLeft", "ProjectAboutToClose", "BusyStatusChanged"):
            self.log("hasattr(event, %s) = %s" % (name, hasattr(sp.event, name)))
        self._connect_events()
        self.rescan()
        QtWidgets.QApplication.instance().installEventFilter(self)
        self.last = self._timed_snapshot()[0]
        self.poll.start()

    # ---- napló
    def log(self, msg):
        line = "[%8.3f] %s" % (time.perf_counter() - self.t0, msg)
        print(line)
        try:
            with open(self.report, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    # ---- bekötések
    def _connect_events(self):
        ev = sp.event
        for cls in ("LayerStacksModelDataChanged", "TextureStateEvent", "ProjectEditionEntered",
                    "ProjectEditionLeft", "ProjectAboutToClose", "ProjectOpened", "BusyStatusChanged"):
            if hasattr(ev, cls):
                cb = partial(self._on_event, cls)
                ev.DISPATCHER.connect_strong(getattr(ev, cls), cb)
                self.ev_conns.append((getattr(ev, cls), cb))

    def _hook(self, obj, signal_name, slot):
        p = ptr(obj)
        if p in self.qt_conns:
            return False
        try:
            getattr(obj, signal_name).connect(slot)
            self.qt_conns[p] = (obj, signal_name, slot)
            return True
        except Exception:
            return False

    def rescan(self):
        """QAction-ök, QMenu-k és dockok (újra)gyűjtése; a lusta menük miatt minden lépés elején."""
        mw = sp_ui.get_main_window()
        actions = list(mw.findChildren(QtGui.QAction))
        menus, docks = [], []
        for w in live_widgets():
            try:
                actions.extend(w.actions())
            except Exception:
                pass
            if isinstance(w, QtWidgets.QMenu):
                menus.append(w)
            elif isinstance(w, QtWidgets.QDockWidget):
                docks.append(w)
        new_a = sum(1 for a in actions if self._hook(a, "triggered", partial(self._on_action, a)))
        new_m = sum(1 for m in menus if self._hook(m, "triggered", partial(self._on_menu, m)))
        new_d = sum(1 for d in docks if self._hook(d, "windowTitleChanged", partial(self._on_dock_title, d)))
        uniq = {ptr(a): a for a in actions}
        self.log("rescan: QAction=%d (új %d), QMenu=%d (új %d), dock=%d (új %d)" % (
            len(uniq), new_a, len(menus), new_m, len(docks), new_d))
        return uniq, docks

    def describe_environment(self):
        uniq, docks = self.rescan()
        self.log("=== KÖRNYEZET")
        for a in uniq.values():
            if not alive(a):
                continue
            sc = a.shortcut().toString()
            txt = a.text().replace("&", "")
            low = (txt + a.objectName()).lower()
            if sc in ("Ctrl+Z", "Ctrl+Y", "Ctrl+Shift+Z", "Ctrl+S") or "undo" in low or "redo" in low:
                self.log("  UNDO/REDO/SAVE-szerű action: text=%r objectName=%r sc=%s" % (txt, a.objectName(), sc))
        tool_like = [a for a in uniq.values() if alive(a) and a.shortcut().toString()
                     and len(a.shortcut().toString()) <= 2]
        self.log("  egybetűs/rövid shortcutos actionök (tool-jelölt): %s" % (
            [(a.text().replace("&", ""), a.shortcut().toString()) for a in tool_like][:60]))
        for d in docks:
            self.log("  dock: objectName=%r title=%r visible=%s" % (d.objectName(), d.windowTitle(), d.isVisible()))
        shortcuts = [w for w in mw_objects(QtGui.QShortcut)]
        self.log("  QShortcut objektumok: %d %s" % (len(shortcuts), [
            _safe(lambda s=s: s.key().toString()) for s in shortcuts][:40]))
        self.probe_history(full=True)

    # ---- History dock
    def history_dock(self):
        for w in live_widgets():
            if isinstance(w, QtWidgets.QDockWidget):
                if "history" in (w.windowTitle() + " " + w.objectName()).lower():
                    return w
        return None

    def probe_history(self, full=False):
        d = self.history_dock()
        if d is None:
            if full:
                self.log("  HISTORY dock: nem található (nyitva van? Window → Views → History)")
            return
        inner = [w for w in live_widgets() if inside(w, d) and ptr(w) != ptr(d)]
        views = [w for w in inner if isinstance(w, QtWidgets.QAbstractItemView)]
        if full:
            classes = sorted({w.metaObject().className() for w in inner})
            self.log("  HISTORY dock objectName=%r title=%r visible=%s, belső widget-osztályok: %s" % (
                d.objectName(), d.windowTitle(), d.isVisible(), classes))
            self.log("  HISTORY item view-k: %d" % len(views))
        for v in views:
            m = _safe(v.model)
            if m is None or isinstance(m, str):
                continue
            n = m.rowCount()
            first = max(0, n - 6)
            rows = [_safe(lambda r=r: m.data(m.index(r, 0))) for r in range(first, n)]
            cur = _safe(lambda: v.currentIndex().row())
            self.log("  HISTORY %s sorok=%d aktuális=%s utolsó sorok=%s" % (
                v.metaObject().className(), n, cur, rows))

    # ---- események
    def _on_event(self, cls, e):
        if not self.thread_checked:
            self.thread_checked = True
            app = QtWidgets.QApplication.instance()
            self.log("callback szál == GUI szál: %s" % (QtCore.QThread.currentThread() == app.thread()))
        st = self.stats
        if cls == "LayerStacksModelDataChanged":
            if st is not None:
                st.lsm_times.append(st.rel())
            self.log("event LayerStacksModelDataChanged")
            self.timer.start()
            return
        if cls == "TextureStateEvent":
            if st is not None:
                st.other_events[cls] = st.other_events.get(cls, 0) + 1
            return  # festés közben nagyon sok lehet; csak számoljuk
        if st is not None:
            st.other_events[cls] = st.other_events.get(cls, 0) + 1
        self.log("event %s %s" % (cls, _safe(lambda: repr(e))))
        if cls in ("ProjectEditionLeft", "ProjectAboutToClose"):
            self.last = None
        self.timer.start()

    def _on_action(self, a, checked=False):
        if not alive(a):
            return
        s = "%r objectName=%r sc=%s checkable=%s checked=%s" % (
            a.text().replace("&", ""), a.objectName(), a.shortcut().toString(), a.isCheckable(), checked)
        self.log("ACTION triggered " + s)
        if self.stats is not None:
            self.stats.actions.append(a.text().replace("&", "") or a.objectName() or "?")

    def _on_menu(self, m, a):
        if not alive(a):
            return
        path = a.text().replace("&", "")
        p = m
        while isinstance(p, QtWidgets.QMenu):
            t = p.title().replace("&", "")
            if t:
                path = t + "/" + path
            p = p.parentWidget()
        self.log("MENU triggered %s (objectName=%r)" % (path, a.objectName()))
        if self.stats is not None:
            self.stats.menus.append(path)

    def _on_dock_title(self, d, title):
        self.log("DOCK TITLE objectName=%r -> %r" % (d.objectName(), title))
        if self.stats is not None:
            self.stats.dock_titles.append("%s→%s" % (d.objectName(), title))

    def eventFilter(self, obj, ev):
        try:
            if ev.type() == QtCore.QEvent.KeyPress and not ev.isAutoRepeat():
                if ev.timestamp() != self.last_key_ts and not (
                        isinstance(obj, QtWidgets.QWidget) and inside(obj, self.panel)):
                    self.last_key_ts = ev.timestamp()
                    k = QtGui.QKeySequence(ev.keyCombination()).toString()
                    if k:
                        self.log("KEY %s (célobjektum: %s)" % (k, obj.metaObject().className()))
                        if self.stats is not None:
                            self.stats.keys.append(k)
        except Exception:
            pass
        return False

    # ---- snapshot feldolgozás
    def _timed_snapshot(self):
        t = time.perf_counter()
        try:
            s = snapshot()
        except Exception as e:
            return "ERR:%r" % e, 0.0
        return s, (time.perf_counter() - t) * 1000

    def _poll(self):
        if self.timer.isActive():
            return  # esemény már jött, a debounce intézi
        self.process("poll")

    def process(self, source):
        cur, ms = self._timed_snapshot()
        if isinstance(cur, str):
            self.log("snapshot hiba: %s" % cur)
            return
        lines = self._diff(self.last, cur)
        if lines:
            n = len(cur["nodes"]) if cur else 0
            self.log("DIFF (%s) snapshot=%.1f ms, node=%d:" % (source, ms, n))
            for line in lines:
                self.log("    " + line)
            if self.stats is not None:
                if source == "event":
                    self.stats.diffs_event += 1
                else:  # poll vagy lezárás: esemény nélkül talált változás
                    self.stats.diffs_poll += 1
        self.last = cur

    def _diff(self, a, b):
        if a is None and b is None:
            return []
        if a is None or b is None:
            return ["(nincs snapshot: előtte=%s utána=%s)" % (a is not None, b is not None)]
        if a["stack"] != b["stack"]:
            return ["AKTÍV STACK VÁLTOZOTT %s -> %s" % (a["stack"], b["stack"])]
        st = self.stats
        out = []
        an, bn = a["nodes"], b["nodes"]
        for u in sorted(bn.keys() - an.keys()):
            r = bn[u]
            out.append("ADDED %s" % json.dumps(r, ensure_ascii=False))
            if u in self.removed:
                note = "UID VISSZATÉRT: uid=%s (%s %r) ugyanazzal az uid-dal jött vissza" % (u, r["type"], r["name"])
                out.append("  !! " + note)
                if st is not None:
                    st.uid_notes.append(note)
                del self.removed[u]
            else:
                twins = [ou for ou, orr in self.removed.items()
                         if orr["type"] == r["type"] and orr["name"] == r["name"]]
                if twins:
                    note = "ÚJ UID egy eltűnt helyén: régi=%s új=%s (%s %r)" % (twins[-1], u, r["type"], r["name"])
                    out.append("  !! " + note)
                    if st is not None:
                        st.uid_notes.append(note)
            if st is not None:
                st.added.append("%s %r" % (r["type"], r["name"]))
        for u in sorted(an.keys() - bn.keys()):
            r = an[u]
            self.removed[u] = r
            out.append("REMOVED uid=%s %s %r" % (u, r["type"], r["name"]))
            if st is not None:
                st.removed.append("%s %r" % (r["type"], r["name"]))
        for u in sorted(an.keys() & bn.keys()):
            for k in sorted(set(an[u]) | set(bn[u])):
                if an[u].get(k) != bn[u].get(k):
                    out.append("CHANGED uid=%s %r.%s: %s -> %s" % (u, bn[u]["name"], k, an[u].get(k), bn[u].get(k)))
                    if st is not None:
                        st.changed.append("%r.%s" % (bn[u]["name"], k))
        if a["selection"] != b["selection"]:
            out.append("SELECTION %s -> %s" % (a["selection"], b["selection"]))
        self.seen.update(bn)
        return out

    # ---- lépések
    def begin_step(self, code, name):
        self.rescan()
        self.stats = StepStats(code, name)
        self.log("")
        self.log("=" * 60)
        self.log("=== LÉPÉS %s %s KEZDŐDIK" % (code, name))

    def end_step(self, note, skipped=False):
        st = self.stats
        if st is None:
            return
        self.timer.stop()
        self.process("lezárás")
        st.note, st.skipped = note, skipped
        dur = st.rel()
        self.log("=== LÉPÉS %s %s VÉGE%s (%.1f s)" % (st.code, st.name, " – KIHAGYVA" if skipped else "", dur))
        if note:
            self.log("  MEGJEGYZÉS: %s" % note)
        if st.dropped:
            self.log("  BEHÚZOTT resource: %s" % st.dropped)
        self.log("  LayerStacksModelDataChanged: %d db, időpontok (s): %s" % (
            len(st.lsm_times), [round(t, 2) for t in st.lsm_times][:40]))
        self.log("  egyéb események: %s" % st.other_events)
        self.log("  diff eseményből: %d | diff esemény NÉLKÜL (poll/lezárás → kimaradt esemény?): %d" % (
            st.diffs_event, st.diffs_poll))
        self.log("  ADDED: %s" % st.added)
        self.log("  REMOVED: %s" % st.removed)
        self.log("  CHANGED: %s" % st.changed[:30])
        if st.uid_notes:
            self.log("  UID: %s" % st.uid_notes)
        self.log("  ACTION: %s | MENU: %s | KEY: %s | DOCK TITLE: %s" % (
            st.actions, st.menus, st.keys, st.dock_titles))
        if st.dropped and st.added:
            dropped_name = st.dropped.split(" | ")[0]
            names = [x.split(" ", 1)[1].strip("'\"") for x in st.added]
            self.log("  NÉV-EGYEZÉS (behúzott resource vs. új node-ok): %s" % (dropped_name in names))
        self.probe_history()
        self.all_stats.append(st)
        self.stats = None

    def summary(self):
        self.log("")
        self.log("#" * 70)
        self.log("ÖSSZESÍTÉS (Painter %s)" % self.version)
        self.log("%-4s %-22s %5s %5s %5s %-30s %s" % ("kód", "név", "LSMDC", "d_ev", "d_pol", "action/menu", "megjegyzés"))
        for st in self.all_stats:
            am = ",".join((st.actions + st.menus)[:3])
            self.log("%-4s %-22s %5s %5d %5d %-30s %s" % (
                st.code, st.name[:22], "-" if st.skipped else len(st.lsm_times),
                st.diffs_event, st.diffs_poll, am[:30], st.note))
        self.log("Riport: %s" % self.report)

    # ---- leállítás
    def shutdown(self):
        self.poll.stop()
        self.timer.stop()
        try:
            QtWidgets.QApplication.instance().removeEventFilter(self)
        except Exception:
            pass
        for cls, cb in self.ev_conns:
            try:
                sp.event.DISPATCHER.disconnect(cls, cb)
            except Exception:
                pass
        for obj, sig, slot in self.qt_conns.values():
            try:
                if alive(obj):
                    getattr(obj, sig).disconnect(slot)
            except Exception:
                pass
        self.qt_conns.clear()
        self.log("leállítva")


def mw_objects(cls):
    try:
        return sp_ui.get_main_window().findChildren(cls)
    except Exception:
        return []


# --------------------------------------------------------------------------- panel

class Panel(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("spx_recording_probe_panel")
        self.setWindowTitle("SPX Recording Probe %s" % PROBE_VERSION)
        self.setAcceptDrops(True)
        self.i = 0
        self.probe = None

        lay = QtWidgets.QVBoxLayout(self)
        self.head = QtWidgets.QLabel()
        f = self.head.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 2)
        self.head.setFont(f)
        lay.addWidget(self.head)
        self.text = QtWidgets.QLabel()
        self.text.setWordWrap(True)
        self.text.setMinimumHeight(90)
        self.text.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        lay.addWidget(self.text)

        self.drop = QtWidgets.QLabel("Ide húzd (csak ha a lépés kéri)")
        self.drop.setAlignment(QtCore.Qt.AlignCenter)
        self.drop.setMinimumHeight(48)
        self.drop.setStyleSheet("border: 2px dashed #888; padding: 6px;")
        self.drop.setWordWrap(True)
        lay.addWidget(self.drop)

        self.note = QtWidgets.QLineEdit()
        self.note.setPlaceholderText("Jegyzet ehhez a lépéshez (ha valami furcsa volt, vagy a lépés kéri)")
        lay.addWidget(self.note)

        row = QtWidgets.QHBoxLayout()
        self.done = QtWidgets.QPushButton("✔ Kész, jöhet a következő")
        self.done.setMinimumHeight(36)
        self.done.clicked.connect(lambda: self.finish(False))
        self.skip = QtWidgets.QPushButton("Kihagyom")
        self.skip.clicked.connect(lambda: self.finish(True))
        row.addWidget(self.done, 3)
        row.addWidget(self.skip, 1)
        lay.addLayout(row)

        b = QtWidgets.QPushButton("Riport mappa megnyitása")
        b.clicked.connect(self.open_dir)
        lay.addWidget(b)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        lay.addStretch(1)

    def start(self):
        self.probe = Probe(self)
        self.probe.describe_environment()
        self.show_step()

    def show_step(self):
        if self.i >= len(STEPS):
            self.head.setText("Kész! Köszönöm 🙏")
            self.text.setText("Nyomd meg a „Riport mappa megnyitása” gombot, és küldd el a rec_….txt fájlt "
                              "(lásd LEPESEK.md, 5. pont).")
            self.done.setEnabled(False)
            self.skip.setEnabled(False)
            return
        code, name, text, flags = STEPS[self.i]
        self.head.setText("%s / %d  –  %s" % (code, len(STEPS) - 1, name))
        self.text.setText(text)
        self.drop.setText("Ide húzd a smart materialt / smart maskot" if "drop" in flags
                          else "Ide húzd (csak ha a lépés kéri)")
        self.note.clear()
        self.done.setEnabled(True)
        self.skip.setEnabled(True)
        self.status.setText("")
        self.probe.begin_step(code, name)

    def finish(self, skipped):
        self.done.setEnabled(False)
        self.skip.setEnabled(False)
        self.status.setText("Feldolgozás…")
        note = self.note.text().strip()
        QtCore.QTimer.singleShot(SETTLE_MS, lambda: self._finish2(note, skipped))

    def _finish2(self, note, skipped):
        try:
            self.probe.end_step(note, skipped)
        except Exception:
            self.probe.log("!! KIVÉTEL a lépés lezárásakor:\n" + traceback.format_exc())
        self.i += 1
        if self.i >= len(STEPS):
            self.probe.summary()
        self.show_step()

    def open_dir(self):
        d = self.probe.report_dir if self.probe else os.path.join(os.environ.get("APPDATA", ""), "spx_recording_probe")
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(d))

    # ---- behúzás (smart material / mask neve)
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        md = e.mimeData()
        url = md.urls()[0].toString() if md.hasUrls() else md.text().strip()
        info = url
        for u in (url, urllib.parse.unquote(url)):
            try:
                found = sp.resource.Resource.retrieve(sp.resource.ResourceID.from_url(u))
                if found:
                    r = found[0]
                    info = "%s | usage=%s | %s" % (r.gui_name(), _safe(lambda: r.usage().name), u)
                    break
            except Exception:
                continue
        self.drop.setText("Behúzva: " + info.split(" | ")[0])
        if self.probe is not None:
            self.probe.log("DROP a probe panelre: %s (formátumok: %s)" % (info, md.formats()))
            if self.probe.stats is not None:
                self.probe.stats.dropped = info
        e.acceptProposedAction()


_panel = None


def start_plugin():
    global _panel
    _panel = Panel()
    sp_ui.add_dock_widget(_panel)
    try:
        _panel.start()
    except Exception:
        print(traceback.format_exc())
        if _panel.probe is not None:
            _panel.probe.log("!! KIVÉTEL induláskor:\n" + traceback.format_exc())


def close_plugin():
    global _panel
    if _panel is not None:
        if _panel.probe is not None:
            _panel.probe.shutdown()
        sp_ui.delete_ui_element(_panel)
        _panel = None


if __name__ == "__main__":
    start_plugin()
