# PROTOTYPE – eldobható kód, nem kerül a main ágra.
# Egyszerűsített Panel (a #8 C változata alapján: elnevezett csoportok), csak Workflow buttonokkal,
# és a sárga változatváltó sáv. A Workflow button kattintásra NEM hajt végre semmit, csak kiírja a Step-eket.

import json

from PySide6 import QtCore, QtGui, QtWidgets

from . import model
from .editors import VARIANTS, Session
from .widgets import FlowLayout, own

Qt = QtCore.Qt
TILE = 40


def sample_workflows():
    S = model.new_step
    r = lambda n, k: {"name": n, "url": "resource://starter_assets/%s/%s" % (k, n)}
    wfs = [
        ("Fill + fekete maszk", [S("fill"), S("mask", bg="Black")]),
        ("Rozsda a maszkban", [S("fill", name="Rozsda"), S("mask", bg="Black"),
                               S("generator", resource=r("Dirt", "generator"), target="mask"),
                               S("levels", target="mask")]),
        ("Kopott él", [S("smart_material", resource=r("Edge Wear Steel", "smart_material")),
                       S("blend", mode="Overlay"), S("opacity", value=60, channels=["BaseColor"])]),
        ("Festésre kész", [S("paint", name="Részletek"), S("mask", bg="White"),
                           S("brush", resource=r("Basic Hard", "brush"))]),
    ]
    return [{"id": i + 1, "name": n, "steps": st} for i, (n, st) in enumerate(wfs)]


class Tile(QtWidgets.QToolButton):
    def __init__(self, wf, strategy, on_click, on_menu):
        super().__init__()
        self.wf = wf
        self.setIcon(model.workflow_icon(wf["steps"], strategy, 64))
        self.setIconSize(QtCore.QSize(TILE - 8, TILE - 8))
        self.setFixedSize(TILE, TILE)
        self.setAutoRaise(True)
        lines = "<br>".join("%d. %s" % (i, model.label(s)) for i, s in enumerate(wf["steps"], 1))
        self.setToolTip("<b>%s</b><br><i>Workflow button</i><br>%s" % (wf["name"], lines))
        self.clicked.connect(lambda: on_click(wf))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda p: on_menu(wf, self.mapToGlobal(p)))


class PanelRoot(QtWidgets.QWidget):
    def __init__(self, host, variant="A"):
        super().__init__()
        self.host = host
        self.setObjectName("spx_workflow_proto")
        self.setProperty("spx", True)   # a rögzítő ezt és a gyerekeit nem figyeli
        self.setWindowTitle("SPX Workflow (prototípus)")
        self.variant = variant if variant in VARIANTS else "A"
        self.groups = [{"name": "Rétegek", "items": sample_workflows(), "open": True},
                       {"name": "Saját", "items": [], "open": True}]
        self.next_id = 100
        self.session = None
        self.driver = None
        self.target_group = None
        self.page_a = VARIANTS["A"](self)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)
        self.strip_slot = QtWidgets.QVBoxLayout()
        lay.addLayout(self.strip_slot)
        self.stack = QtWidgets.QStackedWidget()
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.stack.addWidget(self.scroll)
        self.stack.addWidget(self.page_a)
        lay.addWidget(self.stack, 1)
        self.status_lbl = QtWidgets.QLabel()
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet("color: #9ad; font-size: 11px;")
        lay.addWidget(self.status_lbl)
        lay.addWidget(self._switcher())
        self.render()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        host.log("Panel indul, változat: %s" % self.variant)

    # ---------------------------------------------------------------- sárga sáv
    def _switcher(self):
        bar = QtWidgets.QFrame()
        bar.setStyleSheet("QFrame { background: #e8c547; border-radius: 4px; } QLabel, QToolButton "
                          "{ color: #222; font-weight: bold; } QToolButton { border: none; padding: 0 6px; }")
        h = QtWidgets.QHBoxLayout(bar)
        h.setContentsMargins(4, 1, 4, 1)
        self.prev_btn = QtWidgets.QToolButton(text="◀")
        self.next_btn = QtWidgets.QToolButton(text="▶")
        self.var_lbl = QtWidgets.QLabel()
        self.var_lbl.setWordWrap(True)
        self.var_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        js = QtWidgets.QToolButton(text="{ }")
        js.setToolTip("A Layout adatai (JSON)")
        js.clicked.connect(self._show_json)
        self.prev_btn.clicked.connect(lambda: self.cycle(-1))
        self.next_btn.clicked.connect(lambda: self.cycle(1))
        h.addWidget(self.prev_btn)
        h.addWidget(self.var_lbl, 1)
        h.addWidget(self.next_btn)
        h.addWidget(js)
        self._update_var_lbl()
        return bar

    def _update_var_lbl(self):
        v = VARIANTS[self.variant]
        self.var_lbl.setText("%s – %s" % (self.variant, v.NAME))
        self.var_lbl.setToolTip("Workflow-ikon: " + model.ICON_STRATEGY_HU[model.ICON_STRATEGY[self.variant]])
        busy = self.session is not None
        self.prev_btn.setEnabled(not busy)
        self.next_btn.setEnabled(not busy)

    def cycle(self, d):
        if self.session is not None:
            self.status("Előbb fejezd be (Mentés vagy Mégse) a mostani Workflow-t.")
            return
        keys = list(VARIANTS)
        self.variant = keys[(keys.index(self.variant) + d) % len(keys)]
        self.host.log("változat → %s" % self.variant)
        self._update_var_lbl()
        self.render()
        self.status("%s változat. Új Workflow: a csoport sorában a „+” gomb." % self.variant)

    def keyPressEvent(self, e):
        fw = QtWidgets.QApplication.focusWidget()
        if isinstance(fw, (QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox)):
            return super().keyPressEvent(e)
        if e.key() == Qt.Key.Key_Left:
            self.cycle(-1)
        elif e.key() == Qt.Key.Key_Right:
            self.cycle(1)
        else:
            super().keyPressEvent(e)

    def _show_json(self):
        data = [{"name": g["name"], "buttons": [{"kind": "workflow", **model.clean(w)} for w in g["items"]]}
                for g in self.groups]
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Layout (JSON)")
        d.resize(460, 520)
        t = QtWidgets.QPlainTextEdit(json.dumps(data, ensure_ascii=False, indent=2))
        t.setReadOnly(True)
        QtWidgets.QVBoxLayout(d).addWidget(t)
        d.show()

    # ---------------------------------------------------------------- csoportok
    def render(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(2)
        strat = model.ICON_STRATEGY[self.variant]
        for g in self.groups:
            head = QtWidgets.QHBoxLayout()
            tog = QtWidgets.QToolButton(text=("▾ " if g["open"] else "▸ ") + g["name"])
            tog.setStyleSheet("QToolButton { border: none; font-weight: bold; color: #ccc; }")
            tog.clicked.connect(lambda _=False, g=g: self._toggle(g))
            head.addWidget(tog)
            head.addStretch(1)
            plus = QtWidgets.QToolButton(text="+")
            plus.setToolTip("Új Workflow ebbe a csoportba")
            plus.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
            m = own(QtWidgets.QMenu(plus))
            a1 = own(m.addAction("● Új Workflow rögzítéssel"))
            a1.triggered.connect(lambda _=False, g=g: self.new_workflow(g, True))
            a2 = own(m.addAction("✎ Új Workflow kézzel (üres lista)"))
            a2.triggered.connect(lambda _=False, g=g: self.new_workflow(g, False))
            plus.setMenu(m)
            head.addWidget(plus)
            v.addLayout(head)
            if g["open"]:
                box = QtWidgets.QWidget()
                fl = FlowLayout(box, spacing=2, margin=2)
                for wf in g["items"]:
                    fl.addWidget(Tile(wf, strat, self.run, self.tile_menu))
                if not g["items"]:
                    e = QtWidgets.QLabel("(üres – „+”)")
                    e.setStyleSheet("color: #777;")
                    fl.addWidget(e)
                v.addWidget(box)
        v.addStretch(1)
        self.scroll.setWidget(w)

    def _toggle(self, g):
        g["open"] = not g["open"]
        self.render()

    def run(self, wf):
        txt = " → ".join(model.short(s) for s in wf["steps"])
        self.status("▶ %s: %s  (prototípus: nem hajt végre semmit)" % (wf["name"], txt))
        self.host.log("kattintás: %s" % wf["name"])

    def tile_menu(self, wf, pos):
        m = own(QtWidgets.QMenu(self))
        e = own(m.addAction("Szerkesztés…"))
        e.triggered.connect(lambda: self.edit_workflow(wf))
        d = own(m.addAction("Törlés"))
        d.triggered.connect(lambda: self._delete(wf))
        m.exec(pos)

    def _delete(self, wf):
        for g in self.groups:
            if wf in g["items"]:
                g["items"].remove(wf)
        self.host.log("Workflow törölve: %s" % wf["name"])
        self.render()

    # ---------------------------------------------------------------- szerkesztés
    def new_workflow(self, group, record):
        self._begin(Session(self.host), group, record)

    def edit_workflow(self, wf):
        g = next(g for g in self.groups if wf in g["items"])
        self._begin(Session(self.host, wf), g, False)

    def _begin(self, session, group, record):
        if self.session is not None:
            self.status("Már szerkesztesz egy Workflow-t.")
            return
        self.session = session
        self.target_group = group
        session.done.connect(self._finish)
        session.recStarted.connect(lambda: self.status("● Rögzítés: kattintgass a Painterben, a végén Stop."))
        session.recFinished.connect(lambda r: self.status(
            "Rögzítés vége (%s). Javítsd a listát, adj hozzá Brusht, aztán Mentés." % r))
        self.driver = self.page_a if self.variant == "A" else VARIANTS[self.variant](self)
        self._update_var_lbl()
        self.host.log("UI: %s (%s változat)" % ("új Workflow rögzítéssel" if record else
                                                 ("szerkesztés: " + session.display_name() if session.workflow
                                                  else "új Workflow kézzel"), self.variant))
        self.status("● Rögzítés: kattintgass a Painterben, a végén Stop." if record else
                    "Szerkesztés: a „+ Step”-pel adhatsz hozzá, a brusht az Assets-ből húzd be.")
        self.driver.begin(session, record)

    def _finish(self, wf):
        drv, self.driver = self.driver, None
        self.session = None
        drv.end()
        self.show_page(None)
        if wf is not None:
            if wf["id"] is None:
                wf["id"] = self.next_id
                self.next_id += 1
                self.target_group["items"].append(wf)
            else:
                for g in self.groups:
                    for i, old in enumerate(g["items"]):
                        if old["id"] == wf["id"]:
                            g["items"][i] = wf
            self.host.log("MENTVE: " + json.dumps(model.clean(wf), ensure_ascii=False))
            self.status("Mentve: %s (%d Step)" % (wf["name"], len(wf["steps"])))
        else:
            self.status("Elvetve.")
        self._update_var_lbl()
        self.render()

    def show_page(self, w):
        self.stack.setCurrentWidget(w if w is not None else self.scroll)

    def show_strip(self, w):
        while self.strip_slot.count():
            it = self.strip_slot.takeAt(0)
            if it.widget():
                it.widget().setParent(None)
        if w is not None:
            self.strip_slot.addWidget(w)

    def status(self, msg):
        self.status_lbl.setText(msg)

    def shutdown(self):
        if self.session is not None:
            self.session.cancel()
