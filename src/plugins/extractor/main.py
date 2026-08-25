import logging  # noqa: INP001
import os
import tarfile
import zipfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox, QProgressDialog

from src.core.archive_handler import archive_handler

logger = logging.getLogger(__name__)


def _extract(path, dest, password=None):
    ext = os.path.splitext(path.lower())[1]
    if ext in [".rar", ".7z"]:
        return archive_handler._extract_archive(Path(path), Path(dest), password)  # noqa: SLF001
    if ext == ".zip":
        with zipfile.ZipFile(path, "r") as z:
            if password:
                z.setpassword(password.encode())
            z.extractall(dest)
            return True
    if ext in [".tar", ".gz", ".bz2"]:
        with tarfile.open(path, "r:*") as t:
            t.extractall(dest)
            return True
    return False


def _extract_with_password_prompt(path, dest, parent_window):
    if _extract(path, dest):
        return True
    password, ok = QInputDialog.getText(
        parent_window,
        "Contraseña requerida",
        f"El archivo {os.path.basename(path)} parece protegido"
        " con contraseña.\nIntroduce la contraseña:",
        echo=QLineEdit.EchoMode.Password,
    )
    if not ok:
        return False
    return _extract(path, dest, password)


def register(api):
    pass


def run_extractor(api):
    selected = api.active_panel.get_selected_paths()
    if not selected:
        QMessageBox.warning(
            api.get_parent_window(), "Extractor", "Selecciona al menos un archivo comprimido."
        )
        return

    archives = [p for p in selected if archive_handler.is_archive(p)]
    if not archives:
        QMessageBox.warning(
            api.get_parent_window(),
            "Extractor",
            "Ninguno de los archivos seleccionados es un comprimido soportado.",
        )
        return

    opts = ["Extraer aquí", "Extraer en carpetas separadas"]
    opt, ok = QInputDialog.getItem(
        api.get_parent_window(), "Opciones de Extracción", "Elegir método:", opts, 0, False
    )
    if not ok:
        return

    parent = api.get_parent_window()
    progress = QProgressDialog("Extrayendo archivos...", "Cancelar", 0, len(archives), parent)
    progress.setWindowTitle("Extractor Multi-formato")
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(500)

    count = 0
    for i, archive_path in enumerate(archives):
        progress.setValue(i)
        progress.setLabelText(f"Extrayendo: {os.path.basename(archive_path)}")
        if progress.wasCanceled():
            QMessageBox.information(parent, "Cancelado", "Extracción cancelada por el usuario.")
            return
        try:
            dest = api.active_panel.current_path
            if opt == opts[1]:
                folder_name = os.path.splitext(os.path.basename(archive_path))[0]
                dest = os.path.join(dest, folder_name)
                os.makedirs(dest, exist_ok=True)
            if _extract_with_password_prompt(archive_path, dest, parent):
                count += 1
        except Exception as e:  # noqa: BLE001
            logger.debug("Error extrayendo %s: %s", archive_path, e)

    progress.setValue(len(archives))
    QMessageBox.information(parent, "Completado", f"Se han extraído {count} archivos con éxito.")
    api.active_panel.refresh()
