import json
import logging
import os

# Intentar importar constantes, con fallback para robustez
try:
    from src.toolbar_constants import TOOLBAR_DEFAULT_TOOLTIPS, TOOLBAR_MASTER_LAYOUT
except ImportError:
    try:
        from toolbar_constants import TOOLBAR_DEFAULT_TOOLTIPS, TOOLBAR_MASTER_LAYOUT
    except ImportError:
        TOOLBAR_MASTER_LAYOUT = [
            "up",
            "root",
            "home",
            "refresh",
            "search",
            "separator",
            "select_all",
            "invert_selection",
            "deselect_all",
            "folders_only",
            "separator",
            "new_folder",
            "copy_path",
            "goto",
            "duplicate",
            "separator",
            "terminal",
            "powershell",
            "separator",
            "swap",
            "equal",
            "equal_reverse",
            "explorer",
            "separator",
            "view_mode",
            "recent_paths",
            "bookmarks",
            "plugins",
            "spacer",
            "settings",
            "info",
        ]
        TOOLBAR_DEFAULT_TOOLTIPS = {}

logger = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self, filepath="config.json"):
        self.filepath = filepath
        self.data = {
            "window_geometry": None,
            "is_maximized": False,
            "left_path": os.path.expanduser("~"),
            "right_path": os.path.abspath(os.sep),
            "toolbar_layout": TOOLBAR_MASTER_LAYOUT.copy(),
            "recent_paths": [],
            "tooltips": {},
            "background_operations": True,
            "work_directory": "",
        }
        self.load()

    def get_tooltip(self, key, default=None):
        """Retorna el tooltip personalizado o el predeterminado"""
        user_tooltip = self.data.get("tooltips", {}).get(key)
        if user_tooltip:
            return user_tooltip
        return default or TOOLBAR_DEFAULT_TOOLTIPS.get(key, "")

    def set_tooltips(self, tooltips_dict):
        """Guarda un diccionario de tooltips personalizados"""
        self.data["tooltips"] = tooltips_dict
        self.save()

    def load(self):
        """Carga la configuración desde el archivo JSON"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)

                # Asegurar que el layout tenga todos los botones disponibles
                self._merge_toolbar_layout()

            except Exception as e:
                logger.exception("Error cargando config: %s", e)  # noqa: TRY401
        else:
            logger.info("Archivo de configuración no encontrado, usando valores por defecto")

    def _merge_toolbar_layout(self):
        """Fusiona el layout guardado con la lista maestra para no perder botones nuevos"""
        saved = self.data.get("toolbar_layout", [])

        # Si no hay layout válido, usar el maestro completo
        if not saved or len(saved) < 5:
            self.data["toolbar_layout"] = TOOLBAR_MASTER_LAYOUT.copy()
            return

        # Filtrar items obsoletos y mantener items especiales (separator, spacer)
        new_layout = [
            item
            for item in saved
            if item in TOOLBAR_MASTER_LAYOUT or item in ["separator", "spacer"]
        ]

        # Añadir items faltantes de la lista maestra al final
        for item in TOOLBAR_MASTER_LAYOUT:
            if item not in new_layout:
                new_layout.append(item)

        # Garantizar que el botón de configuración esté siempre presente
        if "settings" not in new_layout:
            new_layout.append("settings")

        self.data["toolbar_layout"] = new_layout

    def save(self):
        """Guarda la configuración actual al archivo JSON"""
        try:
            # Validación de seguridad para el botón de configuración
            if "settings" not in self.data.get("toolbar_layout", []):
                self.data.setdefault("toolbar_layout", []).append("settings")

            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
            logger.debug("Configuración guardada exitosamente")
        except Exception as e:
            logger.exception("Error guardando config: %s", e)  # noqa: TRY401

    def set_window_state(self, x, y, w, h, is_maximized):
        self.data["window_geometry"] = [x, y, w, h]
        self.data["is_maximized"] = is_maximized

    def is_maximized(self):
        return self.data.get("is_maximized", False)

    def get_geometry(self):
        return self.data.get("window_geometry")

    def set_paths(self, left, right):
        self.data["left_path"] = left
        self.data["right_path"] = right

    def get_left_path(self):
        return self.data.get("left_path")

    def get_right_path(self):
        return self.data.get("right_path")

    def set_toolbar_layout(self, layout_list):
        self.data["toolbar_layout"] = layout_list

    def get_toolbar_layout(self):
        return self.data.get("toolbar_layout")

    def add_recent_path(self, path, max_items=10):
        """Muta la llista només en memòria — el save() fa el closeEvent.
        (Escriure config.json a disc a cada navegació era I/O innecessari.)"""
        recent = self.data.get("recent_paths", [])
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        self.data["recent_paths"] = recent[:max_items]

    def get_recent_paths(self):
        return self.data.get("recent_paths", [])

    def clear_recent_paths(self):
        self.data["recent_paths"] = []
        self.save()

    def get_plugin_config(self, plugin_id: str, default=None):
        """Obtiene la configuración guardada de un plugin"""
        plugins_config = self.data.get("plugins_config", {})
        return plugins_config.get(plugin_id, default)

    def set_plugin_config(self, plugin_id: str, config: dict):
        """Guarda la configuración de un plugin"""
        plugins_config = self.data.setdefault("plugins_config", {})
        plugins_config[plugin_id] = config
        self.save()

    def get_background_operations(self) -> bool:
        """Retorna si las operaciones deben ejecutarse en segundo plano por defecto"""
        return self.data.get("background_operations", True)

    def set_background_operations(self, enabled: bool):
        """Configura si las operaciones deben ejecutarse en segundo plano por defecto"""
        self.data["background_operations"] = enabled
        self.save()

    def get_work_directory(self) -> str:
        return self.data.get("work_directory", "")

    def set_work_directory(self, path: str):
        self.data["work_directory"] = path
        self.save()
