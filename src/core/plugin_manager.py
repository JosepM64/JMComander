import importlib.util
import traceback

from src.core.actions import Action, action_registry
from src.core.plugin_api import PluginAPI

"""
PluginManager - Gestor de plugins extensible

Características:
- plugin.json descriptor declarativo
- Carpeta de plugins por usuario (%APPDATA%) tiene prioridad
- main.py con función register(api)
- Registro automático de acciones en ActionRegistry
- API mínima y segura para plugins
"""

import json  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from pathlib import Path  # noqa: E402

logger = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    """Información de un plugin cargado"""

    id: str
    name: str
    version: str
    author: str
    description: str
    path: Path
    bundled: bool  # True si viene con la instalación
    actions: list = field(default_factory=list)
    menus: list = field(default_factory=list)
    config_dialog: callable = None  # Función que retorna QDialog de configuración
    instance: object = None  # Instancia del plugin (para plugins antiguos con execute())
    module: object = None  # Módulo del plugin (para acceder a handlers)


class PluginManager:
    """Gestiona la carga y registro de plugins"""

    def __init__(self, main_window):
        self._mw = main_window
        self._api = None  # Se inicializa después
        self._loaded_plugins: dict[str, PluginInfo] = {}

        # Carpetas de plugins (user > bundled)
        self.plugins_dirs = []

        # Usuario (%APPDATA%)
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            user_dir = Path(appdata) / "JMComander" / "plugins"
            self.plugins_dirs.append(user_dir)

        # Bundled (src/plugins)
        bundled_dir = Path(__file__).parent.parent / "plugins"
        self.plugins_dirs.append(bundled_dir)

        # Crear carpetas user si no existen
        for d in self.plugins_dirs:
            if not d.exists():
                try:
                    d.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    logger.exception("No se pudo crear %s: %s", d, e)  # noqa: TRY401

    def initialize(self):
        """Inicializa el gestor con la API"""

        self._api = PluginAPI(self._mw)
        self.scan_and_load()

    def load_plugins(self):
        """Alias para compatibilidad - llama a scan_and_load"""
        self.scan_and_load()

    def scan_and_load(self):
        """Escanea y carga todos los plugins"""
        loaded_ids = set()

        # User plugins primero (índice 0)
        if len(self.plugins_dirs) > 0:
            loaded_ids.update(self._load_directory(self.plugins_dirs[0], bundled=False))

        # Bundled plugins después
        if len(self.plugins_dirs) > 1:
            loaded_ids.update(self._load_directory(self.plugins_dirs[1], bundled=True))

        logger.info(
            f"Cargados {len(self._loaded_plugins)} plugins: {list(self._loaded_plugins.keys())}"  # noqa: G004
        )

    def _load_directory(self, plugins_dir: Path, bundled: bool) -> set:
        """Carga todos los plugins de un directorio (nuevos y antiguos)"""
        loaded_ids = set()

        if not plugins_dir.exists():
            return loaded_ids

        # Plugins nuevos (carpetas con plugin.json)
        for item in plugins_dir.iterdir():
            if item.is_dir() and not item.name.startswith(".") and item.name != "__pycache__":
                try:
                    plugin_id = self._load_plugin(item, bundled)
                    if plugin_id:
                        loaded_ids.add(plugin_id)
                except Exception as e:
                    logger.exception("Error cargando plugin %s: %s", item, e)  # noqa: TRY401

        # Plugins antiguos (.py sueltos)
        for item in plugins_dir.iterdir():
            if item.is_file() and item.suffix == ".py" and not item.name.startswith("_"):
                try:
                    plugin_id = self._load_old_style_plugin(item, bundled)
                    if plugin_id:
                        loaded_ids.add(plugin_id)
                except Exception as e:
                    logger.exception("Error cargando plugin antiguo %s: %s", item, e)  # noqa: TRY401

        return loaded_ids

    def _load_old_style_plugin(self, plugin_file: Path, bundled: bool) -> str | None:
        """Carga un plugin antiguo (fichero .py único con PluginInterface)"""
        try:
            spec = importlib.util.spec_from_file_location(plugin_file.stem, plugin_file)
            if not spec or not spec.loader:
                return None

            module = importlib.util.module_from_spec(spec)

            old_path = sys.path.copy()
            try:
                sys.path.insert(0, str(plugin_file.parent))
                spec.loader.exec_module(module)
            finally:
                sys.path[:] = old_path

            # Verificar si tiene PluginInterface
            if not hasattr(module, "PluginInterface"):
                logger.debug("Plugin %s no tiene PluginInterface, ignorando", plugin_file)
                return None

            # Obtener la clase del plugin que hereda de PluginInterface
            # (no la clase base PluginInterface misma)
            base_class = module.PluginInterface
            plugin_class = None

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and attr is not base_class
                    and issubclass(attr, base_class)
                ):
                    plugin_class = attr
                    break

            if not plugin_class:
                logger.debug(
                    f"Plugin {plugin_file.name} no tiene clase que herede de PluginInterface"  # noqa: G004
                )
                return None

            instance = plugin_class()

            plugin_id = getattr(instance, "id", plugin_file.stem)
            if plugin_id in self._loaded_plugins:
                logger.debug("Plugin %s ya cargado (saltando .py antiguo)", plugin_id)
                return None

            # Crear PluginInfo desde la interfaz antigua
            # Los métodos name(), version(), author() deben ser llamados
            name_val = getattr(instance, "name", lambda: plugin_file.stem)
            version_val = getattr(instance, "version", lambda: "1.0.0")
            author_val = getattr(instance, "author", lambda: "Desconocido")
            desc_val = getattr(instance, "description", lambda: "")

            info = PluginInfo(
                id=plugin_id,
                name=name_val() if callable(name_val) else name_val,
                version=version_val() if callable(version_val) else version_val,
                author=author_val() if callable(author_val) else author_val,
                description=desc_val() if callable(desc_val) else desc_val,
                path=plugin_file,
                bundled=bundled,
                actions=[],
                menus=[],
                instance=instance,  # Guardar instancia para poder ejecutar el plugin
            )

            # Buscar ConfigDialog
            if hasattr(instance, "has_config") and instance.has_config():
                config_dialog_name = f"{plugin_file.stem.title().replace('_', '')}ConfigDialog"
                if hasattr(module, config_dialog_name):
                    info.config_dialog = getattr(module, config_dialog_name)

            self._loaded_plugins[plugin_id] = info
            logger.info("Plugin antiguo cargado: %s v%s", info, info)
            return plugin_id  # noqa: TRY300

        except Exception as e:
            logger.exception("Error cargando plugin antiguo %s: %s", plugin_file, e)  # noqa: TRY401

            traceback.print_exc()
            return None

    def _load_plugin(self, plugin_dir: Path, bundled: bool) -> str | None:
        """Carga un plugin individual"""
        # Leer plugin.json
        json_path = plugin_dir / "plugin.json"
        if not json_path.exists():
            logger.debug("Directorio %s no tiene plugin.json, ignorando", plugin_dir)
            return None

        try:
            with open(json_path, encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as e:
            logger.exception("Error leyendo %s: %s", json_path, e)  # noqa: TRY401
            return None

        plugin_id = manifest.get("id", plugin_dir.name)

        # Evitar cargar dos veces
        if plugin_id in self._loaded_plugins:
            logger.debug("Plugin %s ya cargado (saltando carpeta)", plugin_id)
            return None

        # Verificar entrada
        main_file = manifest.get("entry", "main.py")
        main_path = plugin_dir / main_file
        if not main_path.exists():
            logger.error("Plugin %s: no existe %s", plugin_id, main_file)
            return None

        # Cargar módulo
        try:
            spec = importlib.util.spec_from_file_location(plugin_id, main_path)
            module = importlib.util.module_from_spec(spec)

            # Crear contexto de import
            old_path = sys.path.copy()
            try:
                sys.path.insert(0, str(plugin_dir))

                # Registrar función register vacía si no existe
                if not hasattr(module, "register"):
                    module.register = lambda _api: None

                spec.loader.exec_module(module)
            finally:
                sys.path[:] = old_path  # Restaurar path incluso si el plugin falla

            # Llamar register con API
            if hasattr(module, "register"):
                module.register(self._api)

            # Crear PluginInfo
            info = PluginInfo(
                id=plugin_id,
                name=manifest.get("name", plugin_id),
                version=manifest.get("version", "1.0.0"),
                author=manifest.get("author", "Desconocido"),
                description=manifest.get("description", ""),
                path=plugin_dir,
                bundled=bundled,
                actions=manifest.get("actions", []),
                menus=manifest.get("menus", []),
                module=module,  # Guardar referencia al módulo
            )

            # Buscar ConfigDialog automáticamente
            config_dialog_class = manifest.get("config_dialog")
            if config_dialog_class and hasattr(module, config_dialog_class):
                info.config_dialog = getattr(module, config_dialog_class)

            # Registrar acciones en ActionRegistry
            self._register_plugin_actions(info, module)

            self._loaded_plugins[plugin_id] = info
            logger.info(
                f"Plugin cargado: {info.name} v{info.version} ({'bundled' if bundled else 'user'})"  # noqa: G004
            )
            return plugin_id  # noqa: TRY300

        except Exception as e:
            logger.exception("Error cargando %s: %s", plugin_id, e)  # noqa: TRY401

            traceback.print_exc()
            return None

    def _register_plugin_actions(self, info: PluginInfo, module=None):
        """Registra las acciones del plugin en ActionRegistry"""

        for action_def in info.actions:
            action_id = action_def.get("id", f"plugin_{info.id}")

            # Buscar el handler en el módulo si está disponible
            handler = None
            if module:
                # Primero intentar con el nombre del handler del plugin.json
                handler_name = action_def.get("handler", action_id.replace("plugin_", "run_"))
                if hasattr(module, handler_name):
                    handler = getattr(module, handler_name)
                # Fallback: intentar con action_id sin prefijo
                elif action_id.startswith("plugin_") and hasattr(
                    module, action_id.replace("plugin_", "run_")
                ):
                    handler = getattr(module, action_id.replace("plugin_", "run_"))

            action = Action(
                id=action_id,
                name=action_def.get("name", info.name),
                icon=action_def.get("icon", "mdi-puzzle"),
                shortcut=action_def.get("shortcut"),
                handler=handler,  # Asignar el handler encontrado
                tooltip=action_def.get("description", info.description),
                category="Plugins",
                order=action_def.get("order", 10),
            )
            action_registry.register(action)

    def get_plugin(self, plugin_id: str) -> PluginInfo | None:
        """Obtiene información de un plugin"""
        return self._loaded_plugins.get(plugin_id)

    def get_plugin_config_dialog(self, plugin_id: str):
        """Obtiene la clase ConfigDialog de un plugin"""
        info = self._loaded_plugins.get(plugin_id)
        if info and info.config_dialog:
            return info.config_dialog
        return None

    def list_plugins(self) -> list[PluginInfo]:
        """Lista todos los plugins cargados"""
        return list(self._loaded_plugins.values())

    def get_plugins(self) -> list:
        """Alias para compatibilidad - retorna lista de objetos plugin"""
        # Compatibilidad: retornar lista con objetos que tienen name() y execute()
        # Por ahora retornamos PluginInfo
        return self.list_plugins()

    def reload_plugin(self, plugin_id: str) -> bool:
        """Recarga un plugin"""
        if plugin_id not in self._loaded_plugins:
            return False
        # TODO: Implementar reload
        return False
