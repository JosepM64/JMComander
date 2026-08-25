import os

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class AppEditDialog(QDialog):
    def __init__(self, name, path, args, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Aplicación")
        self.resize(520, 220)

        self.result_name = name
        self.result_path = path
        self.result_args = args

        layout = QVBoxLayout(self)

        info_label = QLabel("Selecciona el ejecutable (.exe, .bat, .cmd, .vbs) de la aplicación:")
        layout.addWidget(info_label)

        form_layout = QFormLayout()

        self.input_name = QLineEdit(name)
        self.input_name.setPlaceholderText("Nombre que aparecerá en el menú")
        self.input_name.setEnabled(True)
        self.input_name.setReadOnly(False)
        form_layout.addRow("Nombre:", self.input_name)

        path_layout = QHBoxLayout()
        self.input_path = QLineEdit(path)
        self.input_path.setPlaceholderText("Ruta al ejecutable (.exe, .bat, .cmd, .vbs)")
        btn_browse = QPushButton("...")
        btn_browse.setFixedWidth(30)
        btn_browse.clicked.connect(self.browse_path)

        path_layout.addWidget(self.input_path)
        path_layout.addWidget(btn_browse)

        form_layout.addRow("Ejecutable:", path_layout)

        self.input_args = QLineEdit(args)
        self.input_args.setPlaceholderText("Opcional: argumentos de línea de comandos")
        form_layout.addRow("Argumentos:", self.input_args)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
        QTimer.singleShot(50, lambda: (self.input_name.setFocus(), self.input_name.selectAll()))

    def browse_path(self):
        d = QFileDialog.getOpenFileName(
            self,
            "Seleccionar Ejecutable",
            self.input_path.text(),
            "Ejecutables (*.exe *.bat *.cmd *.vbs);;Todos los archivos (*.*)",
        )
        if d and d[0]:
            self.input_path.setText(d[0])
            # Auto-fill name if empty
            if not self.input_name.text():
                self.input_name.setText(os.path.splitext(os.path.basename(d[0]))[0])

    def accept(self):
        self.result_name = self.input_name.text().strip()
        self.result_path = self.input_path.text().strip()
        self.result_args = self.input_args.text().strip()

        if not self.result_name:
            QMessageBox.warning(self, "Error", "El nombre es obligatorio")
            return
        if not self.result_path:
            QMessageBox.warning(self, "Error", "El ejecutable es obligatorio")
            return

        super().accept()


class AppLauncherEditor(QDialog):
    def __init__(self, app_launcher, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gestionar Aplicaciones")
        self.resize(550, 400)
        self.app_launcher = app_launcher

        layout = QVBoxLayout(self)

        info_label = QLabel("Añade programas para ejecutarlos rápidamente desde JMComander:")
        layout.addWidget(info_label)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()

        self.btn_add = QPushButton("Añadir")
        self.btn_add.clicked.connect(self.add_item)

        self.btn_edit = QPushButton("Editar")
        self.btn_edit.clicked.connect(self.edit_item)

        self.btn_delete = QPushButton("Eliminar")
        self.btn_delete.clicked.connect(self.delete_item)

        self.btn_up = QPushButton("Subir")
        self.btn_up.clicked.connect(self.move_up)

        self.btn_down = QPushButton("Bajar")
        self.btn_down.clicked.connect(self.move_down)

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_up)
        btn_layout.addWidget(self.btn_down)

        layout.addLayout(btn_layout)

        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.accept)
        layout.addWidget(self.btn_close)

        self.load_list()

    def load_list(self):
        self.list_widget.clear()
        for app in self.app_launcher.get_all():
            display = f"{app['name']}  [{app['path']}]"
            if app.get("args"):
                display += f" {app['args']}"
            self.list_widget.addItem(display)

    def get_selected_index(self):
        row = self.list_widget.currentRow()
        if row < 0:
            return -1
        return row

    def add_item(self):
        dlg = AppEditDialog("", "", "", self)
        if dlg.exec():
            self.app_launcher.add_app(dlg.result_name, dlg.result_path, dlg.result_args)
            self.load_list()

    def edit_item(self):
        idx = self.get_selected_index()
        if idx == -1:
            QMessageBox.information(self, "Editar", "Selecciona una aplicación de la lista")
            return

        app = self.app_launcher.get_all()[idx]

        dlg = AppEditDialog(app["name"], app["path"], app.get("args", ""), self)
        if dlg.exec():
            self.app_launcher.update_app(idx, dlg.result_name, dlg.result_path, dlg.result_args)
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
                "¿Borrar esta aplicación?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            self.app_launcher.remove_app(idx)
            self.load_list()

    def move_up(self):
        idx = self.get_selected_index()
        if self.app_launcher.move_up(idx):
            self.load_list()
            self.list_widget.setCurrentRow(idx - 1)

    def move_down(self):
        idx = self.get_selected_index()
        if self.app_launcher.move_down(idx):
            self.load_list()
            self.list_widget.setCurrentRow(idx + 1)
