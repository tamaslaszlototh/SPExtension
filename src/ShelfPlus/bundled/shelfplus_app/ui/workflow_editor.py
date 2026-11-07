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
from ..core.workflow_draft import CATALOG, incomplete, short_name, takes_resource, template
from .icons import step_icon, trash_icon


OBJECT_NAME = "ShelfPlusWorkflowEditor"
ROW_TEXT = {blocks.START: "Start: the layer selected when it runs", blocks.END: "At the end of the Workflow"}
INDENT = "      "
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
            QtCore.QTimer.singleShot(0, self.editor, self.editor.refresh)  # not once it is gone

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
        self.settings = QtWidgets.QFrame()
        self.settings.setObjectName(OBJECT_NAME + "Settings")
        self.settings_layout = QtWidgets.QFormLayout(self.settings)
        self.settings_layout.setContentsMargins(4, 4, 4, 4)
        column.addWidget(self.settings)
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
            indent = "" if row.kind == blocks.HEADER else INDENT
            note = incomplete(step)
            text = indent + short_name(step) + (f"  {note}" if note else "")
            item = QtWidgets.QListWidgetItem(self._step_icon(step), text)
            if row.kind == blocks.HEADER:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, row.index)
            item.setToolTip(text.strip())
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
        QtCore.QTimer.singleShot(0, self, self.refresh)

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

        def change(**values):
            new = dict(self.draft.steps[index])
            for key, value in values.items():
                if value is None:
                    new.pop(key, None)
                else:
                    new[key] = value
            self.draft.set_step(index, new)
            self._after_setting()

        if kind == "add_layer":
            edit = self._line("name", step.get("name", ""), "Painter's default name")
            edit.textEdited.connect(lambda text: change(name=text.strip() or None))
            form.addRow("Name", edit)
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
            edit = self._line("resource", step.get("resource", ""), "Drop it here from the Assets window")
            edit.setToolTip("Drag the resource from the Assets window onto the editor, or paste its resource:// URL")
            edit.textEdited.connect(lambda text: change(resource=text.strip() or None, resource_name=None))
            form.addRow("Resource", edit)

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
