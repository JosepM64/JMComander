from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class BookmarkEditDialog(QDialog):
    """Diálogo para editar nombre y ruta de un marcador"""

    def __init__(self, name, path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Marcador")
        self.resize(400, 150)

        self.result_name = name
        self.result_path = path

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Campo Nombre
        self.input_name = QLineEdit(name)
        form_layout.addRow("Nombre:", self.input_name)

        # Campo Ruta + Botón Browse
        path_layout = QHBoxLayout()
        self.input_path = QLineEdit(path)
        btn_browse = QPushButton("...")
        btn_browse.setFixedWidth(30)
        btn_browse.clicked.connect(self.browse_path)

        path_layout.addWidget(self.input_path)
        path_layout.addWidget(btn_browse)

        form_layout.addRow("Ruta:", path_layout)
        layout.addLayout(form_layout)

        # Botones OK/Cancel
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def browse_path(self):
        d = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta", self.input_path.text())
        if d:
            self.input_path.setText(d)

    def accept(self):
        self.result_name = self.input_name.text()
        self.result_path = self.input_path.text()
        super().accept()


class BookmarksEditor(QDialog):
    def __init__(self, bookmark_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gestionar Marcadores")
        self.resize(500, 350)
        self.bm_manager = bookmark_manager

        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        # Botones de Acción
        btn_layout = QHBoxLayout()

        self.btn_edit = QPushButton("Editar")
        self.btn_edit.clicked.connect(self.edit_item)

        self.btn_delete = QPushButton("Eliminar")
        self.btn_delete.clicked.connect(self.delete_item)

        self.btn_up = QPushButton("Subir")
        self.btn_up.clicked.connect(self.move_up)

        self.btn_down = QPushButton("Bajar")
        self.btn_down.clicked.connect(self.move_down)

        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_up)
        btn_layout.addWidget(self.btn_down)

        layout.addLayout(btn_layout)

        # Botón Cerrar
        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.accept)
        layout.addWidget(self.btn_close)

        self.load_list()

    def load_list(self):
        self.list_widget.clear()
        for bm in self.bm_manager.get_all():
            # Mostramos Nombre y Ruta para que sea claro
            self.list_widget.addItem(f"{bm['name']}  [{bm['path']}]")

    def get_selected_index(self):
        row = self.list_widget.currentRow()
        if row < 0:
            return -1
        return row

    def edit_item(self):
        idx = self.get_selected_index()
        if idx == -1:
            return

        bm = self.bm_manager.get_all()[idx]

        # Abrir diálogo personalizado
        dlg = BookmarkEditDialog(bm["name"], bm["path"], self)
        if dlg.exec():
            # Guardar cambios
            self.bm_manager.update_bookmark(idx, dlg.result_name, dlg.result_path)
            self.load_list()
            self.list_widget.setCurrentRow(idx)

    def delete_item(self):
        idx = self.get_selected_index()
        if idx == -1:
            return

        if (
            QMessageBox.question(
                self,
                "Eliminar",
                "¿Borrar marcador?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            self.bm_manager.remove_bookmark(idx)
            self.load_list()

    def move_up(self):
        idx = self.get_selected_index()
        if self.bm_manager.move_up(idx):
            self.load_list()
            self.list_widget.setCurrentRow(idx - 1)

    def move_down(self):
        idx = self.get_selected_index()
        if self.bm_manager.move_down(idx):
            self.load_list()
            self.list_widget.setCurrentRow(idx + 1)
