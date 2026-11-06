"""The Panel (PRD R2): Groups of icon-only tiles, tall or flat by the Panel's shape.

- Tall: Groups stacked, each a wrapping grid, scrolling up and down. Flat: Groups in
  one row that scrolls left and right (the mouse wheel too). The decisions are in
  ``core/flow.py``.
- No edit mode: tiles can be dragged at any time, within and between Groups, or onto
  the trash that appears while dragging. A delete can be undone for a few seconds.
- Right-click menus on tiles and Group names; a "+" in each Group row.
- Every element has a toolTip; ``PenHover`` shows it for the pen too.

The content is rebuilt from the Layout after every change (never during a drag).
"""

import logging
from typing import NamedTuple

from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid

from ..core.flow import FLAT, TALL, drop_index, edge_scroll, grid_columns, orientation
from ..core.panel_state import TILE_SIZE_MAX, TILE_SIZE_MIN
from ..core.storage import ReadOnlyLayoutError
from .icons import automatic_icon, panel_icon, plus_icon, trash_icon
from .pen_hover import PenHover

log = logging.getLogger("ShelfPlus.app.panel")

OBJECT_NAME = "ShelfPlusPanel"
MIME_TYPE = "application/x-shelfplus-button"
STATUS_MS = 3000
UNDO_MS = 5000
SPACING = 4  # between tiles
GROUP_GAP = 12  # between Groups in the flat row
TOOL_SIZE = 20  # collapse arrow
PLUS_SIZE = 24  # the "+" of a Group row
PLUS_ICON_SIZE = 18
EDGE_SCROLL_PX = 24  # holding a dragged Button this close to an edge scrolls
EDGE_SCROLL_STEP = 16
EDGE_SCROLL_MS = 40
MARGIN = 4
TILE_SIZE_SAVE_MS = 400  # the slider's value is saved once it stops moving


def _alive(widget):
    return widget is not None and isValid(widget)


class Plan(NamedTuple):
    """What the content was built for; a re-layout rebuilds only when it changes."""

    orientation: str
    tile_size: int
    label_height: int
    columns: object  # tall: tiles per grid row; flat: None (the row scrolls)


def button_icon(app, button):
    """The Button's own icon file, or its automatic icon if it has none or it cannot be read."""
    path = app.icon_path(button)
    icon = QtGui.QIcon(str(path)) if path is not None else QtGui.QIcon()
    return icon if not icon.isNull() else automatic_icon(button)


class MenuButton(QtWidgets.QToolButton):
    """A tool button that opens a menu when clicked (☰, +).

    The menu is not given to Qt with ``setMenu``: Qt then draws a down arrow on the
    button, which in Painter hides the button's own symbol (a 20 px "+" showed only
    the arrow). ``menu()`` still returns it.
    """

    def __init__(self):
        super().__init__()
        self._popup = None
        self.clicked.connect(self._open)

    def set_popup_menu(self, menu):
        self._popup = menu

    def menu(self):
        return self._popup

    def _open(self):
        if self._popup is not None:
            self._popup.exec(self.mapToGlobal(QtCore.QPoint(0, self.height())))


def add_heading(menu, text):
    """A bold, normally coloured title line in a menu. A disabled item would be greyed out,
    which is hard to read in Painter's dark theme."""
    label = QtWidgets.QLabel(text)
    label.setObjectName("ShelfPlusMenuHeading")
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    label.setContentsMargins(8, 4, 8, 4)
    action = QtWidgets.QWidgetAction(menu)
    action.setText(text)
    action.setDefaultWidget(label)
    menu.addAction(action)
    return action


def carries_button(view, event):
    """Whether a drag event is one of this Panel's tiles being dragged."""
    return event.mimeData().hasFormat(MIME_TYPE) and view.dragging is not None


class _PanelWidget(QtWidgets.QWidget):
    def __init__(self, view):
        super().__init__()
        self._view = view

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._view.schedule_relayout()


class Tile(QtWidgets.QToolButton):
    """One Button: click runs it, drag moves it, right-click opens its menu."""

    def __init__(self, view, button, size, show_label):
        super().__init__()
        self.view = view
        self.button = button
        self.setObjectName("ShelfPlusTile")
        self.setAutoRaise(True)
        self.setIcon(button_icon(view.app, button))
        tip = button.name if button.valid else f"{button.name} (invalid: {button.problem})"
        self.setToolTip(tip)
        label_height = self.fontMetrics().height() if show_label else 0
        self.setFixedSize(size, size + label_height)
        self.setIconSize(QtCore.QSize(size - 10, size - 10))
        if show_label:
            self.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            self.setText(self.fontMetrics().elidedText(button.name, QtCore.Qt.TextElideMode.ElideRight, size - 4))
        else:
            self.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda pos: view.button_menu(button, self.mapToGlobal(pos)))
        self.clicked.connect(lambda: view.app.run_button(button))
        self._press = None

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._press = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._press is not None
            and event.buttons() & QtCore.Qt.MouseButton.LeftButton
            and (event.position().toPoint() - self._press).manhattanLength()
            >= QtWidgets.QApplication.startDragDistance()
            and not self.view.app.read_only
        ):
            self._press = None
            self.setDown(False)
            self.view.start_drag(self)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._press = None
        super().mouseReleaseEvent(event)


class GroupBox(QtWidgets.QFrame):
    """A Group: header (collapse arrow, name, "+") and its tiles. Accepts dropped tiles."""

    def __init__(self, view, group):
        super().__init__()
        self.view = view
        self.group = group
        self.tiles = []
        self.setObjectName("ShelfPlusGroup")
        self.setAcceptDrops(not view.app.read_only)
        self.indicator = QtWidgets.QFrame(self)
        self.indicator.setObjectName("ShelfPlusDropIndicator")
        self.indicator.setStyleSheet("background: #d9822b;")
        self.indicator.hide()

    # -- dropping -------------------------------------------------------------

    def _accepts(self, event):
        return carries_button(self.view, event)

    def _index_at(self, pos):
        """(drop position in the Group, the visible tiles' rectangles)."""
        if self.view.app.is_collapsed(self.group.id):
            return len(self.group.buttons), []
        rects = []
        for tile in self.tiles:
            top_left = tile.mapTo(self, QtCore.QPoint(0, 0))
            rects.append((top_left.x(), top_left.y(), tile.width(), tile.height()))
        return drop_index(rects, pos.x(), pos.y()), rects

    def _show_indicator(self, pos):
        index, rects = self._index_at(pos)
        if not rects:
            self.indicator.hide()
            self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
            return
        if index < len(rects):
            x, y, _, h = rects[index]
            x -= 3
        else:
            x, y, w, h = rects[-1]
            x += w + 1
        self.indicator.setGeometry(max(0, x), y, 2, h)
        self.indicator.show()
        self.indicator.raise_()

    def _clear_indicator(self):
        self.indicator.hide()
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

    def dragEnterEvent(self, event):
        if self._accepts(event):
            event.acceptProposedAction()
            self._show_indicator(event.position().toPoint())

    def dragMoveEvent(self, event):
        if self._accepts(event):
            event.acceptProposedAction()
            self._show_indicator(event.position().toPoint())

    def dragLeaveEvent(self, event):
        self._clear_indicator()

    def dropEvent(self, event):
        self._clear_indicator()
        if not self._accepts(event):
            return
        index, _ = self._index_at(event.position().toPoint())
        event.acceptProposedAction()
        self.view.move_button(self.view.dragging, self.group.id, index)


class Trash(QtWidgets.QToolButton):
    """Shown only while a tile is being dragged."""

    def __init__(self, view):
        super().__init__()
        self.view = view
        self.setObjectName(OBJECT_NAME + "Trash")
        self.setText("Delete")
        self.setIcon(trash_icon())
        self.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setToolTip("Drop a Button here to delete it")
        self.setAcceptDrops(True)
        self.hide()

    def dragEnterEvent(self, event):
        if carries_button(self.view, event):
            event.acceptProposedAction()
            self.setDown(True)

    def dragLeaveEvent(self, event):
        self.setDown(False)

    def dropEvent(self, event):
        self.setDown(False)
        if carries_button(self.view, event):
            event.acceptProposedAction()
            self.view.delete_button(self.view.dragging)


class _SidewaysWheel(QtCore.QObject):
    """In the flat row, the mouse wheel scrolls left and right."""

    def __init__(self, view):
        super().__init__(view.widget)
        self.view = view

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.Wheel and self.view.orientation == FLAT:
            delta = event.angleDelta()
            notches = (delta.y() or delta.x()) / 120
            bar = self.view.scroll.horizontalScrollBar()
            bar.setValue(bar.value() - round(notches * 3 * bar.singleStep()))
            return True
        return False


class QtPanelView:
    """The Panel widget over ``app`` (see ``app.App``)."""

    def __init__(self, app):
        self.app = app
        self.dragging = None  # the Button being dragged
        self.orientation = None
        self._plan = None
        self._render_after_drag = False

        widget = _PanelWidget(self)
        widget.setObjectName(OBJECT_NAME)
        widget.setWindowTitle("Shelf+")
        widget.setWindowIcon(panel_icon())
        self.widget = widget

        root = QtWidgets.QVBoxLayout(widget)
        root.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        root.setSpacing(MARGIN)

        bar = QtWidgets.QHBoxLayout()
        bar.setSpacing(MARGIN)
        self.status = QtWidgets.QLabel()
        self.status.setObjectName(OBJECT_NAME + "Status")
        bar.addWidget(self.status, 1)

        self.undo_label = QtWidgets.QLabel()
        self.undo_label.setObjectName(OBJECT_NAME + "UndoText")
        self.undo_label.hide()
        bar.addWidget(self.undo_label)
        self.undo_button = QtWidgets.QToolButton()
        self.undo_button.setObjectName(OBJECT_NAME + "Undo")
        self.undo_button.setText("Undo")
        self.undo_button.setToolTip("Bring back the deleted Button")
        self.undo_button.clicked.connect(self.undo_delete)
        self.undo_button.hide()
        bar.addWidget(self.undo_button)

        self.trash = Trash(self)
        bar.addWidget(self.trash)

        self.panel_menu_tool = MenuButton()
        self.panel_menu_tool.setObjectName(OBJECT_NAME + "Menu")
        self.panel_menu_tool.setText("☰")
        self.panel_menu_tool.setToolTip("Shelf+ menu")
        self.menu = self._build_panel_menu()
        self.panel_menu_tool.set_popup_menu(self.menu)
        bar.addWidget(self.panel_menu_tool)
        root.addLayout(bar)

        self.messages = QtWidgets.QLabel()
        self.messages.setObjectName(OBJECT_NAME + "Messages")
        self.messages.setWordWrap(True)
        self.messages.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.messages.hide()
        root.addWidget(self.messages)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setObjectName(OBJECT_NAME + "Scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self.scroll, 1)
        self.content = None
        self._wheel = _SidewaysWheel(self)
        self.scroll.viewport().installEventFilter(self._wheel)

        # Timers are parented to the widget, so none can fire after the Panel is gone.
        self.status_timer = QtCore.QTimer(widget)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self.status.clear)
        self.undo_timer = QtCore.QTimer(widget)
        self.undo_timer.setSingleShot(True)
        self.undo_timer.setInterval(UNDO_MS)
        self.undo_timer.timeout.connect(self.expire_delete)
        self.relayout_timer = QtCore.QTimer(widget)
        self.relayout_timer.setSingleShot(True)
        self.relayout_timer.setInterval(0)
        self.relayout_timer.timeout.connect(self.relayout_if_needed)

        self.pen_hover = PenHover(widget, paused=lambda: self.dragging is not None)

    # -- Panel menu -----------------------------------------------------------

    def _build_panel_menu(self):
        menu = QtWidgets.QMenu(self.panel_menu_tool)
        add_heading(menu, f"Shelf+ v{self.app.version}")
        menu.addSeparator()

        menu.addAction(self._tile_size_slider(menu))
        self.labels_action = menu.addAction("Show labels")
        self.labels_action.setCheckable(True)
        self.labels_action.triggered.connect(self.set_show_labels)
        self.new_group_action = menu.addAction("New Group…")
        self.new_group_action.triggered.connect(lambda: self.new_group(len(self.app.layout.groups)))
        menu.addSeparator()
        self.copy_action = menu.addAction("Copy diagnostics")
        self.copy_action.triggered.connect(self.copy_diagnostics)
        return menu

    def _sync_panel_menu(self):
        state = self.app.panel_state
        self.tile_slider.blockSignals(True)
        self.tile_slider.setValue(state["tileSize"])
        self.tile_slider.blockSignals(False)
        self._show_tile_size(state["tileSize"])
        self.labels_action.setChecked(state["showLabels"])
        self.new_group_action.setEnabled(not self.app.read_only)

    def _tile_size_slider(self, menu):
        """"Tile size: 48 px" over a slider from 40 to 80 px, inside the ☰ menu."""
        box = QtWidgets.QWidget()
        box.setObjectName(OBJECT_NAME + "TileSize")
        column = QtWidgets.QVBoxLayout(box)
        column.setContentsMargins(8, 4, 8, 4)
        column.setSpacing(2)
        self.tile_size_label = QtWidgets.QLabel()
        column.addWidget(self.tile_size_label)
        slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        slider.setObjectName(OBJECT_NAME + "TileSizeSlider")
        slider.setRange(TILE_SIZE_MIN, TILE_SIZE_MAX)
        slider.setSingleStep(4)
        slider.setPageStep(8)
        slider.setMinimumWidth(160)
        slider.setToolTip(f"Tile size, {TILE_SIZE_MIN} to {TILE_SIZE_MAX} px")
        slider.valueChanged.connect(self._tile_slider_moved)
        column.addWidget(slider)
        self.tile_slider = slider

        # Parented to the Panel widget like the other timers, so it cannot fire after it is gone.
        self.tile_save_timer = QtCore.QTimer(self.widget)
        self.tile_save_timer.setSingleShot(True)
        self.tile_save_timer.setInterval(TILE_SIZE_SAVE_MS)
        self.tile_save_timer.timeout.connect(self.app.save_panel_state)

        action = QtWidgets.QWidgetAction(menu)
        action.setText("Tile size")
        action.setDefaultWidget(box)
        return action

    def _show_tile_size(self, size):
        self.tile_size_label.setText(f"Tile size: {size} px")

    def _tile_slider_moved(self, size):
        self.app.set_tile_size(size, save=False)
        self._show_tile_size(size)
        self.tile_save_timer.start()
        self.render()

    def set_tile_size(self, size):
        self.app.set_tile_size(size)
        self.render()

    def set_show_labels(self, show):
        self.app.set_show_labels(show)
        self.render()

    def copy_diagnostics(self):
        text = self.app.diagnostics_text()
        QtGui.QGuiApplication.clipboard().setText(text)
        log.info("Diagnostics copied to the clipboard")
        self.show_status("Diagnostics copied.")

    def show_status(self, text):
        self.status.setText(text)
        self.status_timer.start(STATUS_MS)

    # -- layout decisions -----------------------------------------------------

    def _tile_metrics(self):
        size = self.app.panel_state["tileSize"]
        label = self.widget.fontMetrics().height() if self.app.panel_state["showLabels"] else 0
        return size, label

    def _available_width(self):
        viewport = self.scroll.viewport().width()
        bar = self.scroll.verticalScrollBar()
        if not bar.isVisible():  # leave room for it, so a scrollbar appearing does not re-flow
            # (not style().pixelMetric: on Painter 11.1 the style's Python wrapper is already deleted)
            viewport -= bar.sizeHint().width()
        return max(0, viewport - 2 * MARGIN)

    def _name_width(self, name):
        return self.widget.fontMetrics().horizontalAdvance(name) + 8

    def _compute_plan(self):
        self.orientation = orientation(self.widget.width(), self.widget.height(), self.orientation)
        size, label = self._tile_metrics()
        available = self._available_width()
        if self.orientation == TALL:
            return Plan(TALL, size, label, grid_columns(available, size, SPACING))
        return Plan(FLAT, size, label, None)

    def schedule_relayout(self):
        if _alive(self.widget):
            self.relayout_timer.start()

    def relayout_if_needed(self):
        if self.dragging is not None or not _alive(self.widget):
            return
        if self._compute_plan() != self._plan:
            self.render()

    # -- building -------------------------------------------------------------

    def render(self):
        """Rebuild the Panel's content from the Layout and the view state."""
        if self.widget is None:
            return
        if self.dragging is not None:  # the dragged tile must stay alive until the drag ends
            self._render_after_drag = True
            return
        self._sync_panel_menu()
        self.messages.setText("\n".join(self.app.messages))
        self.messages.setVisible(bool(self.app.messages))

        self._plan = self._compute_plan()
        old = self.scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self.content = QtWidgets.QWidget()
        self.content.setObjectName(OBJECT_NAME + "Content")
        self.group_boxes = []
        flat = self._plan.orientation == FLAT
        never, needed = QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff, QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        self.scroll.setHorizontalScrollBarPolicy(needed if flat else never)
        self.scroll.setVerticalScrollBarPolicy(never if flat else needed)
        if not self.app.layout.groups:
            box = QtWidgets.QVBoxLayout(self.content)
            empty = QtWidgets.QLabel("The Layout is empty. Use ☰ → New Group… to start.")
            empty.setObjectName(OBJECT_NAME + "Empty")
            empty.setWordWrap(True)
            box.addWidget(empty)
            box.addStretch(1)
        elif flat:
            self._build_flat()
        else:
            self._build_tall(self._plan.columns)
        self.scroll.setWidget(self.content)

    def _header(self, group):
        collapsed = self.app.is_collapsed(group.id)
        arrow = QtWidgets.QToolButton()
        arrow.setObjectName("ShelfPlusGroupToggle")
        arrow.setAutoRaise(True)
        arrow.setFixedSize(TOOL_SIZE, TOOL_SIZE)
        arrow.setArrowType(QtCore.Qt.ArrowType.RightArrow if collapsed else QtCore.Qt.ArrowType.DownArrow)
        arrow.setToolTip(f"Expand {group.name}" if collapsed else f"Collapse {group.name}")
        arrow.clicked.connect(lambda: self.toggle_group(group))

        name = QtWidgets.QLabel(group.name)
        name.setObjectName("ShelfPlusGroupName")
        name.setToolTip(f"{group.name} (right-click for Group options)")
        name.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        name.customContextMenuRequested.connect(lambda pos: self.group_menu(group, name.mapToGlobal(pos)))
        name.setMinimumWidth(self._name_width(group.name))

        plus = MenuButton()
        plus.setObjectName("ShelfPlusGroupAdd")
        plus.setAutoRaise(True)
        plus.setFixedSize(PLUS_SIZE, PLUS_SIZE)
        plus.setText("+")  # not shown; the icon is
        plus.setIcon(plus_icon())
        plus.setIconSize(QtCore.QSize(PLUS_ICON_SIZE, PLUS_ICON_SIZE))
        plus.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        plus.setToolTip(f"Add a Button to {group.name}")
        plus.set_popup_menu(self._add_menu(group, plus))
        plus.setEnabled(not self.app.read_only)
        return arrow, name, plus

    def _add_menu(self, group, parent):
        menu = QtWidgets.QMenu(parent)
        for label, handler in self.app.add_button_kinds:
            action = menu.addAction(label if handler else f"{label} (coming soon)")
            action.setEnabled(handler is not None)
            if handler is not None:
                action.triggered.connect(lambda checked=False, h=handler: h(group))
        return menu

    def _tile(self, button):
        size, label = self._tile_metrics()
        return Tile(self, button, size, label > 0)

    def _build_tall(self, columns):
        column = QtWidgets.QVBoxLayout(self.content)
        column.setContentsMargins(MARGIN, 0, MARGIN, MARGIN)
        column.setSpacing(MARGIN)
        for group in self.app.layout.groups:
            box = GroupBox(self, group)
            inner = QtWidgets.QVBoxLayout(box)
            inner.setContentsMargins(0, 0, 0, 0)
            inner.setSpacing(2)
            arrow, name, plus = self._header(group)
            header = QtWidgets.QHBoxLayout()
            header.setSpacing(SPACING)
            header.addWidget(arrow)
            header.addWidget(name, 1)
            header.addWidget(plus)
            inner.addLayout(header)
            if not self.app.is_collapsed(group.id) and group.buttons:
                grid = QtWidgets.QGridLayout()
                grid.setSpacing(SPACING)
                grid.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
                for index, button in enumerate(group.buttons):
                    tile = self._tile(button)
                    box.tiles.append(tile)
                    grid.addWidget(tile, index // columns, index % columns)
                inner.addLayout(grid)
            column.addWidget(box)
            self.group_boxes.append(box)
        column.addStretch(1)

    def _build_flat(self):
        row = QtWidgets.QHBoxLayout(self.content)
        row.setContentsMargins(MARGIN, 0, MARGIN, 0)
        row.setSpacing(GROUP_GAP)
        for group in self.app.layout.groups:
            # A small column per Group: its header line on top, its tiles in one row under it.
            box = GroupBox(self, group)
            inner = QtWidgets.QVBoxLayout(box)
            inner.setContentsMargins(0, 0, 0, 0)
            inner.setSpacing(2)
            arrow, name, plus = self._header(group)
            header = QtWidgets.QHBoxLayout()
            header.setSpacing(SPACING)
            header.addWidget(arrow)
            header.addWidget(name, 1)
            header.addWidget(plus)
            inner.addLayout(header)
            if not self.app.is_collapsed(group.id) and group.buttons:
                tiles = QtWidgets.QHBoxLayout()
                tiles.setSpacing(SPACING)
                for button in group.buttons:
                    tile = self._tile(button)
                    box.tiles.append(tile)
                    tiles.addWidget(tile)
                tiles.addStretch(1)
                inner.addLayout(tiles)
            inner.addStretch(1)
            row.addWidget(box, 0, QtCore.Qt.AlignmentFlag.AlignTop)
            self.group_boxes.append(box)
        row.addStretch(1)

    # -- dragging -------------------------------------------------------------

    def start_drag(self, tile):
        self.dragging = tile.button
        self.trash.show()
        mime = QtCore.QMimeData()
        mime.setData(MIME_TYPE, QtCore.QByteArray(b"button"))
        drag = QtGui.QDrag(tile)
        drag.setMimeData(mime)
        drag.setPixmap(tile.grab())
        drag.setHotSpot(QtCore.QPoint(tile.width() // 2, tile.height() // 2))
        edge_timer = QtCore.QTimer(self.widget)
        edge_timer.setInterval(EDGE_SCROLL_MS)
        viewport = self.scroll.viewport()
        edge_timer.timeout.connect(lambda: self.edge_scroll_at(viewport.mapFromGlobal(QtGui.QCursor.pos())))
        edge_timer.start()
        try:
            drag.exec(QtCore.Qt.DropAction.MoveAction)
        finally:
            edge_timer.stop()
            edge_timer.deleteLater()
            self.end_drag()

    def edge_scroll_at(self, pos):
        """Scroll when a dragged Button is held near an edge (``pos`` in viewport coordinates)."""
        viewport = self.scroll.viewport()
        width, height = viewport.width(), viewport.height()
        if 0 <= pos.y() < height:
            dx = edge_scroll(pos.x(), width, EDGE_SCROLL_PX, EDGE_SCROLL_STEP)
            bar = self.scroll.horizontalScrollBar()
            bar.setValue(bar.value() + dx)
        if 0 <= pos.x() < width:
            dy = edge_scroll(pos.y(), height, EDGE_SCROLL_PX, EDGE_SCROLL_STEP)
            bar = self.scroll.verticalScrollBar()
            bar.setValue(bar.value() + dy)

    def end_drag(self):
        self.dragging = None
        if _alive(self.trash):
            self.trash.hide()
        if self._render_after_drag:
            self._render_after_drag = False
            self.render()

    # -- changes --------------------------------------------------------------

    def _edit(self, change):
        """Run a Layout change, report a refusal, and show the result."""
        try:
            change()
        except ReadOnlyLayoutError as error:
            self.show_status(str(error))
        except ValueError as error:
            self.show_status(str(error).capitalize() + ".")
        except KeyError:
            log.exception("A Layout change referred to something that is gone")
            self.show_status("That Button or Group is no longer there.")
        except OSError:
            log.exception("Saving the Layout failed")
            self.show_status("The Layout could not be saved. See the log.")
        self.render()

    def move_button(self, button, group_id, index):
        self._edit(lambda: self.app.editor.move_button(button, group_id, index))

    def delete_button(self, button):
        def change():
            pending = self.app.editor.delete_button(button)
            self.undo_label.setText(f"Deleted “{pending.name}”.")
            self.undo_label.show()
            self.undo_button.show()
            self.undo_timer.start()

        self._edit(change)

    def undo_delete(self):
        self.undo_timer.stop()
        self._hide_undo()
        self._edit(self.app.editor.undo_delete)

    def expire_delete(self):
        self._hide_undo()
        self.app.editor.expire_delete()

    def _hide_undo(self):
        self.undo_label.hide()
        self.undo_button.hide()

    def rename_button(self, button):
        name, ok = QtWidgets.QInputDialog.getText(self.widget, "Rename Button", "Name:", text=button.name)
        if ok:
            self._edit(lambda: self.app.editor.rename_button(button, name))

    def toggle_group(self, group):
        self.app.set_group_collapsed(group.id, not self.app.is_collapsed(group.id))
        self.render()

    def new_group(self, index):
        name, ok = QtWidgets.QInputDialog.getText(self.widget, "New Group", "Name:", text="New Group")
        if ok:
            self._edit(lambda: self.app.editor.add_group(name, index))

    def rename_group(self, group):
        name, ok = QtWidgets.QInputDialog.getText(self.widget, "Rename Group", "Name:", text=group.name)
        if ok:
            self._edit(lambda: self.app.editor.rename_group(group.id, name))

    def move_group(self, group, index):
        self._edit(lambda: self.app.editor.move_group(group.id, index))

    def delete_group(self, group):
        self._edit(lambda: self.app.editor.delete_group(group.id))

    # -- right-click menus ----------------------------------------------------

    def button_actions(self, button):
        """The right-click menu of a tile, as ``[(text, enabled, callback or submenu)]``."""
        editable = not self.app.read_only
        others = [g for g in self.app.layout.groups if all(b is not button for b in g.buttons)]
        moves = [(g.name, True, lambda g=g: self.move_button(button, g.id, len(g.buttons))) for g in others]
        return [
            ("Rename…", editable and button.valid, lambda: self.rename_button(button)),
            ("Move to", editable and bool(moves), moves),
            ("Delete", editable, lambda: self.delete_button(button)),
        ]

    def group_actions(self, group):
        """The right-click menu of a Group name, as ``[(text, enabled, callback)]``."""
        editable = not self.app.read_only
        groups = self.app.layout.groups
        index = groups.index(group)
        earlier, later = ("Move left", "Move right") if self.orientation == FLAT else ("Move up", "Move down")
        return [
            ("Rename…", editable, lambda: self.rename_group(group)),
            (earlier, editable and index > 0, lambda: self.move_group(group, index - 1)),
            (later, editable and index < len(groups) - 1, lambda: self.move_group(group, index + 1)),
            ("New Group…", editable, lambda: self.new_group(index + 1)),
            ("Delete Group", editable and not group.buttons, lambda: self.delete_group(group)),
        ]

    def _popup(self, entries, global_pos):
        menu = QtWidgets.QMenu(self.widget)
        self._fill_menu(menu, entries)
        menu.exec(global_pos)
        menu.deleteLater()

    def _fill_menu(self, menu, entries):
        for text, enabled, target in entries:
            if isinstance(target, list):
                sub = menu.addMenu(text)
                sub.setEnabled(enabled)
                self._fill_menu(sub, target)
            else:
                action = menu.addAction(text)
                action.setEnabled(enabled)
                action.triggered.connect(lambda checked=False, t=target: t())

    def button_menu(self, button, global_pos):
        self._popup(self.button_actions(button), global_pos)

    def group_menu(self, group, global_pos):
        self._popup(self.group_actions(group), global_pos)

    # -- teardown -------------------------------------------------------------

    def dispose(self):
        widget, self.widget = self.widget, None
        if widget is not None and isValid(widget):
            self.pen_hover.stop()
            for timer in (self.status_timer, self.undo_timer, self.relayout_timer, self.tile_save_timer):
                timer.stop()
            widget.deleteLater()
