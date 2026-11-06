# PROTOTYPE – eldobható kód, nem kerül a main ágra.
# Kérdés (Prototype: Workflow szerkesztő, #9): hogyan hoz létre és szerkeszt a felhasználó egy Workflow-t?
# Három, szerkezetében eltérő változat (a Panel alján lévő sárga sávval váltható):
#   A – Panelen belül: a Panel rögzítő nézetre vált, a lista ott nő; Stop után ugyanott szerkeszthető
#       (lista + alatta a kijelölt Step beállításai). Ikon: az első Step ikonja.
#   B – Lebegő REC-sáv + külön ablak: rögzítés közben egy kis, mindig felül lévő sáv; Stop után külön
#       szerkesztőablak két táblázattal („Layer-rész” és „A végén”). Ikon: 2×2 az első négy Step-ből.
#   C – Idővonal-csempék: a Panel tetején Step-csempék sora (Fill → Fekete maszk → … ┃ Brush); csempére
#       kattintva lebegő beállító. Ikon: a fő Step ikonja + Step-szám.
# Közös: a Session (állapot), a rögzítő (recorder.py) és a ParamForm (widgets.py).

from PySide6 import QtCore, QtGui, QtWidgets

from . import model
from .recorder import keep
from .widgets import (FlowLayout, ParamForm, STEP_MIME, own, resource_urls, step_from_drop, step_menu)

Qt = QtCore.Qt
REC_RED = "#c0392b"


class Session(QtCore.QObject):
    """Egy Workflow létrehozása/szerkesztése: Step-lista, név, opcionális rögzítés."""
    changed = QtCore.Signal()          # a lista vagy a név változott
    recChanged = QtCore.Signal()       # rögzítés közbeni frissítés
    recStarted = QtCore.Signal()
    recFinished = QtCore.Signal(str)
    done = QtCore.Signal(object)       # mentett Workflow dict vagy None (Mégse)

    def __init__(self, host, workflow=None):
        super().__init__()
        self.host = host
        self.workflow = workflow
        self.steps = model.clone_steps(workflow["steps"]) if workflow else []
        self.name = workflow["name"] if workflow else ""
        self.name_touched = workflow is not None
        self.rec = None
        self.notices = []
        self.strokes = 0
        self.closed = False

    # ---- rögzítés
    def recording(self):
        return self.rec is not None and self.rec.running

    def start_recording(self):
        self.rec = self.host.make_recorder()
        self.rec.changed.connect(self.recChanged)
        self.rec.finished.connect(self._rec_done)
        self.rec.start()
        self.host.log("UI: rögzítés indítva (%d meglévő Step)" % len(self.steps))
        self.recStarted.emit()

    def stop_recording(self):
        if self.recording():
            self.rec.stop("Stop gomb")

    def live_steps(self):
        """Rögzítés közben: a meglévő + a most rögzített Step-ek."""
        if not self.recording():
            return self.steps
        out = list(self.steps)
        for s in self.rec.steps():
            model.insert_step(out, s)
        return out

    def moved_ids(self):
        return self.rec.moved_ids if self.rec is not None else set()

    def _rec_done(self, reason):
        rec = self.rec
        new = rec.steps()
        for s in new:
            if s["id"] in rec.moved_ids:
                s["moved"] = True
        moved_existing = any(model.zone(s) == model.UI for s in self.steps) and any(
            model.zone(s) == model.LAYER for s in new)
        for s in model.clone_steps(new):
            model.insert_step(self.steps, s)
        self.notices += rec.notices
        self.strokes += rec.strokes
        if moved_existing:
            self.notices.append("az új layer Step-ek a meglévő UI Step-ek elé kerültek")
        self.host.log("UI: rögzítés vége (%s), lista: %s" % (reason, [model.label(s) for s in self.steps]))
        self.recFinished.emit(reason)
        self._changed()

    # ---- szerkesztés
    def display_name(self):
        return self.name if self.name_touched and self.name else model.auto_name(self.steps)

    def set_name(self, n):
        self.name, self.name_touched = n, True
        self.changed.emit()

    def add(self, step):
        model.insert_step(self.steps, step)
        self.host.log("UI: Step hozzáadva: %s" % model.label(step))
        self._changed()
        return step

    def delete(self, step):
        if step in self.steps:
            self.steps.remove(step)
            self.host.log("UI: Step törölve: %s" % model.label(step))
            self._changed()

    def move(self, step, delta):
        i = self.steps.index(step)
        j = i + delta
        if not model.can_move(self.steps, i, j):
            return False
        self.steps[i], self.steps[j] = self.steps[j], self.steps[i]
        self.host.log("UI: Step mozgatva: %s (%+d)" % (model.label(step), delta))
        self._changed()
        return True

    def reorder(self, ids):
        """Húzás után: új sorrend id-k szerint; ha sérti a szabályt, visszarendezzük. Vissza: rendben volt-e."""
        by = {s["id"]: s for s in self.steps}
        new = [by[i] for i in ids if i in by]
        fixed, moved = model.normalize(new)
        self.steps[:] = fixed
        self.host.log("UI: átrendezés%s" % (" – szabálysértés, visszarendezve" if moved else ""))
        self._changed()
        return not moved

    def problems(self):
        out = []
        if not self.steps:
            out.append("Nincs egy Step sem.")
        for i, s in enumerate(self.steps, 1):
            m = model.missing(s)
            if m:
                out.append("%d. %s: %s" % (i, model.CATALOG[s["type"]][0], m))
        return out

    def changed_param(self):
        self._changed()

    def _changed(self):
        self.changed.emit()

    def save(self):
        if self.recording():
            self.stop_recording()
        wf = {"id": self.workflow["id"] if self.workflow else None, "name": self.display_name(),
              "steps": [{k: v for k, v in s.items() if k != "moved"} for s in self.steps]}
        self.host.log("UI: MENTÉS %r, %d Step" % (wf["name"], len(wf["steps"])))
        self.closed = True
        self.done.emit(wf)

    def cancel(self):
        if self.recording():
            self.rec.stop("Mégse")
        self.host.log("UI: Mégse")
        self.closed = True
        self.done.emit(None)


def confirm_save(parent, session):
    probs = session.problems()
    if not probs:
        return True
    QtWidgets.QMessageBox.warning(parent, "Még nem menthető", "Pótold ezeket:\n\n" + "\n".join(probs))
    session.host.log("UI: mentés elutasítva: %s" % probs)
    return False


def notice_text(session, rec_live=False):
    notes = list(session.notices)
    strokes = session.strokes
    if rec_live and session.rec is not None:
        notes += session.rec.notices
        strokes += session.rec.strokes
    parts = []
    if strokes:
        parts.append("festés ×%d (nem Step)" % strokes)
    for n in notes[-3:]:
        parts.append(n)
    if len(notes) > 3:
        parts.insert(1 if strokes else 0, "… +%d korábbi" % (len(notes) - 3))
    return ("Kihagyva: " + " · ".join(parts)) if parts else ""


def tag_text(session, s):
    tags = []
    if s.get("moved") or s["id"] in session.moved_ids():
        tags.append("↓ a végére került")
    m = model.missing(s)
    if m and "⚠" not in model.label(s):
        tags.append("⚠ " + m)
    return tags


# ====================================================================== A – Panelen belül

class StepList(QtWidgets.QListWidget):
    """Lista húzással; Assets-ből behúzott resource → új Step."""
    reordered = QtCore.Signal(list)
    dropped = QtCore.Signal(list)

    def __init__(self, host):
        super().__init__()
        self.host = host
        self.setIconSize(QtCore.QSize(24, 24))
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if resource_urls(e.mimeData()):
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if resource_urls(e.mimeData()):
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if resource_urls(e.mimeData()):
            self.dropped.emit(step_from_drop(self.host, e.mimeData()))
            e.acceptProposedAction()
            return
        super().dropEvent(e)
        ids = [self.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.count())]
        self.reordered.emit([i for i in ids if i is not None])


class VariantA(QtWidgets.QWidget):
    NAME = "Panelen belül"
    in_panel = True

    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.host = panel.host
        self.session = None
        self.form = None
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)

        self.rec_bar = QtWidgets.QFrame()
        self.rec_bar.setStyleSheet("QFrame { background: %s; border-radius: 4px; } QLabel { color: white; }" % REC_RED)
        rb = QtWidgets.QHBoxLayout(self.rec_bar)
        rb.setContentsMargins(6, 4, 6, 4)
        self.rec_lbl = QtWidgets.QLabel("● Rögzítés")
        f = self.rec_lbl.font()
        f.setBold(True)
        self.rec_lbl.setFont(f)
        rb.addWidget(self.rec_lbl, 1)
        self.stop_btn = QtWidgets.QPushButton("■ Stop")
        self.stop_btn.clicked.connect(lambda: self.session.stop_recording())
        rb.addWidget(self.stop_btn)
        lay.addWidget(self.rec_bar)

        self.name_row = QtWidgets.QWidget()
        nr = QtWidgets.QHBoxLayout(self.name_row)
        nr.setContentsMargins(0, 0, 0, 0)
        self.icon_lbl = QtWidgets.QLabel()
        self.icon_lbl.setFixedSize(40, 40)
        self.icon_lbl.setToolTip("A Workflow button ikonja (automatikus: az első Step ikonja)")
        nr.addWidget(self.icon_lbl)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Név")
        self.name_edit.textEdited.connect(lambda t: self.session.set_name(t))
        nr.addWidget(self.name_edit, 1)
        lay.addWidget(self.name_row)

        self.hint = QtWidgets.QLabel()
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #aaa; font-size: 11px;")
        lay.addWidget(self.hint)

        self.list = StepList(self.host)
        self.list.currentRowChanged.connect(self._select)
        self.list.reordered.connect(self._reordered)
        self.list.dropped.connect(self._dropped)
        lay.addWidget(self.list, 3)

        self.tools = QtWidgets.QWidget()
        tl = QtWidgets.QHBoxLayout(self.tools)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(2)
        self.add_btn = QtWidgets.QToolButton(text="+ Step")
        self.add_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.add_btn.setMenu(step_menu(self.add_btn, self._add))
        tl.addWidget(self.add_btn)
        for txt, tip, fn in (("↑", "Feljebb", lambda: self._move(-1)), ("↓", "Lejjebb", lambda: self._move(1)),
                             ("🗑", "Törlés", self._delete)):
            b = QtWidgets.QToolButton(text=txt, toolTip=tip)
            b.clicked.connect(fn)
            tl.addWidget(b)
        tl.addStretch(1)
        self.cont_btn = QtWidgets.QToolButton(text="● Folytatás")
        self.cont_btn.setToolTip("Rögzítés folytatása: az új Step-ek a lista végére kerülnek")
        self.cont_btn.clicked.connect(lambda: self.session.start_recording())
        tl.addWidget(self.cont_btn)
        lay.addWidget(self.tools)

        self.param_box = QtWidgets.QGroupBox("Beállítás")
        self.param_lay = QtWidgets.QVBoxLayout(self.param_box)
        self.param_lay.setContentsMargins(2, 2, 2, 2)
        lay.addWidget(self.param_box, 2)

        bot = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("Mentés")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn = QtWidgets.QPushButton("Mégse")
        self.cancel_btn.clicked.connect(lambda: self.session.cancel())
        bot.addStretch(1)
        bot.addWidget(self.save_btn)
        bot.addWidget(self.cancel_btn)
        lay.addLayout(bot)

    # ---- életciklus
    def begin(self, session, record):
        self.session = session
        session.changed.connect(self.refresh)
        session.recChanged.connect(self.refresh)
        session.recStarted.connect(self.refresh)
        session.recFinished.connect(lambda r: self.refresh())
        self.panel.show_page(self)
        if record:
            session.start_recording()
        self.refresh()

    def end(self):
        self.session = None
        self._set_form(None)

    # ---- megjelenítés
    def refresh(self):
        s = self.session
        if s is None:
            return
        rec = s.recording()
        self.rec_bar.setVisible(rec)
        self.name_row.setVisible(not rec)
        self.tools.setVisible(not rec)
        self.param_box.setVisible(not rec)
        self.save_btn.setVisible(not rec)
        self.cancel_btn.setText("Mégse")
        self.list.setDragEnabled(not rec)
        steps = s.live_steps()
        if self.name_edit.text() != s.display_name() and not self.name_edit.hasFocus():
            self.name_edit.setText(s.display_name())
        self.icon_lbl.setPixmap(model.workflow_icon(steps, model.ICON_STRATEGY["A"], 40).pixmap(40, 40))
        if rec:
            self.hint.setText("Kattintgass a Painterben. Ami a katalógusban van, ide kerül. Ctrl+Z itt is "
                              "visszavon. A Brush Step-et Stop után kell hozzáadni.\n" + notice_text(s, True))
        else:
            self.hint.setText(notice_text(s))
        cur = self._current()
        self.list.blockSignals(True)
        self.list.clear()
        ui_started = False
        for st in steps:
            if model.zone(st) == model.UI and not ui_started:
                ui_started = True
                self._divider()
            tags = tag_text(s, st)
            it = QtWidgets.QListWidgetItem(model.step_icon(st, 24), model.label(st) +
                                           ("   " + "  ".join(tags) if tags else ""))
            it.setData(Qt.ItemDataRole.UserRole, st["id"])
            if model.missing(st):
                it.setForeground(QtGui.QColor("#e0c060"))
            self.list.addItem(it)
        if not ui_started and not rec:
            self._divider()
        self.list.blockSignals(False)
        if rec:
            self.list.scrollToBottom()
            self._set_form(None)
        else:
            self._select_id(cur["id"] if cur else None)

    def _divider(self):
        it = QtWidgets.QListWidgetItem("──── A végén (Brush, menü, mentés) ────")
        it.setFlags(Qt.ItemFlag.NoItemFlags)
        it.setForeground(QtGui.QColor("#888"))
        self.list.addItem(it)

    def _current(self):
        it = self.list.currentItem()
        if it is None or self.session is None:
            return None
        sid = it.data(Qt.ItemDataRole.UserRole)
        return next((x for x in self.session.steps if x["id"] == sid), None)

    def _select_id(self, sid):
        for i in range(self.list.count()):
            if sid is not None and self.list.item(i).data(Qt.ItemDataRole.UserRole) == sid:
                self.list.setCurrentRow(i)
                return
        self._set_form(None)

    def _select(self, row):
        if self.session is None or self.session.recording():
            return
        self._set_form(self._current())

    def _set_form(self, step):
        if self.form is not None:
            self.form.setParent(None)
            self.form.deleteLater()
            self.form = None
        if step is None:
            self.param_box.setTitle("Beállítás – válassz egy Step-et")
            return
        self.param_box.setTitle("Beállítás")
        self.form = ParamForm(self.host, step)
        self.form.changed.connect(self._param_changed)
        self.param_lay.addWidget(self.form)

    def _param_changed(self):
        cur = self._current()
        it = self.list.currentItem()
        if cur and it:
            tags = tag_text(self.session, cur)
            it.setText(model.label(cur) + ("   " + "  ".join(tags) if tags else ""))
            it.setIcon(model.step_icon(cur, 24))
            it.setForeground(QtGui.QColor("#e0c060" if model.missing(cur) else "#d6d6d6"))
        self.icon_lbl.setPixmap(model.workflow_icon(self.session.steps, "first", 40).pixmap(40, 40))
        if self.name_edit.text() != self.session.display_name():
            self.name_edit.setText(self.session.display_name())

    # ---- műveletek
    def _add(self, step):
        self.session.add(step)
        self._select_id(step["id"])

    def _dropped(self, steps):
        for st in steps:
            self.session.add(st)
        if steps:
            self._select_id(steps[-1]["id"])

    def _move(self, d):
        cur = self._current()
        if cur and not self.session.move(cur, d):
            self.panel.status("Nem mozgatható tovább: a UI Step-ek csak a végén állhatnak.")
        if cur:
            self._select_id(cur["id"])

    def _delete(self):
        cur = self._current()
        if cur:
            self.session.delete(cur)

    def _reordered(self, ids):
        cur = self._current()
        if not self.session.reorder(ids):
            self.panel.status("A UI Step-ek (Brush, menü, mentés) csak a végén állhatnak – visszarendeztem.")
        if cur:
            self._select_id(cur["id"])

    def _save(self):
        if confirm_save(self, self.session):
            self.session.save()


# ====================================================================== B – lebegő REC-sáv + külön ablak

class RecPill(QtWidgets.QFrame):
    """Kis, mindig felül lévő sáv rögzítés közben. Az egérrel arrébb húzható."""

    def __init__(self, session, anchor):
        super().__init__(anchor, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.session = session
        self.setStyleSheet("QFrame#pill { background: #1e1e1e; border: 2px solid %s; border-radius: 16px; }"
                           "QLabel { color: #eee; } QPushButton { padding: 2px 8px; }" % REC_RED)
        self.setObjectName("pill")
        self.setProperty("spx", True)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(12, 4, 6, 4)
        self.dot = QtWidgets.QLabel("●")
        self.dot.setStyleSheet("color: %s; font-size: 16px;" % REC_RED)
        lay.addWidget(self.dot)
        self.lbl = QtWidgets.QLabel()
        lay.addWidget(self.lbl)
        self.last = QtWidgets.QLabel()
        self.last.setStyleSheet("color: #9ad;")
        lay.addWidget(self.last)
        stop = QtWidgets.QPushButton("■ Stop")
        stop.clicked.connect(session.stop_recording)
        lay.addWidget(stop)
        x = QtWidgets.QPushButton("✕")
        x.setToolTip("Mégse: a rögzítés elvész")
        x.clicked.connect(session.cancel)
        lay.addWidget(x)
        self._drag = None
        session.recChanged.connect(self.refresh)
        self.refresh()
        self.adjustSize()
        g = keep(anchor.window()).geometry()
        self.move(g.center().x() - self.width() // 2, g.top() + 60)

    def refresh(self):
        s = self.session
        if not s.recording():
            return
        steps = s.live_steps()
        self.lbl.setText("REC · %d Step" % len(steps))
        newest = [x for x in s.rec.steps()]
        self.last.setText(("· utolsó: " + model.short(newest[-1])) if newest else "· kattintgass a Painterben")
        self.setToolTip("\n".join("%d. %s" % (i, model.label(x)) for i, x in enumerate(steps, 1)) or "még üres")
        self.adjustSize()

    def mousePressEvent(self, e):
        self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None


class ZoneTable(QtWidgets.QWidget):
    selected = QtCore.Signal(object)

    def __init__(self, title, zone_key, owner):
        super().__init__()
        self.zone_key, self.owner = zone_key, owner
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        head = QtWidgets.QHBoxLayout()
        t = QtWidgets.QLabel("<b>%s</b>" % title)
        head.addWidget(t, 1)
        add = QtWidgets.QToolButton(text="+")
        add.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        add.setMenu(step_menu(add, owner.add, only_zone=zone_key))
        head.addWidget(add)
        for txt, fn in (("↑", lambda: owner.move(self, -1)), ("↓", lambda: owner.move(self, 1)),
                        ("✕", lambda: owner.delete(self))):
            b = QtWidgets.QToolButton(text=txt)
            b.clicked.connect(fn)
            head.addWidget(b)
        lay.addLayout(head)
        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "Step", "Beállítás", "Állapot"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setIconSize(QtCore.QSize(20, 20))
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(lambda: self.selected.emit(self.current()))
        lay.addWidget(self.table)
        self.rows = []

    def fill(self, steps, session, offset):
        cur = self.current()
        self.table.blockSignals(True)
        self.rows = [s for s in steps if model.zone(s) == self.zone_key]
        self.table.setRowCount(len(self.rows))
        for r, s in enumerate(self.rows):
            lab = model.label(s)
            setting = lab.split(": ", 1)[1] if ": " in lab else lab.replace(model.CATALOG[s["type"]][0], "").strip()
            if s["type"] == "mask":
                setting = "fekete" if s["params"]["bg"] == "Black" else "fehér"
            cells = [str(offset + r + 1), model.CATALOG[s["type"]][0], setting or "–",
                     " ".join([s.get("src", "")] + tag_text(session, s))]
            for c, txt in enumerate(cells):
                it = QtWidgets.QTableWidgetItem(txt)
                if c == 1:
                    it.setIcon(model.step_icon(s, 20))
                if model.missing(s):
                    it.setForeground(QtGui.QColor("#e0c060"))
                self.table.setItem(r, c, it)
        self.table.blockSignals(False)
        if cur in self.rows:
            self.table.selectRow(self.rows.index(cur))

    def current(self):
        r = self.table.currentRow()
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            return None
        r = sel[0].row()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def select(self, step):
        if step in self.rows:
            self.table.selectRow(self.rows.index(step))

    def clear_sel(self):
        self.table.blockSignals(True)
        self.table.clearSelection()
        self.table.blockSignals(False)


class EditorDialog(QtWidgets.QDialog):
    def __init__(self, session, parent):
        super().__init__(parent)
        self.session = session
        self.host = session.host
        self.form = None
        self.setWindowTitle("Workflow szerkesztő")
        self.setProperty("spx", True)
        self.setAcceptDrops(True)
        self.resize(760, 580)
        lay = QtWidgets.QVBoxLayout(self)
        top = QtWidgets.QHBoxLayout()
        self.icon_lbl = QtWidgets.QLabel()
        self.icon_lbl.setFixedSize(48, 48)
        self.icon_lbl.setToolTip("A Workflow button ikonja (automatikus: 2×2 az első négy Step-ből)")
        top.addWidget(self.icon_lbl)
        top.addWidget(QtWidgets.QLabel("Név:"))
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.textEdited.connect(session.set_name)
        top.addWidget(self.name_edit, 1)
        lay.addLayout(top)
        body = QtWidgets.QHBoxLayout()
        left = QtWidgets.QVBoxLayout()
        self.t_layer = ZoneTable("Layer-rész  (egy Ctrl+Z vonja vissza)", model.LAYER, self)
        self.t_ui = ZoneTable("A végén  (Brush, menüparancs, mentés)", model.UI, self)
        self.t_layer.selected.connect(lambda s: self._select(s, self.t_ui))
        self.t_ui.selected.connect(lambda s: self._select(s, self.t_layer))
        left.addWidget(self.t_layer, 3)
        left.addWidget(self.t_ui, 2)
        body.addLayout(left, 3)
        self.param_box = QtWidgets.QGroupBox("Kijelölt Step")
        self.param_box.setMinimumWidth(230)
        self.param_lay = QtWidgets.QVBoxLayout(self.param_box)
        self.param_lay.addStretch(1)
        body.addWidget(self.param_box, 2)
        lay.addLayout(body, 1)
        self.notes = QtWidgets.QLabel()
        self.notes.setWordWrap(True)
        self.notes.setStyleSheet("color: #aaa; font-size: 11px;")
        lay.addWidget(self.notes)
        bot = QtWidgets.QHBoxLayout()
        cont = QtWidgets.QPushButton("● Rögzítés folytatása")
        cont.clicked.connect(self._continue)
        bot.addWidget(cont)
        hint = QtWidgets.QLabel("Tipp: brusht, smart materialt az Assets ablakból ide is behúzhatsz.")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        bot.addWidget(hint, 1)
        save = QtWidgets.QPushButton("Mentés")
        save.setDefault(True)
        save.clicked.connect(self._save)
        cancel = QtWidgets.QPushButton("Mégse")
        cancel.clicked.connect(session.cancel)
        bot.addWidget(save)
        bot.addWidget(cancel)
        lay.addLayout(bot)
        session.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        s = self.session
        if s.closed:
            return
        self.t_layer.fill(s.steps, s, 0)
        self.t_ui.fill(s.steps, s, len(self.t_layer.rows))
        if self.name_edit.text() != s.display_name() and not self.name_edit.hasFocus():
            self.name_edit.setText(s.display_name())
        self.icon_lbl.setPixmap(model.workflow_icon(s.steps, model.ICON_STRATEGY["B"], 48).pixmap(48, 48))
        self.notes.setText(notice_text(s))

    def _select(self, step, other):
        if step is None:
            return
        other.clear_sel()
        if self.form is not None and self.form.step is step:
            return                      # ugyanaz a Step (pl. frissítés után): az űrlap marad, a fókusz nem vész el
        if self.form is not None:
            self.form.setParent(None)
            self.form.deleteLater()
        self.form = ParamForm(self.host, step)
        self.form.changed.connect(self.session.changed_param)
        self.param_lay.insertWidget(0, self.form)

    def current(self):
        return self.t_layer.current() or self.t_ui.current()

    def add(self, step):
        self.session.add(step)
        (self.t_ui if model.zone(step) == model.UI else self.t_layer).select(step)

    def move(self, table, d):
        cur = table.current()
        if cur:
            self.session.move(cur, d)
            table.select(cur)

    def delete(self, table):
        cur = table.current()
        if cur:
            self.session.delete(cur)
            if self.form is not None:
                self.form.setParent(None)
                self.form = None

    def dragEnterEvent(self, e):
        if resource_urls(e.mimeData()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        for st in step_from_drop(self.host, e.mimeData()):
            self.add(st)
        e.acceptProposedAction()

    def _continue(self):
        self.hide()
        self.session.start_recording()

    def _save(self):
        if confirm_save(self, self.session):
            self.session.save()

    def closeEvent(self, e):
        if not self.session.closed:
            self.session.cancel()
        super().closeEvent(e)


class VariantB(QtCore.QObject):
    NAME = "Lebegő REC-sáv + külön ablak"
    in_panel = False

    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.session = None
        self.pill = None
        self.dialog = None

    def begin(self, session, record):
        self.session = session
        session.recStarted.connect(self._rec_started)
        session.recFinished.connect(self._rec_finished)
        self.dialog = EditorDialog(session, keep(self.panel.window()))
        if record:
            session.start_recording()
        else:
            self.dialog.show()

    def _rec_started(self):
        self.panel.status("● Rögzítés fut – a lebegő REC-sávon állítod le.")
        self.pill = RecPill(self.session, self.panel)
        self.pill.show()

    def _rec_finished(self, reason):
        if self.pill is not None:
            self.pill.close()
            self.pill.deleteLater()
            self.pill = None
        if not self.session.closed:
            self.dialog.refresh()
            self.dialog.show()
            self.dialog.raise_()
            self.panel.status("Rögzítés vége (%s). Javítsd a listát a szerkesztőablakban." % reason)

    def end(self):
        if self.pill is not None:
            self.pill.close()
            self.pill = None
        if self.dialog is not None:
            self.dialog.hide()
            self.dialog.deleteLater()
            self.dialog = None
        self.session = None


# ====================================================================== C – idővonal-csempék

class Chip(QtWidgets.QFrame):
    clicked = QtCore.Signal(object)

    def __init__(self, step, session, fresh=False, selected=False):
        super().__init__()
        self.step = step
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 6, 2)
        lay.setSpacing(4)
        ic = QtWidgets.QLabel()
        ic.setPixmap(model.step_pixmap(step, 20))
        lay.addWidget(ic)
        lay.addWidget(QtWidgets.QLabel(model.short(step)))
        tags = tag_text(session, step)
        border = "#e0a800" if model.missing(step) else ("#6aa0ff" if selected else "#555")
        bg = "#3a4a2a" if fresh else ("#2f3b52" if selected else "#333")
        self.setStyleSheet("Chip { background: %s; border: %dpx solid %s; border-radius: 11px; }"
                           % (bg, 2 if (selected or model.missing(step)) else 1, border))
        self.setToolTip(model.label(step) + ("\n" + "\n".join(tags) if tags else "") +
                        "\n\nKattints a beállításhoz; húzd a sorrendhez.")
        self._press = None

    def mousePressEvent(self, e):
        self._press = e.position().toPoint()

    def mouseMoveEvent(self, e):
        if self._press is None or (e.position().toPoint() - self._press).manhattanLength() < 8:
            return
        self._press = None
        md = QtCore.QMimeData()
        md.setData(STEP_MIME, str(self.step["id"]).encode())
        d = QtGui.QDrag(self)
        d.setMimeData(md)
        d.setPixmap(self.grab())
        d.exec(Qt.DropAction.MoveAction)

    def mouseReleaseEvent(self, e):
        if self._press is not None:
            self.clicked.emit(self.step)
        self._press = None


class Popover(QtWidgets.QFrame):
    """Lebegő beállító egy csempéhez. Nem Qt.Popup, mert a menüből elkapáshoz a Painter menüjébe kell kattintani."""

    def __init__(self, strip, step):
        super().__init__(keep(strip.window()), Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("pop")
        self.setProperty("spx", True)
        self.setStyleSheet("QFrame#pop { background: #262626; border: 1px solid #6aa0ff; border-radius: 6px; }")
        self.strip, self.step = strip, step
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.form = ParamForm(strip.host, step)
        self.form.changed.connect(strip.session.changed_param)
        lay.addWidget(self.form)
        row = QtWidgets.QHBoxLayout()
        for txt, tip, fn in (("◀", "Előrébb", lambda: strip.move(step, -1)),
                             ("▶", "Hátrébb", lambda: strip.move(step, 1)),
                             ("🗑 Törlés", "", lambda: strip.delete(step))):
            b = QtWidgets.QPushButton(txt)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        close = QtWidgets.QPushButton("Kész")
        close.clicked.connect(strip.close_pop)
        row.addWidget(close)
        lay.addLayout(row)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.strip.close_pop()
        else:
            super().keyPressEvent(e)


class VariantC(QtWidgets.QFrame):
    NAME = "Idővonal-csempék"
    in_panel = False

    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.host = panel.host
        self.session = None
        self.pop = None
        self.sel = None
        self.seen_ids = set()
        self.setAcceptDrops(True)
        self.setObjectName("strip")
        self.setStyleSheet("QFrame#strip { background: #222; border: 1px solid #444; border-radius: 6px; }")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(3)
        head = QtWidgets.QHBoxLayout()
        self.icon_lbl = QtWidgets.QLabel()
        self.icon_lbl.setFixedSize(32, 32)
        self.icon_lbl.setToolTip("A Workflow button ikonja (automatikus: a fő Step + Step-szám)")
        head.addWidget(self.icon_lbl)
        self.title = QtWidgets.QLabel()
        self.title.setToolTip("Dupla kattintás: átnevezés")
        self.title.mouseDoubleClickEvent = self._edit_name
        f = self.title.font()
        f.setBold(True)
        self.title.setFont(f)
        head.addWidget(self.title, 1)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.hide()
        self.name_edit.editingFinished.connect(self._name_done)
        head.addWidget(self.name_edit, 1)
        self.rec_lbl = QtWidgets.QLabel("● REC")
        self.rec_lbl.setStyleSheet("color: %s; font-weight: bold;" % REC_RED)
        head.addWidget(self.rec_lbl)
        self.stop_btn = QtWidgets.QToolButton(text="■")
        self.stop_btn.setToolTip("Rögzítés leállítása")
        self.stop_btn.clicked.connect(lambda: self.session.stop_recording())
        head.addWidget(self.stop_btn)
        lay.addLayout(head)
        self.chips_w = QtWidgets.QWidget()
        self.flow = FlowLayout(self.chips_w, spacing=3, margin=0)
        lay.addWidget(self.chips_w)
        self.notes = QtWidgets.QLabel()
        self.notes.setWordWrap(True)
        self.notes.setStyleSheet("color: #999; font-size: 11px;")
        lay.addWidget(self.notes)
        self.foot = QtWidgets.QWidget()
        fl = QtWidgets.QHBoxLayout(self.foot)
        fl.setContentsMargins(0, 0, 0, 0)
        cont = QtWidgets.QToolButton(text="● Folytatás")
        cont.clicked.connect(lambda: self.session.start_recording())
        fl.addWidget(cont)
        fl.addStretch(1)
        save = QtWidgets.QPushButton("Mentés")
        save.clicked.connect(self._save)
        cancel = QtWidgets.QPushButton("Mégse")
        cancel.clicked.connect(lambda: self.session.cancel())
        fl.addWidget(save)
        fl.addWidget(cancel)
        lay.addWidget(self.foot)

    def begin(self, session, record):
        self.session = session
        self.seen_ids = {s["id"] for s in session.steps}
        session.changed.connect(self.refresh)
        session.recChanged.connect(self.refresh)
        session.recStarted.connect(self.refresh)
        session.recFinished.connect(lambda r: self.refresh())
        self.panel.show_strip(self)
        if record:
            session.start_recording()
        self.refresh()

    def end(self):
        self.close_pop()
        self.session = None
        self.panel.show_strip(None)

    def refresh(self):
        s = self.session
        if s is None or s.closed:
            return
        rec = s.recording()
        steps = s.live_steps()
        self.rec_lbl.setVisible(rec)
        self.stop_btn.setVisible(rec)
        self.foot.setVisible(not rec)
        if s.name_touched and s.name:
            self.title.setText(s.name)
        else:
            self.title.setText(model.auto_name(steps) if steps else
                               ("Kattintgass a Painterben…" if rec else "Új Workflow"))
        self.icon_lbl.setPixmap(model.workflow_icon(steps, model.ICON_STRATEGY["C"], 32).pixmap(32, 32))
        self.flow.clear()
        ui_started = False
        layer_n = sum(1 for x in steps if model.zone(x) == model.LAYER)
        for i, st in enumerate(steps):
            if model.zone(st) == model.UI and not ui_started:
                ui_started = True
                if not rec:
                    self.flow.addWidget(self._plus(model.LAYER))
                self.flow.addWidget(self._bar())
            elif i > 0:
                self.flow.addWidget(self._arrow())
            fresh = st["id"] not in self.seen_ids
            c = Chip(st, s, fresh=fresh and rec, selected=(st is self.sel))
            c.clicked.connect(self._chip_clicked)
            self.flow.addWidget(c)
        if not rec:
            if not ui_started:
                if layer_n:
                    self.flow.addWidget(self._plus(model.LAYER))
                else:
                    self.flow.addWidget(self._plus(None))
                self.flow.addWidget(self._bar())
            self.flow.addWidget(self._plus(model.UI))
            self.seen_ids = {x["id"] for x in steps}
        self.notes.setText(("Festés, csúszkák és átnevezés nem kerül bele. A Brush Step-et Stop után add hozzá. "
                            if rec else "") + notice_text(s, rec))
        self.chips_w.updateGeometry()

    def _arrow(self):
        lb = QtWidgets.QLabel("→")
        lb.setStyleSheet("color: #888;")
        return lb

    def _bar(self):
        lb = QtWidgets.QLabel("┃ a végén:")
        lb.setStyleSheet("color: #3f9d4a; font-weight: bold;")
        lb.setToolTip("Ettől jobbra csak UI Step állhat (Brush, menüparancs, mentés).")
        return lb

    def _plus(self, zone_key):
        b = QtWidgets.QToolButton(text="+")
        b.setToolTip("Step hozzáadása ide")
        b.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        b.setMenu(step_menu(b, self._add, only_zone=zone_key))
        b.setStyleSheet("QToolButton { border: 1px dashed #777; border-radius: 10px; padding: 1px 6px; }")
        return b

    # ---- csempe-műveletek
    def _chip_clicked(self, step):
        if self.session.recording():
            return
        if self.sel is step and self.pop is not None:
            self.close_pop()
            return
        self.close_pop()
        self.sel = step
        self.refresh()
        self.pop = Popover(self, step)
        self.pop.adjustSize()
        g = self.mapToGlobal(QtCore.QPoint(0, self.height()))
        right = keep(self.window()).geometry().right()
        g.setX(max(keep(self.window()).geometry().left(), min(g.x(), right - self.pop.width())))
        self.pop.move(g)
        self.pop.show()

    def close_pop(self):
        if self.pop is not None:
            self.pop.close()
            self.pop.deleteLater()
            self.pop = None
        if self.sel is not None:
            self.sel = None
            if self.session is not None:
                self.refresh()

    def move(self, step, d):
        if not self.session.move(step, d):
            self.panel.status("Nem mozgatható tovább: a UI Step-ek csak a végén állhatnak.")

    def delete(self, step):
        self.close_pop()
        self.session.delete(step)

    def _add(self, step):
        self.session.add(step)
        self._chip_clicked(step)

    def _edit_name(self, e):
        self.name_edit.setText(self.session.display_name())
        self.title.hide()
        self.name_edit.show()
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _name_done(self):
        if self.name_edit.isVisible():
            self.session.set_name(self.name_edit.text())
            self.name_edit.hide()
            self.title.show()

    def _save(self):
        self.close_pop()
        if confirm_save(self, self.session):
            self.session.save()

    # ---- húzás
    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(STEP_MIME) or resource_urls(e.mimeData()):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        md = e.mimeData()
        if not md.hasFormat(STEP_MIME):
            for st in step_from_drop(self.host, md):
                self.session.add(st)
            e.acceptProposedAction()
            return
        sid = int(bytes(md.data(STEP_MIME)).decode())
        steps = self.session.steps
        step = next((x for x in steps if x["id"] == sid), None)
        if step is None:
            return
        pos = self.chips_w.mapFrom(self, e.position().toPoint())
        chips = [self.flow.itemAt(i).widget() for i in range(self.flow.count())]
        chips = [c for c in chips if isinstance(c, Chip)]
        target = len(chips)
        for k, c in enumerate(chips):
            g = c.geometry()
            if pos.y() < g.top() - 2:
                target = k
                break
            if pos.y() <= g.bottom() + 2 and pos.x() < g.center().x():
                target = k
                break
        ids = [c.step["id"] for c in chips if c.step is not step]
        src = [c.step["id"] for c in chips].index(sid)
        if target > src:
            target -= 1
        ids.insert(target, sid)
        if not self.session.reorder(ids):
            self.panel.status("A UI Step-ek (Brush, menü, mentés) csak a „┃ a végén” rész után állhatnak.")
        e.acceptProposedAction()


VARIANTS = {"A": VariantA, "B": VariantB, "C": VariantC}
