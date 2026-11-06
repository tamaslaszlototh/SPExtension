# PROTOTYPE – eldobható kód. A környezet, amiben a Panel fut: Host (közös) + PainterEnv (Painter API).
# A szimulált Painter környezete a standalone.py-ban van (SimEnv), ugyanazzal a felülettel.

import os
import time
from urllib.parse import unquote

from PySide6 import QtGui, QtWidgets

from .recorder import ActionCapture, Recorder, alive, describe, first_line, is_own

LOG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "spx_workflow_proto")


def name_from_url(url):
    ref = unquote(url or "")
    name = ref.split("?")[0].rstrip("/").split("/")[-1]
    while unquote(name) != name:
        name = unquote(name)
    return name or "?"


class Host:
    def __init__(self, env, log_to_file=True):
        self.env = env
        env.log = self.log
        self.log_path = None
        if log_to_file:
            os.makedirs(LOG_DIR, exist_ok=True)
            self.log_path = os.path.join(LOG_DIR, "naplo.txt")
        self.log("=== indulás: %s ===" % env.describe())

    def log(self, msg):
        line = time.strftime("%H:%M:%S ") + msg
        try:
            print(line)
        except Exception:      # pl. cp1250 konzol és „⚠”: a napló hibája ne állítsa meg a rögzítést
            pass
        if self.log_path:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass

    def make_recorder(self):
        return Recorder(self.env)

    def capture(self):
        return ActionCapture(self.env)

    def resource_info(self, url):
        return self.env.resource_info(url)

    def menu_actions(self):
        seen, out = set(), []
        menus = list(self.env.all_menus())
        for m in menus:
            if not alive(m) or is_own(m):
                continue
            for a in m.actions():
                try:
                    if a.isSeparator() or a.menu() is not None or not first_line(a.text()) or is_own(a):
                        continue
                    info = describe(self.env, a, m)
                except RuntimeError:
                    continue
                if info["path"] in seen:
                    continue
                seen.add(info["path"])
                out.append(info)
        self.log("menüparancs-lista: %d tétel" % len(out))
        return sorted(out, key=lambda x: x["path"].lower())


# ====================================================================== Painter

class PainterEnv:
    def __init__(self):
        import substance_painter as sp
        import substance_painter.application  # noqa: F401
        import substance_painter.event  # noqa: F401
        import substance_painter.layerstack  # noqa: F401
        import substance_painter.project  # noqa: F401
        import substance_painter.resource  # noqa: F401
        import substance_painter.textureset  # noqa: F401
        import substance_painter.ui  # noqa: F401
        self.sp = sp
        self._history = None      # a hivatkozást megtartjuk (#21 szabály), használat előtt isValid
        self._widgets_keep = []
        self.log = print

    def describe(self):
        sp = self.sp
        try:
            v = sp.application.version()
        except Exception as e:
            v = "? (%r)" % e
        import sys
        from PySide6 import QtCore
        return "Painter %s | Python %s | Qt %s" % (v, sys.version.split()[0], QtCore.qVersion())

    # ---- widgetek
    def _live_widgets(self):
        for w in QtWidgets.QApplication.allWidgets():
            if alive(w):
                yield w

    def history_view(self):
        if self._history is not None and alive(self._history):
            return self._history
        self._history = None
        for d in self._live_widgets():
            if not isinstance(d, QtWidgets.QDockWidget):
                continue
            if d.objectName() != "history" and "history" not in d.windowTitle().lower():
                continue
            self._widgets_keep.append(d)
            for v in d.findChildren(QtWidgets.QAbstractItemView):
                if alive(v):
                    self._history = v
                    self._widgets_keep.append(v)
                    self.log("History nézet: %s a(z) %r dockban" % (v.metaObject().className(), d.objectName()))
                    return v
        return None

    def all_actions(self):
        mw = self.sp.ui.get_main_window()
        out = list(mw.findChildren(QtGui.QAction))
        for w in self._live_widgets():
            try:
                out.extend(w.actions())
            except Exception:
                pass
        return out

    def all_menus(self):
        return [w for w in self._live_widgets() if isinstance(w, QtWidgets.QMenu)]

    def main_window(self):
        return self.sp.ui.get_main_window()

    # ---- események
    def connect_events(self, on_change, on_close):
        ev = self.sp.event
        conns = []
        for cls, cb in (("LayerStacksModelDataChanged", lambda e: on_change()),
                        ("ProjectAboutToClose", lambda e: on_close())):
            if hasattr(ev, cls):
                ev.DISPATCHER.connect_strong(getattr(ev, cls), cb)
                conns.append((getattr(ev, cls), cb))

        def disconnect():
            for c, cb in conns:
                try:
                    ev.DISPATCHER.disconnect(c, cb)
                except Exception:
                    pass
        return disconnect

    # ---- layer stack snapshot (a #18 mérőjéből)
    def snapshot(self):
        sp = self.sp
        LS = sp.layerstack
        if not sp.project.is_open() or not sp.project.is_in_edition_state():
            return None
        stack = sp.textureset.get_active_stack()
        channels = list(stack.all_channels().keys())
        nodes = {}

        def safe(f, default=None):
            try:
                return f()
            except Exception:
                return default

        def rec(n, parent_uid, idx, in_mask):
            t = n.get_type()
            r = {"uid": n.uid(), "type": t.name, "name": safe(n.get_name), "parent": parent_uid,
                 "idx": idx, "mask_stack": in_mask}
            if safe(n.has_blending, False) is True:
                if in_mask:
                    r["blend"] = safe(lambda: n.get_blending_mode().name)
                    r["opacity"] = safe(lambda: round(n.get_opacity(), 4))
                else:
                    r["blend"] = {c.name: safe(lambda c=c: n.get_blending_mode(c).name) for c in channels}
                    r["opacity"] = {c.name: safe(lambda c=c: round(n.get_opacity(c), 4)) for c in channels}
            if t in (LS.NodeType.GeneratorEffect, LS.NodeType.FilterEffect):
                src = safe(n.get_source)
                if src is None or isinstance(src, str):
                    r["source"] = src
                else:
                    r["source"] = safe(lambda: src.resource_id.url())
            return r

        def walk(layers, parent_uid):
            for i, n in enumerate(layers):
                r = rec(n, parent_uid, i, False)
                r["has_mask"] = safe(n.has_mask)
                if r["has_mask"] is True:
                    r["mask_bg"] = safe(lambda: n.get_mask_background().name)
                nodes[r["uid"]] = r
                for j, e in enumerate(safe(n.content_effects, []) or []):
                    nodes[e.uid()] = rec(e, n.uid(), j, False)
                for j, e in enumerate(safe(n.mask_effects, []) or []):
                    nodes[e.uid()] = rec(e, n.uid(), j, True)
                if n.get_type() == LS.NodeType.GroupLayer:
                    walk(n.sub_layers(), n.uid())

        walk(LS.get_root_layer_nodes(stack), None)   # a ProjectError (locked) kivételt a rögzítő kezeli
        key = "%s/%s" % (safe(lambda: stack.material().name()), safe(stack.name))
        return {"stack": key, "nodes": nodes}

    # ---- resource-ok
    def _retrieve(self, url):
        res = self.sp.resource
        ref = unquote(url)
        try:
            found = res.Resource.retrieve(res.ResourceID.from_url(ref)) or []
            return found[0] if found else None
        except Exception as e:
            self.log("retrieve hiba: %r (%s)" % (e, ref))
            return None

    def resource_info(self, url):
        ref = unquote(url)
        r = self._retrieve(url)
        name, raw = name_from_url(ref), None
        if r is not None:
            try:
                name = r.gui_name()
            except Exception:
                pass
            try:
                raw = str(r.type())
            except Exception as e:
                raw = "? %r" % e
        low = (raw or "").lower().replace("_", "")
        if "smartmaterial" in low:
            kind = "smart_material"
        elif "smartmask" in low:
            kind = "smart_mask"
        elif "generator" in low:
            kind = "generator"
        elif "filter" in low:
            kind = "filter"
        else:
            kind = "brush"
        return {"name": name, "url": ref, "kind": kind, "raw_type": raw}

    def resource_from_source(self, src):
        info = self.resource_info(src)
        return {"name": info["name"], "url": info["url"]}
