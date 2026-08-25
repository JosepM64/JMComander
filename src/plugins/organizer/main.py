"""
Organizador de Archivos - Plugin para JMComander

Usa la nueva API de plugins (PluginAPI) en lugar de acceso directo a Qt.
"""

import os
import shutil

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.config import ConfigManager

# Categorías predefinidas
CATEGORIES = {
    "IMAGENES": {
        "exts": [
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".svg",
            ".webp",
            ".heic",
            ".tiff",
            ".raw",
            ".bmp",
            ".psd",
            ".heif",
            ".ico",
            ".jfif",
            ".avif",
        ],
        "default_folder": "Imágenes",
    },
    "DOCUMENTOS": {
        "exts": [
            ".doc",
            ".docx",
            ".txt",
            ".md",
            ".pdf",
            ".odt",
            ".rtf",
            ".tex",
            ".pages",
            ".epub",
            ".mobi",
            ".azw3",
            ".fb2",
        ],
        "default_folder": "Documentos",
    },
    "VIDEO": {
        "exts": [
            ".mp4",
            ".avi",
            ".mkv",
            ".mov",
            ".wmv",
            ".webm",
            ".flv",
            ".mpeg",
            ".m4v",
            ".3gp",
            ".ogv",
            ".mts",
        ],
        "default_folder": "Video",
    },
    "AUDIO": {
        "exts": [".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma", ".midi", ".aiff", ".amr"],
        "default_folder": "Audio",
    },
    "PROGRAMAS": {
        "exts": [
            ".exe",
            ".msi",
            ".dmg",
            ".app",
            ".deb",
            ".rpm",
            ".sh",
            ".bin",
            ".apk",
            ".jar",
            ".bat",
            ".cmd",
            ".ps1",
        ],
        "default_folder": "Programas",
    },
    "COMPRIMIDOS": {
        "exts": [
            ".zip",
            ".rar",
            ".7z",
            ".gtar",
            ".gz",
            ".tar",
            ".bz2",
            ".xz",
            ".iso",
            ".tgz",
            ".tbz",
            ".zst",
        ],
        "default_folder": "Comprimidos",
    },
    "HOJAS_DE_CALCULO": {
        "exts": [".xls", ".xlsx", ".csv", ".ods", ".numbers", ".xlsm"],
        "default_folder": "Hojas de cálculo",
    },
    "PRESENTACIONES": {
        "exts": [".ppt", ".pptx", ".odp", ".key", ".pps", ".ppsx"],
        "default_folder": "Presentaciones",
    },
    "PROGRAMACION": {
        "exts": [
            ".py",
            ".js",
            ".html",
            ".css",
            ".json",
            ".xml",
            ".cpp",
            ".c",
            ".java",
            ".php",
            ".sql",
            ".ts",
            ".go",
            ".rb",
            ".swift",
            ".kt",
            ".rs",
            ".lua",
            ".cs",
        ],
        "default_folder": "Programación",
    },
    "FUENTES": {"exts": [".ttf", ".otf", ".woff", ".woff2", ".eot"], "default_folder": "Fuentes"},
    "LIBROS": {
        "exts": [".epub", ".mobi", ".azw3", ".fb2", ".lit", ".djvu"],
        "default_folder": "Libros",
    },
    "DISEÑO": {
        "exts": [".ai", ".eps", ".sketch", ".xcf", ".indd", ".svgz"],
        "default_folder": "Diseño",
    },
    "OTROS": {
        "exts": ["*"],  # Carácter comodín para archivos sin coincidencia
        "default_folder": "Otros",
    },
}


class OrganizerConfigDialog(QDialog):
    """Diálogo de configuración del organizador"""

    def __init__(self, current_config, parent=None, current_path=None):
        super().__init__(parent)
        self._current_path = current_path
        self.setWindowTitle("Configurar Organizador de Archivos")
        self.resize(700, 550)
        self.current_config = current_config
        layout = QVBoxLayout(self)

        # 1. Configuración de tamaño mínimo
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Ignorar archivos más pequeños que:"))
        self.min_size_input = QLineEdit(str(self.current_config.get("min_size_kb", 0)))
        self.min_size_input.setFixedWidth(100)
        size_layout.addWidget(self.min_size_input)
        size_layout.addWidget(QLabel("KB"))
        size_layout.addStretch(1)
        layout.addLayout(size_layout)

        layout.addSpacing(10)
        layout.addWidget(
            QLabel(
                "Selecciona los tipos de archivos a organizar y el nombre de la carpeta destino:"
            )
        )

        # 2. Configuración por categorías
        self.table = QTableWidget(len(CATEGORIES), 3)
        self.table.setHorizontalHeaderLabels(
            ["Activo", "Categoría (Extensiones)", "Carpeta Destino"]
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        # Ajustar anchos de columnas - Activo muy estrecha
        self.table.setColumnWidth(0, 25)  # Activo (mitad de tamaño)
        self.table.setColumnWidth(1, 260)  # Categoría + Extensiones
        self.table.setColumnWidth(2, 260)  # Carpeta Destino

        # Cargar configuración actual o valores por defecto
        saved_rules = self.current_config.get("rules", {})

        for i, (cat_name, data) in enumerate(CATEGORIES.items()):
            # Checkbox activo - centrado
            chk = QCheckBox()
            is_active = any(ext in saved_rules for ext in data["exts"])
            chk.setChecked(is_active)
            # Centrar el checkbox en la celda
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.addWidget(chk)
            self.table.setCellWidget(i, 0, chk_widget)

            # Nombre y extensiones - dos líneas claramente visibles
            if cat_name == "OTROS":
                ext_str_full = "Cualquier otra extensión"
                ext_str_short = "Cualquier otra extensión"
            else:
                ext_str_full = ", ".join(data["exts"])
                ext_str_short = (
                    ext_str_full[:50] + "..." if len(ext_str_full) > 50 else ext_str_full
                )
            # Formato: categoría en línea 1, extensiones en línea 2
            display_text = f"{cat_name}\n{ext_str_short}"
            item = QTableWidgetItem(display_text)
            item.setToolTip(ext_str_full)  # Tooltip con extensiones completas
            self.table.setItem(i, 1, item)

            # Carpeta destino
            current_folder = data["default_folder"]
            for ext in data["exts"]:
                if ext in saved_rules:
                    current_folder = saved_rules[ext]
                    break

            self.table.setItem(i, 2, QTableWidgetItem(current_folder))

        layout.addWidget(self.table)

        # 3. Botones
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Guardar Configuración")
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def get_config(self):
        """Retorna la configuración actual"""
        rules = {}
        for i in range(self.table.rowCount()):
            # Obtener el checkbox del widget contenedor
            chk_widget = self.table.cellWidget(i, 0)
            chk = None
            if chk_widget and chk_widget.layout():
                chk = chk_widget.layout().itemAt(0).widget()
            if chk and chk.isChecked():
                folder_item = self.table.item(i, 2)
                if folder_item:
                    folder = folder_item.text().strip()
                    cat_name = list(CATEGORIES.keys())[i]
                    exts = CATEGORIES[cat_name]["exts"]
                    if cat_name == "OTROS":
                        # Para la categoría Otros, usar comodín "*"
                        rules["*"] = folder
                    else:
                        for ext in exts:
                            rules[ext] = folder

        try:
            min_size = int(self.min_size_input.text())
        except ValueError:
            min_size = 0

        return {"rules": rules, "min_size_kb": max(0, min_size)}

    def _open_destination(self):
        """Abre la carpeta destino de la fila seleccionada"""
        row = self.table.currentRow()
        if row < 0:
            return

        folder_item = self.table.item(row, 2)
        if not folder_item:
            return

        folder_name = folder_item.text().strip()

        base_path = getattr(self.__class__, "_last_path", None)
        if not base_path and self.parent() and hasattr(self.parent(), "active_panel"):
            base_path = self.parent().active_panel.current_path

        if base_path:
            dest_path = os.path.join(base_path, folder_name)
            if os.path.exists(dest_path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(dest_path))
            else:
                # Si no existe la carpeta, intentar crearla y abrirla
                try:
                    os.makedirs(dest_path, exist_ok=True)
                    QDesktopServices.openUrl(QUrl.fromLocalFile(dest_path))
                except Exception as e:  # noqa: BLE001
                    QMessageBox.warning(self, "Error", f"No se pudo abrir la carpeta: {e}")

    def keyPressEvent(self, event):  # noqa: N802
        """Manejar tecla Enter para abrir la carpeta destino"""
        if (event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter) and self.table.hasFocus():
            self._open_destination()
            return
        super().keyPressEvent(event)


def register(api):
    """Función de registro del plugin"""
    # La acción se registra a través de plugin.json y se ejecuta vía ActionRegistry


def run_organizer(api):  # noqa: PLR0912
    """Ejecuta el organizador de archivos"""
    path = api.active_panel.current_path

    # Store current path for config dialog
    OrganizerConfigDialog._last_path = path

    # Obtener configuración guardada o usar valores por defecto

    config = ConfigManager()
    plugin_config = config.get_plugin_config("organizer", {})

    # Usar reglas configuradas o reglas por defecto
    rules = plugin_config.get("rules", {})
    min_size_kb = plugin_config.get("min_size_kb", 0)

    # Si no hay reglas configuradas, usar las predeterminadas
    if not rules:
        rules = {}
        for data in CATEGORIES.values():
            for ext in data["exts"]:
                if ext == "*":  # Para "Otros", usar comodín
                    rules[ext] = data["default_folder"]
                else:
                    rules[ext] = data["default_folder"]

    # Separar regla para "Otros" (si existe)
    other_folder = None
    if "*" in rules:
        other_folder = rules["*"]
        del rules["*"]  # Remover del mapeo normal

    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]

    if not files:
        api.show_message("No hay archivos para organizar.", "info")
        return

    progress = QProgressDialog(
        "Organizando archivos...", "Cancelar", 0, len(files), api.get_parent_window()
    )
    progress.setWindowTitle("Organizador de Archivos")
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(500)

    count = 0
    moved_files = set()  # Para trackear archivos ya movidos

    for i, f in enumerate(files):
        # Actualizar progreso
        progress.setValue(i)
        progress.setLabelText(f"Procesando: {f}")
        if progress.wasCanceled():
            api.show_message("Organización cancelada por el usuario.", "info")
            return

        full_path = os.path.join(path, f)
        ext = os.path.splitext(f)[1].lower()

        # Verificar tamaño mínimo
        if min_size_kb > 0:
            try:
                file_size_kb = os.path.getsize(full_path) / 1024
                if file_size_kb < min_size_kb:
                    continue
            except Exception:  # noqa: BLE001
                pass

        if ext in rules:
            folder_name = rules[ext]
            dest_dir = os.path.join(path, folder_name)
            os.makedirs(dest_dir, exist_ok=True)
            try:
                shutil.move(full_path, os.path.join(dest_dir, f))
                count += 1
                moved_files.add(f)
            except Exception as e:  # noqa: BLE001
                api.show_message(f"Error moviendo {f}: {e}", "error")

    # Procesar archivos restantes para categoría "Otros" (si está configurada)
    if other_folder:
        remaining_files = [f for f in files if f not in moved_files]
        for i, f in enumerate(remaining_files, start=len(moved_files)):
            # Actualizar progreso
            progress.setValue(i)
            progress.setLabelText(f"Moviendo a Otros: {f}")
            if progress.wasCanceled():
                api.show_message("Organización cancelada por el usuario.", "info")
                return

            full_path = os.path.join(path, f)

            # Verificar tamaño mínimo también para "Otros"
            if min_size_kb > 0:
                try:
                    file_size_kb = os.path.getsize(full_path) / 1024
                    if file_size_kb < min_size_kb:
                        continue
                except Exception:  # noqa: BLE001
                    pass

            dest_dir = os.path.join(path, other_folder)
            os.makedirs(dest_dir, exist_ok=True)
            try:
                shutil.move(full_path, os.path.join(dest_dir, f))
                count += 1
            except Exception as e:  # noqa: BLE001
                api.show_message(f"Error moviendo {f} a Otros: {e}", "error")

    progress.setValue(len(files))
    api.show_message(f"Se han organizado {count} archivos.", "info")
    api.active_panel.refresh()
