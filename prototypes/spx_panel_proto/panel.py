# PROTOTYPE – eldobható kód, nem kerül a main ágra.
# Kérdés (Prototype: Panel kinézet és Layout szerkesztő mód, #8):
#   Hogyan nézzen ki és viselkedjen a Panel, és hogyan működjön a Layout szerkesztése?
# Három, szerkezetében eltérő változat, az alsó sávval (◀ ▶) vagy a ←/→ billentyűkkel váltható:
#   A – Rács + szerkesztő mód (ceruza): tördelődő ikonrács, külön szerkesztő mód × jelekkel és „+” csempével.
#   B – Eszköztár + listaszerkesztő: egysoros sáv, ami magától vízszintes vagy függőleges lesz, a ki nem férő
#       gombok a » menübe kerülnek, elválasztókkal. A szerkesztés egy külön lista, Mentés/Mégse gombbal.
#   C – Csoportok, mindig szerkeszthető: elnevezett, összecsukható csoportok. Nincs szerkesztő mód: a gombok
#       bármikor húzhatók, törléshez a lent megjelenő kukába kell húzni, és utána vissza lehet vonni.
# A Painter nélküli futtatáshoz nem használ Painter API-t. A Painter-specifikus részeket a Host adja.

import json
import itertools
from urllib.parse import unquote

from PySide6 import QtCore, QtGui, QtWidgets

Qt = QtCore.Qt
TILE_MIME = "application/x-spx-tile"
TILE = 40          # csempe mérete px
ICON = 30          # ikon mérete px
_ids = itertools.count(1)

KIND_HU = {"brush": "Brush button", "workflow": "Workflow button", "menu": "Menu button", "sep": "Elválasztó"}


# ---------------------------------------------------------------- ikonok, adat

def _hue(name):
    return (sum(ord(c) for c in name) * 37) % 360


def glyph(kind, name, size=64):
    """Saját rajzolt ikon. Brush: gömb, mint egy thumbnail. Workflow: egymásra tett rétegek."""
    pm = QtGui.QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    h = _hue(name)
    if kind == "brush":
        g = QtGui.QRadialGradient(size * 0.4, size * 0.38, size * 0.5)
        g.setColorAt(0, QtGui.QColor.fromHsv(h, 60, 255))
        g.setColorAt(0.6, QtGui.QColor.fromHsv(h, 200, 200))
        g.setColorAt(1, QtGui.QColor.fromHsv(h, 220, 70))
        p.setBrush(g)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QtCore.QRectF(size * 0.08, size * 0.08, size * 0.84, size * 0.84))
    else:
        c = QtGui.QColor.fromHsv(h, 150, 230)
        for i in range(3):
            r = QtCore.QRectF(size * 0.12, size * (0.18 + i * 0.22), size * 0.62, size * 0.18)
            p.setBrush(c.darker(100 + i * 30))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r, 3, 3)
        p.setBrush(QtGui.QColor("#f0f0f0"))
        tri = QtGui.QPolygonF([QtCore.QPointF(size * 0.8, size * 0.55), QtCore.QPointF(size * 0.98, size * 0.7),
                               QtCore.QPointF(size * 0.8, size * 0.85)])
        p.drawPolygon(tri)
    p.setPen(QtGui.QColor(255, 255, 255, 220))
    f = p.font()
    f.setPixelSize(int(size * 0.32))
    f.setBold(True)
    p.setFont(f)
    p.drawText(QtCore.QRectF(0, 0, size * (1 if kind == "brush" else 0.86), size), Qt.AlignmentFlag.AlignCenter,
               name[:1].upper())
    p.end()
    return QtGui.QIcon(pm)


def make_item(kind, name, icon=None, ref=""):
    it = {"id": next(_ids), "kind": kind, "name": name, "ref": ref}
    it["_icon"] = icon if icon is not None else (glyph(kind, name) if kind in ("brush", "workflow") else QtGui.QIcon())
    return it


def clean(obj):
    """JSON-nézet: az _-al kezdődő kulcsok (pl. QIcon) nélkül."""
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    return obj


def sample_items(host):
    def menu(prefix):
        n, icon = host.pick(prefix)
        return make_item("menu", n, icon, ref=n)
    b = lambda n: make_item("brush", n, ref=f"resource://starter_assets/{n}")
    w = lambda n: make_item("workflow", n, ref="steps: (a Workflow szerkesztő külön prototípus)")
    return [b("Basic Hard"), b("Dirt Spread"), b("Chalk Bold"), b("Scratches Fine"),
            w("Fill + fekete maszk"), w("Paint + fehér maszk"), w("Mappa + Levels"), w("Smart mask: Edges"),
            menu("Save"), menu("Export textures")]


def brush_urls(mime):
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


# ---------------------------------------------------------------- közös építőelemek

class FlowLayout(QtWidgets.QLayout):
    """Sorokba tördelő layout (a Qt példa átirata)."""

    def __init__(self, parent=None, spacing=4):
        super().__init__(parent)
        self._items = []
        self.setSpacing(spacing)
        self.setContentsMargins(4, 4, 4, 4)

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


class Tile(QtWidgets.QToolButton):
    """Egy Button a Panelen: csak ikon, a név tooltipben."""
    dragStarted = QtCore.Signal()
    dragFinished = QtCore.Signal()
    deleteRequested = QtCore.Signal(int)

    def __init__(self, item, draggable=False, deletable=False, edit_look=False, size=TILE):
        super().__init__()
        self.item = item
        self.draggable = draggable
        self.setIcon(item["_icon"])
        self.setIconSize(QtCore.QSize(size - 10, size - 10))
        self.setFixedSize(size, size)
        self.setAutoRaise(True)
        self.setToolTip(f"<b>{item['name']}</b><br><i>{KIND_HU[item['kind']]}</i>")
        if item["_icon"].isNull():
            self.setText(item["name"][:2])
        if edit_look:
            self.setStyleSheet("QToolButton { border: 1px dashed #8a8a8a; border-radius: 4px; }")
        self._press = None
        if deletable:
            x = QtWidgets.QToolButton(self)
            x.setText("×")
            x.setFixedSize(15, 15)
            x.move(size - 15, 0)
            x.setStyleSheet("QToolButton { background: #c0392b; color: white; border-radius: 7px;"
                            " font-weight: bold; padding: 0; }")
            x.setToolTip("Törlés")
            x.clicked.connect(lambda: self.deleteRequested.emit(item["id"]))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if (self.draggable and self._press is not None
                and (e.position().toPoint() - self._press).manhattanLength() >= QtWidgets.QApplication.startDragDistance()):
            self._press = None
            self.setDown(False)
            md = QtCore.QMimeData()
            md.setData(TILE_MIME, str(self.item["id"]).encode())
            drag = QtGui.QDrag(self)
            drag.setMimeData(md)
            drag.setPixmap(self.icon().pixmap(ICON, ICON))
            drag.setHotSpot(QtCore.QPoint(ICON // 2, ICON // 2))
            self.dragStarted.emit()
            drag.exec(Qt.DropAction.MoveAction)
            self.dragFinished.emit()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._press = None
        super().mouseReleaseEvent(e)


class DropFlow(QtWidgets.QWidget):
    """Csempék tördelő rácsban. Fogadja a csempe-áthúzást (beszúrási jellel) és a brush-behúzást."""

    def __init__(self, on_tile_drop=None, on_brush_drop=None, empty_hint=""):
        super().__init__()
        self.on_tile_drop, self.on_brush_drop = on_tile_drop, on_brush_drop
        self.flow = FlowLayout(self)
        self.tiles = []
        self.setAcceptDrops(True)
        self._ind = QtWidgets.QFrame(self)
        self._ind.setStyleSheet("background: #3d9bff;")
        self._ind.hide()
        self._hint = None
        if empty_hint:
            self._hint = QtWidgets.QLabel(empty_hint)
            self._hint.setStyleSheet("color: #888; font-style: italic;")
            self.flow.addWidget(self._hint)

    def add_tile(self, t):
        if self._hint:
            self._hint.hide()
        self.tiles.append(t)
        self.flow.addWidget(t)

    def add_extra(self, w):
        if self._hint:
            self._hint.hide()
        self.flow.addWidget(w)

    def index_at(self, pos):
        for i, t in enumerate(self.tiles):
            g = t.geometry()
            if pos.y() < g.top() or (pos.y() <= g.bottom() and pos.x() < g.center().x()):
                return i
        return len(self.tiles)

    def _show_ind(self, i):
        if not self.tiles:
            self._ind.setGeometry(4, 4, 3, TILE)
        elif i < len(self.tiles):
            g = self.tiles[i].geometry()
            self._ind.setGeometry(g.left() - 3, g.top(), 3, g.height())
        else:
            g = self.tiles[-1].geometry()
            self._ind.setGeometry(g.right() + 1, g.top(), 3, g.height())
        self._ind.show()
        self._ind.raise_()

    def _accepts(self, md):
        return (md.hasFormat(TILE_MIME) and self.on_tile_drop) or (brush_urls(md) and self.on_brush_drop)

    def dragEnterEvent(self, e):
        if self._accepts(e.mimeData()):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if self._accepts(e.mimeData()):
            self._show_ind(self.index_at(e.position().toPoint()))
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self._ind.hide()

    def dropEvent(self, e):
        self._ind.hide()
        md, i = e.mimeData(), self.index_at(e.position().toPoint())
        e.acceptProposedAction()
        if md.hasFormat(TILE_MIME):
            tid = int(bytes(md.data(TILE_MIME)).decode())
            QtCore.QTimer.singleShot(0, lambda: self.on_tile_drop(tid, i))   # a forrás csempe még a drag.exec-ben van
        else:
            urls = brush_urls(md)
            QtCore.QTimer.singleShot(0, lambda: self.on_brush_drop(urls, i))


def scroll(w):
    sa = QtWidgets.QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sa.setWidget(w)
    return sa


class MenuPicker(QtWidgets.QDialog):
    """Menu button létrehozása: kereshető lista a Painter menüparancsaiból (QAction-ök, ikonnal)."""

    def __init__(self, parent, actions):
        super().__init__(parent)
        self.setWindowTitle("Menu button hozzáadása")
        self.resize(320, 420)
        lay = QtWidgets.QVBoxLayout(self)
        self.filter = QtWidgets.QLineEdit()
        self.filter.setPlaceholderText("Keresés a menüparancsok között…")
        self.lst = QtWidgets.QListWidget()
        for name, icon in actions:
            QtWidgets.QListWidgetItem(icon, name, self.lst)
        self.filter.textChanged.connect(self._f)
        self.lst.itemDoubleClicked.connect(self.accept)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok
                                        | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        for w in (self.filter, self.lst, bb):
            lay.addWidget(w)

    def _f(self, t):
        for i in range(self.lst.count()):
            it = self.lst.item(i)
            it.setHidden(t.lower() not in it.text().lower())

    def chosen(self):
        it = self.lst.currentItem()
        return (it.text(), it.icon()) if it and not it.isHidden() else None


def add_menu(parent, host, on_item, with_sep=False):
    """A „+” menü tartalma: Workflow / Menu button / (elválasztó) / brush-tipp."""
    m = QtWidgets.QMenu(parent)

    def wf():
        name, ok = QtWidgets.QInputDialog.getText(parent, "Workflow button", "A Workflow neve:")
        if ok and name.strip():
            on_item(make_item("workflow", name.strip(), ref="steps: (a Workflow szerkesztő külön prototípus)"))

    def mn():
        d = MenuPicker(parent, host.menu_actions())
        if d.exec() and d.chosen():
            n, ic = d.chosen()
            on_item(make_item("menu", n, ic, ref=n))

    m.addAction("Új Workflow button…", wf)
    m.addAction("Új Menu button…", mn)
    if with_sep:
        m.addAction("Elválasztó", lambda: on_item(make_item("sep", "—")))
    a = m.addAction("Brush button: húzz be egy brusht az Assets ablakból")
    a.setEnabled(False)
    return m


def items_from_urls(host, urls):
    return [make_item("brush", *host.brush_info(u)) for u in urls]


class VariantBase(QtWidgets.QWidget):
    KEY = "?"
    TITLE = "?"
    changed = QtCore.Signal()

    def __init__(self, host):
        super().__init__()
        self.host = host

    def state(self):
        return {}

    def click(self, item):
        self.host.click(item)


# ---------------------------------------------------------------- A: rács + szerkesztő mód

class VariantA(VariantBase):
    KEY, TITLE = "A", "Rács + szerkesztő mód"

    def __init__(self, host):
        super().__init__(host)
        self.items = sample_items(host)
        self.edit = False
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        head = QtWidgets.QHBoxLayout()
        head.setContentsMargins(4, 2, 4, 0)
        self.hint = QtWidgets.QLabel("Szerkesztő mód: húzással rendezed, × töröl, + új Button. Esc vagy Kész: kilépés.")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #e0a030;")
        self.pencil = QtWidgets.QToolButton()
        self.pencil.setText("✎")
        self.pencil.setToolTip("Layout szerkesztése")
        self.pencil.setCheckable(True)
        self.pencil.setAutoRaise(True)
        self.pencil.toggled.connect(self.set_edit)
        head.addWidget(self.hint, 1)
        head.addStretch(0)
        head.addWidget(self.pencil, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(head)
        self.sa = scroll(QtWidgets.QWidget())
        lay.addWidget(self.sa, 1)
        QtGui.QShortcut(QtGui.QKeySequence(Qt.Key.Key_Escape), self, lambda: self.pencil.setChecked(False),
                        context=Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.set_edit(False)

    def set_edit(self, on):
        self.edit = on
        self.hint.setVisible(on)
        self.pencil.setText("Kész" if on else "✎")
        self.rebuild()

    def rebuild(self):
        c = DropFlow(self.move_tile if self.edit else None, self.drop_brush)
        for it in self.items:
            t = Tile(it, draggable=self.edit, deletable=self.edit, edit_look=self.edit)
            t.clicked.connect(lambda _=False, it=it: None if self.edit else self.click(it))
            t.deleteRequested.connect(self.delete)
            c.add_tile(t)
        if self.edit:
            plus = QtWidgets.QToolButton()
            plus.setText("+")
            plus.setFixedSize(TILE, TILE)
            plus.setStyleSheet("QToolButton { border: 1px dashed #3d9bff; border-radius: 4px; font-size: 18px; }")
            plus.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
            plus.setMenu(add_menu(plus, self.host, self.add))
            c.add_extra(plus)
        self.sa.setWidget(c)
        self.changed.emit()

    def find(self, tid):
        return next(i for i, it in enumerate(self.items) if it["id"] == tid)

    def move_tile(self, tid, to):
        fr = self.find(tid)
        it = self.items.pop(fr)
        self.items.insert(to - 1 if fr < to else to, it)
        self.rebuild()

    def delete(self, tid):
        self.items.pop(self.find(tid))
        self.rebuild()

    def add(self, it):
        self.items.append(it)
        self.rebuild()

    def drop_brush(self, urls, i):
        self.items[i:i] = items_from_urls(self.host, urls)
        self.rebuild()

    def state(self):
        return {"edit_mode": self.edit, "buttons": clean(self.items)}


# ---------------------------------------------------------------- B: eszköztár + listaszerkesztő

class Strip(QtWidgets.QWidget):
    """Egysoros sáv: vízszintes, ha a Panel széles, függőleges, ha magas. Ami nem fér ki, a » menübe kerül."""

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setAcceptDrops(True)
        self.setMinimumSize(TILE + 4, TILE + 4)
        self.widgets = []
        self.more = QtWidgets.QToolButton(self)
        self.more.setText("»")
        self.more.setFixedSize(22, TILE)
        self.more.setAutoRaise(True)
        self.more.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more.setToolTip("További Buttonok")
        self.gear = QtWidgets.QToolButton(self)
        self.gear.setText("⚙")
        self.gear.setFixedSize(22, TILE)
        self.gear.setAutoRaise(True)
        self.gear.setToolTip("Layout szerkesztése (jobb klikk a sávon is)")
        self.gear.clicked.connect(owner.open_editor)

    def set_items(self, items):
        for w in self.widgets:
            w.hide()
            w.deleteLater()
        self.widgets = []
        for it in items:
            if it["kind"] == "sep":
                w = QtWidgets.QFrame(self)
                w.setStyleSheet("background: #666;")
            else:
                w = Tile(it)
                w.setParent(self)
                w.clicked.connect(lambda _=False, it=it: self.owner.click(it))
            w.item = it
            w.show()
            self.widgets.append(w)
        self.relayout()

    def resizeEvent(self, e):
        self.relayout()

    def relayout(self):
        horiz = self.width() >= self.height()
        avail = (self.width() if horiz else self.height()) - 4
        reserve = 2 * 24
        pos, shown, overflow = 2, [], []
        for w in self.widgets:
            ln = 9 if w.item["kind"] == "sep" else TILE + 2
            if not overflow and pos + ln <= avail - reserve:
                shown.append((w, pos))
                pos += ln
            else:
                overflow.append(w)
        for w, p in shown:
            sep = w.item["kind"] == "sep"
            if horiz:
                w.setGeometry(p + (4 if sep else 0), 2 + (6 if sep else 0), 1 if sep else TILE, TILE - 12 if sep else TILE)
            else:
                w.setGeometry(2 + (6 if sep else 0), p + (4 if sep else 0), TILE - 12 if sep else TILE, 1 if sep else TILE)
            w.show()
        for w in overflow:
            w.hide()
        m = QtWidgets.QMenu(self.more)
        for w in overflow:
            if w.item["kind"] == "sep":
                m.addSeparator()
            else:
                m.addAction(w.item["_icon"], w.item["name"], lambda it=w.item: self.owner.click(it))
        self.more.setMenu(m)
        self.more.setVisible(bool([w for w in overflow if w.item["kind"] != "sep"]))
        for b in (self.more, self.gear):
            b.setFixedSize(*((22, TILE) if horiz else (TILE, 22)))
        if horiz:
            self.more.move(pos, 2)
            self.gear.move(pos + (24 if self.more.isVisible() else 0), 2)
        else:
            self.more.move(2, pos)
            self.gear.move(2, pos + (24 if self.more.isVisible() else 0))

    def contextMenuEvent(self, e):
        m = QtWidgets.QMenu(self)
        m.addAction("Layout szerkesztése…", self.owner.open_editor)
        m.exec(e.globalPos())

    def dragEnterEvent(self, e):
        e.acceptProposedAction() if brush_urls(e.mimeData()) else e.ignore()

    def dropEvent(self, e):
        urls = brush_urls(e.mimeData())
        e.acceptProposedAction()
        QtCore.QTimer.singleShot(0, lambda: self.owner.append(items_from_urls(self.owner.host, urls)))


class EditList(QtWidgets.QListWidget):
    """A szerkesztő lista: belső átrendezés húzással, és fogadja az Assets-ből behúzott brusht."""

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setIconSize(QtCore.QSize(24, 24))
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked)

    def dragEnterEvent(self, e):
        if brush_urls(e.mimeData()):
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if brush_urls(e.mimeData()):
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        urls = brush_urls(e.mimeData())
        if urls:
            row = self.indexAt(e.position().toPoint()).row()
            e.acceptProposedAction()
            for it in items_from_urls(self.owner.host, urls):
                self.owner.list_insert(it, row if row >= 0 else self.count())
        else:
            super().dropEvent(e)


class VariantB(VariantBase):
    KEY, TITLE = "B", "Eszköztár + listaszerkesztő"

    def __init__(self, host):
        super().__init__(host)
        it = sample_items(host)
        sep = lambda: make_item("sep", "—")
        self.items = it[:4] + [sep()] + it[4:8] + [sep()] + it[8:]
        self.stack = QtWidgets.QStackedLayout(self)
        self.strip = Strip(self)
        self.stack.addWidget(self.strip)
        self.stack.addWidget(self._editor())
        self.strip.set_items(self.items)

    def _editor(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        t = QtWidgets.QLabel("<b>Layout szerkesztése</b><br><small>Húzással rendezed, dupla klikk: átnevezés. "
                             "Brush: húzd be az Assets ablakból ide.</small>")
        t.setWordWrap(True)
        self.lst = EditList(self)
        tb = QtWidgets.QHBoxLayout()
        plus = QtWidgets.QToolButton()
        plus.setText("+ Új")
        plus.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        plus.setMenu(add_menu(plus, self.host, lambda it: self.list_insert(it, self.lst.count()), with_sep=True))
        dele = QtWidgets.QToolButton()
        dele.setText("Törlés")
        dele.clicked.connect(lambda: [self.lst.takeItem(self.lst.row(i)) for i in self.lst.selectedItems()])
        tb.addWidget(plus)
        tb.addWidget(dele)
        tb.addStretch(1)
        bb = QtWidgets.QHBoxLayout()
        cancel = QtWidgets.QPushButton("Mégse")
        save = QtWidgets.QPushButton("Mentés")
        save.setDefault(True)
        cancel.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        save.clicked.connect(self.save)
        bb.addStretch(1)
        bb.addWidget(cancel)
        bb.addWidget(save)
        for x in (t,):
            lay.addWidget(x)
        lay.addLayout(tb)
        lay.addWidget(self.lst, 1)
        lay.addLayout(bb)
        return w

    def list_insert(self, it, row):
        li = QtWidgets.QListWidgetItem(it["_icon"], it["name"] if it["kind"] != "sep" else "──── elválasztó ────")
        li.setData(Qt.ItemDataRole.UserRole, it)
        flags = li.flags() | Qt.ItemFlag.ItemIsDragEnabled
        if it["kind"] != "sep":
            flags |= Qt.ItemFlag.ItemIsEditable
        li.setFlags(flags & ~Qt.ItemFlag.ItemIsDropEnabled)
        li.setToolTip(KIND_HU[it["kind"]])
        self.lst.insertItem(row, li)

    def open_editor(self):
        self.lst.clear()
        for it in self.items:
            self.list_insert(dict(it), self.lst.count())
        self.stack.setCurrentIndex(1)
        self.changed.emit()

    def save(self):
        new = []
        for i in range(self.lst.count()):
            li = self.lst.item(i)
            it = dict(li.data(Qt.ItemDataRole.UserRole))
            if it["kind"] != "sep":
                it["name"] = li.text()
            new.append(it)
        self.items = new
        self.strip.set_items(self.items)
        self.stack.setCurrentIndex(0)
        self.changed.emit()

    def append(self, its):
        self.items += its
        self.strip.set_items(self.items)
        self.changed.emit()

    def state(self):
        return {"editor_open": self.stack.currentIndex() == 1, "buttons": clean(self.items)}


# ---------------------------------------------------------------- C: csoportok, mindig szerkeszthető

class VariantC(VariantBase):
    KEY, TITLE = "C", "Csoportok, mindig szerkeszthető"

    def __init__(self, host):
        super().__init__(host)
        it = sample_items(host)
        self.groups = [{"name": "Brushok", "collapsed": False, "items": it[:4]},
                       {"name": "Rétegek", "collapsed": False, "items": it[4:8]},
                       {"name": "Fájl", "collapsed": False, "items": it[8:]}]
        self.undo = None
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.sa = scroll(QtWidgets.QWidget())
        lay.addWidget(self.sa, 1)
        self.trash = DropFlow(self.trash_drop, None)
        self.trash.flow.addWidget(QtWidgets.QLabel("🗑  Húzd ide a törléshez"))
        self.trash.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.trash.setStyleSheet("background: #7a2626; color: white; font-weight: bold;")
        self.trash.setFixedHeight(36)
        self.trash.hide()
        lay.addWidget(self.trash)
        self.undobar = QtWidgets.QFrame()
        ub = QtWidgets.QHBoxLayout(self.undobar)
        ub.setContentsMargins(6, 2, 6, 2)
        self.undolabel = QtWidgets.QLabel()
        ubtn = QtWidgets.QPushButton("Visszavonás")
        ubtn.clicked.connect(self.do_undo)
        ub.addWidget(self.undolabel, 1)
        ub.addWidget(ubtn)
        self.undobar.setStyleSheet("background: #333; color: #eee;")
        self.undobar.hide()
        lay.addWidget(self.undobar)
        self.undotimer = QtCore.QTimer(self, singleShot=True, interval=6000, timeout=self.undobar.hide)
        self.rebuild()

    def rebuild(self):
        body = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(body)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(0)
        for gi, g in enumerate(self.groups):
            v.addWidget(self._header(gi, g))
            if not g["collapsed"]:
                c = DropFlow(lambda tid, i, gi=gi: self.move_tile(tid, gi, i),
                             lambda urls, i, gi=gi: self.drop_brush(urls, gi, i),
                             empty_hint="(üres – húzz ide Buttont vagy brusht)")
                for it in g["items"]:
                    t = Tile(it, draggable=True)
                    t.clicked.connect(lambda _=False, it=it: self.click(it))
                    t.dragStarted.connect(self.trash.show)
                    t.dragFinished.connect(self.trash.hide)
                    t.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                    t.customContextMenuRequested.connect(lambda p, t=t, gi=gi: self.tile_menu(t, gi, p))
                    c.add_tile(t)
                v.addWidget(c)
        add = QtWidgets.QToolButton()
        add.setText("+ Új csoport")
        add.setAutoRaise(True)
        add.clicked.connect(self.new_group)
        v.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)
        v.addStretch(1)
        self.sa.setWidget(body)
        self.changed.emit()

    def _header(self, gi, g):
        h = QtWidgets.QWidget()
        hl = QtWidgets.QHBoxLayout(h)
        hl.setContentsMargins(2, 4, 2, 0)
        arrow = QtWidgets.QToolButton()
        arrow.setAutoRaise(True)
        arrow.setText(("▶ " if g["collapsed"] else "▼ ") + g["name"] + (f"  ({len(g['items'])})" if g["collapsed"] else ""))
        arrow.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        arrow.setStyleSheet("QToolButton { font-weight: bold; color: #bbb; }")
        arrow.clicked.connect(lambda: (g.__setitem__("collapsed", not g["collapsed"]), self.rebuild()))
        plus = QtWidgets.QToolButton()
        plus.setText("+")
        plus.setAutoRaise(True)
        plus.setToolTip(f"Új Button a(z) „{g['name']}” csoportba")
        plus.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        plus.setMenu(add_menu(plus, self.host, lambda it, g=g: (g["items"].append(it), self.rebuild())))
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setStyleSheet("color: #555;")
        hl.addWidget(arrow)
        hl.addWidget(line, 1)
        hl.addWidget(plus)
        h.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        h.customContextMenuRequested.connect(lambda p: self.group_menu(h, gi, p))
        return h

    def locate(self, tid):
        for gi, g in enumerate(self.groups):
            for ii, it in enumerate(g["items"]):
                if it["id"] == tid:
                    return gi, ii
        return None

    def move_tile(self, tid, to_g, to_i):
        loc = self.locate(tid)
        if not loc:
            return
        fg, fi = loc
        it = self.groups[fg]["items"].pop(fi)
        if fg == to_g and fi < to_i:
            to_i -= 1
        self.groups[to_g]["items"].insert(to_i, it)
        self.rebuild()

    def drop_brush(self, urls, gi, i):
        self.groups[gi]["items"][i:i] = items_from_urls(self.host, urls)
        self.rebuild()

    def remove(self, tid):
        gi, ii = self.locate(tid)
        it = self.groups[gi]["items"].pop(ii)
        self.undo = (gi, ii, it)
        self.undolabel.setText(f"„{it['name']}” törölve")
        self.undobar.show()
        self.undotimer.start()
        self.rebuild()

    def trash_drop(self, tid, _i):
        self.trash.hide()
        self.remove(tid)

    def do_undo(self):
        if self.undo:
            gi, ii, it = self.undo
            gi = min(gi, len(self.groups) - 1)
            self.groups[gi]["items"].insert(ii, it)
            self.undo = None
        self.undobar.hide()
        self.rebuild()

    def tile_menu(self, t, gi, p):
        it = t.item
        m = QtWidgets.QMenu(t)
        def ren():
            n, ok = QtWidgets.QInputDialog.getText(self, "Átnevezés", "Név (hoverre ez jelenik meg):", text=it["name"])
            if ok and n.strip():
                it["name"] = n.strip()
                self.rebuild()
        m.addAction("Átnevezés…", ren)
        mv = m.addMenu("Áthelyezés csoportba")
        for gj, g in enumerate(self.groups):
            a = mv.addAction(g["name"], lambda gj=gj: self.move_tile(it["id"], gj, len(self.groups[gj]["items"])))
            a.setEnabled(gj != gi)
        m.addSeparator()
        m.addAction("Törlés", lambda: self.remove(it["id"]))
        m.exec(t.mapToGlobal(p))

    def group_menu(self, h, gi, p):
        g = self.groups[gi]
        m = QtWidgets.QMenu(h)
        def ren():
            n, ok = QtWidgets.QInputDialog.getText(self, "Csoport átnevezése", "Név:", text=g["name"])
            if ok and n.strip():
                g["name"] = n.strip()
                self.rebuild()
        def dele():
            if g["items"]:
                QtWidgets.QMessageBox.information(self, "Csoport törlése", "Csak üres csoport törölhető.")
                return
            self.groups.pop(gi)
            self.rebuild()
        def up(d):
            j = gi + d
            if 0 <= j < len(self.groups):
                self.groups[gi], self.groups[j] = self.groups[j], self.groups[gi]
                self.rebuild()
        m.addAction("Átnevezés…", ren)
        m.addAction("Feljebb", lambda: up(-1)).setEnabled(gi > 0)
        m.addAction("Lejjebb", lambda: up(1)).setEnabled(gi < len(self.groups) - 1)
        m.addAction("Új csoport", self.new_group)
        m.addSeparator()
        m.addAction("Csoport törlése", dele)
        m.exec(h.mapToGlobal(p))

    def new_group(self):
        n, ok = QtWidgets.QInputDialog.getText(self, "Új csoport", "A csoport neve:")
        if ok and n.strip():
            self.groups.append({"name": n.strip(), "collapsed": False, "items": []})
            self.rebuild()

    def state(self):
        return {"groups": clean(self.groups)}


# ---------------------------------------------------------------- a Panel: változat-váltó + állapot

VARIANTS = [VariantA, VariantB, VariantC]


class PanelRoot(QtWidgets.QWidget):
    def __init__(self, host, start="A"):
        super().__init__()
        self.host = host
        host.status = self.set_status
        self.setObjectName("spx_panel_proto")
        self.setWindowTitle("SPX Panel (prototípus)")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.stack = QtWidgets.QStackedWidget()
        self.variants = [V(host) for V in VARIANTS]
        for v in self.variants:
            self.stack.addWidget(v)
            v.changed.connect(self.show_state)
        lay.addWidget(self.stack, 1)

        # --- prototípus-keret: ez NEM a terv része ---
        self.statusl = QtWidgets.QLabel("Vidd az egeret egy Buttonra, vagy kattints rá.")
        self.statusl.setStyleSheet("color: #9ad; padding: 2px 6px;")
        self.statusl.setWordWrap(True)
        self.state = QtWidgets.QPlainTextEdit()
        self.state.setReadOnly(True)
        self.state.setMaximumHeight(160)
        self.state.setStyleSheet("font-family: Menlo, Consolas, monospace; font-size: 10px;")
        self.state.hide()
        bar = QtWidgets.QFrame()
        bar.setStyleSheet("QFrame { background: #ffd23f; } QToolButton, QLabel { color: #111; font-weight: bold; }")
        bl = QtWidgets.QHBoxLayout(bar)
        bl.setContentsMargins(4, 1, 4, 1)
        prev, nxt = QtWidgets.QToolButton(), QtWidgets.QToolButton()
        prev.setText("◀")
        nxt.setText("▶")
        prev.clicked.connect(lambda: self.cycle(-1))
        nxt.clicked.connect(lambda: self.cycle(1))
        self.label = QtWidgets.QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        st = QtWidgets.QToolButton()
        st.setText("{ }")
        st.setToolTip("Layout állapot (JSON) mutatása/elrejtése")
        st.setCheckable(True)
        st.toggled.connect(lambda on: (self.state.setVisible(on), self.show_state()))
        bl.addWidget(prev)
        bl.addWidget(self.label, 1)
        bl.addWidget(nxt)
        bl.addWidget(st)
        lay.addWidget(self.statusl)
        lay.addWidget(self.state)
        lay.addWidget(bar)
        for key, d in ((Qt.Key.Key_Left, -1), (Qt.Key.Key_Right, 1)):
            QtGui.QShortcut(QtGui.QKeySequence(key), self, lambda d=d: self.cycle(d),
                            context=Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.go(next((i for i, v in enumerate(self.variants) if v.KEY == start.upper()), 0))

    def go(self, i):
        self.stack.setCurrentIndex(i)
        v = self.variants[i]
        self.label.setText(f"{v.KEY} – {v.TITLE}")
        self.host.log(f"változat: {v.KEY}")
        self.show_state()

    def cycle(self, d):
        self.go((self.stack.currentIndex() + d) % len(self.variants))

    def set_status(self, msg):
        self.statusl.setText(msg)

    def show_state(self):
        if self.state.isVisible():
            v = self.variants[self.stack.currentIndex()]
            self.state.setPlainText(json.dumps({"variant": v.KEY, **v.state()}, ensure_ascii=False, indent=1))
        self.host.log_size(self)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.host.log_size(self)
