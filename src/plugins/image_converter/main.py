import os

from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_SUPPORT = True
except ImportError:
    pillow_heif = None
    HEIF_SUPPORT = False

from src.core.plugin_settings import load_settings, save_settings


class ImageConverterWorker(QThread):
    progress = Signal(int, int, str)
    finished = Signal(int, int, list)
    error = Signal(str)

    def __init__(
        self,
        files,
        output_dir,
        format,  # noqa: A002
        quality,
        resize_width,
        resize_height,
        maintain_ratio,
        preserve_original,
        parent=None,
    ):
        super().__init__(parent)
        self.files = files
        self.output_dir = output_dir
        self.format = format
        self.quality = quality
        self.resize_width = resize_width
        self.resize_height = resize_height
        self.maintain_ratio = maintain_ratio
        self.preserve_original = preserve_original
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        converted = 0
        errors = []
        total = len(self.files)

        for i, src_path in enumerate(self.files):
            if self.is_cancelled:
                break

            try:
                self.progress.emit(i + 1, total, os.path.basename(src_path))

                img = Image.open(src_path)

                # Calculate target dimensions respecting aspect ratio if requested
                orig_w, orig_h = img.size
                target_w = self.resize_width
                target_h = self.resize_height

                if self.maintain_ratio and (target_w > 0 or target_h > 0):
                    if target_w > 0 and target_h == 0:
                        # Width specified, calculate height from ratio
                        target_h = int(orig_h * target_w / orig_w)
                    elif target_h > 0 and target_w == 0:
                        # Height specified, calculate width from ratio
                        target_w = int(orig_w * target_h / orig_h)
                    # If both > 0, use as-is (user explicitly set both)

                if target_w > 0 and target_h > 0:
                    img = img.resize(
                        (target_w, target_h), Image.Resampling.LANCZOS
                    )

                if self.preserve_original:
                    name = os.path.splitext(os.path.basename(src_path))[0]
                    ext = self._get_output_ext()
                    dst_path = os.path.join(self.output_dir, f"{name}_conv.{ext}")
                else:
                    dst_path = os.path.join(self.output_dir, os.path.basename(src_path))

                counter = 1
                base_dst = dst_path
                while os.path.exists(dst_path):
                    name = os.path.splitext(os.path.basename(base_dst))[0]
                    ext = os.path.splitext(base_dst)[1]
                    dst_path = os.path.join(self.output_dir, f"{name}_{counter}{ext}")
                    counter += 1

                save_kwargs = {"format": self.format}
                if self.format in ("JPEG", "WEBP"):
                    save_kwargs["quality"] = self.quality
                    if self.format == "JPEG":
                        img = img.convert("RGB")

                img.save(dst_path, **save_kwargs)
                converted += 1

            except Exception as e:  # noqa: BLE001
                errors.append(f"{os.path.basename(src_path)}: {e!s}")

        self.finished.emit(converted, total - converted if self.is_cancelled else total, errors)

    def _get_output_ext(self):
        ext_map = {
            "PNG": "png",
            "JPEG": "jpg",
            "WEBP": "webp",
            "BMP": "bmp",
            "TIFF": "tiff",
            "GIF": "gif",
        }
        return ext_map.get(self.format, "png")


class ImageConverterConfigDialog(QDialog):
    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Conversor de Imágenes")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Formato de salida:"))
        self.combo_format = QComboBox()
        self.combo_format.addItems(["PNG", "JPEG", "WEBP", "BMP", "TIFF", "GIF"])
        self.combo_format.setCurrentText(current_config.get("default_format", "PNG"))
        format_layout.addWidget(self.combo_format)
        layout.addLayout(format_layout)

        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Calidad:"))
        self.spin_quality = QSpinBox()
        self.spin_quality.setRange(1, 100)
        self.spin_quality.setValue(current_config.get("quality", 85))
        quality_layout.addWidget(self.spin_quality)
        quality_layout.addStretch()
        layout.addLayout(quality_layout)

        btn_save = QPushButton("Guardar Configuración")
        btn_save.clicked.connect(self.accept)
        layout.addWidget(btn_save)

    def get_settings(self):
        return {
            "default_format": self.combo_format.currentText(),
            "quality": self.spin_quality.value(),
        }

    def get_config(self):
        return self.get_settings()


class ImageConverterDialog(QDialog):
    def __init__(self, files, config, parent=None):
        super().__init__(parent)
        self.files = files
        self.config = config
        self.worker = None
        self.setWindowTitle(f"Conversor de Imágenes ({len(files)} archivos)")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"Archivos seleccionados: {len(files)}"))

        output_group = QGroupBox("Carpeta de salida")
        output_layout = QHBoxLayout()
        self.txt_output = QLineEdit()
        self.txt_output.setText(os.path.dirname(files[0]) if files else "")
        self.btn_browse = QPushButton("Examinar...")
        self.btn_browse.clicked.connect(self.browse_output)
        output_layout.addWidget(self.txt_output)
        output_layout.addWidget(self.btn_browse)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Formato:"))
        self.combo_format = QComboBox()
        self.combo_format.addItems(["PNG", "JPEG", "WEBP", "BMP", "TIFF", "GIF"])
        self.combo_format.setCurrentText(config.get("default_format", "PNG"))
        format_layout.addWidget(self.combo_format)

        format_layout.addWidget(QLabel("Calidad:"))
        self.spin_quality = QSpinBox()
        self.spin_quality.setRange(1, 100)
        self.spin_quality.setValue(config.get("quality", 85))
        format_layout.addWidget(self.spin_quality)
        format_layout.addStretch()
        layout.addLayout(format_layout)

        resize_group = QGroupBox("Redimensionar (opcional)")
        resize_layout = QGridLayout()
        resize_layout.addWidget(QLabel("Ancho:"), 0, 0)
        self.spin_width = QSpinBox()
        self.spin_width.setRange(0, 10000)
        self.spin_width.setValue(0)
        self.spin_width.setSuffix(" px")
        self.spin_width.setSpecialValueText("Sin cambio")
        resize_layout.addWidget(self.spin_width, 0, 1)

        resize_layout.addWidget(QLabel("Alto:"), 0, 2)
        self.spin_height = QSpinBox()
        self.spin_height.setRange(0, 10000)
        self.spin_height.setValue(0)
        self.spin_height.setSuffix(" px")
        self.spin_height.setSpecialValueText("Sin cambio")
        resize_layout.addWidget(self.spin_height, 0, 3)

        self.chk_maintain_ratio = QCheckBox("Mantener proporción")
        self.chk_maintain_ratio.setChecked(True)
        resize_layout.addWidget(self.chk_maintain_ratio, 1, 0, 1, 4)
        resize_group.setLayout(resize_layout)
        layout.addWidget(resize_group)

        mode_group = QGroupBox("Modo de salida")
        mode_layout = QVBoxLayout()
        self.radio_preserve = QRadioButton("Crear copia con sufijo '_conv' (recomendado)")
        self.radio_preserve.setChecked(True)
        mode_layout.addWidget(self.radio_preserve)
        self.radio_overwrite = QRadioButton("Sobrescribir originales")
        mode_layout.addWidget(self.radio_overwrite)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Listo")
        layout.addWidget(self.lbl_status)

        btn_layout = QHBoxLayout()
        self.btn_convert = QPushButton("Convertir")
        self.btn_convert.clicked.connect(self.start_conversion)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.cancel_conversion)
        self.btn_cancel.setEnabled(False)
        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_convert)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

    def browse_output(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Seleccionar carpeta de salida", self.txt_output.text()
        )
        if folder:
            self.txt_output.setText(folder)

    def start_conversion(self):
        output_dir = self.txt_output.text().strip()
        if not output_dir or not os.path.isdir(output_dir):
            QMessageBox.warning(self, "Error", "Selecciona una carpeta de salida válida.")
            return

        self.btn_convert.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Convirtiendo...")

        format_map = {
            "PNG": "PNG",
            "JPEG": "JPEG",
            "WEBP": "WEBP",
            "BMP": "BMP",
            "TIFF": "TIFF",
            "GIF": "GIF",
        }

        self.worker = ImageConverterWorker(
            files=self.files,
            output_dir=output_dir,
            format=format_map.get(self.combo_format.currentText(), "PNG"),
            quality=self.spin_quality.value(),
            resize_width=self.spin_width.value(),
            resize_height=self.spin_height.value(),
            maintain_ratio=self.chk_maintain_ratio.isChecked(),
            preserve_original=self.radio_preserve.isChecked(),
        )

        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, current, total, filename):
        percent = int((current / total) * 100)
        self.progress_bar.setValue(percent)
        self.lbl_status.setText(f"{current}/{total}: {filename}")

    def on_finished(self, converted, skipped, errors):
        self.btn_convert.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setValue(100)

        msg = "Conversión completada:\n\n"
        msg += f"• Convertidas: {converted}\n"
        if skipped > 0:
            msg += f"• Canceladas: {skipped}\n"
        if errors:
            msg += f"• Errores: {len(errors)}\n\n"
            msg += "\n".join(errors[:5])
            if len(errors) > 5:
                msg += f"\n... y {len(errors) - 5} más."

        QMessageBox.information(self, "Completado", msg)
        self.lbl_status.setText(f"Completado: {converted} archivos")

    def cancel_conversion(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.lbl_status.setText("Cancelando...")

    def closeEvent(self, event):  # noqa: N802
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
        super().closeEvent(event)


def _load_settings():
    return load_settings("image_converter", {"default_format": "PNG", "quality": 85})


def _save_settings(settings):
    save_settings("image_converter", settings)


def register(api):
    pass


def run_image_converter(api):
    selected = api.active_panel.get_selected_paths()
    if not selected:
        return

    supported_extensions = (
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
        ".tiff",
        ".tif",
        ".gif",
        ".ico",
    )
    if HEIF_SUPPORT:
        supported_extensions += (".heic", ".heif")
    valid = [p for p in selected if p.lower().endswith(supported_extensions)]

    if not valid:
        QMessageBox.information(
            api.get_parent_window(), "Info", "No hay imágenes válidas seleccionadas."
        )
        return

    settings = _load_settings()
    dlg = ImageConverterDialog(valid, settings, api.get_parent_window())
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dlg.show()
