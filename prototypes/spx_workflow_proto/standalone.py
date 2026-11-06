# PROTOTYPE – a Workflow szerkesztő kipróbálása Painter nélkül, szimulált Painterrel.
#   pip install PySide6
#   python prototypes/spx_workflow_proto/standalone.py [A|B|C]
# A szimulált Painter ugyanazt adja, mint a valódi: History nézet (QListView), layer stack snapshot,
# menüsor QAction-ökkel, Assets-ből húzható resource-ok. A rögzítő (recorder.py) változatlanul fut rajta.
# Fejlesztői képernyőkép: SPX_DEMO=<forgatókönyv> SPX_SHOT=out.png (lásd DEMOS lent).

import copy
import itertools
import os
import sys
from urllib.parse import quote, unquote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402
from spx_workflow_proto import host as host_mod, panel  # noqa: E402

Qt = QtCore.Qt
CH = ["BaseColor", "Roughness", "Metallic", "Height"]
_uid = itertools.count(1000)


def layer(t, name):
    return {"uid": next(_uid), "type": t, "name": name, "children": [], "content": [], "mask": None,
            "blend": {c: "Normal" for c in CH}, "opacity": {c: 1.0 for c in CH}}


def effect(t, name, source=None):
    return {"uid": next(_uid), "type": t, "name": name, "source": source, "blend": "Normal", "opacity": 1.0}


def res_url(kind, name):
    return "resource://starter_assets/%s/%s?version=1" % (kind, name)


class FakePainter(QtCore.QObject):
    stackChanged = QtCore.Signal()
    closing = QtCore.Signal()

    def __init__(self, win):
        super().__init__()
        self.win = win
        base = layer("FillLayer", "Base")
        self.sets = {"Body": [base], "Head": [layer("FillLayer", "Head base")]}
        self.active = "Body"
        self.selected = base["uid"]
        self.states = [("<empty>", copy.deepcopy(self.sets))]
        self.idx = 0
        self.counter = {"FillLayer": 1, "PaintLayer": 1, "GroupLayer": 1}
        self.hist_model = QtGui.QStandardItemModel()
        self.hist_view = QtWidgets.QListView()
        self.hist_view.setModel(self.hist_model)
        self.hist_view.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Layer stack (szimulált)"])
        self.tree.itemClicked.connect(self._tree_click)
        self._sync()

    # ---- állapot
    def layers(self):
        return self.sets[self.active]

    def find(self, uid, layers=None, parent=None):
        layers = self.layers() if layers is None else layers
        for i, l in enumerate(layers):
            if l["uid"] == uid:
                return l, layers, i
            got = self.find(uid, l["children"], l)
            if got:
                return got
        return None

    def sel_layer(self):
        got = self.find(self.selected)
        if got is None:
            if self.layers():
                self.selected = self.layers()[0]["uid"]
                return self.layers()[0]
            return None
        return got[0]

    def op(self, label, fn):
        if fn() is False:
            return
        del self.states[self.idx + 1:]
        self.states.append((label, copy.deepcopy(self.sets)))
        self.idx = len(self.states) - 1
        self._sync()

    def undo(self):
        if self.idx > 0:
            self.idx -= 1
            self.sets = copy.deepcopy(self.states[self.idx][1])
            self._sync()

    def redo(self):
        if self.idx < len(self.states) - 1:
            self.idx += 1
            self.sets = copy.deepcopy(self.states[self.idx][1])
            self._sync()

    def switch_set(self):
        self.active = "Head" if self.active == "Body" else "Body"
        self.selected = self.layers()[0]["uid"] if self.layers() else None
        self._sync()

    def _sync(self):
        self.hist_model.clear()
        for lab, _ in self.states:
            self.hist_model.appendRow(QtGui.QStandardItem(lab))
        self.hist_view.setCurrentIndex(self.hist_model.index(self.idx, 0))
        self.tree.clear()

        def add(parent, layers):
            for l in layers:
                extra = []
                if l["mask"] is not None:
                    extra.append("maszk:%s" % l["mask"]["bg"])
                if l["blend"]["BaseColor"] != "Normal":
                    extra.append(l["blend"]["BaseColor"])
                if l["opacity"]["BaseColor"] != 1.0:
                    extra.append("op %d%%" % round(l["opacity"]["BaseColor"] * 100))
                it = QtWidgets.QTreeWidgetItem([l["name"] + ("  [" + ", ".join(extra) + "]" if extra else "")])
                it.setData(0, Qt.ItemDataRole.UserRole, l["uid"])
                for e in l["content"]:
                    QtWidgets.QTreeWidgetItem(it, ["  ƒ " + e["name"]])
                if l["mask"] is not None:
                    for e in l["mask"]["effects"]:
                        QtWidgets.QTreeWidgetItem(it, ["  ◐ " + e["name"]])
                (parent.addChild(it) if parent else self.tree.addTopLevelItem(it))
                add(it, l["children"])
                if l["uid"] == self.selected:
                    self.tree.setCurrentItem(it)
        add(None, self.layers())
        self.tree.expandAll()
        self.tree.setHeaderLabels(["Layer stack – %s (szimulált)" % self.active])
        self.stackChanged.emit()

    def _tree_click(self, it):
        uid = it.data(0, Qt.ItemDataRole.UserRole)
        if uid:
            self.selected = uid

    # ---- műveletek (mint a Painter gombjai)
    def add_layer(self, t, base, label):
        def fn():
            l = layer(t, "%s %d" % (base, self.counter[t]))
            self.counter[t] += 1
            got = self.find(self.selected)
            if got is None:
                self.layers().insert(0, l)
            else:
                _, lst, i = got
                lst.insert(i, l)
            self.selected = l["uid"]
        self.op(label, fn)

    def add_mask(self, bg):
        def fn():
            l = self.sel_layer()
            if l is None or l["mask"] is not None:
                return False
            l["mask"] = {"bg": bg, "effects": []}
        self.op("Add %s mask" % bg.lower(), fn)

    def add_effect(self, t, name, label, source=None):
        def fn():
            l = self.sel_layer()
            if l is None:
                return False
            (l["mask"]["effects"] if l["mask"] is not None else l["content"]).append(effect(t, name, source))
        self.op(label, fn)

    def set_generator(self, name):
        def fn():
            l = self.sel_layer()
            if l is None:
                return False
            for e in reversed((l["mask"] or {"effects": []})["effects"] + l["content"]):
                if e["type"] == "GeneratorEffect" and e["source"] is None:
                    e["source"] = res_url("generator", name)
                    e["name"] = name
                    return True
            return False
        self.op("Set generator", fn)

    def set_blend(self, mode):
        def fn():
            l = self.sel_layer()
            if l is None:
                return False
            l["blend"] = {c: mode for c in CH}
        self.op("set blending mode", fn)

    def set_opacity(self, v, ch="BaseColor"):
        def fn():
            l = self.sel_layer()
            if l is None:
                return False
            l["opacity"][ch] = v
        self.op("set blending opacity", fn)

    def smart_material(self, name):
        def fn():
            g = layer("GroupLayer", name)
            g["children"] = [layer("FillLayer", "Base"), layer("FillLayer", "Edges")]
            got = self.find(self.selected)
            lst, i = (got[1], got[2]) if got else (self.layers(), 0)
            lst.insert(i, g)
            self.selected = g["uid"]
        self.op("Drop layer preset", fn)

    def smart_mask(self):
        def fn():
            l = self.sel_layer()
            if l is None:
                return False
            if l["mask"] is None:
                l["mask"] = {"bg": "White", "effects": []}
            l["mask"]["effects"].append(effect("GeneratorEffect", "Mask Editor", None))
        self.op("Drop resource on new mask", fn)

    def stroke(self):
        self.op("Add stroke", lambda: True)

    def rename(self):
        def fn():
            l = self.sel_layer()
            if l is None:
                return False
            l["name"] += "*"
        self.op("label", fn)

    def remove(self):
        def fn():
            got = self.find(self.selected)
            if got is None:
                return False
            got[1].pop(got[2])
            self.selected = None
        self.op("Remove layer(s)", fn)

    # ---- snapshot (ugyanaz a forma, mint a PainterEnv-é)
    def snapshot(self):
        nodes = {}

        def walk(layers, parent):
            for i, l in enumerate(layers):
                nodes[l["uid"]] = {"uid": l["uid"], "type": l["type"], "name": l["name"], "parent": parent,
                                   "idx": i, "mask_stack": False, "blend": dict(l["blend"]),
                                   "opacity": dict(l["opacity"]), "has_mask": l["mask"] is not None,
                                   "mask_bg": l["mask"]["bg"] if l["mask"] else None}
                for j, e in enumerate(l["content"]):
                    nodes[e["uid"]] = dict(e, parent=l["uid"], idx=j, mask_stack=False)
                for j, e in enumerate((l["mask"] or {"effects": []})["effects"]):
                    nodes[e["uid"]] = dict(e, parent=l["uid"], idx=j, mask_stack=True)
                walk(l["children"], l["uid"])
        walk(self.layers(), None)
        return {"stack": "mat/" + self.active, "nodes": nodes}


class SimEnv:
    def __init__(self, win, fake):
        self.win, self.fake = win, fake
        self.log = print

    def describe(self):
        return "szimulált Painter (standalone), Qt %s" % QtCore.qVersion()

    def snapshot(self):
        return self.fake.snapshot()

    def history_view(self):
        return self.fake.hist_view

    def all_actions(self):
        return self.win.findChildren(QtGui.QAction)

    def all_menus(self):
        return self.win.findChildren(QtWidgets.QMenu)

    def main_window(self):
        return self.win

    def connect_events(self, on_change, on_close):
        a = lambda: on_change()
        b = lambda: on_close()
        self.fake.stackChanged.connect(a)
        self.fake.closing.connect(b)

        def disconnect():
            self.fake.stackChanged.disconnect(a)
            self.fake.closing.disconnect(b)
        return disconnect

    def resource_info(self, url):
        ref = unquote(url)
        parts = ref.split("?")[0].split("/")
        kind = parts[-2] if len(parts) >= 2 else "brush"
        return {"name": host_mod.name_from_url(ref), "url": ref,
                "kind": kind if kind in ("brush", "smart_material", "smart_mask", "generator", "filter")
                else "brush", "raw_type": kind}

    def resource_from_source(self, src):
        return {"name": host_mod.name_from_url(src), "url": src}


class FakeAssets(QtWidgets.QTreeWidget):
    DATA = [("brush", ["Basic Hard", "Dirt Spread", "Chalk Bold"]),
            ("smart_material", ["Rust Coat", "Edge Wear Steel"]),
            ("smart_mask", ["Edges Soft", "Cavity Dirt"]),
            ("generator", ["Dirt", "Metal Edge Wear"]),
            ("filter", ["Blur", "Sharpen"])]

    def __init__(self):
        super().__init__()
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragOnly)
        for kind, names in self.DATA:
            top = QtWidgets.QTreeWidgetItem(self, [kind])
            top.setFlags(Qt.ItemFlag.ItemIsEnabled)
            for n in names:
                it = QtWidgets.QTreeWidgetItem(top, [n])
                it.setData(0, Qt.ItemDataRole.UserRole, res_url(kind, n))
        self.expandAll()

    def mimeData(self, items):
        md = QtCore.QMimeData()
        urls = [quote(i.data(0, Qt.ItemDataRole.UserRole), safe="") for i in items
                if i.data(0, Qt.ItemDataRole.UserRole)]
        md.setData("text/uri-list", "\r\n".join(urls).encode())
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


def build(variant):
    win = QtWidgets.QMainWindow()
    win.setWindowTitle("Szimulált Painter – SPX Workflow prototípus")
    fake = FakePainter(win)
    acts = {}

    def act(menu, text, fn, sc=None, group=None):
        a = QtGui.QAction(text, win)
        if sc:
            a.setShortcut(QtGui.QKeySequence(sc))
        if group is not None:
            a.setCheckable(True)
            group.addAction(a)
        a.triggered.connect(fn)
        menu.addAction(a)
        acts[text] = a
        return a

    mb = win.menuBar()
    st = win.style()
    fm = mb.addMenu("File")
    act(fm, "Save", lambda: None, "Ctrl+S").setIcon(st.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogSaveButton))
    act(fm, "Save as...", lambda: None)
    act(fm, "Export textures...", lambda: None, "Ctrl+Shift+E").setIcon(
        st.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowUp))
    act(fm, "Close", lambda: fake.closing.emit())
    em = mb.addMenu("Edit")
    act(em, "Undo", fake.undo, "Ctrl+Z")
    act(em, "Redo", fake.redo, "Ctrl+Y")
    wm = mb.addMenu("Window")
    vm = wm.addMenu("Views")
    act(vm, "Log", lambda: None)
    act(vm, "History", lambda: None)
    mm = mb.addMenu("Mode")
    grp = QtGui.QActionGroup(win)
    act(mm, "Paint", lambda: None, "1", grp)
    act(mm, "Eraser", lambda: None, "2", grp)
    lm = mb.addMenu("Layer")
    layer_ops = [
        ("Add fill layer", lambda: fake.add_layer("FillLayer", "Fill layer", "Add fill layer")),
        ("Add layer", lambda: fake.add_layer("PaintLayer", "Layer", "Add layer")),
        ("Add group", lambda: fake.add_layer("GroupLayer", "Folder", "Add group")),
        ("Add black mask", lambda: fake.add_mask("Black")),
        ("Add white mask", lambda: fake.add_mask("White")),
        ("Add generator", lambda: fake.add_effect("GeneratorEffect", "Generator (empty)", "Add generator")),
        ("Generator forrása: Dirt", lambda: fake.set_generator("Dirt")),
        ("Add filter: Blur", lambda: fake.add_effect("FilterEffect", "Blur", "Add filter",
                                                     res_url("filter", "Blur"))),
        ("Add levels", lambda: fake.add_effect("LevelsEffect", "Levels", "Add levels")),
        ("Add anchor point", lambda: fake.add_effect("AnchorPointEffect", "Anchor Point", "Add anchor point")),
        ("Blend → Multiply", lambda: fake.set_blend("Multiply")),
        ("Opacity → 40% (BaseColor)", lambda: fake.set_opacity(0.4)),
        ("Smart material: Rust Coat", lambda: fake.smart_material("Rust Coat")),
        ("Smart mask (behúzás)", fake.smart_mask),
        ("Festés (egy vonás)", fake.stroke),
        ("Átnevezés", fake.rename),
        ("Remove layer(s)", fake.remove),
        ("Texture set váltás", fake.switch_set),
    ]
    for text, fn in layer_ops:
        act(lm, text, fn)
    acts["Texture set váltás"].setProperty("spx", True)   # a Painterben ez nem QAction, hanem a listában kattintás

    ops = QtWidgets.QWidget()
    grid = QtWidgets.QGridLayout(ops)
    grid.setSpacing(2)
    for i, (text, _) in enumerate(layer_ops + [("Undo", None), ("Redo", None)]):
        b = QtWidgets.QToolButton()
        b.setDefaultAction(acts[text])
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        grid.addWidget(b, i // 2, i % 2)
    left = QtWidgets.QWidget()
    lv = QtWidgets.QVBoxLayout(left)
    lv.setContentsMargins(2, 2, 2, 2)
    lv.addWidget(fake.tree, 1)
    lv.addWidget(ops)
    win.setCentralWidget(left)

    def dock(title, w, area, name):
        d = QtWidgets.QDockWidget(title)
        d.setObjectName(name)
        d.setWidget(w)
        win.addDockWidget(area, d)
        return d

    d_assets = dock("Assets (szimulált)", FakeAssets(), Qt.DockWidgetArea.LeftDockWidgetArea, "NewShelf")
    d_hist = dock("History", fake.hist_view, Qt.DockWidgetArea.LeftDockWidgetArea, "history")
    env = SimEnv(win, fake)
    host = host_mod.Host(env, log_to_file=False)
    root = panel.PanelRoot(host, variant)
    d_panel = dock("SPX Workflow (prototípus)", root, Qt.DockWidgetArea.RightDockWidgetArea, "spx_dock")
    win.resize(1280, 760)
    win.resizeDocks([d_assets, d_panel], [190, 330], Qt.Orientation.Horizontal)
    win.resizeDocks([d_assets, d_hist], [380, 300], Qt.Orientation.Vertical)
    return win, fake, root, acts


# ---------------------------------------------------------------- fejlesztői demók (képernyőképhez)

def demo_steps(name, win, fake, root, acts):
    """(késleltetés ms, függvény) lista. A rögzítést a Panel „+” menüjének útján indítja."""
    T = lambda t: acts[t].trigger()
    g = lambda: root.groups[1]
    rec = [
        (300, lambda: root.new_workflow(g(), True)),
        (500, lambda: T("Add fill layer")),
        (500, lambda: T("Add black mask")),
        (500, lambda: T("Save")),
        (900, lambda: T("Add generator")),
        (500, lambda: T("Generator forrása: Dirt")),
        (500, lambda: T("Festés (egy vonás)")),
        (500, lambda: T("Add levels")),
        (500, lambda: T("Undo")),
        (500, lambda: T("Blend → Multiply")),
        (500, lambda: T("Opacity → 40% (BaseColor)")),
        (500, lambda: T("Átnevezés")),
        (500, lambda: T("Smart mask (behúzás)")),
        (500, lambda: T("Export textures...")),
        (1200, lambda: None),
    ]
    stop = [(300, lambda: root.session.stop_recording()), (600, lambda: None)]
    if name == "rec":
        return rec
    if name == "edit":
        return rec + stop + [(300, lambda: _select_some(root))]
    if name == "pop":
        return rec + stop + [(300, lambda: _select_some(root, popover=True))]
    return []


def _select_some(root, popover=False):
    drv = root.driver
    steps = root.session.steps
    target = next((s for s in steps if s["type"] == "smart_mask"), steps[0])
    if root.variant == "A":
        drv._select_id(target["id"])
    elif root.variant == "B":
        drv.dialog.t_layer.select(target)
    elif root.variant == "C":
        drv._chip_clicked(target)


def main():
    app = QtWidgets.QApplication(sys.argv)
    dark(app)
    variant = sys.argv[1] if len(sys.argv) > 1 else "A"
    win, fake, root, acts = build(variant)
    win.show()
    demo = os.environ.get("SPX_DEMO")
    shot = os.environ.get("SPX_SHOT")
    if demo:
        steps = demo_steps(demo, win, fake, root, acts)
        t = 0
        for delay, fn in steps:
            t += delay
            QtCore.QTimer.singleShot(t, fn)
        if shot:
            def grab():
                base, ext = os.path.splitext(shot)
                win.grab().save(shot)
                for i, w in enumerate(QtWidgets.QApplication.topLevelWidgets()):
                    if w is not win and w.isVisible() and w.width() > 40:
                        w.grab().save("%s_top%d%s" % (base, i, ext))
                app.quit()
            QtCore.QTimer.singleShot(t + 400, grab)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
