# PROTOTYPE – eldobható kód. Közös építőelemek a három változathoz (az elrendezést a változatok adják).

from urllib.parse import unquote

from PySide6 import QtCore, QtGui, QtWidgets

from . import model
from .recorder import keep

Qt = QtCore.Qt
STEP_MIME = "application/x-spx-step"


def own(obj):
    """Megjelöli a prototípus saját QAction/QMenu objektumait, hogy a rögzítő ne vegye fel őket."""
    obj.setProperty("spx", True)
    return obj


def resource_urls(mime):
    raw = ""
    if mime.hasFormat("text/uri-list"):
        raw = bytes(mime.data("text/uri-list")).decode("utf-8", "ignore")
    elif mime.hasText():
        raw = mime.text()
    out = []
    for line in raw.replace("\r", "\n").split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and unquote(line).startswith("resource://"):
            out.append(line)
    return out


def step_from_drop(host, mime):
    """Assets-ből behúzott resource → Step (a resource típusa szerint)."""
    out = []
    for url in resource_urls(mime):
        info = host.resource_info(url)
        kind = info.get("kind") or "brush"
        p = {"resource": {"name": info["name"], "url": info["url"]}}
        if kind in ("generator", "filter"):
            p["target"] = "mask" if kind == "generator" else "layer"
        out.append(model.new_step(kind, "kézi", **p))
        host.log("behúzás: %s → %s Step (resource típus: %s)" % (info["name"], kind, info.get("raw_type")))
    return out


class FlowLayout(QtWidgets.QLayout):
    """Sorokba tördelő layout (a Qt példa átirata)."""

    def __init__(self, parent=None, spacing=4, margin=4):
        super().__init__(parent)
        self._items = []
        self.setSpacing(spacing)
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._do(QtCore.QRect(0, 0, w, 0), True)

    def setGeometry(self, r):
        super().setGeometry(r)
        self._do(r, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QtCore.QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return s + QtCore.QSize(m.left() + m.right(), m.top() + m.bottom())

    def clear(self):
        while self._items:
            w = self._items.pop().widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _do(self, r, test):
        m = self.contentsMargins()
        eff = r.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line, sp = eff.x(), eff.y(), 0, self.spacing()
        for it in self._items:
            if it.isEmpty():
                continue
            sz = it.sizeHint()
            nx = x + sz.width() + sp
            if nx - sp > eff.right() + 1 and line > 0:
                x, y, line = eff.x(), y + line + sp, 0
                nx = x + sz.width() + sp
            if not test:
                it.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), sz))
            x = nx
            line = max(line, sz.height())
        return y + line - r.y() + m.bottom()


def step_menu(parent, on_pick, only_zone=None):
    """A „+ Step” menü a katalógusból."""
    menu = own(QtWidgets.QMenu(parent))
    for title, kinds in model.MENU_GROUPS:
        kinds = [k for k in kinds if only_zone is None or model.CATALOG[k][1] == only_zone]
        if not kinds:
            continue
        sec = menu.addSection(title)
        own(sec)
        for k in kinds:
            if k == "mask":
                for bg, hu in (("Black", "Fekete maszk"), ("White", "Fehér maszk")):
                    s = model.new_step("mask", bg=bg)
                    a = own(menu.addAction(model.step_icon(s, 32), hu))
                    a.triggered.connect(lambda _=False, bg=bg: on_pick(model.new_step("mask", bg=bg)))
                continue
            s = model.new_step(k)
            a = own(menu.addAction(model.step_icon(s, 32), model.CATALOG[k][0]))
            a.triggered.connect(lambda _=False, k=k: on_pick(model.new_step(k)))
    return menu


class DropField(QtWidgets.QLabel):
    """Resource mező: az Assets ablakból kell ide húzni."""
    changed = QtCore.Signal()

    def __init__(self, host, step):
        super().__init__()
        self.host, self.step = host, step
        self.setAcceptDrops(True)
        self.setMinimumHeight(30)
        self.setWordWrap(True)
        self.refresh()

    def refresh(self):
        r = self.step["params"].get("resource")
        if r:
            self.setText("📦 " + r["name"])
            self.setStyleSheet("QLabel { border: 1px solid #666; border-radius: 3px; padding: 4px; }")
        else:
            self.setText("⚠ Húzd ide az Assets ablakból")
            self.setStyleSheet("QLabel { border: 2px dashed #e0a800; border-radius: 3px; padding: 4px;"
                               " color: #e0c060; }")

    def dragEnterEvent(self, e):
        if resource_urls(e.mimeData()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        url = resource_urls(e.mimeData())[0]
        info = self.host.resource_info(url)
        self.step["params"]["resource"] = {"name": info["name"], "url": info["url"]}
        self.host.log("resource beállítva: %s → %s" % (model.CATALOG[self.step["type"]][0], info["name"]))
        e.acceptProposedAction()
        self.refresh()
        self.changed.emit()


class MenuPicker(QtWidgets.QDialog):
    """Kereshető lista a főablak menüparancsairól (tartalék a menüből elkapáshoz)."""

    def __init__(self, host, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Menüparancs kiválasztása")
        self.setProperty("spx", True)
        self.resize(360, 420)
        self.result_info = None
        lay = QtWidgets.QVBoxLayout(self)
        self.search = QtWidgets.QLineEdit(placeholderText="Keresés…")
        self.list = QtWidgets.QListWidget()
        lay.addWidget(self.search)
        lay.addWidget(self.list)
        self.items = host.menu_actions()
        for info in self.items:
            it = QtWidgets.QListWidgetItem(info["_icon"], info["path"])
            it.setData(Qt.ItemDataRole.UserRole, info)
            self.list.addItem(it)
        self.search.textChanged.connect(self._filter)
        self.list.itemDoubleClicked.connect(self._pick)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(lambda: self._pick(self.list.currentItem()))
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _filter(self, t):
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(t.lower() not in it.text().lower())

    def _pick(self, it):
        if it is not None:
            self.result_info = it.data(Qt.ItemDataRole.UserRole)
            self.accept()


class ParamForm(QtWidgets.QWidget):
    """Egy Step beállításai. A változtatás azonnal a Step dict-be íródik, majd `changed`."""
    changed = QtCore.Signal()

    def __init__(self, host, step, parent=None):
        super().__init__(parent)
        self.host, self.step = host, step
        self._capture = None
        p = step["params"]
        t = step["type"]
        form = QtWidgets.QFormLayout(self)
        form.setContentsMargins(4, 4, 4, 4)
        head = QtWidgets.QLabel()
        head.setPixmap(model.step_pixmap(step, 28))
        title = QtWidgets.QLabel("<b>%s</b>" % model.CATALOG[t][0] +
                                 ("  <i>(rögzített)</i>" if step.get("src") == "rögzített" else "  <i>(kézi)</i>"))
        form.addRow(head, title)
        if step.get("note"):
            n = QtWidgets.QLabel("ℹ " + step["note"])
            n.setWordWrap(True)
            n.setStyleSheet("color: #e0c060;")
            form.addRow(n)

        if t in ("fill", "paint", "folder"):
            e = QtWidgets.QLineEdit(p.get("name", ""), placeholderText="(alapnév)")
            e.textChanged.connect(lambda v: self._set("name", v))
            form.addRow("Név:", e)
            form.addRow(self._hint("A current layer fölé kerül, és ő lesz a current layer."))
        elif t == "mask":
            c = QtWidgets.QComboBox()
            c.addItems(["Fekete", "Fehér"])
            c.setCurrentIndex(0 if p["bg"] == "Black" else 1)
            c.currentIndexChanged.connect(lambda i: self._set("bg", "Black" if i == 0 else "White"))
            form.addRow("Szín:", c)
        if t in ("generator", "filter", "smart_material", "smart_mask", "brush"):
            d = DropField(host, step)
            d.changed.connect(self.changed)
            form.addRow("Resource:", d)
        if t in ("generator", "filter", "levels", "anchor"):
            c = QtWidgets.QComboBox()
            c.addItems(["Maszkra", "Layerre"])
            c.setCurrentIndex(0 if p["target"] == "mask" else 1)
            c.currentIndexChanged.connect(lambda i: self._set("target", "mask" if i == 0 else "layer"))
            form.addRow("Hova:", c)
        if t == "blend":
            c = QtWidgets.QComboBox()
            c.addItems(model.BLEND_MODES)
            if p["mode"] not in model.BLEND_MODES:
                c.addItem(p["mode"])
            c.setCurrentText(p["mode"])
            c.currentTextChanged.connect(lambda v: self._set("mode", v))
            form.addRow("Mód:", c)
            form.addRow(self._hint("Minden csatornára."))
        if t == "opacity":
            s = QtWidgets.QSpinBox(minimum=0, maximum=100, suffix=" %")
            s.setValue(int(p["value"]))
            s.valueChanged.connect(lambda v: self._set("value", v))
            form.addRow("Érték:", s)
            box = QtWidgets.QWidget()
            fl = FlowLayout(box, spacing=2, margin=0)
            chans = list(dict.fromkeys(model.CHANNELS + list(p["channels"])))
            for ch in chans:
                cb = QtWidgets.QCheckBox(ch)
                cb.setChecked(ch in p["channels"])
                cb.toggled.connect(lambda on, ch=ch: self._toggle_ch(ch, on))
                fl.addWidget(cb)
            form.addRow("Csatornák:", box)
        if t == "menu":
            a = p.get("action")
            self.menu_lbl = QtWidgets.QLabel(a["path"] if a else "⚠ nincs kiválasztva")
            self.menu_lbl.setWordWrap(True)
            form.addRow("Parancs:", self.menu_lbl)
            row = QtWidgets.QHBoxLayout()
            b1 = QtWidgets.QPushButton("Elkapás a menüből")
            b1.setToolTip("Kattints utána a Painter menüjében a parancsra")
            b1.clicked.connect(self._start_capture)
            b2 = QtWidgets.QPushButton("Listából…")
            b2.clicked.connect(self._pick_list)
            row.addWidget(b1)
            row.addWidget(b2)
            form.addRow(row)
            self.cap_btn = b1
        if t == "save":
            form.addRow(self._hint("Nincs beállítás: a Painter Save parancsa."))
        if model.CATALOG[t][1] == model.UI:
            form.addRow(self._hint("UI Step: csak a Workflow végén állhat."))

    def _hint(self, text):
        lb = QtWidgets.QLabel(text)
        lb.setWordWrap(True)
        lb.setStyleSheet("color: #999; font-size: 11px;")
        return lb

    def _set(self, k, v):
        self.step["params"][k] = v
        self.changed.emit()

    def _toggle_ch(self, ch, on):
        chs = self.step["params"]["channels"]
        if on and ch not in chs:
            chs.append(ch)
        if not on and ch in chs:
            chs.remove(ch)
        self.changed.emit()

    def _set_action(self, info):
        self.step["params"]["action"] = info
        self.menu_lbl.setText(info["path"])
        self.host.log("menüparancs beállítva: %s" % info["path"])
        self.changed.emit()

    def _start_capture(self):
        self.cap_btn.setText("Kattints a Painter menüjében…")
        self._capture = self.host.capture()
        self._capture.captured.connect(self._captured)
        self._capture.start()

    def _captured(self, info):
        if not self.isVisible() and keep(self.parent()) is None:
            return
        try:
            self.cap_btn.setText("Elkapás a menüből")
        except RuntimeError:
            return
        self._set_action(info)

    def _pick_list(self):
        d = MenuPicker(self.host, keep(self.window()))
        if d.exec() and d.result_info:
            self._set_action(d.result_info)

    def hideEvent(self, e):
        if self._capture is not None:
            self._capture.stop()
        super().hideEvent(e)
