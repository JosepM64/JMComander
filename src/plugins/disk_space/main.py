import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from src.core.fs_utils import safe_delete


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


@dataclass
class FolderSize:
    path: str
    name: str
    size: int
    is_drive_root: bool = False


class FolderSizeWorker(QThread):
    """Worker en segon pla que calcula mides de carpetes directes d'un directori."""
    progress = Signal(str, int)  # status text, folders_scanned
    folder_found = Signal(FolderSize)  # emitted per folder for incremental UI
    finished = Signal(list)  # list of FolderSize
    error = Signal(str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        try:
            results = []
            folders_scanned = 0

            # Check if it's a drive root (e.g., C:\, D:\)
            is_drive_root = len(Path(self.path).parts) <= 1

            # Use os.scandir for speed
            with os.scandir(self.path) as it:
                for entry in it:
                    if self.is_cancelled:
                        self.finished.emit([])
                        return

                    if entry.is_dir(follow_symlinks=False):
                        try:
                            # Calculate size recursively (non-blocking check)
                            size = self._get_folder_size(entry.path)
                            fs = FolderSize(
                                path=entry.path,
                                name=entry.name,
                                size=size,
                                is_drive_root=is_drive_root,
                            )
                            results.append(fs)
                            self.folder_found.emit(fs)
                        except (OSError, PermissionError):
                            # Skip folders we can't access
                            pass
                        folders_scanned += 1
                        self.progress.emit(f"Escaneando: {entry.name}", folders_scanned)

            self.finished.emit(results)

        except Exception as e:  # noqa: BLE001
            self.error.emit(f"Error escaneant {self.path}: {e!s}")

    def _get_folder_size(self, path: str) -> int:
        """Calcula la mida total d'una carpeta (recursiu)."""
        total = 0
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if self.is_cancelled:
                        return total
                    try:
                        if entry.is_file(follow_symlinks=False):
                            total += entry.stat().st_size
                        elif entry.is_dir(follow_symlinks=False):
                            total += self._get_folder_size(entry.path)
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            pass
        return total


class DeleteFoldersWorker(QThread):
    """Esborra carpetes en segon pla (paperera o permanent) sense bloquejar la UI."""
    finished = Signal(int, list)  # deleted_count, errors
    error = Signal(str)

    def __init__(self, paths: list, use_trash: bool):
        super().__init__()
        self.paths = paths
        self.use_trash = use_trash
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        if self.is_cancelled:
            self.finished.emit(0, [])
            return
            
        deleted = 0
        errors = []
        for path in self.paths:
            if self.is_cancelled:
                break
            try:
                safe_delete(path, use_trash=self.use_trash)
                deleted += 1
            except Exception as e:  # noqa: BLE001
                errors.append(f"{path}: {e!s}")
        self.finished.emit(deleted, errors)


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


def _format_size(bytes_val: int) -> str:
    """Format bytes to human readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024 or unit == "TB":
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"


class DiskSpaceDialog(QDialog):
    """Diàleg amb vista d'arbre per drill-down de carpetes (estil WizTree/WinDirStat)."""
    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path
        self.current_path = path
        self.worker: Optional[FolderSizeWorker] = None
        self.setWindowTitle(f"Espacio en Disco - {path}")
        self.resize(900, 600)

        layout = QVBoxLayout(self)

        # Path bar with back button
        path_bar = QHBoxLayout()
        self.btn_back = QPushButton("← Subir")
        self.btn_back.clicked.connect(self.go_up)
        self.btn_back.setEnabled(False)
        path_bar.addWidget(self.btn_back)

        self.lbl_current_path = QLabel(path)
        self.lbl_current_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_bar.addWidget(self.lbl_current_path, 1)
        layout.addLayout(path_bar)

        # Tree widget for folders with sizes
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Carpeta", "Mida", "%"])
        self.tree.setColumnWidth(0, 500)
        self.tree.setColumnWidth(1, 120)
        self.tree.setColumnWidth(2, 60)
        self.tree.setSortingEnabled(True)
        self.tree.itemDoubleClicked.connect(self.on_folder_double_clicked)
        self.tree.itemSelectionChanged.connect(self.on_selection_changed)
        # Mejorar contraste de selección (más visible)
        self.tree.setStyleSheet("""
        QTreeWidget::item:selected {
            background-color: #005a9e;
            color: white;
        }
        """)
        layout.addWidget(self.tree)

        # Progress
        self.lbl_status = QLabel("Preparat per escanejar")
        layout.addWidget(self.lbl_status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Indeterminate while scanning
        layout.addWidget(self.progress)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_scan = QPushButton("Escanear")
        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.cancel_scan)
        self.btn_cancel.setEnabled(False)
        self.btn_open = QPushButton("Obrir al Explorador")
        self.btn_open.clicked.connect(self.open_selected)
        self.btn_open.setEnabled(False)
        self.btn_delete_trash = QPushButton("Eliminar (Paperera)")
        self.btn_delete_trash.clicked.connect(lambda: self.delete_selected(use_trash=True))
        self.btn_delete_trash.setEnabled(False)
        self.btn_delete_trash.setToolTip("Mou les carpetes seleccionades a la paperera.")
        self.btn_delete_permanent = QPushButton("Eliminar Permanent")
        self.btn_delete_permanent.clicked.connect(lambda: self.delete_selected(use_trash=False))
        self.btn_delete_permanent.setEnabled(False)
        self.btn_delete_permanent.setToolTip(
            "Esborra definitivament les carpetes seleccionades (sense paperera). Dooble confirmació."
        )
        btn_layout.addWidget(self.btn_scan)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_open)
        btn_layout.addWidget(self.btn_delete_trash)
        btn_layout.addWidget(self.btn_delete_permanent)
        layout.addLayout(btn_layout)

        self.delete_worker: DeleteFoldersWorker | None = None

        # Auto-start scan
        self.start_scan()

    def start_scan(self):
        # Cancel any ongoing scan
        if self.worker and self.worker.isRunning():
            self.worker.cancel()

        self.btn_scan.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_open.setEnabled(False)
        self.tree.clear()
        self.progress.setRange(0, 0)
        self.lbl_status.setText(f"Escanejant {self.current_path}...")

        # Create worker and assign to self.worker
        worker = FolderSizeWorker(self.current_path)
        self.worker = worker
        self.worker.folder_found.connect(self.on_folder_found)
        self.worker.finished.connect(lambda results: self.on_scan_finished(worker, results))
        self.worker.error.connect(lambda msg: self.on_scan_error(msg, worker))
        self.worker.progress.connect(lambda t, v: self.lbl_status.setText(t))
        self.worker.start()

    def cancel_scan(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.lbl_status.setText("Escaneig cancel·lat")
            self.btn_scan.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.progress.setRange(0, 100)
            self.progress.setValue(0)

    def on_folder_found(self, fs: FolderSize):
        """Afegir carpeta a l'arbre incrementalment."""
        item = QTreeWidgetItem([
            fs.name,
            _format_size(fs.size),
            ""  # percentage filled later
        ])
        item.setData(0, Qt.ItemDataRole.UserRole, fs.path)
        item.setData(1, Qt.ItemDataRole.UserRole, fs.size)
        self.tree.addTopLevelItem(item)

    def on_scan_finished(self, worker, results: list):
        """Calcular percentatges i habilitar UI."""
        # Only proceed if this worker is still the current one
        if self.worker is not worker:
            return

        total_size = sum(fs.size for fs in results)
        if total_size > 0:
            for i in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(i)
                size = item.data(1, Qt.ItemDataRole.UserRole)
                pct = (size / total_size) * 100
                item.setText(2, f"{pct:.1f}%")

        self.lbl_status.setText(f"Completat: {self.tree.topLevelItemCount()} carpetes, total {_format_size(total_size)}")
        self.btn_scan.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_open.setEnabled(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.worker = None

    def on_scan_error(self, worker, msg: str):
        self.lbl_status.setText(f"Error: {msg}")
        self.btn_scan.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        # Only clear worker if it's the same one
        if self.worker is worker:
            self.worker = None

    def on_folder_double_clicked(self, item: QTreeWidgetItem, _column: int):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.isdir(path):
            self.drill_down(path)

    def drill_down(self, path: str):
        self.current_path = path
        self.lbl_current_path.setText(path)
        self.btn_back.setEnabled(True)
        self.start_scan()

    def go_up(self):
        parent = os.path.dirname(self.current_path)
        if parent and parent != self.current_path:
            self.current_path = parent
            self.lbl_current_path.setText(parent)
            self.btn_back.setEnabled(parent != self.path)
            self.start_scan()

    def on_selection_changed(self):
        selected = self.tree.selectedItems()
        has_selection = bool(selected)
        self.btn_open.setEnabled(has_selection)
        self.btn_delete_trash.setEnabled(has_selection)
        self.btn_delete_permanent.setEnabled(has_selection)

    def open_selected(self):
        selected = self.tree.selectedItems()
        if selected:
            path = selected[0].data(0, Qt.ItemDataRole.UserRole)
            if path and os.path.exists(path):
                subprocess.Popen(f'explorer "{path}"', shell=True)

    def delete_selected(self, use_trash: bool):
        """Esborra les carpetes seleccionades (paperera o permanent)."""
        selected = self.tree.selectedItems()
        paths = [
            item.data(0, Qt.ItemDataRole.UserRole)
            for item in selected
            if item.data(0, Qt.ItemDataRole.UserRole) and os.path.exists(item.data(0, Qt.ItemDataRole.UserRole))
        ]
        if not paths:
            return

        if use_trash:
            confirm_btn = QMessageBox.question(
                self,
                "Eliminar a la Paperera",
                f"¿Moure {len(paths)} carpeta(es) a la paperera?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm_btn != QMessageBox.StandardButton.Yes:
                return
            self._run_delete(paths, use_trash=True)
            return

        # Permanent: doble confirmació
        first = QMessageBox.warning(
            self,
            "Eliminar Permanentment",
            f"AVÍS: Esborraràs {len(paths)} carpeta(es) DEFINITIVAMENT (sense paperera).\n\n"
            "Aquesta acció no es pot desfer. ¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if first != QMessageBox.StandardButton.Yes:
            return
        second = QMessageBox.warning(
            self,
            "Confirmar Eliminació Permanent",
            "¿Segur que vols esborrar-ho PERMANENTMENT? Aquesta és la darrera oportunitat.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if second != QMessageBox.StandardButton.Yes:
            return
        self._run_delete(paths, use_trash=False)

    def _run_delete(self, paths: list, use_trash: bool):
        """Llança el borrat en segon pla i desactiva la UI fins a acabar."""
        self.delete_worker = DeleteFoldersWorker(paths, use_trash)
        self.delete_worker.finished.connect(self.on_delete_finished)
        self.delete_worker.error.connect(lambda msg: self.lbl_status.setText(f"Error: {msg}"))
        self._set_delete_buttons_enabled(False)
        self.lbl_status.setText("Esborrant carpetes...")
        self.progress.setRange(0, 0)
        self.delete_worker.start()

    def on_delete_finished(self, deleted: int, errors: list):
        self.delete_worker = None
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        if errors:
            QMessageBox.warning(
                self,
                "Error en esborrar",
                f"S'han esborrat {deleted} carpeta(es).\n\nNo s'han pogut esborrar:\n"
                + "\n".join(errors[:20]),
            )
        self.lbl_status.setText(f"Esborrat completat: {deleted} carpeta(es).")
        self._set_delete_buttons_enabled(True)
        # Actualitzar el tree (re-escanejar el directori actual)
        self.start_scan()

    def _set_delete_buttons_enabled(self, enabled: bool):
        self.btn_delete_trash.setEnabled(enabled)
        self.btn_delete_permanent.setEnabled(enabled)
        self.btn_scan.setEnabled(enabled)
        self.btn_cancel.setEnabled(not enabled)
        self.btn_open.setEnabled(enabled)
        self.btn_back.setEnabled(enabled)


def register(api):
    pass


def run_disk_space(api):
    path = api.active_panel.current_path
    # Pujar a l'arrel del disc per obtenir una vista global de la unitat activa
    drive, _ = os.path.splitdrive(path)
    root = drive + os.sep if drive else path
    dlg = DiskSpaceDialog(root, api.get_parent_window())
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dlg.show()


def run_empty_folders(api):
    dlg = FolderSearchDialog(api.active_panel.current_path, "empty", api.get_parent_window())
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dlg.show()


def run_duplicate_folders(api):
    dlg = FolderSearchDialog(api.active_panel.current_path, "duplicate", api.get_parent_window())
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dlg.show()
