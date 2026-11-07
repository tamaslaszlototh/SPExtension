"""A searchable list of Painter's resources (materials, generators, filters, smart masks,
textures, brushes…), for every Step setting that takes a resource. Generators and
filters cannot be dragged out of the Assets window, so this is how they are chosen."""

from PySide6 import QtCore, QtWidgets

OBJECT_NAME = "ShelfPlusResourcePicker"
SEARCH_DELAY_MS = 250  # Painter is asked once typing pauses


class ResourcePicker(QtWidgets.QDialog):
    def __init__(self, app, title, query="", parent=None):
        super().__init__(parent)
        self.app = app
        self.setObjectName(OBJECT_NAME)
        self.setWindowTitle(title)
        self.resize(420, 480)
        column = QtWidgets.QVBoxLayout(self)
        self.search = QtWidgets.QLineEdit(query)
        self.search.setObjectName(OBJECT_NAME + "Search")
        self.search.setPlaceholderText("Search Painter's resources by name")
        self.search.setClearButtonEnabled(False)  # its clear action would be one more QAction
        column.addWidget(self.search)
        self.list = QtWidgets.QListWidget()
        self.list.setObjectName(OBJECT_NAME + "List")
        self.list.itemDoubleClicked.connect(lambda item: self.accept())
        self.list.currentRowChanged.connect(self._sync_ok)
        column.addWidget(self.list, 1)
        self.empty_label = QtWidgets.QLabel()
        self.empty_label.setObjectName(OBJECT_NAME + "Empty")
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()
        column.addWidget(self.empty_label)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText("Choose")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        column.addWidget(buttons)

        self._found = []
        self.search_timer = QtCore.QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(SEARCH_DELAY_MS)
        self.search_timer.timeout.connect(self.run_search)
        self.search.textChanged.connect(lambda text: self.search_timer.start())
        self.run_search()

    def run_search(self):
        query = self.search.text().strip()
        self._found = self.app.search_resources(query) if query else []
        self.list.clear()
        for resource in self._found:
            text = f"{resource.gui_name} — {resource.kind}" if resource.kind else resource.gui_name
            item = QtWidgets.QListWidgetItem(text)
            item.setToolTip(resource.url)
            self.list.addItem(item)
        if self._found:
            self.list.setCurrentRow(0)
        self.empty_label.setText(
            f"Nothing in Painter matches “{query}”." if query else "Type part of the resource's name."
        )
        self.empty_label.setVisible(not self._found)
        self._sync_ok()

    def _sync_ok(self, *args):
        self.ok_button.setEnabled(self.chosen() is not None)

    def rows(self):
        return [self.list.item(i).text() for i in range(self.list.count())]

    def chosen(self):
        row = self.list.currentRow()
        return self._found[row] if 0 <= row < len(self._found) else None
