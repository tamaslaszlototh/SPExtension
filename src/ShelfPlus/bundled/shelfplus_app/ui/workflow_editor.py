"""The Workflow editor (PRD R7), shown inside the Panel in place of the Groups.

- On top: the Workflow's icon (click: an image from disk, or back to the automatic one),
  its name (automatic until typed) and a trash that deletes the Workflow after Yes/No.
- In the middle: the block tree (``core/blocks.py``). Every Step row has ↑, ↓ and X;
  rows are dragged, and a drop that breaks a rule snaps back. The Start block's title row
  is always there but hidden unless the block has Steps or a row is being dragged.
- "+ Add Step" adds from the catalog by the R7.3 rules.
- Below: the selected Step's settings, then the reason saving is blocked, Save and Cancel.
- A resource dragged from the Assets window onto the editor fills the selected
  incomplete Step (or, a brush, adds a Brush Step).

The rules live in ``core/workflow_draft.py``; this file only draws and forwards.
"""


from PySide6 import QtCore, QtGui, QtWidgets

from ..core import blocks
from ..core.workflow_draft import (
    CATALOG,
    COLOUR_CHANNELS,
    incomplete,
    resource_name,
    short_name,
    takes_resource,
    template,
)
from .icons import step_icon, trash_icon
from .resource_picker import ResourcePicker


OBJECT_NAME = "ShelfPlusWorkflowEditor"
ROW_TEXT = {blocks.START: "Start: the layer selected when it runs", blocks.END: "At the end of the Workflow"}
INDENT = "   "
# Before a Step under a header or title row: "├" while more of the block follows, "└" on its last Step.
BRANCH, LAST_BRANCH = "├ ", "└ "
ICON_SIZE = 20
IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
ICON_PX = 256  # an image from disk is stored at most this big

BLEND_MODES = [
    "Normal", "Replace", "Multiply", "Divide", "InverseDivide", "Darken", "Lighten", "LinearDodge",
    "Subtract", "InverseSubtract", "Difference", "Exclusion", "SignedAddition", "Overlay", "Screen",
    "LinearBurn", "ColorBurn", "ColorDodge", "SoftLight", "HardLight", "VividLight", "LinearLight",
    "PinLight", "Saturation", "Color", "Hue", "Value", "Passthrough", "Disable",
]
CHANNELS = ["BaseColor", "Height", "Roughness", "Metallic", "Normal", "Emissive", "Opacity", "Specular"]
# A Fill layer's content, as the settings offer it
CONTENT_DEFAULT, CONTENT_MATERIAL, CONTENT_CHANNELS = "Painter's default", "One material", "Per channel"
SOURCE_VALUE, SOURCE_RESOURCE = "Value", "Resource"
DEFAULT_GREY = 0.5
DEFAULT_COLOUR = "#808080"


def default_source(channel):
    """What a channel of a Fill layer starts with in "Per channel"."""
    return {"color": DEFAULT_COLOUR} if channel in COLOUR_CHANNELS else {"value": DEFAULT_GREY}


def image_png(path, size=ICON_PX):
    """The image file at ``path`` as PNG bytes, scaled down to ``size`` px; ``None`` if it
    cannot be read."""
    image = QtGui.QImage(str(path))
    if image.isNull():
        return None
    if image.width() > size or image.height() > size:
        image = image.scaled(size, size, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                             QtCore.Qt.TransformationMode.SmoothTransformation)
    data = QtCore.QByteArray()
    buffer = QtCore.QBuffer(data)
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


def _resource_text(mime):
    if not mime.hasFormat("text/uri-list"):
        return ""
    text = bytes(mime.data("text/uri-list")).decode("utf-8", "replace")
    return text if "resource://" in text else ""


class StepTree(QtWidgets.QListWidget):
    """The block tree: one item per ``blocks.rows(steps, dragging=True)`` row."""

    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.setObjectName(OBJECT_NAME + "Tree")
        self.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.drag_source = None  # the flat index of the Step being dragged

    def startDrag(self, actions):
        item = self.currentItem()
        index = None if item is None else item.data(QtCore.Qt.ItemDataRole.UserRole)
        if index is None:
            return
        self.drag_source = index
        self.editor.show_start_row(True)
        try:
            super().startDrag(actions)
        finally:
            self.drag_source = None
            # after the drag's own event loop: the tree is rebuilt from the draft
            self.editor.refresh_later()

    def _ours(self, event):
        return event.source() is self and self.drag_source is not None

    def dragEnterEvent(self, event):
        if self._ours(event):
            super().dragEnterEvent(event)
            event.acceptProposedAction()
        elif _resource_text(event.mimeData()):
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._ours(event):
            super().dragMoveEvent(event)
            event.acceptProposedAction()
        elif _resource_text(event.mimeData()):
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def gap_at(self, pos):
        """The gap of the rows a drop at ``pos`` lands in (gap g is above row g)."""
        item = self.itemAt(pos)
        if item is None:
            return self.count()
        row = self.row(item)
        rect = self.visualItemRect(item)
        return row if pos.y() < rect.center().y() else row + 1

    def dropEvent(self, event):
        text = _resource_text(event.mimeData())
        if self._ours(event):
            # Never a Qt move: the tree is rebuilt from the draft.
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
            self.editor.drop_row(self.drag_source, self.gap_at(event.position().toPoint()))
        elif text:
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
            self.editor.drop_resource(text)
        else:
            event.ignore()


class RowWidget(QtWidgets.QWidget):
    """A Step row's ↑, ↓ and X, right-aligned over the item."""

    def __init__(self, editor, index):
        super().__init__()
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 2, 0)
        row.setSpacing(1)
        row.addStretch(1)
        self.buttons = {}
        for name, text, tip, slot in (
            ("up", "↑", "Move up", lambda: editor.move(index, -1)),
            ("down", "↓", "Move down", lambda: editor.move(index, +1)),
            ("delete", "✕", "Delete", lambda: editor.delete_row(index)),
        ):
            button = QtWidgets.QToolButton()
            button.setObjectName(f"{OBJECT_NAME}Row{name.capitalize()}")
            button.setAutoRaise(True)
            button.setText(text)
            button.setToolTip(tip)
            button.setFixedSize(20, 20)
            button.clicked.connect(slot)
            row.addWidget(button)
            self.buttons[name] = button


class WorkflowEditor(QtWidgets.QFrame):
    """The editor over ``view.app.workflow_draft``."""

    def __init__(self, view, draft):
        super().__init__()
        self.view = view
        self.app = view.app
        self.draft = draft
        self.setObjectName(OBJECT_NAME)
        self.setAcceptDrops(True)
        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)

        # -- header: icon, name, trash
        top = QtWidgets.QHBoxLayout()
        top.setSpacing(4)
        self.icon_button = QtWidgets.QToolButton()
        self.icon_button.setObjectName(OBJECT_NAME + "Icon")
        self.icon_button.setFixedSize(36, 36)
        self.icon_button.setIconSize(QtCore.QSize(30, 30))
        self.icon_button.setToolTip("The Workflow's icon: click to choose an image from disk")
        self.icon_button.clicked.connect(self._icon_menu)
        top.addWidget(self.icon_button)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setObjectName(OBJECT_NAME + "Name")
        self.name_edit.setToolTip("The Workflow's name. Clear it to name it after its Steps again.")
        self.name_edit.textEdited.connect(self._name_edited)
        top.addWidget(self.name_edit, 1)
        self.trash = QtWidgets.QToolButton()
        self.trash.setObjectName(OBJECT_NAME + "Delete")
        self.trash.setIcon(trash_icon())
        self.trash.setToolTip("Delete this Workflow")
        self.trash.clicked.connect(self.delete_workflow)
        top.addWidget(self.trash)
        column.addLayout(top)

        # -- the block tree
        self.tree = StepTree(self)
        self.tree.currentRowChanged.connect(self._row_selected)
        column.addWidget(self.tree, 1)

        self.add_button = QtWidgets.QPushButton("+ Add Step")
        self.add_button.setObjectName(OBJECT_NAME + "Add")
        self.add_button.setToolTip("Add a Step from the catalog")
        self.add_menu = self._build_add_menu()
        self.add_button.clicked.connect(
            lambda: self.add_menu.exec(self.add_button.mapToGlobal(QtCore.QPoint(0, self.add_button.height())))
        )
        column.addWidget(self.add_button)

        # -- the selected Step's settings
        self.settings = QtWidgets.QScrollArea()
        self.settings.setObjectName(OBJECT_NAME + "Settings")
        self.settings.setWidgetResizable(True)
        self.settings.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.settings.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QtWidgets.QWidget()
        self.settings_layout = QtWidgets.QFormLayout(inner)
        self.settings_layout.setContentsMargins(4, 4, 4, 4)
        self.settings.setWidget(inner)
        column.addWidget(self.settings, 1)
        self.fields = {}

        # -- saving
        self.problem_label = QtWidgets.QLabel()
        self.problem_label.setObjectName(OBJECT_NAME + "Problem")
        self.problem_label.setWordWrap(True)
        self.problem_label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        column.addWidget(self.problem_label)
        bottom = QtWidgets.QHBoxLayout()
        bottom.addStretch(1)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setObjectName(OBJECT_NAME + "Cancel")
        self.cancel_button.clicked.connect(self.app.close_workflow_editor)
        bottom.addWidget(self.cancel_button)
        self.save_button = QtWidgets.QPushButton("Save")
        self.save_button.setObjectName(OBJECT_NAME + "Save")
        self.save_button.clicked.connect(self.save)
        bottom.addWidget(self.save_button)
        column.addLayout(bottom)

        # Redraws once the current event is over (after a drag's own event loop). Parented
        # to the editor, so it cannot fire once the editor is gone. (Not
        # ``QTimer.singleShot(0, context, callable)``: PySide6 6.5 in Painter 11.1 has no
        # such call, and a drop was lost to the TypeError.)
        self.refresh_timer = QtCore.QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(0)
        self.refresh_timer.timeout.connect(self.refresh)
        # The settings are rebuilt after the signal that changed them: the widget sending
        # it is one of those deleted.
        self.settings_timer = QtCore.QTimer(self)
        self.settings_timer.setSingleShot(True)
        self.settings_timer.setInterval(0)
        self.settings_timer.timeout.connect(self._build_settings)

        self.refresh()

    # -- drawing -------------------------------------------------------------

    def _step_icon(self, step):
        return step_icon(step, self.app.step_action_png(step))

    def _workflow_icon(self):
        draft = self.draft
        if draft.icon_png:
            pixmap = QtGui.QPixmap()
            if pixmap.loadFromData(draft.icon_png):
                return QtGui.QIcon(pixmap)
        if not draft.icon_reset and draft.button_id is not None:
            button = self.app.draft_button()
            path = self.app.icon_path(button) if button is not None else None
            if path is not None:
                icon = QtGui.QIcon(str(path))
                if not icon.isNull():
                    return icon
        if draft.steps:
            return self._step_icon(draft.steps[0])
        return QtGui.QIcon()

    def refresh_later(self):
        self.refresh_timer.start()

    def refresh(self):
        """Redraw everything from the draft (not the settings fields being typed in)."""
        if self.tree.drag_source is not None:
            return
        self.icon_button.setIcon(self._workflow_icon())
        self._sync_name()
        self._fill_tree()
        self._sync_problem()
        self._build_settings()

    def _fill_tree(self):
        tree = self.tree
        tree.blockSignals(True)
        tree.clear()
        self.rows = blocks.rows(self.draft.steps, dragging=True)
        self.row_widgets = {}
        current = None
        for number, row in enumerate(self.rows):
            if row.kind in (blocks.START, blocks.END):
                item = QtWidgets.QListWidgetItem(ROW_TEXT[row.kind])
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, None)
                tree.addItem(item)
                continue
            step = self.draft.steps[row.index]
            note = incomplete(step)
            label = short_name(step) + (f"  {note}" if note else "")
            if row.kind == blocks.HEADER:
                text = label
            else:
                following = self.rows[number + 1] if number + 1 < len(self.rows) else None
                more = following is not None and following.kind == blocks.STEP and following.block == row.block
                text = INDENT + (BRANCH if more else LAST_BRANCH) + label
            item = QtWidgets.QListWidgetItem(self._step_icon(step), text)
            if row.kind == blocks.HEADER:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, row.index)
            item.setToolTip(label)
            item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsEnabled
                | QtCore.Qt.ItemFlag.ItemIsSelectable
                | QtCore.Qt.ItemFlag.ItemIsDragEnabled
            )
            tree.addItem(item)
            widget = RowWidget(self, row.index)
            tree.setItemWidget(item, widget)
            self.row_widgets[row.index] = widget
            if row.index == self.draft.selected:
                current = number
        self.show_start_row(False)
        if current is not None:
            tree.setCurrentRow(current)
        tree.blockSignals(False)

    def show_start_row(self, dragging):
        """The Start block's title: shown when it has Steps, or while a row is dragged."""
        has_start = any(r.block == blocks.START and r.kind == blocks.STEP for r in self.rows)
        self.tree.setRowHidden(0, not (dragging or has_start))

    def visible_rows(self):
        """The text of every row not hidden (tests read the tree with it)."""
        return [
            self.tree.item(i).text().strip()
            for i in range(self.tree.count())
            if not self.tree.isRowHidden(i)
        ]

    def _sync_name(self):
        """The name field follows the automatic name; a name being typed is left alone."""
        typing = self.name_edit.hasFocus() and not self.draft.name_is_automatic
        if not typing and self.name_edit.text() != self.draft.name:
            self.name_edit.setText(self.draft.name)

    def _sync_problem(self):
        problem = self.draft.problem
        self.problem_label.setText(problem or "")
        self.problem_label.setVisible(bool(problem))
        self.save_button.setEnabled(problem is None)
        self.save_button.setToolTip(problem or "Save the Workflow")

    # -- the catalog ---------------------------------------------------------

    def _build_add_menu(self):
        menu = QtWidgets.QMenu(self)
        menu.setObjectName(OBJECT_NAME + "AddMenu")
        sections = {}
        for section, label in CATALOG:
            if section not in sections:
                sub = menu.addMenu(section)
                sub.setObjectName(OBJECT_NAME + "AddSubMenu")
                sections[section] = sub
            action = sections[section].addAction(label)
            action.triggered.connect(lambda checked=False, label=label: self.add_step(label))
        return menu

    def add_step(self, label):
        self.draft.add(template(label))
        self.refresh()

    # -- editing -------------------------------------------------------------

    def _row_selected(self, number):
        index = self.tree.item(number).data(QtCore.Qt.ItemDataRole.UserRole) if number >= 0 else None
        self.draft.select(index)
        self._build_settings()

    def select_step(self, index):
        """Select the row of the Step at ``index`` (as a click does)."""
        number = next(n for n, row in enumerate(self.rows) if row.kind != blocks.START and row.index == index)
        self.tree.setCurrentRow(number)

    def move(self, index, delta):
        moved = self.draft.move_up(index) if delta < 0 else self.draft.move_down(index)
        if not moved:
            self.view.show_status("That Step cannot move there.")
        self.refresh()

    def drop_row(self, source, gap):
        if not self.draft.drop(source, gap):
            self.view.show_status("A Step cannot go there; it was put back.")
        self.refresh_later()

    def delete_row(self, index):
        count = blocks.block_size(self.draft.steps, index)
        if count:
            name = short_name(self.draft.steps[index])
            answer = QtWidgets.QMessageBox.question(
                self, "Delete block", f"Delete “{name}” and the {count} Step(s) acting on it?"
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self.draft.delete(index)
        self.refresh()

    def drop_resource(self, uri_list):
        self.app.workflow_resource_drop(uri_list)
        self.refresh()

    def _name_edited(self, text):
        self.draft.set_name(text)

    # -- the icon --------------------------------------------------------------

    def _icon_menu(self):
        menu = QtWidgets.QMenu(self)
        menu.setObjectName(OBJECT_NAME + "IconMenu")
        menu.addAction("Choose image…").triggered.connect(self.choose_icon)
        automatic = menu.addAction("Use the first Step's icon")
        automatic.triggered.connect(self.reset_icon)
        menu.exec(self.icon_button.mapToGlobal(QtCore.QPoint(0, self.icon_button.height())))
        menu.deleteLater()

    def choose_icon(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Choose an icon", "", IMAGE_FILTER)
        if path:
            self.set_icon_file(path)

    def set_icon_file(self, path):
        png = image_png(path)
        if png is None:
            self.view.show_status("That image could not be read.")
            return
        self.draft.icon_png = png
        self.draft.icon_reset = False
        self.refresh()

    def reset_icon(self):
        self.draft.icon_png = None
        self.draft.icon_reset = True
        self.refresh()

    # -- saving and deleting -----------------------------------------------------

    def save(self):
        self.draft.set_name(self.name_edit.text())
        self.app.save_workflow()

    def delete_workflow(self):
        answer = QtWidgets.QMessageBox.question(self, "Delete Workflow", f"Delete “{self.draft.name}”?")
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        pending = self.app.delete_workflow()
        if pending is not None:
            self.view.show_undo(pending)

    # -- dropping resources onto the editor -----------------------------------------

    def dragEnterEvent(self, event):
        if _resource_text(event.mimeData()):
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        text = _resource_text(event.mimeData())
        if text:
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
            self.drop_resource(text)

    # -- the settings panel ------------------------------------------------------

    def _clear_settings(self):
        while self.settings_layout.rowCount():
            self.settings_layout.removeRow(0)
        self.fields = {}

    def _build_settings(self):
        self._clear_settings()
        index = self.draft.selected
        if index is None:
            self.settings.hide()
            return
        self.settings.show()
        step = self.draft.steps[index]
        kind = step["type"]
        form = self.settings_layout

        def change(rebuild=False, **values):
            """Set (``None``: remove) keys of the Step; ``rebuild`` redraws these settings
            too (their rows depend on what changed)."""
            new = dict(self.draft.steps[index])
            for key, value in values.items():
                if value is None:
                    new.pop(key, None)
                else:
                    new[key] = value
            self.draft.set_step(index, new)
            self._after_setting()
            if rebuild:
                self.settings_timer.start()

        if kind == "add_layer":
            edit = self._line("name", step.get("name", ""), "Painter's default name")
            edit.textEdited.connect(lambda text: change(name=text.strip() or None))
            form.addRow("Name", edit)
            if step["layer"] in ("fill", "paint"):
                self._layer_settings(step, change)
        elif kind == "add_mask":
            combo = self._combo("background", ["black", "white"], step["background"])
            combo.currentTextChanged.connect(lambda text: change(background=text))
            form.addRow("Background", combo)
        elif kind == "add_effect":
            combo = self._combo("target", ["mask", "layer"], step["target"])
            combo.currentTextChanged.connect(lambda text: change(target=text))
            form.addRow("On the", combo)
        elif kind == "set_blend":
            combo = self._combo("blend", BLEND_MODES, step["blend"], editable=True)
            combo.currentTextChanged.connect(lambda text: change(blend=text.strip() or None))
            form.addRow("Blend mode", combo)
        elif kind == "set_opacity":
            self._opacity_rows(step, change)
        elif kind == "select_layer":
            edit = self._line("name", step.get("name", ""), "The exact name of the layer")
            edit.textEdited.connect(lambda text: change(name=text))
            form.addRow("Layer name", edit)
            use = QtWidgets.QPushButton("Use selected layer's name")
            use.setObjectName(OBJECT_NAME + "UseSelected")
            use.clicked.connect(lambda: self._use_selected_name(edit, change))
            self.fields["use_selected"] = use
            form.addRow("", use)
        elif kind == "run_action":
            edit = self._line("action", step.get("action", ""), "The command's objectName")
            edit.textEdited.connect(lambda text: change(action=text.strip()))
            form.addRow("Command", edit)
            pick = QtWidgets.QPushButton("Choose from list…")
            pick.setObjectName(OBJECT_NAME + "ChooseCommand")
            pick.clicked.connect(lambda: self._choose_command(edit, change))
            form.addRow("", pick)
        elif kind == "save":
            form.addRow(QtWidgets.QLabel("Saves the project."))
        if takes_resource(step):
            def picked(ref):
                change(rebuild=True, resource=ref.get("resource") or None, resource_name=ref.get("resource_name"))

            form.addRow("Resource", self._resource_field("resource", step, picked))

    # -- resource fields -----------------------------------------------------------

    def _pick_resource(self, title, query=""):
        """The resource picker; the chosen resource, or ``None``."""
        picker = ResourcePicker(self.app, title, query, parent=self)
        try:
            if picker.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                return picker.chosen()
            return None
        finally:
            picker.deleteLater()

    def _resource_field(self, key, ref, picked, title="Choose a resource"):
        """The name of the chosen resource (or its URL, editable) and "Choose…".
        ``ref``: a dict with ``resource`` and maybe ``resource_name``; ``picked(new ref)``."""
        box = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        url = ref.get("resource") or ""
        edit = self._line(key, url, "Choose it, drop it here, or paste its resource:// URL")
        if url:
            edit.setToolTip(f"{ref.get('resource_name') or resource_name(url)}\n{url}")
        edit.textEdited.connect(lambda text: picked({"resource": text.strip()}))
        row.addWidget(edit, 1)
        choose = QtWidgets.QPushButton("Choose…")
        choose.setObjectName(f"{OBJECT_NAME}Choose{key.capitalize()}")
        self.fields[f"choose_{key}"] = choose

        def choose_one():
            resource = self._pick_resource(title, ref.get("resource_name") or "")
            if resource is not None:
                picked({"resource": resource.url, "resource_name": resource.gui_name})

        choose.clicked.connect(choose_one)
        row.addWidget(choose)
        return box

    # -- a new layer's channels and content ----------------------------------------

    def _layer_settings(self, step, change):
        """Active channels (Fill and Paint layers) and a Fill layer's content."""
        form = self.settings_layout
        offered = self.app.texture_channels()
        active = step.get("channels")
        offered += [c for c in (active or []) if c not in offered]

        grid_box = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(grid_box)
        grid.setContentsMargins(0, 0, 0, 0)
        checks = {}
        for number, channel in enumerate(offered):
            box = QtWidgets.QCheckBox(channel)
            box.setChecked(active is None or channel in active)
            grid.addWidget(box, number // 2, number % 2)
            checks[channel] = box
        self.fields["channels"] = checks

        def channels_changed():
            chosen = [c for c in offered if checks[c].isChecked()]
            current = self.draft.selected_step
            sources = current.get("sources")
            if sources is not None:  # per channel: one source per active channel
                sources = {c: sources.get(c) or default_source(c) for c in chosen}
            everything = chosen == offered and active is None
            change(rebuild=True, channels=None if everything else chosen, sources=sources or None)

        for box in checks.values():
            box.toggled.connect(lambda checked: channels_changed())
        form.addRow("Channels", grid_box)
        if step["layer"] != "fill":
            return

        mode = CONTENT_MATERIAL if "material" in step else CONTENT_CHANNELS if "sources" in step else CONTENT_DEFAULT
        combo = self._combo("content", [CONTENT_DEFAULT, CONTENT_MATERIAL, CONTENT_CHANNELS], mode)

        def content_changed(text):
            if text == CONTENT_MATERIAL:
                change(rebuild=True, material={"resource": ""}, sources=None)
            elif text == CONTENT_CHANNELS:
                channels = step.get("channels") or offered
                change(rebuild=True, material=None, sources={c: default_source(c) for c in channels})
            else:
                change(rebuild=True, material=None, sources=None)

        combo.currentTextChanged.connect(content_changed)
        form.addRow("Content", combo)
        if mode == CONTENT_MATERIAL:
            def material_picked(ref):
                change(rebuild="resource_name" in ref, material=ref)

            form.addRow("Material", self._resource_field("material", step["material"], material_picked, "Choose a material"))
        elif mode == CONTENT_CHANNELS:
            for channel, source in step["sources"].items():
                form.addRow(channel, self._source_field(channel, source, change))

    def _source_field(self, channel, source, change):
        """One channel of a Fill layer: Value (a colour or a grey) or Resource."""
        box = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        def set_source(new, rebuild=False):
            sources = dict(self.draft.selected_step["sources"])
            sources[channel] = new
            change(rebuild=rebuild, sources=sources)

        kind = self._combo(f"kind_{channel}", [SOURCE_VALUE, SOURCE_RESOURCE],
                           SOURCE_RESOURCE if "resource" in source else SOURCE_VALUE)
        kind.currentTextChanged.connect(
            lambda text: set_source({"resource": ""} if text == SOURCE_RESOURCE else default_source(channel), True)
        )
        row.addWidget(kind)
        if "resource" in source:
            row.addWidget(self._resource_field(f"source_{channel}", source,
                                               lambda ref: set_source(ref, "resource_name" in ref),
                                               f"Choose a resource for {channel}"), 1)
        elif "color" in source:
            button = QtWidgets.QPushButton(source["color"])
            button.setObjectName(f"{OBJECT_NAME}Colour")
            button.setStyleSheet(f"background: {source['color']};")
            button.setToolTip(f"{channel} colour: click to change it")
            self.fields[f"colour_{channel}"] = button

            def pick_colour():
                colour = QtWidgets.QColorDialog.getColor(QtGui.QColor(source["color"]), self, f"{channel} colour")
                if colour.isValid():
                    set_source({"color": colour.name()}, True)

            button.clicked.connect(pick_colour)
            row.addWidget(button, 1)
        else:
            spin = QtWidgets.QDoubleSpinBox()
            spin.setObjectName(f"{OBJECT_NAME}Value")
            spin.setRange(0, 1)
            spin.setDecimals(3)
            spin.setSingleStep(0.05)
            spin.setValue(source["value"])
            spin.valueChanged.connect(lambda value: set_source({"value": value}))
            self.fields[f"value_{channel}"] = spin
            row.addWidget(spin, 1)
        return box

    def _after_setting(self):
        """A setting changed: redraw the rows and the name, keep the fields."""
        self.icon_button.setIcon(self._workflow_icon())
        self._sync_name()
        self._fill_tree()
        self._sync_problem()

    def _line(self, key, text, placeholder):
        edit = QtWidgets.QLineEdit(text)
        edit.setObjectName(f"{OBJECT_NAME}Field{key.capitalize()}")
        edit.setPlaceholderText(placeholder)
        edit.setClearButtonEnabled(False)  # its clear action would be one more QAction
        self.fields[key] = edit
        return edit

    def _combo(self, key, values, current, editable=False):
        combo = QtWidgets.QComboBox()
        combo.setObjectName(f"{OBJECT_NAME}Field{key.capitalize()}")
        combo.addItems(values)
        combo.setEditable(editable)
        if current not in values:
            combo.addItem(current)
        combo.setCurrentText(current)
        self.fields[key] = combo
        return combo

    def _opacity_rows(self, step, change):
        values = dict(step["opacity"])
        self.fields["opacity"] = {}

        def update():
            chosen = {ch: spin.value() for ch, (box, spin) in self.fields["opacity"].items() if box.isChecked()}
            change(opacity=chosen or None)

        for channel in CHANNELS + [c for c in values if c not in CHANNELS]:
            box = QtWidgets.QCheckBox(channel)
            box.setChecked(channel in values)
            spin = QtWidgets.QSpinBox()
            spin.setRange(0, 100)
            spin.setSuffix(" %")
            spin.setValue(round(values.get(channel, 100)))
            box.toggled.connect(lambda checked: update())
            spin.valueChanged.connect(lambda value: update())
            self.fields["opacity"][channel] = (box, spin)
            self.settings_layout.addRow(box, spin)

    def _use_selected_name(self, edit, change):
        name = self.app.selected_layer_name()
        if not name:
            self.view.show_status("Select a layer in Painter first.")
            return
        edit.setText(name)
        change(name=name)

    def _choose_command(self, edit, change):
        from .panel import ActionPicker

        picker = ActionPicker(self.app, parent=self, title="Choose a menu command")
        try:
            if picker.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                action = picker.chosen()
                if action is not None and action.name:
                    edit.setText(action.name)
                    change(action=action.name)
        finally:
            picker.deleteLater()
