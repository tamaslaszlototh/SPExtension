# PROTOTYPE – eldobható kód, nem kerül a main ágra.
# Egyszerűsített Recording a #18 mérése alapján (Prototype: Recording mérése a layer stack eseményekkel):
#   - elsődleges jel a History (QUndoView): új sor = művelet, az index mozgása = undo/redo;
#   - minden History-változásra layer stack diff (snapshot), ebből lesznek a Step-ek;
#   - a menüparancsokat a QAction (és 12.2-n a QMenu) `triggered` hook adja; ha utána 700 ms-on belül
#     History-sor jön, az layer-parancs volt, azt a diff kezeli.
# A környezetet (Painter vagy a szimulált Painter) az `env` objektum adja, a logika ugyanaz.

import re
import time
from functools import partial

from PySide6 import QtCore, QtGui, QtWidgets

from . import model

try:
    import shiboken6
except ImportError:  # pragma: no cover
    from PySide6 import shiboken6

POLL_MS = 250
MENU_SETTLE_S = 0.7
IGNORE_PREFIX = ("Undo", "Redo", "Add ", "Remove", "Delete", "Duplicate", "Close", "Quit", "Exit")
DEFAULT_NAME = re.compile(r"^(Fill layer|Layer|Folder|Paint layer)( \d+)?$")


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


def first_line(text):
    t = text.replace("&&", "\0").replace("&", "").replace("\0", "&")
    return t.split("\n")[0].split("\t")[0].strip()


def is_own(obj):
    """A prototípus saját QAction-jei és menüi „spx” property-t kapnak; ezeket nem rögzítjük."""
    try:
        while obj is not None:
            if obj.property("spx"):
                return True
            obj = obj.parent()
    except Exception:
        return False
    return False


def menu_path(env, a, menu=None):
    text = first_line(a.text())
    m = menu
    if m is None:
        for mm in env.all_menus():
            try:
                if a in mm.actions():
                    m = mm
                    break
            except Exception:
                continue
    path = text
    while isinstance(m, QtWidgets.QMenu):
        t = first_line(m.title())
        if t:
            path = t + "/" + path
        m = m.parentWidget()
    return path


def describe(env, a, menu=None):
    return {"text": first_line(a.text()), "objectName": a.objectName(), "path": menu_path(env, a, menu),
            "_icon": QtGui.QIcon(a.icon()), "_action": a}


class ActionHooks(QtCore.QObject):
    """QAction.triggered + QMenu.triggered figyelése, duplikátumszűréssel (#18, 5. probléma)."""

    def __init__(self, env, callback, on_trigger=None):
        super().__init__()
        self.env, self.cb, self.on_trigger = env, callback, on_trigger
        self.conns = {}          # ptr -> (obj, signal, slot); a hivatkozásokat megtartjuk (#21 szabály)
        self.last = {}           # kulcs -> időbélyeg
        self.pending = {}
        self.rescan_timer = QtCore.QTimer(self, interval=1500, timeout=self.rescan)
        self.flush_timer = QtCore.QTimer(self, singleShot=True, interval=120, timeout=self._flush)

    def start(self):
        self.rescan()
        self.rescan_timer.start()

    def stop(self):
        self.rescan_timer.stop()
        for obj, sig, slot in self.conns.values():
            try:
                if alive(obj):
                    getattr(obj, sig).disconnect(slot)
            except Exception:
                pass
        self.conns.clear()

    def _hook(self, obj, sig, slot):
        p = ptr(obj)
        if p in self.conns:
            return
        try:
            getattr(obj, sig).connect(slot)
            self.conns[p] = (obj, sig, slot)
        except Exception:
            pass

    def rescan(self):
        for a in self.env.all_actions():
            if alive(a):
                self._hook(a, "triggered", partial(self._on_action, a))
        for m in self.env.all_menus():
            if alive(m):
                self._hook(m, "triggered", partial(self._on_menu, m))

    def _accept(self, a):
        if not alive(a) or is_own(a) or a.isSeparator():
            return False
        if a.actionGroup() is not None:      # eszközváltás (Paint, Eraser…): nem menüparancs
            return False
        t = first_line(a.text())
        return bool(t) and not t.startswith(IGNORE_PREFIX)

    def _on_action(self, a, checked=False):
        if self._accept(a):
            self._queue(a, None)
        elif self.on_trigger is not None and alive(a) and not is_own(a):
            self.on_trigger()        # pl. „Add fill layer”: a saját History-sorát most számoljuk el

    def _on_menu(self, m, a):
        if self._accept(a) and not is_own(m):
            self._queue(a, m)

    def _queue(self, a, menu):
        key = ptr(a)
        info = describe(self.env, a, menu)
        old = self.pending.get(key)
        info["ts"] = old["ts"] if old else time.monotonic()    # a kattintás pillanata, nem a flush-é
        if old is None and self.on_trigger is not None:
            info["own_row"] = self.on_trigger()
        elif old is not None:
            info["own_row"] = old.get("own_row", False)
        if old is None or len(info["path"]) > len(old["path"]):
            self.pending[key] = info
        self.flush_timer.start()

    def _flush(self):
        now = time.monotonic()
        for key, info in self.pending.items():
            if now - self.last.get(key, 0) > 0.5:
                self.last[key] = now
                self.cb(info)
        self.pending.clear()


class Recorder(QtCore.QObject):
    changed = QtCore.Signal()
    finished = QtCore.Signal(str)

    def __init__(self, env):
        super().__init__()
        self.env = env
        self.ops = []            # {"row", "label", "steps", "active", "kind"}
        self.notices = []
        self.strokes = 0
        self.moved_ids = set()
        self.node_step = {}      # uid -> Step (generator/filter/smart mask: később jöhet a forrása)
        self.pending_menu = []   # (időbélyeg, Step)
        self.hist_events = []    # a History modell jeleinek pontos időpontjai
        self._hist_conns = []
        self.last_row_t = 0.0    # az utolsó új History-sor (becsült) időpontja
        self.running = False
        self.t0 = 0.0
        self.hooks = ActionHooks(env, self._on_menu_action, self._on_trigger)
        self.timer = QtCore.QTimer(self, interval=POLL_MS, timeout=self._tick)
        self.poke_timer = QtCore.QTimer(self, singleShot=True, interval=150, timeout=self._tick)
        self._disconnect = None

    # ---------------------------------------------------------------- életciklus
    def start(self):
        self.t0 = time.monotonic()
        self.base = self._snapshot()
        self.h_texts, self.h_idx = self._read_history()
        if self.h_texts is None:
            self._note("A History nem található – undo/redo és a layer-műveletek nem rögzíthetők")
        self._connect_history()
        self.hooks.start()
        self.timer.start()
        self._disconnect = self.env.connect_events(self.poke, lambda: self.stop("a projekt bezárult"))
        self.running = True
        self.env.log("REC indul; History sorok=%s index=%s" % (
            None if self.h_texts is None else len(self.h_texts), self.h_idx))

    def stop(self, reason="Stop"):
        if not self.running:
            return
        self._tick()
        self._commit_menu(force=True)
        self.running = False
        self.timer.stop()
        self.hooks.stop()
        for obj, sig in self._hist_conns:
            try:
                if alive(obj):
                    getattr(obj, sig).disconnect(self._hist_event)
            except Exception:
                pass
        self._hist_conns = []
        if self._disconnect:
            self._disconnect()
        self.env.log("REC vége (%s): %d Step, %d kihagyott, %d festés" % (
            reason, len(self.steps()), len(self.notices), self.strokes))
        self.finished.emit(reason)

    def elapsed(self):
        return time.monotonic() - self.t0

    def poke(self, *args):
        self.poke_timer.start()

    def _connect_history(self):
        """A History modell jelei pontos időbélyeget adnak (a 250 ms-os poll csak a tartalmat olvassa)."""
        v = self.env.history_view()
        if v is None:
            return
        m, sm = v.model(), v.selectionModel()
        for obj, sig in ((m, "rowsInserted"), (m, "rowsRemoved"), (m, "modelReset"), (m, "dataChanged"),
                         (m, "layoutChanged"), (sm, "currentChanged")):
            try:
                getattr(obj, sig).connect(self._hist_event)
                self._hist_conns.append((obj, sig))
            except Exception as e:
                self.env.log("History jel nem köthető: %s (%r)" % (sig, e))

    def _hist_event(self, *args):
        self.hist_events.append(time.monotonic())
        del self.hist_events[:-200]
        self.poke()

    # ---------------------------------------------------------------- eredmény
    def steps(self):
        flat = [s for op in self.ops if op["active"] for s in op["steps"]]
        out, moved = model.normalize(flat)
        self.moved_ids = {s["id"] for s in moved}
        return out

    def _note(self, text):
        self.notices.append(text)
        self.env.log("REC kihagyva/megjegyzés: " + text)

    # ---------------------------------------------------------------- History
    def _read_history(self):
        v = self.env.history_view()
        if v is None:
            return None, None
        try:
            m = v.model()
            n = m.rowCount()
            texts = [str(m.data(m.index(r, 0))) for r in range(n)]
            idx = v.currentIndex().row()
            return texts, (idx if idx >= 0 else n - 1)
        except Exception as e:
            self.env.log("History olvasási hiba: %r" % e)
            return None, None

    def _snapshot(self):
        try:
            return self.env.snapshot()
        except Exception as e:          # pl. ProjectError('The project is locked.') mentés közben (#18, 7.)
            self.env.log("snapshot hiba (újrapróbálom): %r" % e)
            return "ERR"

    def _tick(self):
        if not self.running:
            return
        self._commit_menu()
        texts, idx = self._read_history()
        if texts is None or (texts == self.h_texts and idx == self.h_idx):
            return
        cur = self._snapshot()
        if cur == "ERR":
            return                       # a History-gyorsítótárat nem frissítjük: a következő tick újra próbál
        pt, pi = self.h_texts or [], self.h_idx if self.h_idx is not None else -1
        now = time.monotonic()
        if texts == pt:
            kind = "undo" if idx < pi else "redo"
            self.env.log("REC %s: index %s -> %s" % (kind, pi, idx))
        else:
            shift = 0
            if len(texts) == len(pt):     # History-limit: a legrégebbi sor kiesett, minden sor eggyel feljebb csúszik
                for k in (1, 2, 3):
                    if texts[:len(texts) - k] == pt[k:]:
                        shift = k
                        break
            if shift:
                for op in self.ops:
                    if op["row"] is not None:
                        op["row"] -= shift
                pt = pt[shift:]
            p = 0
            while p < min(len(texts), len(pt)) and texts[p] == pt[p]:
                p += 1
            dropped = [op for op in self.ops if op["row"] is not None and op["row"] >= p]
            if dropped:
                self.env.log("REC új művelet undo után: %d visszavont művelet végleg elvetve" % len(dropped))
            self.ops = [op for op in self.ops if op["row"] is None or op["row"] < p]
            new_rows = list(range(p, len(texts)))
            labels = [texts[r] for r in new_rows]
            self.env.log("REC History új sor(ok): %s" % labels)
            steps = self._classify(self.base, cur, labels)
            for k, r in enumerate(new_rows):
                lab = texts[r]
                if lab.lower() == "add stroke":
                    self.strokes += 1
                ev = [h for h in self.hist_events if now - POLL_MS / 1000.0 - 0.1 <= h <= now]
                op = {"row": r, "label": lab, "steps": steps if k == len(new_rows) - 1 else [],
                      "active": True, "kind": "history", "t": ev[0] if ev else now}
                self.last_row_t = op["t"]
                self.ops.append(op)
        for op in self.ops:
            if op["row"] is not None:
                op["active"] = op["row"] <= idx
        self.h_texts, self.h_idx = texts, idx
        self.base = cur
        self.changed.emit()

    # ---------------------------------------------------------------- diff -> Step-ek
    def _res(self, src):
        if not src:
            return None
        return self.env.resource_from_source(src)

    def _classify(self, a, b, labels):
        lab = ", ".join(labels)
        if not isinstance(a, dict) or not isinstance(b, dict):
            self._note("nincs összehasonlítható állapot (%s)" % lab)
            return []
        if a["stack"] != b["stack"]:
            self._note("texture set váltás (%s → %s): új kiindulási állapot" % (a["stack"], b["stack"]))
            return []
        an, bn = a["nodes"], b["nodes"]
        added = [u for u in bn if u not in an]
        added_set = set(added)
        out, notes = [], []
        updated = False
        smart_mask_parents = set()

        for u in sorted(added, key=lambda x: (bn[x]["parent"] is not None, -bn[x]["idx"])):
            r = bn[u]
            if r["parent"] in added_set:
                continue                       # a smart material csoport belseje
            t = r["type"]
            if t == "GroupLayer" and any(bn[x]["parent"] == u for x in added):
                out.append(model.new_step("smart_material", "rögzített", resource={"name": r["name"], "url": None}))
            elif t in ("FillLayer", "PaintLayer", "GroupLayer"):
                kind = {"FillLayer": "fill", "PaintLayer": "paint", "GroupLayer": "folder"}[t]
                name = "" if DEFAULT_NAME.match(r["name"] or "") else (r["name"] or "")
                out.append(model.new_step(kind, "rögzített", name=name))
            elif t in ("GeneratorEffect", "FilterEffect"):
                tgt = "mask" if r["mask_stack"] else "layer"
                if t == "GeneratorEffect" and r["mask_stack"] and (
                        r["name"] == "Mask Editor" or "drop resource" in lab.lower()):
                    s = model.new_step("smart_mask", "rögzített")
                    s["note"] = "a rögzítés nem látja, melyik smart mask volt"
                    smart_mask_parents.add(r["parent"])
                else:
                    s = model.new_step("generator" if t == "GeneratorEffect" else "filter", "rögzített",
                                       resource=self._res(r.get("source")), target=tgt)
                self.node_step[u] = s
                out.append(s)
            elif t in ("LevelsEffect", "AnchorPointEffect"):
                out.append(model.new_step("levels" if t == "LevelsEffect" else "anchor", "rögzített",
                                          target="mask" if r["mask_stack"] else "layer"))
            else:
                notes.append("nem katalógusbeli elem: %s" % t)

        for u in an.keys() & bn.keys():
            o, n = an[u], bn[u]
            if o.get("has_mask") is False and n.get("has_mask") is True and u not in smart_mask_parents:
                out.append(model.new_step("mask", "rögzített", bg=n.get("mask_bg") or "Black"))
            if o.get("blend") != n.get("blend"):
                if isinstance(n.get("blend"), dict):
                    ch = [c for c in n["blend"] if (o.get("blend") or {}).get(c) != n["blend"][c]]
                    modes = [n["blend"][c] for c in ch]
                    mode = max(set(modes), key=modes.count) if modes else "Normal"
                    out.append(model.new_step("blend", "rögzített", mode=mode))
                else:
                    notes.append("maszk-effekt blend módja (nem katalógusbeli)")
            if o.get("opacity") != n.get("opacity"):
                if isinstance(n.get("opacity"), dict):
                    oo = o.get("opacity") or {}
                    ch = [c for c in n["opacity"] if oo.get(c) != n["opacity"][c]]
                    if ch:
                        val = int(round((n["opacity"][ch[0]] or 0) * 100))
                        out.append(model.new_step("opacity", "rögzített", value=val, channels=ch))
                else:
                    notes.append("maszk-effekt opacity-je (nem katalógusbeli)")
            if o.get("source") != n.get("source"):
                s = self.node_step.get(u)
                if s is not None and s["type"] in ("generator", "filter"):
                    s["params"]["resource"] = self._res(n.get("source"))
                    updated = True
                    self.env.log("REC forrás frissítve: %s" % model.label(s))
                else:
                    notes.append("meglévő effekt forrásának cseréje")
            if o.get("name") != n.get("name") and u not in self.node_step:
                notes.append("átnevezés")
            if (o.get("parent"), o.get("idx")) != (n.get("parent"), n.get("idx")) and not added:
                notes.append("átrendezés")
        if any(u not in bn for u in an):
            notes.append("törlés")

        for nt in sorted(set(notes)):
            self._note("%s (%s)" % (nt, lab))
        if not out and not notes and not updated and not all(x.lower() == "add stroke" for x in labels):
            self._note("nem katalógusbeli művelet: %s" % lab)
        for s in out:
            self.env.log("REC Step: %s" % model.label(s))
        return out

    # ---------------------------------------------------------------- menüparancsok
    def _on_menu_action(self, info):
        if not self.running:
            return
        if info["text"] == "Save" or info["objectName"].lower() in ("save", "actionsave"):
            s = model.new_step("save", "rögzített")
        else:
            s = model.new_step("menu", "rögzített", action=info)
        self.env.log("REC menü-jel: %s (objectName=%r, saját History-sor a kattintáskor: %s)" % (
            info["path"], info["objectName"], info.get("own_row")))
        if info.get("own_row"):
            self.env.log("REC menü-jel eldobva (History-sor jött vele, layer-parancs): %s" % model.label(s))
            return
        self.pending_menu.append((info.get("ts", time.monotonic()), s))

    def _on_trigger(self):
        """A kattintás pillanatában: a már megjelent History-sorokat feldolgozzuk. Igaz, ha épp most
        (100 ms-on belül) jött új sor – akkor a Painter a sort a hookunk előtt tette be, a parancs layer-parancs."""
        if not self.running:
            return False
        before = self.last_row_t
        self._tick()
        return self.last_row_t != before and time.monotonic() - self.last_row_t < 0.1

    def _commit_menu(self, force=False):
        now = time.monotonic()
        keep = []
        for ts, s in self.pending_menu:
            if any(op["kind"] == "history" and ts < op.get("t", 0) <= ts + MENU_SETTLE_S for op in self.ops):
                self.env.log("REC menü-jel eldobva (History-sor jött utána, layer-parancs): %s" % model.label(s))
            elif force or now - ts > MENU_SETTLE_S:
                self.ops.append({"row": None, "label": model.label(s), "steps": [s], "active": True, "kind": "menu"})
                self.env.log("REC Step: %s" % model.label(s))
                self.changed.emit()
            else:
                keep.append((ts, s))
        self.pending_menu = keep


class ActionCapture(QtCore.QObject):
    """„Elkapás a menüből”: a következő Painter-menüparancsot visszaadja (Menu button / Menüparancs Step)."""
    captured = QtCore.Signal(dict)

    def __init__(self, env):
        super().__init__()
        self.hooks = ActionHooks(env, self._got)

    def start(self):
        self.hooks.start()

    def stop(self):
        self.hooks.stop()

    def _got(self, info):
        self.stop()
        self.captured.emit(info)
