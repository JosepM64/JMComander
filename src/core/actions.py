"""
ActionRegistry - Registro centralizado de acciones del core

Las acciones se definen aquí con:
- ID único
- Nombre/Descripción
- Icono (Material Design)
- Handler (función) que recibe ActionContext
"""

import logging
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QInputDialog, QMessageBox

from src.core.fs_utils import get_locked_paths
from src.plugins.compare_dirs.main import compare_dirs
from src.plugins.organizer.main import run_organizer

logger = logging.getLogger(__name__)


@dataclass
class ActionContext:
    """
    Context mínim per als handlers d'accions.
    MainWindow construeix aquest objecte i el passa al handler.
    """
    active_panel: object
    inactive_panel: object
    engine: object
    bookmarks: object | None = None
    parent: object | None = None
    run_operation: Callable | None = None
    refresh_bookmarks_bar: Callable | None = None
    update_bookmarks_menu: Callable | None = None


@dataclass
class Action:
    id: str
    name: str
    icon: str | None = None
    shortcut: str | None = None
    handler: Callable | None = None
    tooltip: str | None = None
    category: str = "General"
    order: int = 0


class ActionCategory(Enum):
    FILE = "Archivo"
    EDIT = "Editar"
    VIEW = "Vista"
    SELECT = "Selección"
    PANELS = "Paneles"
    PLUGINS = "Plugins"
    HELP = "Ayuda"


class ActionRegistry:
    def __init__(self):
        self._actions: dict[str, Action] = {}
        self._action_order = []

    def register(self, action: Action):
        self._actions[action.id] = action
        if action.id not in self._action_order:
            self._action_order.append(action.id)

    def get(self, action_id: str) -> Action | None:
        return self._actions.get(action_id)

    def list_all(self) -> list[Action]:
        return [self._actions[aid] for aid in self._action_order if aid in self._actions]

    def list_by_category(self, category: str) -> list[Action]:
        return sorted(
            [a for a in self._actions.values() if a.category == category], key=lambda x: x.order
        )

    def list_plugins(self) -> list[Action]:
        return [a for a in self._actions.values() if a.category == ActionCategory.PLUGINS.value]


action_registry = ActionRegistry()


# === Handlers per a accions de fitxers ===

def _is_shell_path(p):
    return str(p).startswith("::") or "\\SID-" in str(p) or "shell::" in str(p).lower()


def _copy_files(ctx: ActionContext):
    s = ctx.active_panel.get_selected_paths()
    d = ctx.inactive_panel.current_path
    if s and QMessageBox.question(
        ctx.parent, "Copiar", f"¿Copiar {len(s)} items?"
    ) == QMessageBox.StandardButton.Yes:
        if _is_shell_path(s[0]):
            # MTP/iPhone: còpia en background (la síncrona congelava la UI)
            if ctx.run_operation:
                from src.core.jobs import MtpCopyJob  # noqa: PLC0415

                job = MtpCopyJob(s, d)
                job.signals.finished.connect(lambda: ctx.active_panel.refresh())
                ctx.run_operation(job, "Copiant del iPhone")
            return
        if ctx.run_operation:
            ctx.run_operation(ctx.engine.queue_copy(s, d), "Copiando")


def _move_files(ctx: ActionContext):
    s = ctx.active_panel.get_selected_paths()
    d = ctx.inactive_panel.current_path
    if s and QMessageBox.question(
        ctx.parent, "Mover", f"¿Mover {len(s)} items?"
    ) == QMessageBox.StandardButton.Yes:
        if _is_shell_path(s[0]):
            # MTP/iPhone: no hi ha move natiu fiable -> còpia en background
            if ctx.run_operation:
                from src.core.jobs import MtpCopyJob  # noqa: PLC0415

                job = MtpCopyJob(s, d)
                job.signals.finished.connect(lambda: ctx.active_panel.refresh())
                ctx.run_operation(job, "Copiant del iPhone")
            return
        if ctx.run_operation:
            ctx.run_operation(ctx.engine.queue_move(s, d), "Moviendo")


def _delete_files(ctx: ActionContext):
    s = ctx.active_panel.get_selected_paths()
    if not s:
        return
    locked = get_locked_paths(s)
    if locked:
        locked_names = [os.path.basename(p) for p in locked]
        msg = (
            "Los siguientes elementos están siendo usados"
            " por otro proceso y no se pueden eliminar:\n\n"
        )
        msg += "\n".join(f"  - {name}" for name in locked_names)
        msg += "\n\nCierra los programas que los estén usando e intenta de nuevo."
        QMessageBox.warning(ctx.parent, "Archivo en uso", msg)
        return
    reply = QMessageBox.question(
        ctx.parent,
        "Eliminar",
        f"¿Eliminar {len(s)} elementos?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if reply == QMessageBox.StandardButton.Yes and ctx.run_operation:
        ctx.run_operation(ctx.engine.queue_delete(s, True), "Eliminando")


def _create_folder(ctx: ActionContext):
    n, ok = QInputDialog.getText(ctx.parent, "Nueva Carpeta", "Nombre:")
    if ok and n:
        full_path = os.path.join(ctx.active_panel.current_path, n)
        try:
            os.mkdir(full_path)
            ctx.active_panel.refresh()
            ctx.active_panel.select_and_focus(full_path)
        except Exception as e:
            QMessageBox.critical(ctx.parent, "Error", str(e))


def _duplicate_selected(ctx: ActionContext):
    ctx.active_panel.duplicate_selected()


def _open_terminal_here(ctx: ActionContext):
    subprocess.Popen(["cmd.exe", "/k", "cd", "/d", ctx.active_panel.current_path])


def _open_powershell_here(ctx: ActionContext):
    path = ctx.active_panel.current_path
    subprocess.Popen(["powershell.exe", "-NoExit", "-Command", f'Set-Location "{path}"'])


def _open_in_explorer(ctx: ActionContext):
    QDesktopServices.openUrl(QUrl.fromLocalFile(ctx.active_panel.current_path))


def _go_to_folder(ctx: ActionContext):
    p, ok = QInputDialog.getText(
        ctx.parent, "Ir a", "Ruta:", text=ctx.active_panel.current_path
    )
    if ok and p:
        p = os.path.expanduser(os.path.expandvars(p.strip()))
        if os.path.isdir(p):
            ctx.active_panel.set_path(p)


def _add_current_to_bookmarks(ctx: ActionContext):
    name, ok = QInputDialog.getText(
        ctx.parent,
        "Añadir Marcador",
        "Nombre:",
        text=os.path.basename(ctx.active_panel.current_path),
    )
    if ok and name.strip() and ctx.bookmarks:
        ctx.bookmarks.add_bookmark(name.strip(), ctx.active_panel.current_path)
        if ctx.refresh_bookmarks_bar:
            ctx.refresh_bookmarks_bar()
        if ctx.update_bookmarks_menu:
            ctx.update_bookmarks_menu()


def _view_file(ctx: ActionContext):
    s = ctx.active_panel.get_selected_paths()
    if s and os.path.isfile(s[0]):
        QDesktopServices.openUrl(QUrl.fromLocalFile(s[0]))


def _edit_file(ctx: ActionContext):
    s = ctx.active_panel.get_selected_paths()
    if s and os.path.isfile(s[0]):
        subprocess.Popen(["notepad.exe", s[0]])


def _show_about(ctx: ActionContext):
    # El diàleg About viu a MainWindow — abans l'acció no tenia handler i no feia res
    if hasattr(ctx.parent, "show_about_dialog"):
        ctx.parent.show_about_dialog()


# === Handlers per a plugins ===

def _run_compare_dirs(api):
    compare_dirs(api)


def _run_organize(api):
    run_organizer(api)


# === Registre ===

def register_core_actions():
    action_registry.register(
        Action(id="new_folder", name="Nueva carpeta", icon="mdi-folder-plus",
               shortcut="Ctrl+N", category=ActionCategory.FILE.value, order=1,
               handler=_create_folder)
    )
    action_registry.register(
        Action(id="open_terminal", name="Terminal aquí", icon="mdi-terminal-outline",
               category=ActionCategory.FILE.value, order=2,
               handler=_open_terminal_here)
    )
    action_registry.register(
        Action(id="open_powershell", name="PowerShell aquí", icon="mdi-console",
               category=ActionCategory.FILE.value, order=3,
               handler=_open_powershell_here)
    )
    action_registry.register(
        Action(id="copy_path", name="Copiar ruta", icon="mdi-content-copy-outline",
               shortcut="Ctrl+Shift+C", category=ActionCategory.FILE.value, order=4)
    )
    action_registry.register(
        Action(id="exit", name="Salir", icon="mdi-exit-to-app",
               shortcut="Alt+F4", category=ActionCategory.FILE.value, order=99)
    )
    action_registry.register(
        Action(id="rename", name="Renombrar", icon="mdi-pencil",
               shortcut="F2", category=ActionCategory.EDIT.value, order=1)
    )
    action_registry.register(
        Action(id="copy", name="Copiar", icon="mdi-content-copy",
               shortcut="F5", category=ActionCategory.EDIT.value, order=2,
               handler=_copy_files)
    )
    action_registry.register(
        Action(id="move", name="Mover", icon="mdi-file-move",
               shortcut="F6", category=ActionCategory.EDIT.value, order=3,
               handler=_move_files)
    )
    action_registry.register(
        Action(id="duplicate", name="Duplicar", icon="mdi-content-duplicate",
               shortcut="Ctrl+D", category=ActionCategory.EDIT.value, order=4,
               handler=_duplicate_selected)
    )
    action_registry.register(
        Action(id="delete", name="Borrar", icon="mdi-delete",
               shortcut="F8", category=ActionCategory.EDIT.value, order=5,
               handler=_delete_files)
    )
    action_registry.register(
        Action(id="goto", name="Ir a...", icon="mdi-folder-open",
               shortcut="Ctrl+G", category=ActionCategory.EDIT.value, order=6,
               handler=_go_to_folder)
    )
    action_registry.register(
        Action(id="view_file", name="Ver archivo", icon="mdi-eye",
               shortcut="F3", category=ActionCategory.VIEW.value, order=1,
               handler=_view_file)
    )
    action_registry.register(
        Action(id="edit_file", name="Editar archivo", icon="mdi-pencil",
               shortcut="F4", category=ActionCategory.VIEW.value, order=2,
               handler=_edit_file)
    )
    action_registry.register(
        Action(id="select_all", name="Seleccionar todo", icon="mdi-select-all",
               shortcut="Ctrl+A", category=ActionCategory.SELECT.value, order=1)
    )
    action_registry.register(
        Action(id="invert_selection", name="Invertir selección", icon="mdi-select-inverse",
               shortcut="Ctrl+I", category=ActionCategory.SELECT.value, order=2)
    )
    action_registry.register(
        Action(id="deselect_all", name="Deseleccionar todo", icon="mdi-selection-off",
               shortcut="Ctrl+U", category=ActionCategory.SELECT.value, order=3)
    )
    action_registry.register(
        Action(id="refresh", name="Refrescar", icon="mdi-refresh",
               shortcut="Ctrl+R", category=ActionCategory.PANELS.value, order=1)
    )
    action_registry.register(
        Action(id="switch_panel", name="Cambiar panel", icon="mdi-swap-horizontal",
               shortcut="Tab", category=ActionCategory.PANELS.value, order=2)
    )
    action_registry.register(
        Action(id="go_up", name="Subir nivel", icon="mdi-arrow-up",
               shortcut="Backspace", category=ActionCategory.PANELS.value, order=3)
    )
    action_registry.register(
        Action(id="open_in_explorer", name="Abrir en Explorador", icon="mdi-folder-open-outline",
               category=ActionCategory.FILE.value, order=6,
               handler=_open_in_explorer)
    )
    action_registry.register(
        Action(id="sync_panels", name="Sincronizar paneles", icon="mdi-sync",
               category=ActionCategory.PANELS.value, order=4)
    )
    action_registry.register(
        Action(id="plugin_compare", name="Comparar directorios", icon="mdi-compare",
               handler=_run_compare_dirs, category=ActionCategory.PLUGINS.value, order=1)
    )
    action_registry.register(
        Action(id="plugin_multi_rename", name="Renombrado múltiple",
               icon="mdi-format-list-checks",
               category=ActionCategory.PLUGINS.value, order=2)
    )
    action_registry.register(
        Action(id="plugin_organize", name="Organizar archivos", icon="mdi-folder-sync",
               handler=_run_organize, category=ActionCategory.PLUGINS.value, order=3)
    )
    action_registry.register(
        Action(id="search", name="Buscar archivos", icon="mdi-magnify",
               shortcut="Alt+F7", category=ActionCategory.PLUGINS.value, order=4)
    )
    action_registry.register(
        Action(id="add_bookmark", name="Añadir marcador", icon="mdi-star-plus",
               category=ActionCategory.FILE.value, order=5,
               handler=_add_current_to_bookmarks)
    )
    action_registry.register(
        Action(id="edit_bookmarks", name="Editar marcadores", icon="mdi-star",
               category=ActionCategory.PLUGINS.value, order=5)
    )
    action_registry.register(
        Action(id="about", name="Acerca de", icon="mdi-information",
               category=ActionCategory.HELP.value, order=1,
               handler=_show_about)
    )


register_core_actions()
