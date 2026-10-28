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
from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox

from src.core.fs_utils import get_locked_paths
from src.core.terminal import open_wezterm
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


def _copiar_mover_a_mtp_bloqueado(ctx: ActionContext, d: object, verbo: str) -> bool:
    """
    El destí és una ruta Shell (dispositiu iPhone/MTP): l'escriptura directa
    no està suportada (no és una unitat de disc real). Mostra un avís clar i
    retorna True per cancel·lar l'operació.
    """
    if not _is_shell_path(d):
        return False
    QMessageBox.warning(
        ctx.parent,
        verbo,
        f"No se puede {verbo.lower()} directamente a un dispositivo iPhone/MTP.\n\n"
        "La ruta de destino es un espacio de nombres Shell del dispositivo "
        "(no es una unidad de disco real), por lo que la escritura directa "
        "falla (\"medio protegido contra escritura\" o \"permiso denegado\").\n\n"
        f"Para {verbo.lower()} archivos DESDE el iPhone al PC:\n"
        "1. Deje el panel del iPhone como PANEL ACTIVO.\n"
        "2. Seleccione los archivos y pulse Copiar/Mover.\n"
        "3. El panel inactivo debe ser la unidad de PC de destino.",
        QMessageBox.StandardButton.Ok,
    )
    return True


def _no_selection(ctx: ActionContext, title: str):
    """Avisa l'usuari enlloc de no fer res (F5/F6 no semblaven funcionar)."""
    QMessageBox.information(
        ctx.parent,
        title,
        "No hay elementos seleccionados.\n\n"
        "Selecciona uno o varios elementos en el panel activo y vuelve a intentarlo.",
    )


def _confirm_delete_enabled(ctx: ActionContext) -> bool:
    """Indica si cal demanar confirmació abans d'eliminar (opció de configuració).

    Si no hi ha configuració accessible (per exemple en proves), es confirma
    sempre per seguretat: es prefereix un diàleg de més a una eliminació
    accidental.
    """
    config = getattr(ctx.parent, "config", None)
    if config is None:
        return True
    getter = getattr(config, "get_confirm_delete", None)
    if getter is None:
        return True
    try:
        return bool(getter())
    except Exception:
        logger.warning("No s'ha pogut llegir confirm_delete de la configuració", exc_info=True)
        return True


def _copy_files(ctx: ActionContext):
    s = ctx.active_panel.get_selected_paths()
    if not s:
        _no_selection(ctx, "Copiar")
        return
    d = ctx.inactive_panel.current_path
    if _copiar_mover_a_mtp_bloqueado(ctx, d, "Copiar"):
        return
    if (
        s
        and QMessageBox.question(ctx.parent, "Copiar", f"¿Copiar {len(s)} items?")
        == QMessageBox.StandardButton.Yes
    ):
        if _is_shell_path(s[0]):
            # MTP/iPhone: còpia en background (la síncrona congelava la UI)
            if ctx.run_operation:
                from src.core.jobs import MtpCopyJob  # noqa: PLC0415

                job = MtpCopyJob(s, d)
                job.signals.finished.connect(ctx.active_panel.refresh)
                ctx.run_operation(job, "Copiant del iPhone")
            return
        if ctx.run_operation:
            ctx.run_operation(ctx.engine.queue_copy(s, d), "Copiando")


def _move_files(ctx: ActionContext):
    s = ctx.active_panel.get_selected_paths()
    if not s:
        _no_selection(ctx, "Mover")
        return
    d = ctx.inactive_panel.current_path
    if _copiar_mover_a_mtp_bloqueado(ctx, d, "Mover"):
        return
    if (
        s
        and QMessageBox.question(ctx.parent, "Mover", f"¿Mover {len(s)} items?")
        == QMessageBox.StandardButton.Yes
    ):
        if _is_shell_path(s[0]):
            # MTP/iPhone: no hi ha move natiu fiable -> còpia en background
            if ctx.run_operation:
                from src.core.jobs import MtpCopyJob  # noqa: PLC0415

                job = MtpCopyJob(s, d)
                job.signals.finished.connect(ctx.active_panel.refresh)
                ctx.run_operation(job, "Copiant del iPhone")
            return
        if ctx.run_operation:
            ctx.run_operation(ctx.engine.queue_move(s, d), "Moviendo")


def _delete_files(ctx: ActionContext):
    s = ctx.active_panel.get_selected_paths()
    if not s:
        _no_selection(ctx, "Eliminar")
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
    reply = QMessageBox.StandardButton.Yes
    if _confirm_delete_enabled(ctx):
        reply = QMessageBox.question(
            ctx.parent,
            "Eliminar",
            f"¿Eliminar {len(s)} elementos?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
    if reply == QMessageBox.StandardButton.Yes and ctx.run_operation:
        ctx.run_operation(ctx.engine.queue_delete(s, True), "Eliminando")


def _secure_delete(ctx: ActionContext):
    """Borrat segur: sobreescriu el contingut abans de suprimir els elements.

    Reutilitza el motor d'operacions (SecureDeleteJob) perquè el procés
    llarg es mostri amb la barra de progrés i es pugui cancel·lar.
    """
    s = ctx.active_panel.get_selected_paths()
    if not s:
        _no_selection(ctx, "Borrado seguro")
        return

    from src.ui.dialogs.secure_delete_dialog import SecureDeleteDialog  # noqa: PLC0415

    dialog = SecureDeleteDialog(ctx.parent, s)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    params = dialog.params()
    if ctx.run_operation:
        job = ctx.engine.queue_secure_delete(s, params)
        job.signals.finished.connect(ctx.active_panel.refresh)
        ctx.run_operation(job, "Borrado seguro")


def _create_folder(ctx: ActionContext):
    n, ok = QInputDialog.getText(ctx.parent, "Nueva Carpeta", "Nombre:")
    if ok and n:
        full_path = os.path.join(ctx.active_panel.current_path, n)
        try:
            os.mkdir(full_path)
            ctx.active_panel.refresh()
            ctx.active_panel.select_and_focus(full_path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(ctx.parent, "Error", str(e))


def _duplicate_selected(ctx: ActionContext):
    if not ctx.active_panel.get_selected_paths():
        _no_selection(ctx, "Duplicar")
        return
    ctx.active_panel.duplicate_selected()


def _open_terminal_here(ctx: ActionContext):
    subprocess.Popen(["cmd.exe", "/k", "cd", "/d", ctx.active_panel.current_path])


def _open_powershell_here(ctx: ActionContext):
    path = ctx.active_panel.current_path
    subprocess.Popen(["powershell.exe", "-NoExit", "-Command", f'Set-Location "{path}"'])


def _open_wezterm_here(ctx: ActionContext):
    """Obre WezTerm al path actiu; fallback a PowerShell si no està instal·lat."""
    path = ctx.active_panel.current_path
    if open_wezterm(path):
        return
    try:
        QMessageBox.warning(
            ctx.parent,
            "WezTerm no trobat",
            "No s'ha trobat WezTerm instal·lat.\n\n"
            "S'obrirà PowerShell com a alternativa.\n"
            "(Instal·la WezTerm des de https://wezfurlong.org/wezterm/)",
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        subprocess.Popen(["powershell.exe", "-NoExit", "-Command", f'Set-Location "{path}"'])
    except Exception as e:  # noqa: BLE001
        try:
            QMessageBox.critical(ctx.parent, "Error", f"No s'ha pogut obrir cap terminal:\n{e}")
        except Exception:  # noqa: BLE001
            pass


def _open_in_explorer(ctx: ActionContext):
    QDesktopServices.openUrl(QUrl.fromLocalFile(ctx.active_panel.current_path))


def _go_to_folder(ctx: ActionContext):
    p, ok = QInputDialog.getText(ctx.parent, "Ir a", "Ruta:", text=ctx.active_panel.current_path)
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
    if not s:
        _no_selection(ctx, "Ver")
        return
    if os.path.isfile(s[0]):
        QDesktopServices.openUrl(QUrl.fromLocalFile(s[0]))


def _edit_file(ctx: ActionContext):
    s = ctx.active_panel.get_selected_paths()
    if not s:
        _no_selection(ctx, "Editar")
        return
    if os.path.isfile(s[0]):
        subprocess.Popen(["notepad.exe", s[0]])


def _show_about(ctx: ActionContext):
    # El diàleg About viu a MainWindow — abans l'acció no tenia handler i no feia res
    if hasattr(ctx.parent, "show_about_dialog"):
        ctx.parent.show_about_dialog()


# === Handlers que abans eren "orfes" (declarats al registre però sense handler) ===


def _copy_path(ctx: ActionContext):
    """Copia la ruta del fitxer seleccionat al porta-retalls."""
    ctx.active_panel.copy_path_to_clipboard()


def _exit_app(ctx: ActionContext):
    """Tanca l'aplicació (equivalent a Alt+F4)."""
    if ctx.parent is not None:
        ctx.parent.close()


def _rename(ctx: ActionContext):
    """Reanomena l'element seleccionat (F2)."""
    if not ctx.active_panel.get_selected_paths():
        _no_selection(ctx, "Renombrar")
        return
    ctx.active_panel.rename_selected_item()


def _select_all(ctx: ActionContext):
    """Selecciona tots els elements del panell actiu (Ctrl+A)."""
    ctx.active_panel.select_all()


def _invert_selection(ctx: ActionContext):
    """Inverteix la selecció del panell actiu (Ctrl+I)."""
    ctx.active_panel.invert_selection()


def _deselect_all(ctx: ActionContext):
    """Deselecciona tot (Ctrl+Shift+A)."""
    ctx.active_panel.clear_selection()


def _refresh(ctx: ActionContext):
    """Refresca el panell actiu (Ctrl+R)."""
    ctx.active_panel.refresh()


def _switch_panel(ctx: ActionContext):
    """Canvia al panell inactiu (Tab)."""
    if ctx.parent is not None:
        ctx.parent.set_active_panel(ctx.inactive_panel)


def _go_up(ctx: ActionContext):
    """Puja un nivell al panell actiu (Retrocés / Backspace)."""
    ctx.active_panel.go_up()


def _sync_dirs(ctx: ActionContext):
    """Obre el diàleg de sincronització de directoris."""
    if ctx.parent is not None and hasattr(ctx.parent, "open_sync_dirs_dialog"):
        ctx.parent.open_sync_dirs_dialog()


def _search(ctx: ActionContext):
    """Obre el diàleg de cerca de fitxers (Alt+F7)."""
    if ctx.parent is not None and hasattr(ctx.parent, "open_search_files_dialog"):
        ctx.parent.open_search_files_dialog()


def _edit_bookmarks(ctx: ActionContext):
    """Obre el gestor de marcadors."""
    if ctx.parent is not None and hasattr(ctx.parent, "open_bookmarks_editor"):
        ctx.parent.open_bookmarks_editor()


def _quick_look(ctx: ActionContext):
    """Mostra/amaga la previsualització ràpida (F3)."""
    if ctx.parent is not None and hasattr(ctx.parent, "toggle_quick_look"):
        ctx.parent.toggle_quick_look()


# === Handlers per a plugins ===


def _run_compare_dirs(api):
    compare_dirs(api)


def _run_organize(api):
    run_organizer(api)


# === Registre ===


def register_core_actions():
    action_registry.register(
        Action(
            id="new_folder",
            name="Nueva carpeta",
            icon="mdi-folder-plus",
            shortcut="F7",
            category=ActionCategory.FILE.value,
            order=1,
            handler=_create_folder,
        )
    )
    action_registry.register(
        Action(
            id="open_terminal",
            name="Terminal aquí",
            icon="mdi-terminal-outline",
            category=ActionCategory.FILE.value,
            order=2,
            handler=_open_terminal_here,
        )
    )
    action_registry.register(
        Action(
            id="open_powershell",
            name="PowerShell aquí",
            icon="mdi-console",
            category=ActionCategory.FILE.value,
            order=3,
            handler=_open_powershell_here,
        )
    )
    action_registry.register(
        Action(
            id="open_wezterm",
            name="WezTerm aquí",
            icon="mdi-wezterm",
            category=ActionCategory.FILE.value,
            order=4,
            handler=_open_wezterm_here,
        )
    )
    action_registry.register(
        Action(
            id="copy_path",
            name="Copiar ruta",
            icon="mdi-content-copy-outline",
            shortcut="Ctrl+Shift+C",
            category=ActionCategory.FILE.value,
            order=5,
            handler=_copy_path,
        )
    )
    action_registry.register(
        Action(
            id="exit",
            name="Salir",
            icon="mdi-exit-to-app",
            shortcut="Alt+F4",
            category=ActionCategory.FILE.value,
            order=99,
            handler=_exit_app,
        )
    )
    action_registry.register(
        Action(
            id="rename",
            name="Renombrar",
            icon="mdi-pencil",
            shortcut="F2",
            category=ActionCategory.EDIT.value,
            order=1,
            handler=_rename,
        )
    )
    action_registry.register(
        Action(
            id="copy",
            name="Copiar",
            icon="mdi-content-copy",
            shortcut="F5",
            category=ActionCategory.EDIT.value,
            order=2,
            handler=_copy_files,
        )
    )
    action_registry.register(
        Action(
            id="move",
            name="Mover",
            icon="mdi-file-move",
            shortcut="F6",
            category=ActionCategory.EDIT.value,
            order=3,
            handler=_move_files,
        )
    )
    action_registry.register(
        Action(
            id="duplicate",
            name="Duplicar",
            icon="mdi-content-duplicate",
            shortcut="F9",
            category=ActionCategory.EDIT.value,
            order=4,
            handler=_duplicate_selected,
        )
    )
    action_registry.register(
        Action(
            id="delete",
            name="Borrar",
            icon="mdi-delete",
            shortcut="F8",
            category=ActionCategory.EDIT.value,
            order=5,
            handler=_delete_files,
        )
    )
    action_registry.register(
        Action(
            id="secure_delete",
            name="Borrado seguro",
            icon="mdi-lock",
            shortcut="Ctrl+Shift+Del",
            category=ActionCategory.EDIT.value,
            order=6,
            handler=_secure_delete,
        )
    )
    action_registry.register(
        Action(
            id="goto",
            name="Ir a...",
            icon="mdi-folder-open",
            shortcut="Ctrl+G",
            category=ActionCategory.EDIT.value,
            order=6,
            handler=_go_to_folder,
        )
    )
    action_registry.register(
        Action(
            id="view_file",
            name="Ver archivo",
            icon="mdi-eye",
            # F3 NO és d'aquesta acció: F3 és el Quick Look (veure quick_look).
            category=ActionCategory.VIEW.value,
            order=1,
            handler=_view_file,
        )
    )
    action_registry.register(
        Action(
            id="quick_look",
            name="Quick Look",
            icon="mdi-eye-outline",
            shortcut="F3",
            category=ActionCategory.VIEW.value,
            order=3,
            handler=_quick_look,
        )
    )
    action_registry.register(
        Action(
            id="edit_file",
            name="Editar archivo",
            icon="mdi-pencil",
            shortcut="F4",
            category=ActionCategory.VIEW.value,
            order=2,
            handler=_edit_file,
        )
    )
    action_registry.register(
        Action(
            id="select_all",
            name="Seleccionar todo",
            icon="mdi-select-all",
            shortcut="Ctrl+A",
            category=ActionCategory.SELECT.value,
            order=1,
            handler=_select_all,
        )
    )
    action_registry.register(
        Action(
            id="invert_selection",
            name="Invertir selección",
            icon="mdi-select-inverse",
            shortcut="Ctrl+I",
            category=ActionCategory.SELECT.value,
            order=2,
            handler=_invert_selection,
        )
    )
    action_registry.register(
        Action(
            id="deselect_all",
            name="Deseleccionar todo",
            icon="mdi-selection-off",
            shortcut="Ctrl+Shift+A",
            category=ActionCategory.SELECT.value,
            order=3,
            handler=_deselect_all,
        )
    )
    action_registry.register(
        Action(
            id="refresh",
            name="Refrescar",
            icon="mdi-refresh",
            shortcut="Ctrl+R",
            category=ActionCategory.PANELS.value,
            order=1,
            handler=_refresh,
        )
    )
    action_registry.register(
        Action(
            id="switch_panel",
            name="Cambiar panel",
            icon="mdi-swap-horizontal",
            shortcut="Tab",
            category=ActionCategory.PANELS.value,
            order=2,
            handler=_switch_panel,
        )
    )
    action_registry.register(
        Action(
            id="go_up",
            name="Subir nivel",
            icon="mdi-arrow-up",
            shortcut="Backspace",
            category=ActionCategory.PANELS.value,
            order=3,
            handler=_go_up,
        )
    )
    action_registry.register(
        Action(
            id="open_in_explorer",
            name="Abrir en Explorador",
            icon="mdi-folder-open-outline",
            category=ActionCategory.FILE.value,
            order=7,
            handler=_open_in_explorer,
        )
    )
    action_registry.register(
        Action(
            id="sync_dirs",
            name="Sincronizar directorios",
            icon="mdi-sync",
            category=ActionCategory.PANELS.value,
            order=4,
            handler=_sync_dirs,
        )
    )
    action_registry.register(
        Action(
            id="plugin_compare",
            name="Comparar directorios",
            icon="mdi-compare",
            handler=_run_compare_dirs,
            category=ActionCategory.PLUGINS.value,
            order=1,
        )
    )
    action_registry.register(
        Action(
            id="plugin_multi_rename",
            name="Renombrado múltiple",
            icon="mdi-format-list-checks",
            category=ActionCategory.PLUGINS.value,
            order=2,
        )
    )
    action_registry.register(
        Action(
            id="plugin_organize",
            name="Organizar archivos",
            icon="mdi-folder-sync",
            handler=_run_organize,
            category=ActionCategory.PLUGINS.value,
            order=3,
        )
    )
    action_registry.register(
        Action(
            id="search",
            name="Buscar archivos",
            icon="mdi-magnify",
            shortcut="Alt+F7",
            category=ActionCategory.PLUGINS.value,
            order=4,
            handler=_search,
        )
    )
    action_registry.register(
        Action(
            id="add_bookmark",
            name="Añadir marcador",
            icon="mdi-star-plus",
            category=ActionCategory.FILE.value,
            order=6,
            handler=_add_current_to_bookmarks,
        )
    )
    action_registry.register(
        Action(
            id="edit_bookmarks",
            name="Editar marcadores",
            icon="mdi-star",
            category=ActionCategory.PLUGINS.value,
            order=5,
            handler=_edit_bookmarks,
        )
    )
    action_registry.register(
        Action(
            id="about",
            name="Acerca de",
            icon="mdi-information",
            category=ActionCategory.HELP.value,
            order=1,
            handler=_show_about,
        )
    )


register_core_actions()
