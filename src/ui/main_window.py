import ctypes
import logging
import os
import sys
from functools import partial
from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QFont, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.actions import ActionContext, action_registry
from src.core.app_launcher import AppLauncher
from src.core.bookmarks import BookmarkManager
from src.core.config import ConfigManager
from src.core.engine import OperationEngine
from src.core.plugin_manager import PluginManager
from src.core.taskbar_progress import TaskbarProgress
from src.icon_loader import IconLoader
from src.toolbar_manager import ToolbarManager
from src.ui.app_launcher_editor import AppLauncherEditor
from src.ui.bookmarks_editor import BookmarksEditor
from src.ui.conflict_dialog import ConflictDialog
from src.ui.panel import FilePanel
from src.ui.quick_look import QuickLook
from src.ui.search_dialog import SearchDialog
from src.ui.settings_dialog import SettingsDialog
from src.version import __author__, __dependencies__, __tech_stack__, __version__, __website__

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"JMComander {__version__} - by {__author__}")
        logger.info("JMComander version %s by %s (%s)", __version__, __author__, __website__)

        self._init_core()
        self._init_window_geometry()
        self._init_ui_structure()
        self._init_panels()
        self._init_background_progress()
        self._init_quick_look()
        self._init_toolbar()
        self._init_bookmarks_bar()
        self._init_content()
        self._init_signals()
        self._init_quicklook_shortcut()

        self.set_active_panel(self.left_panel)

        QTimer.singleShot(200, self._startup_refresh)

    def _init_core(self):
        self.config = ConfigManager()
        self.icon_loader = IconLoader()
        self.engine = OperationEngine.instance(self)
        self.bookmarks = BookmarkManager()
        self.app_launcher = AppLauncher()
        self.plugin_manager = PluginManager(self)
        self._setup_window_icon()

    def _init_window_geometry(self):
        from PySide6.QtGui import QGuiApplication  # noqa: PLC0415

        geom = self.config.get_geometry()
        valid_geometry = None

        if geom:
            x, y, w, h = geom
            for screen in QGuiApplication.screens():
                screen_geom = screen.availableGeometry()
                if (
                    x >= screen_geom.left()
                    and y >= screen_geom.top()
                    and x + w <= screen_geom.right()
                    and y + h <= screen_geom.bottom()
                ):
                    valid_geometry = geom
                    logger.info(
                        f"Finestra adaptada a pantalla:"
                        f" {screen.name()}"
                        f" {screen_geom.width()}x{screen_geom.height()}"
                    )
                    break

            if not valid_geometry:
                logger.warning(
                    f"Geometria fora de totes les pantalles: {geom}. Buscant pantalla..."  # noqa: G004
                )

        if valid_geometry:
            self.setGeometry(QRect(*valid_geometry))
        else:
            primary_screen = QGuiApplication.primaryScreen()
            if primary_screen:
                primary_geom = primary_screen.availableGeometry()
                new_w, new_h = 1200, 500
                if new_w > primary_geom.width():
                    new_w = primary_geom.width() - 50
                if new_h > primary_geom.height():
                    new_h = primary_geom.height() - 50
                new_x = primary_geom.left() + (primary_geom.width() - new_w) // 2
                new_y = primary_geom.top() + (primary_geom.height() - new_h) // 2
                self.setGeometry(new_x, new_y, new_w, new_h)
                logger.info("Finestra centrada: %sx%s a %s,%s", new_w, new_h, new_x, new_y)
            else:
                self.resize(1200, 500)

        if self.config.is_maximized():
            self.showMaximized()

    def _init_ui_structure(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self._main_layout = QVBoxLayout(central_widget)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

    def _validate_startup_path(self, path):
        if path and (os.path.exists(path) or path.startswith("::") or "shell::" in path.lower()):
            return path

        recent = self.config.get_recent_paths()
        work_dir = self.config.get_work_directory()
        fallback_candidates = []
        if work_dir and os.path.isdir(work_dir):
            fallback_candidates.append(work_dir)
        for rp in recent:
            if rp and os.path.isdir(rp) and rp not in fallback_candidates and not rp.startswith("::") and "shell::" not in rp.lower():
                fallback_candidates.append(rp)
        for candidate in fallback_candidates:
            logger.info("Path no trobat, provant ruta local: %s (original: %s)", candidate, path)
            return candidate

        home = os.path.expanduser("~")
        if os.path.isdir(home):
            logger.info("Path no trobat, usant directori usuari: %s (original: %s)", home, path)
            return home
        logger.info("Path i home no trobats, usant C:\\: %s", path)
        return os.path.abspath(os.sep)

    def _init_panels(self):
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        left_path = self._validate_startup_path(self.config.get_left_path())
        right_path = self._validate_startup_path(self.config.get_right_path())
        self.left_panel = FilePanel("left", left_path, detect_iphone_on_init=True)
        self.right_panel = FilePanel("right", right_path, detect_iphone_on_init=False)

        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setHandleWidth(4)
        self._main_layout.addWidget(self.splitter, 1)

        QTimer.singleShot(0, self._init_splitter_sizes)

        self.active_panel = self.left_panel
        self.inactive_panel = self.right_panel

    def _init_background_progress(self):
        self.bg_progress_frame = QFrame()
        self.bg_progress_frame.setFixedHeight(45)
        self.bg_progress_frame.setStyleSheet(
            "background-color: #e8f4fc; border-top: 2px solid #2196F3;"
        )
        self.bg_progress_frame.hide()
        bg_layout = QHBoxLayout(self.bg_progress_frame)
        bg_layout.setContentsMargins(10, 8, 10, 8)

        self.bg_operation_label = QLabel("Operación")
        self.bg_operation_label.setStyleSheet("font-weight: bold; color: #1565C0; font-size: 12px;")
        bg_layout.addWidget(self.bg_operation_label)

        self.bg_file_label = QLabel("")
        self.bg_file_label.setStyleSheet("color: #1565C0; font-size: 11px;")
        self.bg_file_label.setMaximumWidth(500)
        bg_layout.addWidget(self.bg_file_label)

        bg_layout.addStretch()

        self.bg_progress_bar = QProgressBar()
        self.bg_progress_bar.setFixedWidth(200)
        self.bg_progress_bar.setFixedHeight(20)
        self.bg_progress_bar.setRange(0, 100)
        self.bg_progress_bar.setValue(0)
        self.bg_progress_bar.setTextVisible(True)
        self.bg_progress_bar.setInvertedAppearance(False)
        bg_layout.addWidget(self.bg_progress_bar)

        self.bg_cancel_btn = QPushButton("✕")
        self.bg_cancel_btn.setFixedSize(30, 24)
        self.bg_cancel_btn.setStyleSheet(
            "background-color: #f44336; color: white; border-radius: 3px; font-weight: bold;"
        )
        self.bg_cancel_btn.clicked.connect(self._cancel_background_operation)
        bg_layout.addWidget(self.bg_cancel_btn)

        self._main_layout.addWidget(self.bg_progress_frame)

    def _init_quick_look(self):
        self.quick_look = QuickLook(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.quick_look)
        self.quick_look.hide()

    def _init_toolbar(self):
        self.main_toolbar = QToolBar("Main")
        self.main_toolbar.setMovable(False)
        self.main_toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(self.main_toolbar)
        self.toolbar_manager = ToolbarManager(self)

    def _init_bookmarks_bar(self):
        self.bm_bar = QToolBar("Bookmarks Quick")
        self.bm_bar.setMovable(False)
        self.bm_bar.setFixedHeight(34)
        self.addToolBarBreak()
        self.addToolBar(self.bm_bar)

    def _init_content(self):
        self.plugin_manager.initialize()
        self._create_toolbar_widgets()
        self.setup_actions()
        self.refresh_main_toolbar()
        self.refresh_bookmarks_bar()
        self.update_apps_menu()
        self.setup_function_bar(self._main_layout)
        self.setup_enhanced_status_bar()

    def _init_signals(self):
        for p in [self.left_panel, self.right_panel]:
            p.focused.connect(lambda p_ref=p: self.set_active_panel(p_ref))
            p.path_changed.connect(self._on_path_changed)
            p.selection_changed.connect(lambda p_ref=p: self._on_selection_changed(p_ref))
            p.delete_requested.connect(self.delete_files)
            if p.current_path:
                self.config.add_recent_path(p.current_path)

        self.update_recent_paths_menu()
        # Reconstrucció lazy: el menú de recents es refa només quan s'obré
        if hasattr(self, "btn_recent_paths"):
            self.btn_recent_paths.pressed.connect(self.update_recent_paths_menu)

    def _init_quicklook_shortcut(self):
        self.action_toggle_quicklook = QAction("Quick Look", self)
        self.action_toggle_quicklook.setShortcut("F3")
        self.action_toggle_quicklook.triggered.connect(self._toggle_quick_look)
        self.addAction(self.action_toggle_quicklook)

    def _startup_refresh(self):
        for panel in [self.left_panel, self.right_panel]:
            try:
                panel.refresh(force=True)
            except Exception as e:  # noqa: BLE001
                logger.debug("Startup refresh error per %s: %s", panel.panel_id, e)

    def _init_splitter_sizes(self):
        """Initialize splitter with equal panel sizes"""
        total_width = self.splitter.width()
        if total_width > 0:
            half = total_width // 2
            self.splitter.setSizes([half, half])

    def _create_toolbar_widgets(self):
        self.btn_settings = self._create_settings_button()
        self.btn_view_mode = self._create_view_mode_button()
        self.btn_recent_paths = self._create_recent_paths_button()
        self.btn_plugins = self._create_plugins_button()
        self.btn_bookmarks_menu = self._create_bookmarks_button()
        self.btn_apps_menu = self._create_apps_button()

        self.btn_folders_only = QToolButton(self)
        self.btn_folders_only.setObjectName("btn_folders_only")
        self.btn_folders_only.setCheckable(True)
        self.btn_folders_only.setIcon(self.icon_loader.load_icon("folder-file", "C"))
        self.btn_folders_only.setToolTip("Solo carpetas (Ctrl+Shift+F)")
        self.btn_folders_only.clicked.connect(self.toggle_folders_only)

    def setup_actions(self):
        self.actions_map = {}

        def add_act(key, icon_name, text, slot, shortcut=None):
            logging.debug(
                f"setup_actions: creating action '{key}'"
                f" -> {slot.__name__ if hasattr(slot, '__name__') else slot}"
            )
            icon = self.icon_loader.load_icon(icon_name, text[0])
            act = QAction(icon, text, self)
            if shortcut:
                act.setShortcut(QKeySequence(shortcut))
            act.triggered.connect(slot)
            self.actions_map[key] = act
            self.addAction(act)
            return act

        add_act("up", "mdi-arrow-up", "Subir", self.go_up)
        add_act("root", "mdi-harddisk", "Raíz", self.go_root)
        add_act("home", "mdi-home", "Usuario", self.go_home)
        add_act("back", "mdi-arrow-left", "Enrere", self.go_back, "Alt+Left")
        add_act("forward", "mdi-arrow-right", "Endavant", self.go_forward, "Alt+Right")
        add_act("new_tab", "mdi-tab-plus", "Nova pestanya", self.new_tab, "Ctrl+T")
        add_act("close_tab", "mdi-tab-remove", "Tancar pestanya", self.close_tab, "Ctrl+W")
        add_act("hotlist", "mdi-folder-star", "Directoris freqüents", self.show_hotlist, "Ctrl+D")
        add_act("sync_dirs", "mdi-sync", "Sincronitzar directoris", self.show_sync_dirs)
        add_act("refresh", "mdi-refresh", "Refrescar", self.refresh_panel)
        add_act("search", "mdi-magnify", "Buscar", self.open_search_dialog, "Alt+F7")
        add_act("swap", "mdi-swap-horizontal", "Intercambiar", self.swap_panels, "Ctrl+U")
        add_act("equal", "mdi-arrow-right-bold", "Igualar", self.equal_panels)
        add_act(
            "equal_reverse",
            "mdi-arrow-left-bold",
            "IgualarInv",
            self.equal_panels_reverse,
            "Ctrl+Alt+Left",
        )
        add_act("explorer", "mdi-monitor", "Explorer", self.open_in_explorer)
        add_act("terminal", "mdi-terminal-outline", "Terminal", self.open_terminal_here)
        add_act("powershell", "mdi-console", "PowerShell", self.open_powershell_here)
        add_act("duplicate", "mdi-content-duplicate", "Duplicar", self.duplicate_selected, "F9")
        add_act("goto", "mdi-folder-open", "Ir a...", self.go_to_folder, "Ctrl+G")
        self._goto_shift_action = QAction("Ir a (Shift+F7)", self)
        self._goto_shift_action.setShortcut(QKeySequence("Shift+F7"))
        self._goto_shift_action.triggered.connect(self.go_to_folder)
        self.addAction(self._goto_shift_action)
        add_act("select_all", "mdi-select-all", "Sel. Todo", self.select_all, "Ctrl+A")
        add_act("copy_path", "mdi-content-copy-outline", "Copiar ruta", self.copy_path_to_clipboard)
        add_act("new_folder", "mdi-folder-plus", "Nueva carpeta", self.create_folder)
        add_act(
            "invert_selection",
            "mdi-select-inverse",
            "Invertir selección",
            self.invert_selection,
            "Ctrl+I",
        )
        add_act("deselect_all", "mdi-selection-off", "Deseleccionar todo", self.deselect_all)
        add_act("rename", "mdi-rename-box", "Renombrar", self.rename_item, "F2")
        add_act("view", "mdi-eye", "Ver", self.view_file)
        add_act("edit", "mdi-pencil", "Editar", self.edit_file, "F4")
        add_act("copy", "mdi-content-copy", "Copiar", self.copy_files, "F5")
        add_act("move", "mdi-file-move", "Mover", self.move_files, "F6")
        add_act("new_folder_act", "mdi-folder-plus", "Nueva carpeta", self.create_folder, "F7")
        add_act("delete", "mdi-delete", "Borrar", self.delete_files, "F8")

        self.actions_map.update({"folders_only": self.btn_folders_only})
        self.actions_map["help"] = QAction(
            self.icon_loader.load_icon("mdi-help-circle", "?"), "Ajuda", self
        )
        self.actions_map["help"].setShortcut(QKeySequence("F1"))
        self.actions_map["help"].triggered.connect(self.show_quick_help)

        widget_map = {
            "settings": "btn_settings",
            "view_mode": "btn_view_mode",
            "recent_paths": "btn_recent_paths",
            "plugins": "btn_plugins",
            "bookmarks": "btn_bookmarks_menu",
            "apps": "btn_apps_menu",
            "folders_only": "btn_folders_only",
        }
        for k, attr_name in widget_map.items():
            w = getattr(self, attr_name)
            self.toolbar_manager.register_special_widget(k, w)

    def set_active_panel(self, panel):
        self.active_panel = panel
        self.inactive_panel = self.right_panel if panel == self.left_panel else self.left_panel

        # Aplicar estils NOMÉS si el color de fons canvia (cada setStyleSheet
        # força recàlcul d'estil complet del subarbre)
        for p, active in [(self.active_panel, True), (self.inactive_panel, False)]:
            bg = "#bbdefb" if active else "#f5f5f5"
            if getattr(p.nav_frame, "_active_bg", None) != bg:
                p.nav_frame._active_bg = bg  # noqa: SLF001
                p.nav_frame.setStyleSheet(
                    f"#navFrame {{ background-color: {bg}; }}"
                    f"BreadcrumbBar {{ background-color: {bg}; }}"
                )
                p.tree.header().setStyleSheet(f"background-color: {bg};")
                p.path_input.setStyleSheet(
                    f"background-color: {'#fff9c4' if active else '#fafafa'};"
                )

        self.inactive_panel.clear_selection()
        if hasattr(self.active_panel, "current_view_widget"):
            self.active_panel.current_view_widget.setFocus()
        self.update_status_bar(self.active_panel)

    def refresh_main_toolbar(self):
        self.toolbar_manager.refresh_toolbar()

    def refresh_bookmarks_bar(self):
        self.bm_bar.clear()
        for bm in self.bookmarks.get_all():
            btn = QToolButton(self)
            btn.setText(bm["name"][:10])
            btn.setToolTip(f"{bm['name']}\n{bm['path']}")
            btn.setStyleSheet(
                "QToolButton { background-color: #f8f9fa;"
                " border: 1px solid #dee2e6;"
                " border-radius: 4px; padding: 4px; }"
            )
            btn.clicked.connect(partial(self._on_path_request, bm["path"]))
            self.bm_bar.addWidget(btn)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.bm_bar.addWidget(spacer)
        btn_add = QToolButton(self)
        btn_add.setText("+")
        btn_add.setToolTip("Afegir als marcadors")
        btn_add.setStyleSheet(
            "QToolButton { background-color: #e3f2fd;"
            " border: 1px solid #1976D2;"
            " border-radius: 4px; padding: 4px; font-weight: bold; }"
        )
        btn_add.clicked.connect(self.add_current_to_bookmarks)
        self.bm_bar.addWidget(btn_add)
        btn_m = QToolButton(self)
        btn_m.setText("⚙")
        btn_m.clicked.connect(self.open_bookmarks_manager)
        self.bm_bar.addWidget(btn_m)

    def update_apps_menu(self):
        menu = QMenu(self)
        menu.addAction("Gestionar aplicaciones", self.open_app_launcher_manager)
        menu.addSeparator()
        for app in self.app_launcher.get_all():
            menu.addAction(app["name"], partial(self._launch_app, app))
        if hasattr(self, "btn_apps_menu"):
            self.btn_apps_menu.setMenu(menu)

    def _launch_app(self, app):
        try:
            import subprocess  # noqa: PLC0415

            exe_path = app["path"]
            args = app.get("args", "").strip()

            cwd = self.active_panel.current_path
            ext = os.path.splitext(exe_path)[1].lower()

            if ext == ".vbs":
                cmd = ["wscript.exe", exe_path] + (args.split() if args else [])
                subprocess.Popen(cmd, cwd=cwd)
            elif ext in (".bat", ".cmd"):
                cmd = [exe_path] + (args.split() if args else [])
                subprocess.Popen(cmd, cwd=cwd, shell=True)
            elif args:
                subprocess.Popen([exe_path] + args.split(), cwd=cwd)  # noqa: RUF005
            else:
                subprocess.Popen(exe_path, cwd=cwd)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Error", f"No se pudo ejecutar {app['name']}:\n{e!s}")

    def open_app_launcher_manager(self):
        AppLauncherEditor(self.app_launcher, self).exec()
        self.update_apps_menu()

    def go_up(self):
        self.active_panel.go_up()

    def go_root(self):
        self.active_panel.go_root()

    def go_home(self):
        self.active_panel.go_home()

    def go_back(self):
        self.active_panel.go_back()

    def go_forward(self):
        self.active_panel.go_forward()

    def new_tab(self):
        self.active_panel.add_tab()

    def close_tab(self):
        if self.active_panel.tab_bar and self.active_panel.tab_bar.count() > 1:
            self.active_panel.tab_bar.removeTab(self.active_panel.tab_bar.currentIndex())

    def show_hotlist(self):
        from src.ui.dialogs.directory_hotlist import DirectoryHotlistDialog  # noqa: PLC0415

        dlg = DirectoryHotlistDialog(self.active_panel.current_path, self)
        dlg.directory_selected.connect(self.active_panel.set_path)
        dlg.exec()

    def show_sync_dirs(self):
        from src.ui.dialogs.sync_dirs import SyncDirsDialog  # noqa: PLC0415

        left = self.left_panel.current_path
        right = self.right_panel.current_path
        dlg = SyncDirsDialog(left, right, self)
        dlg.sync_completed.connect(self.refresh_both_panels)
        dlg.exec()

    def refresh_panel(self):
        logging.debug(f"refresh_panel called, active_panel={self.active_panel}")  # noqa: G004
        self.active_panel.refresh()

    def select_all(self):
        self.active_panel.select_all()

    def invert_selection(self):
        self.active_panel.invert_selection()

    def deselect_all(self):
        self.active_panel.clear_selection()

    def rename_item(self):
        self.active_panel.rename_selected_item()

    def copy_path_to_clipboard(self):
        self.active_panel.copy_path_to_clipboard()

    def toggle_folders_only(self):
        self.active_panel.set_folders_only(self.btn_folders_only.isChecked())

    def open_terminal_here(self):
        self._run_action("open_terminal")

    def open_powershell_here(self):
        self._run_action("open_powershell")

    def open_in_explorer(self):
        self._run_action("open_in_explorer")

    def go_to_folder(self):
        self._run_action("goto")

    def _toggle_quick_look(self):
        self.quick_look.setVisible(not self.quick_look.isVisible())
        if self.quick_look.isVisible():
            self._update_quick_look_preview()

    def _update_quick_look_preview(self):
        panel = self.active_panel
        selected = panel.get_selected_paths()
        if selected and len(selected) == 1:
            self.quick_look.update_preview(selected[0])
        else:
            self.quick_look.clear()

    def _on_selection_changed(self, panel):
        self.update_status_bar(panel)
        if self.quick_look.isVisible():
            self._update_quick_look_preview()

    def duplicate_selected(self):
        self._run_action("duplicate")

    def copy_files(self):
        self._run_action("copy")

    def move_files(self):
        self._run_action("move")

    def delete_files(self):
        self._run_action("delete")

    def create_folder(self):
        self._run_action("new_folder")

    def _on_path_request(self, p):
        # Assegurar que el panell actiu té el focus abans de canviar el path
        if hasattr(self.active_panel, 'setFocus'):
            self.active_panel.setFocus()
        logger.debug(f"_on_path_request called with path: {p}")
        self.active_panel.set_path(p)

    @property
    def _action_context(self) -> ActionContext:
        return ActionContext(
            active_panel=self.active_panel,
            inactive_panel=self.inactive_panel,
            engine=self.engine,
            bookmarks=self.bookmarks,
            parent=self,
            run_operation=self._run_operation,
            refresh_bookmarks_bar=self.refresh_bookmarks_bar,
            update_bookmarks_menu=self.update_bookmarks_menu,
        )

    def _run_action(self, action_id: str):
        action = action_registry.get(action_id)
        if action and action.handler:
            action.handler(self._action_context)
        else:
            logger.warning("Action %s not found or has no handler", action_id)

    def _on_path_changed(self, p):
        # Només muta en memòria; el menú es reconstrueix lazy al prémer el botó
        # (reconstruir QMenu + escriure config per navegació era treball inútil)
        self.config.add_recent_path(p)

    def update_plugins_menu(self):
        menu = QMenu("Plugins", self)
        plugins = self.plugin_manager.list_plugins()

        if not plugins:
            menu.addAction("(Sin plugins)").setEnabled(False)
        else:
            for plugin in plugins:
                plugin_menu = menu.addMenu(plugin.name)
                plugin_menu.setToolTip(f"v{plugin.version} - {plugin.description}")

                # Añadir acciones del plugin (sistema nuevo)
                if plugin.actions:
                    for action in plugin.actions:
                        act = QAction(action.get("name", plugin.name), self)
                        act.setToolTip(action.get("description", plugin.description))
                        icon_name = action.get("icon", "mdi-puzzle")
                        icon = self.icon_loader.load_icon(icon_name, "")
                        if icon:
                            act.setIcon(icon)
                        act.triggered.connect(
                            lambda _checked=False, a=action: self.run_action(a.get("id"))
                        )
                        plugin_menu.addAction(act)
                # Plugins antiguos: añadir acción por defecto que ejecute el plugin
                elif plugin.instance and hasattr(plugin.instance, "execute"):
                    act = QAction(f"Ejecutar {plugin.name}", self)
                    act.setToolTip(plugin.description)
                    icon = self.icon_loader.load_icon("mdi-puzzle", "")
                    if icon:
                        act.setIcon(icon)
                    act.triggered.connect(
                        lambda _checked=False, p=plugin: p.instance.execute(
                            self.plugin_manager._api  # noqa: SLF001
                        )
                    )
                    plugin_menu.addAction(act)

                # Añadir opción de configuración si existe
                config_dialog_class = self.plugin_manager.get_plugin_config_dialog(plugin.id)
                if config_dialog_class:
                    plugin_menu.addSeparator()
                    config_act = QAction("⚙ Configurar", self)
                    config_act.triggered.connect(
                        lambda _checked=False, p=plugin, d=config_dialog_class: (
                            self.open_plugin_config(p, d)
                        )
                    )
                    plugin_menu.addAction(config_act)

        if hasattr(self, "btn_plugins"):
            self.btn_plugins.setMenu(menu)

    def open_plugin_config(self, plugin, config_dialog_class):
        """Abre el diálogo de configuración de un plugin"""
        try:
            if config_dialog_class:
                # Nuevo sistema de plugins
                plugin_config = self.config.get_plugin_config(plugin.id, {})
                dialog = config_dialog_class(plugin_config, self)
                if dialog.exec():
                    new_config = dialog.get_config()
                    if new_config:
                        self.config.set_plugin_config(plugin.id, new_config)
            else:
                # Sistema antiguo con PluginInterface - buscar la instancia
                for loaded_plugin in self.plugin_manager.list_plugins():
                    if loaded_plugin.id == plugin.id:
                        # Buscar la instancia real del plugin
                        for item in loaded_plugin.path.parent.iterdir():
                            if (
                                item.is_file()
                                and item.suffix == ".py"
                                and item.stem == loaded_plugin.id
                            ):
                                try:
                                    import importlib.util  # noqa: PLC0415

                                    spec = importlib.util.spec_from_file_location(item.stem, item)
                                    module = importlib.util.module_from_spec(spec)
                                    spec.loader.exec_module(module)
                                    if hasattr(module, "PluginInterface"):
                                        instance = module.PluginInterface()
                                        if hasattr(instance, "show_config"):
                                            instance.show_config(self)
                                            return
                                except Exception as e:
                                    logger.exception("Error cargando instancia del plugin: %s", e)  # noqa: TRY401
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(
                self, "Error", f"No se pudo abrir la configuración de {plugin.name}:\n{e}"
            )

    def run_action(self, action_id):  # noqa: PLR0912
        """Ejecuta una acción por ID"""
        from src.core.plugin_api import PluginAPI  # noqa: PLC0415

        # Obtener el API en tiempo de ejecución (no usar self._api que puede ser None)
        api = PluginAPI(self)

        action = action_registry.get(action_id)
        if action and action.handler:
            # Verificar si el handler necesita argumentos (api)
            import inspect  # noqa: PLC0415

            sig = inspect.signature(action.handler)
            param_count = len(
                [p for p in sig.parameters.values() if p.default == inspect.Parameter.empty]
            )
            if param_count >= 1:
                # El handler necesita el api
                action.handler(api)
            else:
                action.handler()
        else:
            # Intentar ejecutar el plugin directamente desde el plugin_manager
            plugin_info = None
            for plugin in self.plugin_manager.list_plugins():
                for act in plugin.actions:
                    if act.get("id") == action_id:
                        plugin_info = plugin
                        break
                if plugin_info:
                    break

            if plugin_info and plugin_info.module:
                # Buscar la función handler en el módulo
                handler_name = None
                for act in plugin_info.actions:
                    if act.get("id") == action_id:
                        handler_name = act.get(
                            "handler",
                            action_id.replace("plugin_", "")
                            if action_id.startswith("plugin_")
                            else action_id,
                        )
                        break

                if handler_name and hasattr(plugin_info.module, handler_name):
                    handler = getattr(plugin_info.module, handler_name)
                    handler(api)
                elif hasattr(plugin_info.module, "execute"):
                    plugin_info.module.execute(api)
                else:
                    from PySide6.QtWidgets import QMessageBox  # noqa: PLC0415

                    QMessageBox.warning(
                        self, "Plugin", f"No se encontró el handler para la acción: {action_id}"
                    )
            else:
                from PySide6.QtWidgets import QMessageBox  # noqa: PLC0415

                QMessageBox.warning(
                    self, "Plugin", f"No se encontró el plugin o handler para: {action_id}"
                )

    def update_recent_paths_menu(self):
        if not hasattr(self, "btn_recent_paths"):
            return

        # Eliminar menú anterior si existe para evitar fugas
        old_menu = self.btn_recent_paths.menu()
        if old_menu:
            old_menu.deleteLater()

        menu = QMenu(self)
        paths = self.config.get_recent_paths()

        if not paths:
            menu.addAction("Sin rutas").setEnabled(False)
        else:
            for p in paths:
                menu.addAction(p, partial(self._on_path_request, p))

        menu.addSeparator()
        menu.addAction("Limpiar historial", self.clear_recent_paths)
        self.btn_recent_paths.setMenu(menu)

    def clear_recent_paths(self):
        self.config.clear_recent_paths()
        self.update_recent_paths_menu()

    def update_view_mode_menu(self):
        menu = QMenu(self)
        for n, m in [
            ("Detalles", "details"),
            ("Lista", "list"),
            ("Iconos P", "icons"),
            ("Iconos G", "icons_large"),
        ]:
            menu.addAction(n, partial(self.active_panel.set_view_mode, m))
        if hasattr(self, "btn_view_mode"):
            self.btn_view_mode.setMenu(menu)

    def update_bookmarks_menu(self):
        menu = QMenu(self)
        menu.addAction("Añadir", self.add_current_to_bookmarks)
        menu.addAction("Gestionar", self.open_bookmarks_manager)
        menu.addSeparator()
        for bm in self.bookmarks.get_all():
            menu.addAction(bm["name"], partial(self._on_path_request, bm["path"]))
        if hasattr(self, "btn_bookmarks_menu"):
            self.btn_bookmarks_menu.setMenu(menu)

    def add_current_to_bookmarks(self):
        self._run_action("add_bookmark")

    def open_settings(self):
        if SettingsDialog(self.config, self.plugin_manager, self).exec():
            self.refresh_main_toolbar()

    def open_bookmarks_manager(self):
        BookmarksEditor(self.bookmarks, self).exec()
        self.refresh_bookmarks_bar()
        self.update_bookmarks_menu()

    def view_file(self):
        self._run_action("view_file")

    def edit_file(self):
        self._run_action("edit_file")

    def show_quick_help(self):
        from src.ui.dialogs.quick_help import QuickHelpDialog  # noqa: PLC0415

        if not hasattr(self, "_quick_help_dialog"):
            self._quick_help_dialog = QuickHelpDialog(self)
        sender = self.sender()
        if isinstance(sender, QAction):
            for w in self.main_toolbar.findChildren(QToolButton):
                if self.main_toolbar.widgetForAction(sender) == w:
                    self._quick_help_dialog.show_near_button(w)
                    return
        self._quick_help_dialog.show_near_button(self)

    def show_about_dialog(self):
        deps_info = "<br>".join([f"<b>{k}:</b> {v}" for k, v in __dependencies__.items()])
        tech_info = "<br>".join([f"<b>{k}:</b> {v}" for k, v in __tech_stack__.items()])

        html = f"""
        <h2>JMComander {__version__}</h2>
        <p><b>Autor:</b> {__author__}</p>
        <p><b>Web:</b> <a href='{__website__}'>{__website__}</a></p>
        <hr>
        <h3>Tecnologias Utilizadas</h3>
        <p>{tech_info}</p>
        <hr>
        <h3>Dependencias</h3>
        <p style='font-size: 11px;'>{deps_info}</p>
        """
        QMessageBox.about(self, "Acerca de JMComander", html)

    def open_search_dialog(self):
        SearchDialog(self.active_panel.current_path, self).show()

    def setup_enhanced_status_bar(self):
        w = QWidget()
        l = QHBoxLayout(w)  # noqa: E741
        l.setContentsMargins(5, 0, 5, 0)
        self.status_label = QLabel("Listo")
        l.addWidget(self.status_label, 1)
        self.progress_label = QLabel("")
        self.progress_label.hide()
        l.addWidget(self.progress_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        self.progress_bar.setMaximumWidth(200)
        l.addWidget(self.progress_bar)
        self.cancel_btn = QPushButton("✕")
        self.cancel_btn.setFixedSize(20, 20)
        self.cancel_btn.hide()
        l.addWidget(self.cancel_btn)
        self.statusBar().addWidget(w, 1)
        for p in [self.left_panel, self.right_panel]:
            p.focused.connect(lambda p=p: self.update_status_bar(p))

    def update_status_bar(self, p):
        if hasattr(self, "status_label"):
            self.status_label.setText(p.get_selection_info())

    def run_operation(self, j, _t):
        self.engine.start_job(j)

        # Barra in-line només al panell actiu (on es copia)
        self.active_panel.show_inline_progress(0)
        # Desconnectar abans de connectar: sense això, N operacions = N slots
        # executats per cada clic al botó ✕ (sobre jobs ja morts)
        cancel_btn = self.active_panel.inline_cancel_btn
        try:
            cancel_btn.clicked.disconnect()
        except RuntimeError:
            pass  # no hi havia cap connexió prèvia
        cancel_btn.clicked.connect(lambda: self._cancel_operation(j))

        if sys.platform == "win32" and self.winId():
            self._taskbar_progress = TaskbarProgress(int(self.winId()))
            self._taskbar_progress.set_state(TaskbarProgress.TBPF_INDETERMINATE)
            logger.info("[MainWindow] Taskbar progress initialized")

        j.signals.progress.connect(self._on_dialog_progress)
        j.signals.finished.connect(self._on_dialog_finished)
        j.signals.error.connect(self._on_dialog_error)

    def _on_dialog_progress(self, _text, percent):
        if self._taskbar_progress and percent > 0:
            self._taskbar_progress.set_progress(percent, 100)
        self.active_panel.show_inline_progress(percent)
        if self.isMinimized():
            self._flash_if_minimized()

    def _on_dialog_finished(self):
        if getattr(self, "_taskbar_progress", None):
            self._taskbar_progress.clear()
            self._taskbar_progress = None
        self.active_panel.hide_inline_progress()

    def _on_dialog_error(self, error_msg):
        logger.error("[MainWindow] Operation error: %s", error_msg)
        self._on_dialog_finished()

    def _cancel_operation(self, job):
        job.cancel()
        logger.info("[MainWindow] Operation cancelled by user")

    def _flash_if_minimized(self):
        if self.isMinimized() and sys.platform == "win32":
            try:
                ctypes.windll.user32.FlashWindow(self.winId(), True)
            except Exception as e:  # noqa: BLE001
                logger.debug("Flash window failed: %s", e)

    def _run_in_background(self, job, title):
        self.bg_operation_label.setText(title)
        self.bg_file_label.setText("")
        self.bg_progress_bar.setValue(0)
        self.bg_progress_frame.show()
        self._flash_if_minimized()

        # Windows taskbar progress
        if sys.platform == "win32" and self.winId():
            self._taskbar_progress = TaskbarProgress(int(self.winId()))
            self._taskbar_progress.set_state(TaskbarProgress.TBPF_INDETERMINATE)
            logger.info("[MainWindow] Taskbar progress initialized for background operation")

            def update_taskbar(_text, percent):
                if self._taskbar_progress and percent > 0:
                    self._taskbar_progress.set_progress(percent, 100)

            def clear_taskbar():
                if hasattr(self, "_taskbar_progress") and self._taskbar_progress:
                    self._taskbar_progress.clear()
                    self._taskbar_progress = None

            job.signals.progress.connect(update_taskbar)
            job.signals.finished.connect(clear_taskbar)
            job.signals.cancelled.connect(clear_taskbar)

        job.signals.progress.connect(self._on_bg_progress)
        job.signals.file_started.connect(self._on_bg_file_started)
        job.signals.finished.connect(self._on_bg_finished)
        job.signals.cancelled.connect(self._on_bg_finished)
        job.signals.error.connect(self._on_bg_error)

        self._current_bg_job = job
        self.bg_cancel_btn.setEnabled(True)
        self.bg_cancel_btn.setText("Cancelar")

        self.engine.start_job(job)

    def _on_bg_progress(self, text, percent):
        self.bg_file_label.setText(text)
        self.bg_progress_bar.setValue(percent)

    def _on_bg_file_started(self, _filename, current, total):
        self.bg_file_label.setText(f"Archivo {current}/{total}")

    def _on_bg_finished(self):
        self.bg_progress_frame.hide()
        if hasattr(self, "_current_bg_job"):
            del self._current_bg_job
        self.refresh_both_panels()

    def _on_bg_error(self, error_msg):
        logger.error("[MainWindow] Background operation error: %s", error_msg)
        from PySide6.QtWidgets import QMessageBox  # noqa: PLC0415

        QMessageBox.critical(self, "Error en operación", error_msg)
        self.bg_progress_frame.hide()
        if hasattr(self, "_current_bg_job"):
            del self._current_bg_job
        if hasattr(self, "_taskbar_progress") and self._taskbar_progress:
            self._taskbar_progress.clear()
            self._taskbar_progress = None
        self.refresh_both_panels()

    def refresh_both_panels(self):
        for panel in [self.left_panel, self.right_panel]:
            try:
                panel.refresh()
            except Exception as e:
                logger.exception("Error refreshing %s panel: %s", panel, e)  # noqa: TRY401

    def _handle_copy_conflict(self, job, src, dst, index, total):
        dlg = ConflictDialog(self, src, dst, index, total)
        dlg.decision_made.connect(job.resolve_conflict)

        if self.isMinimized():
            dlg.setWindowFlags(
                Qt.WindowType.Window
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowCloseButtonHint
                | Qt.WindowType.WindowMinimizeButtonHint
            )
            dlg.showNormal()
            dlg.raise_()
            dlg.activateWindow()

        dlg.exec()

    def _cancel_background_operation(self):
        if hasattr(self, "_current_bg_job") and self._current_bg_job:
            self._current_bg_job.cancel()
            self.bg_cancel_btn.setEnabled(False)
            self.bg_cancel_btn.setText("Cancelando...")

    def _run_operation(self, job, title):
        """Run operation with appropriate UI based on window state."""
        if self.isMinimized():
            # Window minimized: run in background with minimal UI
            self._run_in_background(job, title)
        else:
            # Window normal: barra in-line al panell actiu
            self.run_operation(job, title)

    def setup_function_bar(self, layout):
        f = QFrame()
        f.setFixedHeight(40)
        f.setStyleSheet("background-color: #f0f0f0; border-top: 1px solid #ccc;")
        l = QHBoxLayout(f)  # noqa: E741
        l.setContentsMargins(5, 2, 5, 2)
        ops = [
            ("F2 Renombrar", self.rename_item),
            ("F3 Ver", self.view_file),
            ("F4 Editar", self.edit_file),
            ("F5 Copiar", self.copy_files),
            ("F6 Mover", self.move_files),
            ("F7 Carpeta", self.create_folder),
            ("F8 Borrar", self.delete_files),
            ("F9 Duplicar", self.duplicate_selected),
        ]
        for t, s in ops:
            btn = QPushButton(t)
            btn.clicked.connect(s)
            l.addWidget(btn)
        layout.addWidget(f)

    def _setup_window_icon(self):
        b = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent.parent  # noqa: SLF001
        ico = b / "assets" / "jmcomander.ico"
        if ico.exists():
            icon = QIcon(str(ico))
            QApplication.instance().setWindowIcon(icon)
            self.setWindowIcon(icon)
            if sys.platform == "win32":
                QTimer.singleShot(1000, lambda: self._apply_winapi_icon(str(ico)))

    def _apply_winapi_icon(self, p):
        """Aplica el icono mediante llamadas directas a la API de Windows para mayor persistencia"""
        import ctypes  # noqa: PLC0415

        try:
            if self.winId():
                hwnd = int(self.winId())
                # Cargar versiones de 48x48 (Grande) y 16x16 (Pequeña)
                hl = ctypes.windll.user32.LoadImageW(0, p, 1, 48, 48, 0x10)
                hs = ctypes.windll.user32.LoadImageW(0, p, 1, 16, 16, 0x10)

                if hl:
                    # WM_SETICON: 1 = Big, 0 = Small
                    ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hl)
                    # GCL_HICON: -14
                    ctypes.windll.user32.SetClassLongW(hwnd, -14, hl)

                if hs:
                    ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hs)
                    # GCL_HICONSM: -34
                    ctypes.windll.user32.SetClassLongW(hwnd, -34, hs)

                # Forzar actualización de la ventana
                ctypes.windll.user32.SetWindowPos(
                    hwnd, None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020
                )
        except Exception as _e:  # noqa: BLE001
            pass

    def _reapply_icon_after_show(self):
        if sys.platform == "win32" and self.winId():
            try:
                ctypes.windll.user32.RedrawWindow(int(self.winId()), None, None, 0x0500)
            except Exception as _e:  # noqa: BLE001
                pass

    def keyPressEvent(self, event):  # noqa: N802
        k, _m = event.key(), event.modifiers()
        if k == Qt.Key.Key_Tab:
            self.set_active_panel(self.inactive_panel)
            return
        if k == Qt.Key.Key_Backspace:
            self.go_up()
            return
        if k == Qt.Key.Key_Delete:
            self.delete_files()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):  # noqa: N802
        if self.engine.active_jobs:
            reply = QMessageBox.question(
                self,
                "Operaciones en progreso",
                f"Hay {len(self.engine.active_jobs)} operación(es)"
                " de copia/mover en segundo plano.\n\n"
                "¿Cancelar las operaciones y salir?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

            # Cancelar todas las operaciones
            self.engine.cancel_all()

            # Esperar un poco a que terminen
            for _ in range(10):
                if self.engine.thread_pool.waitForDone(300):
                    break
            # Aunque no hayan terminado, cerrar igual (force quit)

        geo = self.geometry()
        self.config.set_window_state(
            geo.x(), geo.y(), geo.width(), geo.height(), self.isMaximized()
        )
        self.config.set_paths(self.left_panel.current_path, self.right_panel.current_path)
        self.config.save()
        super().closeEvent(event)

    def nativeEvent(self, eventType, message):  # noqa: N802, N803
        """Maneja eventos nativos de Windows para detectar cambios en dispositivos (USB)"""
        if sys.platform == "win32" and eventType == b"windows_generic_MSG":
            # El mensaje llega como un puntero a una estructura MSG
            from ctypes import wintypes  # noqa: PLC0415

            msg = wintypes.MSG.from_address(message.__int__())

            # WM_DEVICECHANGE = 0x0219
        if msg.message == 0x0219 and msg.wParam in (0x8000, 0x8004):
            logger.info("Cambio detectado en unidades de almacenamiento. Refrescando...")
            # Pequeño retraso para que el sistema operativo registre la unidad completamente
            QTimer.singleShot(1000, self.refresh_drives)

        return super().nativeEvent(eventType, message)

    def refresh_drives(self):
        """Refresca la lista de unidades en ambos paneles"""
        if hasattr(self, "left_panel"):
            self.left_panel.update_drives(force_refresh=True)
        if hasattr(self, "right_panel"):
            self.right_panel.update_drives(force_refresh=True)

    def _create_settings_button(self):
        b = QToolButton(self)
        b.setObjectName("btn_settings")
        b.setText("⚙")
        f = QFont()
        f.setPointSize(14)
        b.setFont(f)
        b.clicked.connect(self.open_settings)
        return b

    def _create_view_mode_button(self):
        b = QToolButton(self)
        b.setObjectName("btn_view_mode")
        b.setText("Vista")
        b.setIcon(self.icon_loader.load_icon("mdi-view-list", "V"))
        b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        return b

    def _create_recent_paths_button(self):
        b = QToolButton(self)
        b.setObjectName("btn_recent_paths")
        b.setText("Recientes")
        b.setIcon(self.icon_loader.load_icon("archive-arrow-down", "R"))
        b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        return b

    def _create_plugins_button(self):
        b = QToolButton(self)
        b.setObjectName("btn_plugins")
        b.setText("Plugins")
        b.setIcon(self.icon_loader.load_icon("mdi-puzzle", "P"))
        b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        return b

    def _create_bookmarks_button(self):
        b = QToolButton(self)
        b.setObjectName("btn_bookmarks_menu")
        b.setText("Marcadores")
        b.setIcon(self.icon_loader.load_icon("mdi-bookmark", "M"))
        b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        return b

    def _create_apps_button(self):
        b = QToolButton(self)
        b.setObjectName("btn_apps_menu")
        b.setText("Aplicaciones")
        b.setIcon(self.icon_loader.load_icon("application", "A"))
        b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        return b

    def swap_panels(self):
        l, r = self.left_panel.current_path, self.right_panel.current_path  # noqa: E741
        self.left_panel.set_path(r)
        self.right_panel.set_path(l)

    def equal_panels(self):
        self.inactive_panel.set_path(self.active_panel.current_path)

    def equal_panels_reverse(self):
        self.active_panel.set_path(self.inactive_panel.current_path)
