import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap


# Detectar tema directamente desde el archivo de configuración
def _get_theme():
    """Lee el tema directamente del archivo icon_theme.py"""
    try:
        # En modo PyInstaller, buscar en diferentes ubicaciones
        if getattr(sys, "frozen", False):
            base_paths = [
                Path(sys._MEIPASS),  # noqa: SLF001
                Path(sys.executable).parent,
                Path(sys.executable).parent / "_internal",
            ]
        else:
            base_paths = [Path(__file__).parent]

        for base in base_paths:
            theme_file = base / "src" / "assets" / "icon_theme.py"
            if theme_file.exists():
                content = theme_file.read_text()
                if 'ICON_THEME = "PHOSPHOR"' in content:
                    return "PHOSPHOR"
                if 'ICON_THEME = "MATERIAL"' in content:
                    return "MATERIAL"
    except Exception:  # noqa: BLE001
        pass

    # Default
    return "MATERIAL"


ICON_THEME = _get_theme()


class IconLoader:
    def __init__(self, theme=None):
        self.theme = theme or ICON_THEME
        self.icon_dirs = []

        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).parent

            if self.theme == "PHOSPHOR":
                self.icon_dirs = [
                    exe_dir / "_internal" / "src" / "assets" / "icons-phosphor",
                    exe_dir / "src" / "assets" / "icons-phosphor",
                ]
            else:
                self.icon_dirs = [
                    exe_dir / "_internal" / "src" / "assets" / "icons",
                    exe_dir / "src" / "assets" / "icons",
                ]
        else:
            base_path = Path(__file__).parent / "assets"
            if self.theme == "PHOSPHOR":
                self.icon_dirs = [base_path / "icons-phosphor"]
            else:
                self.icon_dirs = [base_path / "icons"]

    def load_icon(self, name: str, fallback_text: str | None = None) -> QIcon:
        phosphor_aliases = {
            "mdi-arrow-up": "arrow-up",
            "mdi-harddisk": "folder",
            "mdi-home": "home",
            "mdi-refresh": "refresh",
            "mdi-magnify": "search",
            "mdi-view-list": "list",
            "mdi-view-grid": "grid",
            "mdi-swap-horizontal": "swap",
            "mdi-arrow-right-bold": "arrow-right",
            "mdi-arrow-left-bold": "arrow-left",
            "mdi-monitor": "monitor",
            "mdi-terminal-outline": "terminal",
            "mdi-console": "terminal",
            "mdi-content-duplicate": "files",
            "mdi-folder-open": "folder",
            "mdi-select-all": "select-all",
            "mdi-content-copy-outline": "copy",
            "mdi-folder-plus-outline": "folder-plus",
            "mdi-select-inverse": "select-all",
            "mdi-selection-off": "select-none",
            "mdi-information": "info",
            "mdi-puzzle": "plugins",
            "mdi-bookmark": "bookmark",
        }

        for icon_dir in self.icon_dirs:
            # Intentar nombre directo primero
            svg_path = icon_dir / f"{name}.svg"
            if svg_path.exists():
                return QIcon(str(svg_path))

            # Si es Phosphor, intentar alias
            if self.theme == "PHOSPHOR" and name in phosphor_aliases:
                alias_path = icon_dir / f"{phosphor_aliases[name]}.svg"
                if alias_path.exists():
                    return QIcon(str(alias_path))

        # Fallback - Icono generado con color neutro (no azul llamativo)
        letter = (fallback_text or name[:1]).upper()
        pix = QPixmap(20, 20)
        # Color gris neutro en lugar de azul brillante
        pix.fill(QColor("#9E9E9E"))
        painter = QPainter(pix)
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.drawText(pix.rect(), Qt.AlignCenter, letter)
        painter.end()
        return QIcon(pix)

    def get_theme(self) -> str:
        return self.theme
