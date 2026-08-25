import os  # noqa: INP001
import shutil
import subprocess

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class EmptyFoldersWorker(QThread):
    progress = Signal(str, int)
    finished = Signal(list)

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        empty_folders = []
        total_dirs = 0

        for root, dirs, files in os.walk(self.path):
            if self.is_cancelled:
                self.finished.emit([])
                return
            total_dirs += 1  # noqa: SIM113
            if not files and not dirs:
                empty_folders.append(root)
                self.progress.emit(f"Verificando: {root}", len(empty_folders))

        self.finished.emit(empty_folders)


class DuplicateFoldersWorker(QThread):
    progress = Signal(str, int)
    finished = Signal(dict)

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        folder_names = {}

        for root, dirs, _files in os.walk(self.path):
            if self.is_cancelled:
                self.finished.emit({})
                return
            for d in dirs:
                full_path = os.path.join(root, d)
                folder_names.setdefault(d.lower(), []).append(full_path)
                self.progress.emit(f"Escaneando: {full_path}", len(folder_names))

        duplicates = {name: paths for name, paths in folder_names.items() if len(paths) > 1}
        self.finished.emit(duplicates)


class FolderSearchDialog(QDialog):
    def __init__(self, path, mode, parent=None):
        super().__init__(parent)
        self.path = path
        self.mode = mode
        self.setWindowTitle(
            "Buscar Carpetas Vacías" if mode == "empty" else "Buscar Carpetas Duplicadas"
        )
        self.resize(700, 500)

        layout = QVBoxLayout(self)

        self.lbl_status = QLabel("Preparado")
        layout.addWidget(self.lbl_status)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        self.list_results = QListWidget()
        layout.addWidget(self.list_results)

        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("Empezar Escaneo")
        self.btn_start.clicked.connect(self.start_scan)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.cancel_scan)
        self.btn_cancel.setEnabled(False)
        self.btn_delete = QPushButton("Eliminar Seleccionadas")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_open = QPushButton("Abrir Carpeta")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self.open_folder)
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_open)
        layout.addLayout(btn_layout)

        self.list_results.itemSelectionChanged.connect(self.on_selection_changed)
        self.list_results.itemDoubleClicked.connect(self.on_double_click)

    def on_double_click(self, item):
        path = item.text()
        if os.path.exists(path):
            folder = os.path.dirname(path)
            subprocess.Popen(f'explorer "{folder}"', shell=True)

    def start_scan(self):
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_delete.setEnabled(False)
        self.list_results.clear()

        if self.mode == "empty":
            self.worker = EmptyFoldersWorker(self.path)
        else:
            self.worker = DuplicateFoldersWorker(self.path)

        self.worker.progress.connect(
            lambda t, v: (self.lbl_status.setText(t), self.progress.setValue(v))
        )
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def cancel_scan(self):
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.cancel()
            self.lbl_status.setText("Escaneo cancelado por el usuario.")
            self.btn_start.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.progress.setValue(0)

    def _on_finished(self, results):
        if self.mode == "empty":
            self.lbl_status.setText(
                f"Escaneo finalizado. {len(results)} carpetas vacías encontradas."
            )
            for folder in results:
                item = QListWidgetItem(folder)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.list_results.addItem(item)
        else:
            self.lbl_status.setText(
                f"Escaneo finalizedo. {len(results)} grupos de nombres duplicados."
            )
            for name, paths in results.items():
                item = QListWidgetItem(f"Nombre: {name} ({len(paths)} carpetas)")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                item.setBackground(Qt.GlobalColor.lightGray)
                self.list_results.addItem(item)
                for p in paths:
                    child = QListWidgetItem(p)
                    child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    child.setCheckState(Qt.CheckState.Unchecked)
                    self.list_results.addItem(child)

        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_delete.setEnabled(True)
        self.btn_open.setEnabled(True)

    def on_selection_changed(self):
        selected = self.list_results.selectedItems()
        if selected:
            text = selected[0].text()
            if os.path.exists(text):
                self.btn_open.setEnabled(True)
            else:
                self.btn_open.setEnabled(False)
        else:
            self.btn_open.setEnabled(False)

    def open_folder(self):
        selected = self.list_results.selectedItems()
        if selected:
            path = selected[0].text()
            if os.path.exists(path):
                subprocess.Popen(f'explorer "{path}"', shell=True)

    def delete_selected(self):
        to_delete = [
            self.list_results.item(i).text()
            for i in range(self.list_results.count())
            if self.list_results.item(i).checkState() == Qt.CheckState.Checked
            and os.path.exists(self.list_results.item(i).text())
        ]
        if (
            to_delete
            and QMessageBox.question(self, "Eliminar", f"¿Eliminar {len(to_delete)} carpetas?")
            == QMessageBox.StandardButton.Yes
        ):
            for p in to_delete:
                try:
                    shutil.rmtree(p)
                except Exception as e:  # noqa: BLE001
                    QMessageBox.warning(self, "Error", f"No se pudo eliminar: {p}\n{e!s}")
            self.accept()


def register(api):
    pass


def run_disk_space(api):
    path = api.active_panel.current_path
    total, used, free = shutil.disk_usage(path)
    gb = 1024**3
    msg = (
        f"Ubicación: {path}\n\n"
        f"Total: {total / gb:.2f} GB\n"
        f"Usado: {used / gb:.2f} GB\n"
        f"Libre: {free / gb:.2f} GB"
    )
    QMessageBox.information(api.get_parent_window(), "Espacio en Disco", msg)


def run_empty_folders(api):
    dlg = FolderSearchDialog(api.active_panel.current_path, "empty", api.get_parent_window())
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dlg.show()


def run_duplicate_folders(api):
    dlg = FolderSearchDialog(api.active_panel.current_path, "duplicate", api.get_parent_window())
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dlg.show()
