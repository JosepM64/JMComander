import os  # noqa: INP001
import shutil
import subprocess
import zipfile

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
)

from src.core.archive_handler import archive_handler


class CompressorDialog(QDialog):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Comprimir Archivos")
        self.resize(400, 200)
        self.items = items

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Comprimiendo {len(items)} elementos."))
        layout.addWidget(QLabel("Nombre del archivo:"))
        self.input_name = QLineEdit("archivo_comprimido")
        layout.addWidget(self.input_name)
        layout.addWidget(QLabel("Formato:"))
        self.combo_format = QComboBox()
        self.combo_format.addItems(["zip", "tar", "gztar", "rar", "7z"])
        layout.addWidget(self.combo_format)
        btn = QPushButton("Comprimir")
        btn.clicked.connect(self.compress)
        layout.addWidget(btn)

    def _count_files(self, items):
        total = 0
        for item in items:
            if os.path.isdir(item):
                for _root, _dirs, files in os.walk(item):
                    total += len(files)
            else:
                total += 1
        return total

    def compress(self):
        name = self.input_name.text()
        fmt = self.combo_format.currentText()
        if not name:
            return
        base_dir = os.path.dirname(self.items[0])
        output_filename = os.path.join(base_dir, name)

        # Progress dialog
        total_files = self._count_files(self.items)
        progress = QProgressDialog(
            "Comprimiendo archivos...", "Cancelar", 0, total_files, self
        )
        progress.setWindowTitle("Compresión")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(500)

        def make_process_fn(item, fmt, progress, output_filename):
            def process(item):
                if os.path.isdir(item):
                    for root, _dirs, files in os.walk(item):
                        for file in files:
                            if progress.wasCanceled():
                                progress.close()
                                QMessageBox.information(
                                    self, "Cancelado", "Compresión cancelada."
                                )
                                raise StopIteration
                            zf.write(
                                os.path.join(root, file),
                                os.path.relpath(
                                    os.path.join(root, file), os.path.dirname(item)
                                ),
                            )
                else:
                    if progress.wasCanceled():
                        progress.close()
                        QMessageBox.information(self, "Cancelado", "Compresión cancelada.")
                        raise StopIteration
                    zf.write(item, os.path.basename(item))
            return process

        try:
            if fmt == "zip":
                full_output = f"{output_filename}.zip"
                with zipfile.ZipFile(full_output, "w", zipfile.ZIP_DEFLATED) as zf:
                    progress.setLabelText("Iniciando compresión ZIP...")
                    archive_handler._progress_cancel_loop(
                        progress,
                        self.items,
                        make_process_fn("", fmt, progress, full_output),
                    )
                progress.setValue(total_files)
                progress.close()
                QMessageBox.information(self, "Éxito", f"Creado: {full_output}")
                self.accept()

            elif fmt == "tar":
                if len(self.items) == 1 and os.path.isdir(self.items[0]):
                    progress.setLabelText("Comprimiendo carpeta TAR...")
                    progress.setRange(0, 0)
                    progress.setValue(0)
                    shutil.make_archive(
                        output_filename, "tar", self.items[0]
                    )
                    progress.setValue(0)
                    progress.close()
                    QMessageBox.information(self, "Éxito", f"Creado: {output_filename}.tar")
                    self.accept()
                else:
                    QMessageBox.warning(
                        self, "Aviso", "Para TAR selecciona una sola carpeta."
                    )

            elif fmt == "gztar":
                if len(self.items) == 1 and os.path.isdir(self.items[0]):
                    progress.setLabelText("Comprimiendo gztar...")
                    progress.setRange(0, 0)
                    progress.setValue(0)
                    shutil.make_archive(
                        output_filename, "gztar", self.items[0]
                    )
                    progress.setValue(0)
                    progress.close()
                    QMessageBox.information(self, "Éxito", f"Creado: {output_filename}.tar.gz")
                    self.accept()
                else:
                    QMessageBox.warning(
                        self, "Aviso", "Para GZTAR selecciona una sola carpeta."
                    )

            elif fmt == "rar":
                full_output = f"{output_filename}.rar"
                # NOTA: rarfile 4.x no pot crear arxius ("RarFile supports only mode=r")
                # i el UnRAR.exe gratuït inclòs a assets/ SOLAMENT extreu.
                # Crear RAR requereix WinRAR.exe / RAR.exe.
                rar_creator = archive_handler._find_rar_creator()
                if not rar_creator:
                    progress.close()
                    QMessageBox.critical(
                        self,
                        "Error",
                        "No hay ningún motor de creación RAR disponible.\n\n"
                        "El UnRAR.exe incluido sólo puede extraer archivos.\n"
                        "Instala WinRAR para poder crear archivos .rar.",
                    )
                    return
                try:
                    cmd = [rar_creator, "a", "-y", "-ep1", full_output, *self.items]
                    progress.setLabelText("Comprimiendo con RAR...")
                    if progress.wasCanceled():
                        progress.close()
                        return
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        timeout=300,
                        check=False,
                        creationflags=(
                            subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                        ),
                    )
                    progress.setValue(total_files)
                    progress.close()
                    if result.returncode == 0 and os.path.exists(full_output):
                        QMessageBox.information(self, "Éxito", f"Creado: {full_output}")
                        self.accept()
                    else:
                        stderr = (result.stderr or b"")[:300].decode(errors="replace")
                        QMessageBox.critical(
                            self,
                            "Error",
                            f"No se pudo crear el archivo RAR (código {result.returncode}).\n{stderr}",
                        )
                except Exception as e:
                    progress.close()
                    QMessageBox.critical(self, "Error", f"Error compressing RAR: {e}")

            elif fmt == "7z":
                full_output = f"{output_filename}.7z"
                seven_zip_exe = archive_handler.SEVEN_ZIP_EXE
                if seven_zip_exe:
                    # Utilitzar 7z.exe CLI
                    cmd = [seven_zip_exe, "a", "-y", "-t7z", full_output, *self.items]
                    progress.setLabelText("Comprimiendo con 7z.exe...")
                    result = None
                    if not progress.wasCanceled():
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            timeout=600,
                            check=False,
                            creationflags=(
                                subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                            ),
                        )
                    progress.setValue(total_files if total_files > 0 else 0)
                    progress.close()
                    if result is not None and result.returncode == 0 and os.path.exists(full_output):
                        QMessageBox.information(self, "Éxito", f"Creado: {full_output}")
                        self.accept()
                    else:
                        rc = result.returncode if result is not None else "cancelado"
                        stderr = (
                            (result.stderr or b"")[:300].decode(errors="replace")
                            if result is not None
                            else ""
                        )
                        QMessageBox.critical(
                            self, "Error", f"No se pudo crear el archivo 7z (código {rc}).\n{stderr}"
                        )
                else:
                    # Fallback: intentar py7zr si està disponible
                    try:
                        import py7zr

                        with py7zr.SevenZipFile(full_output, "w") as sz:
                            archive_handler._progress_cancel_loop(
                                progress,
                                self.items,
                                lambda item: sz.write(item),  # noqa: PLW0108
                            )
                        progress.setValue(total_files)
                        progress.close()
                        QMessageBox.information(self, "Éxito", f"Creado: {full_output}")
                        self.accept()
                    except ImportError:
                        QMessageBox.critical(
                            self,
                            "Error",
                            "No available 7-Zip engine (neither 7z.exe nor py7zr).",
                        )

            else:
                QMessageBox.warning(self, "Aviso", f"Formato {fmt} no soportado.")

        except StopIteration:
            progress.close()
            QMessageBox.information(self, "Cancelado", "Compresión cancelada.")
        except Exception:
            QMessageBox.critical(self, "Error", "Error inesperado durante la compresión.")


def register(api):
    pass


def run_compressor(api):
    items = api.active_panel.get_selected_paths()
    if not items:
        QMessageBox.warning(api.get_parent_window(), "Aviso", "Selecciona archivos.")
        return
    dlg = CompressorDialog(items, api.get_parent_window())
    dlg.exec()
    api.active_panel.refresh()
