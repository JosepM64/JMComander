import fnmatch
import logging
import os
import re
import shutil
import subprocess
import time
import winreg
from datetime import UTC, datetime

from PySide6.QtCore import (
    QDir,
    QItemSelection,
    QItemSelectionModel,
    QSize,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileIconProvider,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedLayout,
    QStyle,
    QToolButton,
    QTreeView,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.assets.icon_utils import load_icon
from src.core.mtp_handler import get_shell_display_name, list_shell_folder, open_shell_file
from src.ui.file_system_model import ExtendedFileSystemModel, FileSystemProxyModel

try:
    from src.ui.components.breadcrumb_bar import BreadcrumbBar
except ImportError:
    BreadcrumbBar = None

try:
    from src.ui.components.drive_combo import DriveCombo
except ImportError:
    DriveCombo = None

try:
    from src.ui.components.archive_browser import ArchiveBrowser
except ImportError:
    ArchiveBrowser = None

try:
    from src.ui.components.shell_browser import ShellBrowser
except ImportError:
    ShellBrowser = None

try:
    from src.ui.components.folder_tab_bar import FolderTabBar
except ImportError:
    FolderTabBar = None

from PySide6.QtGui import QAction, QCursor, QDesktopServices

from src.core.archive_handler import archive_handler
from src.core.directory_watcher import DirectoryWatcher
from src.core.path_history import PathHistory

logger = logging.getLogger(__name__)


class FilePanel(QWidget):
    focused = Signal(object)
    selection_changed = Signal()
    path_changed = Signal(str)
    delete_requested = Signal()  # Nueva señal para borrar desde el menú

    def __init__(self, panel_id, initial_path=None, detect_iphone_on_init=True):
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.panel_id = panel_id
        self.current_path = initial_path or QDir.homePath()
        self.view_mode = "details"
        self.is_in_archive = False
        self.detect_iphone_on_init = detect_iphone_on_init
        self._path_history = PathHistory()
        self._path_history.push(self.current_path)
        self._tab_navigating = False

        self._watcher = DirectoryWatcher(self)
        self._watcher.directory_changed.connect(self._on_watcher_refresh)

        self.init_ui()
        self.setup_model()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if FolderTabBar:
            self.tab_bar = FolderTabBar()
            self.tab_bar.add_tab(self.current_path)
            self.tab_bar.tab_path_changed.connect(self._on_tab_path_changed)
            self.tab_bar.tab_close_requested.connect(self._on_tab_close)
            self.tab_bar.new_tab_requested.connect(self._on_new_tab)
            layout.addWidget(self.tab_bar)
        else:
            self.tab_bar = None

        self.nav_frame = QFrame()
        self.nav_frame.setObjectName("navFrame")
        self.nav_frame.setStyleSheet(
            "#navFrame { border-bottom: 3px solid #1976D2; background-color: #f0f7ff; }"
        )
        self.nav_frame.setMouseTracking(True)
        self.nav_frame.installEventFilter(self)
        nav = QHBoxLayout(self.nav_frame)
        nav.setContentsMargins(2, 2, 2, 2)
        nav.setSpacing(2)

        self.up_btn = QToolButton()
        self.up_btn.setIcon(load_icon("mdi-arrow-up.svg", QStyle.StandardPixmap.SP_ArrowUp))
        self.up_btn.setToolTip("Pujar un nivell (Backspace)")
        self.up_btn.clicked.connect(self.go_up)
        nav.addWidget(self.up_btn)

        self.back_btn = QToolButton()
        self.back_btn.setIcon(load_icon("mdi-arrow-left.svg", QStyle.StandardPixmap.SP_ArrowBack))
        self.back_btn.setToolTip("Enrere (Alt+←)")
        self.back_btn.clicked.connect(self.go_back)
        self.back_btn.setEnabled(False)
        nav.addWidget(self.back_btn)

        self.forward_btn = QToolButton()
        self.forward_btn.setIcon(
            load_icon("mdi-arrow-right.svg", QStyle.StandardPixmap.SP_ArrowForward)
        )
        self.forward_btn.setToolTip("Endavant (Alt+→)")
        self.forward_btn.clicked.connect(self.go_forward)
        self.forward_btn.setEnabled(False)
        nav.addWidget(self.forward_btn)

        if DriveCombo:
            self.drive_combo = DriveCombo()
            self.drive_combo.drive_activated.connect(self.set_path)
            self.drive_combo.update_drives(
                self.current_path, force_refresh=self.detect_iphone_on_init
            )
        else:
            self.drive_combo = QComboBox()
            self.drive_combo.setFixedWidth(80)
        nav.addWidget(self.drive_combo)

        self.create_btn = QToolButton()
        self.create_btn.setText("Crea")
        self.create_btn.setIcon(
            load_icon("creation.svg", QStyle.StandardPixmap.SP_FileDialogNewFolder)
        )
        self.create_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.create_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._setup_create_menu()
        nav.addWidget(self.create_btn)

        # Breadcrumb bar (replaces path_input)
        if BreadcrumbBar:
            self.breadcrumb_bar = BreadcrumbBar()
            self.breadcrumb_bar.path_changed.connect(self._on_breadcrumb_path_changed)
            nav.addWidget(self.breadcrumb_bar, 1)

        self.path_input = QLineEdit()
        self.path_changed.connect(self._on_path_changed_update_nav)
        self.path_input.returnPressed.connect(self.on_path_entered)
        # textEdited (no textChanged): setText() programàtic de set_path no ha
        # d'emetre focused — era un canvi de panell fantasma a cada navegació
        self.path_input.textEdited.connect(lambda _t: self.focused.emit(self))
        self.path_input.hide()  # Oculto el input antiguo, usamos BreadcrumbBar
        nav.addWidget(self.path_input)

        # Filtro rápido (As-You-Type)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filtra...")
        self.filter_input.setFixedWidth(100)
        self.filter_input.setStyleSheet(
            "background-color: #e8f0fe; border: 1px solid #7fb3e8; border-radius: 3px;"
        )
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(lambda t: self._on_filter_changed(t))  # noqa: PLW0108
        self.filter_input.hide()  # Inicialment ocult
        nav.addWidget(self.filter_input)

        self.ext_filter_btn = QToolButton()
        self.ext_filter_btn.setText("*.ext")
        self.ext_filter_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.ext_filter_btn.setToolTip("Filtrar per extensió")
        self._setup_ext_filter_menu()
        nav.addWidget(self.ext_filter_btn)

        self.exit_btn = QPushButton("×")
        self.exit_btn.setFixedSize(20, 20)
        self.exit_btn.hide()
        nav.addWidget(self.exit_btn)

        layout.addWidget(self.nav_frame)

        # Barra de progreso in-line (se muestra solo durante operaciones)
        self.inline_progress = QFrame()
        self.inline_progress.setFixedHeight(20)
        self.inline_progress.setStyleSheet("background-color: #e8f0fe; border: 1px solid #90caf9; border-radius: 2px;")
        self.inline_progress.hide()
        inline_layout = QHBoxLayout(self.inline_progress)
        inline_layout.setContentsMargins(4, 0, 4, 0)
        inline_layout.setSpacing(4)

        self.inline_progress_bar = QProgressBar()
        self.inline_progress_bar.setRange(0, 100)
        self.inline_progress_bar.setValue(0)
        self.inline_progress_bar.setTextVisible(True)
        self.inline_progress_bar.setFormat("%p%")
        self.inline_progress_bar.setStyleSheet(
            "QProgressBar { border: none; min-height: 10px; max-height: 14px;"
            " background-color: #e3f2fd; }"
            "QProgressBar::chunk { background-color: #1976D2; }"
        )
        inline_layout.addWidget(self.inline_progress_bar, 1)

        self.inline_cancel_btn = QPushButton("✕")
        self.inline_cancel_btn.setFixedSize(18, 18)
        self.inline_cancel_btn.setStyleSheet(
            "QPushButton { background: #e53935; color: white; border: none; "
            "border-radius: 9px; font-size: 10px; padding: 0; }"
            "QPushButton:hover { background: #c62828; }"
        )
        self.inline_cancel_btn.setEnabled(False)
        inline_layout.addWidget(self.inline_cancel_btn)

        layout.addWidget(self.inline_progress)

        self.stack = QStackedLayout()

        self.tree = QTreeView()
        self.list = QListView()
        self.icon = QListView()
        self._setup_view(self.tree)
        self._setup_view(self.list)
        self._setup_view(self.icon)
        self.icon.setViewMode(QListView.ViewMode.IconMode)
        self.icon.setIconSize(QSize(48, 48))

        if ArchiveBrowser:
            self.archive_browser = ArchiveBrowser()
        else:
            self.archive_browser = QListWidget()
            self.archive_browser.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            self.archive_browser.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
            self.archive_browser.setStyleSheet("""
                QListWidget { outline: none; }
                QListWidget::item:selected { background-color: #4A90E2; color: white; }
                QListWidget::item:selected:!active { background-color: #7FB3E8; color: white; }
                QListWidget::item:hover { background-color: #C8E0F4; border: 1px solid #4A90E2; }
                QListWidget::item:selected:hover { background-color: #5A9FE8; }
            """)
        self.archive_browser.itemDoubleClicked.connect(self._on_archive_item_double_clicked)
        self.archive_browser.clicked.connect(
            lambda idx: self._on_item_clicked(idx, self.archive_browser)
        )
        self.archive_browser.viewport().installEventFilter(self)
        self.archive_browser.installEventFilter(self)

        # Browser per a dispositius MTP (iPhone): QTreeWidget amb columnes ordenables
        self.shell_browser = ShellBrowser() if ShellBrowser else None
        if self.shell_browser:
            self.shell_browser.itemDoubleClicked.connect(self._on_archive_item_double_clicked)
            self.shell_browser.itemClicked.connect(
                lambda item, col: self._on_shell_item_clicked(item)
            )
            self.shell_browser.viewport().installEventFilter(self)
            self.shell_browser.installEventFilter(self)

        self.icon_provider = QFileIconProvider()
        self.folder_icon = self.icon_provider.icon(QFileIconProvider.IconType.Folder)
        self.file_icon = self.icon_provider.icon(QFileIconProvider.IconType.File)

        views = [self.tree, self.list, self.icon, self.archive_browser]
        if self.shell_browser:
            views.append(self.shell_browser)
        for v in views:
            self.stack.addWidget(v)
        layout.addLayout(self.stack)
        self.current_view_widget = self.tree
        self._setup_context_menus()

    def _on_shell_item_clicked(self, item):
        """Click simple en un item del ShellBrowser (res per ara, només selecció)."""
        return

    def _setup_view(self, view):
        view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.setDragEnabled(True)
        view.setAcceptDrops(True)
        view.viewport().setAcceptDrops(True)
        view.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        view.clicked.connect(lambda idx: self._on_item_clicked(idx, view))
        view.doubleClicked.connect(self.on_item_double_clicked)
        view.viewport().installEventFilter(self)
        # Instalar eventFilter en la vista para capturar teclas
        view.installEventFilter(self)
        if isinstance(view, QTreeView):
            view.setRootIsDecorated(False)
            view.setUniformRowHeights(True)
            view.setSortingEnabled(False)

        # Aplicar estilo de selección más oscuro con hover mejorado
        view.setStyleSheet("""
            QTreeView, QListView {
                outline: none;
            }
            QTreeView::item:selected, QListView::item:selected {
                background-color: #4A90E2;
                color: white;
            }
            QTreeView::item:selected:!active, QListView::item:selected:!active {
                background-color: #7FB3E8;
                color: white;
            }
            QTreeView::item:hover, QListView::item:hover {
                background-color: #C8E0F4;
                border: 1px solid #4A90E2;
            }
            QTreeView::item:selected:hover, QListView::item:selected:hover {
                background-color: #5A9FE8;
            }
        """)

    def _on_item_clicked(self, index, view):
        """Track focused panel on click"""
        self.focused.emit(self)

    def _on_filter_changed(self, text):
        """Aplica el filtro de búsqueda al modelo proxy o al archive browser"""
        logger.debug("Filter changed: '%s'", text)
        logger.debug("Current path: %s, is_in_archive: %s", self, self)

        if self.shell_browser and self.current_view_widget is self.shell_browser:
            self.shell_browser.filter_items(text.lower())
            return

        if self.is_in_archive:
            if isinstance(self.archive_browser, ArchiveBrowser):
                self.archive_browser.filter_items(text.lower())
            else:
                for i in range(self.archive_browser.count()):
                    item = self.archive_browser.item(i)
                    if not text:
                        item.setHidden(False)
                    else:
                        match = text.lower() in item.text().lower()
                        item.setHidden(not match)
            logger.debug("Archive browser filtered with '%s'", text)
            return

        # Para carpetas normales (proxy model)
        logger.debug(
            f"proxy_model exists: {hasattr(self, 'proxy_model')},"
            f" source_model exists: {hasattr(self, 'source_model')}"
        )

        if not text:
            # Si el texto está vacío, limpiar el filtro pero mantener la vista actual
            logger.debug("Clearing filter")
            self.proxy_model.setFilterFixedString("")
            self.proxy_model.setFilterKeyColumn(-1)  # Resetear a todas las columnas
            # Forzar recálculo del filtro
            self.proxy_model.invalidateFilter()
            logger.debug("Filter invalidated")
            # Restaurar el índice raíz para asegurar que seguimos en el directorio correcto
            if hasattr(self, "source_model"):
                idx = self.proxy_model.mapFromSource(self.source_model.index(self.current_path))
                logger.debug("Root index mapped: %s", idx)
                for v in [self.tree, self.list, self.icon]:
                    v.setRootIndex(idx)
                    v.update()  # Forzar actualización de la vista
        else:
            # Aplicar filtro usando expresión regular para buscar en cualquier parte del nombre
            logger.debug("Applying filter with regex .*%s.* (case-insensitive)", text)
            self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.proxy_model.setFilterKeyColumn(0)
            # Usar expresión regular para buscar texto en cualquier posición del nombre
            # '.*' para cualquier carácter antes/después, re.escape para caracteres especiales
            pattern = f".*{re.escape(text)}.*"
            logger.debug("Setting filter pattern: %s", pattern)
            self.proxy_model.setFilterRegularExpression(pattern)
            # Log después de establecer el filtro
            regex = self.proxy_model.filterRegularExpression()
            logger.debug(
                f"Proxy model filter regex valid={regex.isValid()},"
                f" pattern={regex.pattern() if regex.isValid() else 'invalid'}"
            )
            # Log current root source index
            if (
                self.proxy_model.current_root_source_index
                and self.proxy_model.current_root_source_index.isValid()
                and hasattr(self.source_model, "filePath")
            ):
                root_path = self.source_model.filePath(self.proxy_model.current_root_source_index)
                logger.debug("Current root source index path: %s", root_path)
            # Forzar recálculo del filtro
            self.proxy_model.invalidateFilter()
            logger.debug("Filter invalidated after setting regex")
            # CON FILTRE ACTIVO: no cambiar rootIndex, proxy muestra filtrados
            # El filtro se aplica automáticamente sobre el contenido del directorio actual

    def _trigger_pattern_selection(self, select):
        """Método público para activar selección/deselección por patrón desde eventFilter global"""
        # Guardar el foco actual antes de abrir el diálogo
        from PySide6.QtWidgets import QApplication  # noqa: PLC0415

        app = QApplication.instance()

        pattern, ok = QInputDialog.getText(
            self,
            "Seleccionar per patró" if select else "Deseleccionar per patró",
            "Patró (ex: *.jpg):",
            text="*",
        )

        # Procesar eventos pendientes para limpiar el estado del diálogo
        app.processEvents()

        if ok and pattern:
            logger.debug("Pattern dialog closed with pattern: %s", pattern)
            self._select_by_pattern(pattern, select)

            # Restaurar el foco al widget actual de la vista
            if self.current_view_widget:
                self.current_view_widget.setFocus()
                logger.debug("Focus restored to current view widget")

    def _select_by_pattern(self, pattern, select):
        """Lògica de selecció/deselecció per patró (com Total Commander)"""
        if self.is_in_archive:
            # Per a arxius comprimits (QListWidget)
            for i in range(self.archive_browser.count()):
                item = self.archive_browser.item(i)
                if fnmatch.fnmatch(item.text().lower(), pattern.lower()):
                    item.setSelected(select)
        else:
            # Per a carpetes normals - Usar modelo fuente directamente
            # para evitar problemas con filtros activos
            source_root = self.source_model.index(self.current_path)
            sm = self.current_view_widget.selectionModel()

            logger.debug(
                f"Selecting by pattern '{pattern}' in '{self.current_path}' (select={select})"  # noqa: G004
            )

            for row in range(self.source_model.rowCount(source_root)):
                source_idx = self.source_model.index(row, 0, source_root)
                filename = self.source_model.fileName(source_idx)

                if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                    # Mapear índice fuente a proxy para seleccionar
                    proxy_idx = self.proxy_model.mapFromSource(source_idx)
                    if proxy_idx.isValid():
                        mode = (
                            QItemSelectionModel.Select if select else QItemSelectionModel.Deselect
                        )
                        sm.select(proxy_idx, mode | QItemSelectionModel.Rows)
                        logger.debug("  Selected: %s", filename)
                    else:
                        logger.debug("  Skipped (filtered): %s", filename)

    def _start_inline_rename(self, index):
        """Inicia el renombrado inline"""
        p = self.get_path_from_index(index)
        if p and os.path.exists(p):
            full_name = os.path.basename(p)
            name_part, ext_part = os.path.splitext(full_name)  # noqa: RUF059

            # Crear diálogo personalizado
            dialog = QDialog(self)
            dialog.setWindowTitle("Renombrar")
            dialog.setMinimumWidth(400)

            layout = QVBoxLayout()
            layout.addWidget(QLabel("Nombre:"))

            line_edit = QLineEdit()
            line_edit.setText(full_name)
            layout.addWidget(line_edit)

            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            dialog.setLayout(layout)

            # Asegurar que el line edit tenga el foco y seleccionar después de mostrar
            line_edit.setFocus()

            def select_name_part():
                if ext_part:
                    line_edit.setSelection(0, len(full_name) - len(ext_part))
                else:
                    line_edit.selectAll()

            # Usar timer para seleccionar después de que el diálogo se muestre
            QTimer.singleShot(0, select_name_part)

            ok = dialog.exec()
            n = line_edit.text()

            if ok and n:
                try:
                    os.rename(p, os.path.join(os.path.dirname(p), n))
                    self.refresh()
                except Exception as e:  # noqa: BLE001
                    QMessageBox.warning(self, "Error", str(e))

    def setup_model(self):
        logger.debug("=== FilePanel.setup_model START ===")
        _start_time = time.time()

        self.source_model = ExtendedFileSystemModel()
        self.source_model.setReadOnly(False)
        self.source_model.directoryLoaded.connect(self._on_directory_loaded)
        self.proxy_model = FileSystemProxyModel(self)
        self.proxy_model.setSourceModel(self.source_model)
        self.proxy_model.setDynamicSortFilter(True)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy_model.setFilterRole(Qt.ItemDataRole.DisplayRole)
        self.proxy_model.setSortRole(Qt.ItemDataRole.UserRole)
        self.proxy_model.setRecursiveFilteringEnabled(False)
        for v in [self.tree, self.list, self.icon]:
            v.setModel(self.proxy_model)
            if v.selectionModel():
                v.selectionModel().selectionChanged.connect(lambda: self.selection_changed.emit())  # noqa: PLW0108
        self.tree.header().sectionClicked.connect(self.on_header_clicked)

        logger.debug("Model setup basic took %ss", time)

        _path_set_start = time.time()
        self.set_path(self.current_path)
        logger.debug("set_path() took %ss", time)

        logger.debug("=== FilePanel.setup_model END total=%ss ===", time)

        # Set initial sort to date column, descending order (newest first)
        self.proxy_model.sort(4, Qt.SortOrder.DescendingOrder)

    def on_header_clicked(self, s):
        o = (
            Qt.SortOrder.DescendingOrder
            if self.proxy_model.sortOrder() == Qt.SortOrder.AscendingOrder
            else Qt.SortOrder.AscendingOrder
        )
        logger.debug(
            f"Header clicked: column={s}, new order={o},"
            f" current before toggle={self.proxy_model.sortOrder()}"
        )
        # Reset debug counter to see new sort comparisons
        if hasattr(self.proxy_model, "_sort_debug_counter"):
            self.proxy_model._sort_debug_counter = 0  # noqa: SLF001
        # Force sort
        self.proxy_model.sort(s, o)
        logger.debug(
            f"After sort: sortColumn={self.proxy_model.sortColumn()},"
            f" sortOrder={self.proxy_model.sortOrder()}"
        )

    def set_path(self, p):
        logger.debug("set_path called with: %s", p)
        _set_path_start = time.time()

        is_shell_path = p.startswith("::") or p.startswith("\\\\?\\") or "shell::" in p.lower()

        if not is_shell_path and not os.path.exists(p):
            logging.warning(f"Path does not exist and is not shell path: {p}")
            return

        if is_shell_path:
            self._set_shell_path(p)
            return

        self.current_path = os.path.normpath(p)

        if archive_handler.is_inside_archive(self.current_path):
            self._apply_to_archive(self.current_path)
        else:
            self._apply_to_model(self.current_path)

        self.path_changed.emit(self.current_path)
        self._push_history(self.current_path)

        if self.view_mode == "details" and not archive_handler.is_inside_archive(self.current_path):
            self._configure_tree_headers()

        self._watcher.watch(self.current_path)

        # El refresc+ordenació el fan _on_directory_loaded (càrrega nova) o
        # _delayed_directory_refresh (directoris ja en caché) — no cal un tercer sort aquí
        if not archive_handler.is_inside_archive(self.current_path):
            QTimer.singleShot(100, self._delayed_directory_refresh)

        logger.debug("set_path() took %ss", time)

    def _apply_to_model(self, path):
        """P2b: Set model root, proxy, and view indices for a normal directory."""
        self.archive_browser.hide()
        self.proxy_model._timestamp_cache.clear()
        if self.source_model.rootPath() != path:
            self.source_model.setRootPath(path)
        source_root_idx = self.source_model.index(path)
        self.proxy_model.set_current_root_source_index(source_root_idx)
        idx = self.proxy_model.mapFromSource(source_root_idx)
        for v in [self.tree, self.list, self.icon]:
            v.setRootIndex(idx)

        if self.view_mode == "details":
            self.current_view_widget = self.tree
        elif self.view_mode == "list":
            self.current_view_widget = self.list
        else:
            self.current_view_widget = self.icon

        self.stack.setCurrentWidget(self.current_view_widget)

    def _apply_to_archive(self, path):
        """P2b: Show archive browser for a path inside an archive."""
        self.stack.setCurrentWidget(self.archive_browser)
        self.current_view_widget = self.archive_browser
        self._populate_archive_browser(path)
        self.archive_browser.show()

    def _on_path_changed_update_nav(self, path):
        """P1: path_changed signal updates breadcrumb, path_input, drive_combo, tabs."""
        self.path_input.setText(path)
        if BreadcrumbBar and hasattr(self, "breadcrumb_bar"):
            self.breadcrumb_bar.set_path(path)
        shell_current_path = getattr(self, "shell_current_path", None)
        if isinstance(self.drive_combo, DriveCombo):
            self.drive_combo.update_drives(
                path, shell_current_path=shell_current_path, force_refresh=False
            )
        elif hasattr(self, "update_drives"):
            self.update_drives(force_refresh=False)
        if self.tab_bar and not self._tab_navigating:
            self.tab_bar.update_tab(self.tab_bar.currentIndex(), path)

    def _push_history(self, path):
        """P2b: Push path to history and update navigation buttons."""
        self._path_history.push(path)
        self._update_history_buttons()

    def _reapply_root_index(self):
        """Cos compartit de _on_directory_loaded i _delayed_directory_refresh."""
        source_idx = self.source_model.index(self.current_path)
        if not source_idx.isValid():
            return
        self.proxy_model.set_current_root_source_index(source_idx)
        proxy_idx = self.proxy_model.mapFromSource(source_idx)
        if proxy_idx.isValid():
            for v in [self.tree, self.list, self.icon]:
                v.setRootIndex(proxy_idx)
        self.proxy_model.sort(self.proxy_model.sortColumn(), self.proxy_model.sortOrder())

    def _on_directory_loaded(self, path):
        if not self.current_path or archive_handler.is_inside_archive(self.current_path):
            return
        norm_path = os.path.normpath(str(path))
        norm_current = os.path.normpath(self.current_path)
        if norm_path.lower() != norm_current.lower():
            return
        self._reapply_root_index()

    def _delayed_directory_refresh(self):
        if not self.current_path or archive_handler.is_inside_archive(self.current_path):
            return
        self._reapply_root_index()

    def _on_watcher_refresh(self, path):
        """Handle auto-refresh from DirectoryWatcher (OS watcher or polling)."""
        if not self.current_path or path != self.current_path:
            return
        if archive_handler.is_inside_archive(self.current_path):
            return
        self.proxy_model._timestamp_cache.clear()
        self.source_model.setRootPath("")
        self.source_model.setRootPath(self.current_path)
        source_root_idx = self.source_model.index(self.current_path)
        self.proxy_model.set_current_root_source_index(source_root_idx)
        idx = self.proxy_model.mapFromSource(source_root_idx)
        for v in [self.tree, self.list, self.icon]:
            v.setRootIndex(idx)
            v.viewport().update()

    def _set_shell_path(self, shell_path):
        self.current_path = shell_path
        self.shell_current_path = shell_path
        logging.info(f"_set_shell_path: {shell_path}")  # noqa: G004

        items = list_shell_folder(shell_path)
        logging.info(f"_set_shell_path: got {len(items)} items")  # noqa: G004

        if not items:
            logging.warning(f"_set_shell_path: no items returned for {shell_path}")  # noqa: G004
            # Detectar si és una ruta MTP amb SID (com iPhone)
            if "\\SID-" in shell_path:
                # Extreure la ruta base del dispositiu (abans del \SID-)
                base_path = shell_path.split("\\SID-")[0]
                logging.info(f"Intentando con ruta base del dispositivo MTP: {base_path}")  # noqa: G004
                items = list_shell_folder(base_path)
                logging.info(f"Items con ruta base: {len(items)}")  # noqa: G004
                if items:
                    # Actualitzar la ruta i mostrar el dispositivo base
                    self.current_path = base_path
                    self.shell_current_path = base_path
            elif "\\" in shell_path:
                # Intentar listar el directorio padre (per a altres rutes shell)
                parent_path = shell_path.rsplit("\\", 1)[0]
                logging.info(f"Intentando con directorio padre: {parent_path}")  # noqa: G004
                parent_items = list_shell_folder(parent_path)
                logging.info(f"Parent items: {len(parent_items)}")  # noqa: G004
                for item in parent_items:
                    logging.info(f"  Parent item: {item['name']} -> {item['path']}")  # noqa: G004

        self._populate_shell_browser(items)

        # Emit path_changed first (P1: signal handler updates nav widgets with real path)
        self.path_changed.emit(self.current_path)
        # Then override with display name for shell paths
        display_name = get_shell_display_name(self.current_path)
        self.path_input.setText(f"[iPhone] {display_name}")
        if BreadcrumbBar and hasattr(self, "breadcrumb_bar"):
            self.breadcrumb_bar.set_path(f"[iPhone] {display_name}")
        if isinstance(self.drive_combo, DriveCombo):
            self.drive_combo.update_drives(
                self.current_path, shell_current_path=self.shell_current_path, force_refresh=True
            )

    def _populate_shell_browser(self, items):
        if self.shell_browser:
            # MTP/iPhone: QTreeWidget amb columnes Nom/Mida/Data ordenables
            self.shell_browser.populate_shell_items(items)
            self.shell_browser.show()
            self.stack.setCurrentWidget(self.shell_browser)
            self.current_view_widget = self.shell_browser
            return
        if isinstance(self.archive_browser, ArchiveBrowser):
            self.archive_browser.populate_shell_items(items)
        else:
            self.archive_browser.clear()
            for item in items:
                lw_item = QListWidgetItem(item["name"])
                lw_item.setData(Qt.ItemDataRole.UserRole, item["path"])
                lw_item.setData(Qt.ItemDataRole.DisplayRole + 1, item["is_dir"])
                if item["is_dir"]:
                    lw_item.setIcon(self.folder_icon)
                else:
                    lw_item.setIcon(self.file_icon)
                self.archive_browser.addItem(lw_item)
        self.archive_browser.show()
        self.stack.setCurrentWidget(self.archive_browser)

    def _populate_archive_browser(self, path):
        if isinstance(self.archive_browser, ArchiveBrowser):
            self.archive_browser.populate_from_path(path)
        else:
            self.archive_browser.clear()
            try:
                for item in os.listdir(path):
                    full_path = os.path.join(path, item)
                    is_dir = os.path.isdir(full_path)
                    lw_item = QListWidgetItem(item)
                    lw_item.setData(Qt.ItemDataRole.UserRole, full_path)
                    if is_dir:
                        lw_item.setIcon(self.folder_icon)
                    else:
                        lw_item.setIcon(self.file_icon)
                    self.archive_browser.addItem(lw_item)
            except Exception as e:
                logger.exception("Error populating archive browser: %s", e)  # noqa: TRY401

    def _configure_tree_headers(self):
        h = self.tree.header()
        h.setSectionsMovable(True)
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.resizeSection(0, 260)
        h.resizeSection(1, 40)
        h.resizeSection(2, 70)
        h.resizeSection(3, 70)
        h.resizeSection(4, 90)
        h.resizeSection(5, 70)
        self.tree.setSortingEnabled(True)
        h.setSortIndicatorShown(True)
        # Default sort: files first (by our priority), then by date descending (newest first)
        self.tree.sortByColumn(4, Qt.SortOrder.DescendingOrder)
        model = self.tree.model()
        if model and hasattr(model, "setHeaderData"):
            model.setHeaderData(0, Qt.Orientation.Horizontal, "Nombre")
            model.setHeaderData(1, Qt.Orientation.Horizontal, "Ext")
            model.setHeaderData(2, Qt.Orientation.Horizontal, "Tamaño")
            model.setHeaderData(3, Qt.Orientation.Horizontal, "Tipo")
            model.setHeaderData(4, Qt.Orientation.Horizontal, "Fecha")
            model.setHeaderData(5, Qt.Orientation.Horizontal, "Hora")

    def _setup_ext_filter_menu(self):
        menu = QMenu(self)
        ext_categories = [
            (
                "Documents",
                [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf", ".odt"],
            ),
            (
                "Imatges",
                [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tiff", ".ico"],
            ),
            ("Vídeo", [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v"]),
            ("Àudio", [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"]),
            ("Arxius", [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"]),
            (
                "Codi",
                [
                    ".py",
                    ".js",
                    ".html",
                    ".css",
                    ".java",
                    ".cpp",
                    ".c",
                    ".h",
                    ".json",
                    ".xml",
                    ".yaml",
                    ".yml",
                ],
            ),
        ]
        clear_act = QAction("Mostrar tots", self)
        clear_act.triggered.connect(lambda: self._apply_ext_filter(None))
        menu.addAction(clear_act)
        menu.addSeparator()
        for name, exts in ext_categories:
            act = QAction(name, self)
            act.triggered.connect(lambda _checked=False, e=exts: self._apply_ext_filter(e))
            menu.addAction(act)
        self.ext_filter_btn.setMenu(menu)

    def _apply_ext_filter(self, extensions):
        self.proxy_model.set_extension_filter(extensions)
        if extensions:
            self.ext_filter_btn.setText(
                ",".join(e.strip(".") for e in extensions[:3])
                + ("..." if len(extensions) > 3 else "")
            )
        else:
            self.ext_filter_btn.setText("*.ext")

    def _setup_create_menu(self):
        menu = QMenu(self)
        # Opció bàsica de carpeta
        new_folder_act = QAction("Nova Carpeta", self)
        new_folder_act.triggered.connect(lambda: self._create_new_item(None, "folder"))
        menu.addAction(new_folder_act)
        menu.addSeparator()

        # Escanejar registre per ShellNew
        extensions = [".txt", ".docx", ".xlsx", ".pptx", ".rtf", ".bmp", ".zip"]
        for ext in extensions:
            try:
                # Intentar treure el nom descriptiu del tipus de fitxer
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ext) as key:
                    file_type, _ = winreg.QueryValueEx(key, "")
                    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, file_type) as type_key:
                        friendly_name, _ = winreg.QueryValueEx(type_key, "")

                label = f"{friendly_name} ({ext})" if friendly_name else f"Fitxer {ext}"
                act = QAction(label, self)
                act.triggered.connect(
                    lambda _checked=False, e=ext: self._create_new_item(e, "file")
                )
                menu.addAction(act)
            except Exception as _e:  # noqa: BLE001
                # Fallback si no trobem el nom al registre
                labels = {
                    ".txt": "Document de text",
                    ".docx": "Document de Word",
                    ".xlsx": "Full de càlcul Excel",
                    ".pptx": "Presentació PowerPoint",
                }
                label = labels.get(ext, f"Fitxer {ext}")
                act = QAction(label, self)
                act.triggered.connect(
                    lambda _checked=False, e=ext: self._create_new_item(e, "file")
                )
                menu.addAction(act)

        self.create_btn.setMenu(menu)

    def _create_new_item(self, ext, item_type):
        if item_type == "folder":
            name, ok = QInputDialog.getText(self, "Nova Carpeta", "Nom:")
            if ok and name:
                path = os.path.join(self.current_path, name)
                try:
                    os.mkdir(path)
                    self.refresh()
                    self.select_and_focus(path)
                except Exception as e:  # noqa: BLE001
                    QMessageBox.critical(self, "Error", str(e))
        else:
            default_name = "Nou Document" if not ext else f"Nou Document{ext}"
            name, ok = QInputDialog.getText(self, "Nou Fitxer", "Nom:", text=default_name)
            if ok and name:
                if ext and not name.lower().endswith(ext.lower()):
                    name += ext
                path = os.path.join(self.current_path, name)
                try:
                    # Crear fitxer buit
                    with open(path, "w") as _f:
                        pass
                    self.refresh()
                    self.select_and_focus(path)
                except Exception as e:  # noqa: BLE001
                    QMessageBox.critical(self, "Error", str(e))

    def update_drives(self, force_refresh=False):
        if isinstance(self.drive_combo, DriveCombo):
            shell_current_path = getattr(self, "shell_current_path", None)
            self.drive_combo.update_drives(
                self.current_path,
                shell_current_path=shell_current_path,
                force_refresh=force_refresh,
            )

    def on_path_entered(self):
        p = os.path.expanduser(os.path.expandvars(self.path_input.text().strip()))
        if os.path.isdir(p):
            self.set_path(p)

    def _on_breadcrumb_path_changed(self, path):
        if os.path.isdir(path):
            self.set_path(path)

    def on_item_double_clicked(self, idx):  # noqa: PLR0912
        logger.debug("on_item_double_clicked START")
        p = self.get_path_from_index(idx)
        logger.debug("on_item_double_clicked: p=%s", p)
        if not p:
            logger.warning("Ruta nula, ignorando")
            self._clear_double_click_flag()
            return
        if os.path.isdir(p):
            logger.debug("Es directorio, navegando a: %s", p)
            self.set_path(p)
        elif p.lower().endswith(".bat") or p.lower().endswith(".cmd"):
            logger.info("Ejecutando archivo .bat: %s", p)
            QTimer.singleShot(0, lambda: self._execute_bat_safely(p))
        elif archive_handler.is_archive(p):
            logger.info("Es archivo comprimido, montando internamente: %s", p)
            mount_point = archive_handler.mount_archive(p)
            if mount_point:
                logger.info("Archivado montado en: %s", mount_point)
                QTimer.singleShot(50, lambda mp=mount_point: self.set_path(mp))
            else:
                logger.error("No se pudo montar el archivo: %s", p)
                # Mensaje de error más informativo
                ext = os.path.splitext(p.lower())[1]
                if ext == ".rar":
                    msg = (
                        f"No se pudo abrir el archivo RAR: {p}\n\n"
                        "Para abrir archivos RAR necesitas tener instalado WinRAR o 7-Zip.\n"
                        "Asegúrate de que una de estas aplicaciones esté instalada y en el PATH."
                    )
                elif ext == ".7z":
                    msg = (
                        f"No se pudo abrir el archivo 7-Zip: {p}\n\n"
                        "Para abrir archivos 7z necesitas tener instalado 7-Zip.\n"
                        "Asegúrate de que 7-Zip esté instalado y en el PATH."
                    )
                else:
                    msg = (
                        f"No se pudo abrir el archivo comprimido: {p}\n\n"
                        "El archivo puede estar corrupto o en un formato no soportado."
                    )
                QMessageBox.warning(self, "Error", msg)
        else:
            logger.debug("Abriendo archivo: %s", p)
            try:
                # Confirmació per arxius grans (>100 MB) en unitats lentes
                size = os.path.getsize(p)
                if size > 100 * 1024 * 1024:  # 100 MB
                    size_mb = size / (1024 * 1024)
                    reply = QMessageBox.question(
                        self,
                        "Archivo grande",
                        f'El archivo "{os.path.basename(p)}" tiene {size_mb:.0f} MB.\n\n'
                        "¿Abrirlo de todas formas?\n(Si está en una unidad lenta, puede tardar)",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                QDesktopServices.openUrl(QUrl.fromLocalFile(p))
            except Exception as e:
                logger.exception("Error abriendo %s: %s", p, e)  # noqa: TRY401
                QMessageBox.warning(self, "Error", f"No se pudo abrir {p}: {e}")
        logger.debug("on_item_double_clicked END")

    def _on_archive_item_double_clicked(self, item):
        # QTreeWidgetItem.data(column, role) vs QListWidgetItem.data(role)
        if isinstance(item, QTreeWidgetItem):
            full_path = item.data(0, Qt.ItemDataRole.UserRole)
            is_dir = item.data(0, Qt.ItemDataRole.DisplayRole + 1)
        else:
            full_path = item.data(Qt.ItemDataRole.UserRole)
            is_dir = item.data(Qt.ItemDataRole.DisplayRole + 1)

        if full_path and (
            full_path.startswith(("::", "\\\\?\\")) or "shell::" in full_path.lower()
        ):
            if is_dir:
                self.set_path(full_path)
            else:
                open_shell_file(full_path)
        elif os.path.isdir(full_path):
            self.set_path(full_path)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(full_path))

    def _execute_bat_safely(self, bat_path):
        """
        Ejecuta un archivo .bat de forma segura desde aplicación PyInstaller
        sin cerrar el proceso padre.
        """
        import threading  # noqa: PLC0415

        def run_bat():
            try:
                cwd = os.path.dirname(bat_path)
                bat_name = os.path.basename(bat_path)

                creation_flags = (
                    subprocess.CREATE_NO_WINDOW
                    | subprocess.DETACHED_PROCESS
                    | subprocess.CREATE_NEW_PROCESS_GROUP
                )

                command = f'cmd.exe /c "{bat_name}"'

                proc = subprocess.Popen(
                    command,
                    cwd=cwd,
                    shell=True,
                    creationflags=creation_flags,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                )

                logger.info("Proceso .bat iniciado con PID: %s", proc)

            except Exception as e:
                logger.exception("Error ejecutando .bat: %s", e)  # noqa: TRY401
                try:
                    os.startfile(bat_path)
                except Exception as e:  # noqa: BLE001
                    pass

        thread = threading.Thread(target=run_bat, daemon=True)
        thread.start()
        logger.info("Thread de ejecución .bat iniciado")

    def get_path_from_index(self, idx):
        if not idx.isValid():
            return None
        return self.source_model.filePath(self.proxy_model.mapToSource(idx))

    def get_selected_paths(self):
        if self.shell_browser and self.current_view_widget is self.shell_browser:
            return self.shell_browser.get_selected_paths()
        if archive_handler.is_inside_archive(self.current_path):
            if isinstance(self.archive_browser, ArchiveBrowser):
                return self.archive_browser.get_selected_paths()
            return [
                item.data(Qt.ItemDataRole.UserRole) for item in self.archive_browser.selectedItems()
            ]
        return [
            self.get_path_from_index(i)
            for i in self.current_view_widget.selectedIndexes()
            if i.column() == 0
        ]

    def get_selection_info(self):
        s = self.get_selected_paths()
        if not s:
            return self.current_path
        total_size = 0
        info_text = ""
        if len(s) == 1:
            p = s[0]
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(p), tz=UTC).strftime(
                    "%Y-%m-%d %H:%M"
                )
                if os.path.isfile(p):
                    total_size = os.path.getsize(p)
                    info_text = f"{os.path.basename(p)} | {mtime} | {self.format_size(total_size)}"
                else:
                    info_text = f"{os.path.basename(p)} [Carpeta] | {mtime}"
            except Exception as _e:  # noqa: BLE001
                info_text = os.path.basename(p)
        else:
            for p in s:
                try:
                    if os.path.isfile(p):
                        total_size += os.path.getsize(p)
                except Exception as _e:  # noqa: BLE001
                    pass
            info_text = f"{len(s)} elementos seleccionados ({self.format_size(total_size)})"
        return info_text

    def format_size(self, b):
        from src.core.utils import format_size as _fmt  # noqa: PLC0415

        return _fmt(b)

    def set_folders_only(self, b):
        self.proxy_model.folders_only = b
        self.proxy_model.invalidateFilter()

    def select_all(self):
        self.current_view_widget.selectAll()

    def invert_selection(self):
        """Invertir selección actual"""
        if self.shell_browser and self.current_view_widget is self.shell_browser:
            self.shell_browser.invert_selection()
        elif archive_handler.is_inside_archive(self.current_path):
            if isinstance(self.archive_browser, ArchiveBrowser):
                self.archive_browser.invert_selection()
            else:
                for i in range(self.archive_browser.count()):
                    item = self.archive_browser.item(i)
                    item.setSelected(not item.isSelected())
        else:
            root = self.current_view_widget.rootIndex()
            total = self.proxy_model.rowCount(root)
            if total == 0:
                return

            sm = self.current_view_widget.selectionModel()

            was_selected = set()
            for idx in sm.selectedIndexes():
                if idx.column() == 0:
                    was_selected.add(idx.row())

            sm.clear()

            for row in range(total):
                if row not in was_selected:
                    proxy_idx = self.proxy_model.index(row, 0, root)
                    sm.select(proxy_idx, QItemSelectionModel.Select | QItemSelectionModel.Rows)

    def set_view_mode(self, m):
        if m == "details":
            self.stack.setCurrentIndex(0)
            self.current_view_widget = self.tree
            self._configure_tree_headers()
        elif m == "list":
            self.stack.setCurrentIndex(1)
            self.current_view_widget = self.list
        else:
            self.stack.setCurrentIndex(2)
            self.current_view_widget = self.icon
            self.icon.setIconSize(QSize(64, 64) if m == "icons_large" else QSize(48, 48))
        self.view_mode = m

    def go_up(self):
        if archive_handler.is_inside_archive(self.current_path):
            info = archive_handler.get_mount_info(self.current_path)
            if info:
                # Normalizar rutas para comparar
                curr = os.path.normpath(self.current_path).lower()
                mnt = os.path.normpath(str(info.mount_point)).lower()

                if curr == mnt:
                    # Estamos en la raíz del montaje, salir del archivo
                    archive_handler.unmount_archive(str(info.archive_path))
                    self.set_path(os.path.dirname(str(info.archive_path)))
                else:
                    # Subir nivel dentro del montaje temporal
                    self.set_path(os.path.dirname(self.current_path))
        else:
            self.set_path(os.path.dirname(self.current_path))

    def go_root(self):
        self.set_path(os.path.splitdrive(self.current_path)[0] + os.sep)

    def go_home(self):
        self.set_path(QDir.homePath())

    def refresh(self, force=False):
        logger.debug("refresh() called, current_path=%s, force=%s", self, force)
        if not self.current_path:
            return
        if not os.path.exists(self.current_path):
            logger.warning("Path no longer exists, cannot refresh: %s", self)
            self.source_model.setRootPath("")
            return
        if self.is_in_archive:
            self._populate_archive_browser(self.current_path)
            return
        self._on_watcher_refresh(self.current_path)

    def _refresh_views(self):
        # Update all views to show current directory
        if not os.path.exists(self.current_path):
            return
        try:
            source_root_idx = self.source_model.index(self.current_path)
            self.proxy_model.set_current_root_source_index(source_root_idx)
            idx = self.proxy_model.mapFromSource(source_root_idx)
            for v in [self.tree, self.list, self.icon]:
                v.setRootIndex(idx)
                v.update()
        except Exception as e:
            logger.exception("Error refreshing views: %s", e)  # noqa: TRY401

    def clear_selection(self):
        self.current_view_widget.clearSelection()

    def select_and_focus(self, path):
        if self.shell_browser and self.current_view_widget is self.shell_browser:
            self.shell_browser.select_item_by_path(path)
            return
        if archive_handler.is_inside_archive(path):
            if isinstance(self.archive_browser, ArchiveBrowser):
                self.archive_browser.select_item_by_path(path)
            else:
                for i in range(self.archive_browser.count()):
                    item = self.archive_browser.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == path:
                        self.archive_browser.setCurrentItem(item)
                        self.archive_browser.setFocus()
                        return
        else:
            idx = self.proxy_model.mapFromSource(self.source_model.index(path))
            self.current_view_widget.setCurrentIndex(idx)
            self.current_view_widget.setFocus()

    def select_paths(self, paths):
        if not paths:
            return
        QApplication.processEvents()
        sm = self.current_view_widget.selectionModel()
        if not sm:
            return
        proxy = self.proxy_model
        source = self.source_model
        selection = QItemSelection()
        first_idx = None
        for path in paths:
            norm = os.path.normpath(path)
            source_idx = source.index(norm)
            if not source_idx.isValid():
                continue
            proxy_idx = proxy.mapFromSource(source_idx)
            if not proxy_idx.isValid():
                continue
            selection.select(proxy_idx, proxy_idx)
            if first_idx is None:
                first_idx = proxy_idx
        if selection.isEmpty():
            QTimer.singleShot(100, lambda: self.select_paths(paths))
            return
        sm.select(selection, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
        if first_idx is not None:
            sm.setCurrentIndex(first_idx, QItemSelectionModel.NoUpdate)
            self.current_view_widget.scrollTo(first_idx)
            self.current_view_widget.setFocus()

    def navigate_and_select(self, full_path):
        if not os.path.exists(full_path):
            return
        parent = os.path.dirname(full_path)
        filename = os.path.basename(full_path)
        self.set_path(parent)
        QTimer.singleShot(100, lambda: self._select_by_name(filename))

    def _select_by_name(self, name):
        if self.shell_browser and self.current_view_widget is self.shell_browser:
            self.shell_browser.select_item_by_name(name)
            return
        if archive_handler.is_inside_archive(self.current_path):
            if isinstance(self.archive_browser, ArchiveBrowser):
                self.archive_browser.select_item_by_name(name)
            else:
                for i in range(self.archive_browser.count()):
                    item = self.archive_browser.item(i)
                    if item.text() == name:
                        self.archive_browser.setCurrentItem(item)
                        self.archive_browser.scrollToItem(item)
                        self.archive_browser.setFocus()
                        return
        else:
            row_count = self.proxy_model.rowCount()
            for row in range(row_count):
                idx = self.proxy_model.index(row, 0)
                if self.proxy_model.data(idx) == name:
                    self.current_view_widget.setCurrentIndex(idx)
                    self.current_view_widget.scrollTo(idx)
                    self.current_view_widget.setFocus()
                    return

    def rename_selected_item(self):
        idx = self.current_view_widget.selectedIndexes()
        if idx:
            self._start_inline_rename(idx[0])

    def copy_path_to_clipboard(self):
        s = self.get_selected_paths()
        if s:
            QApplication.clipboard().setText("\n".join(s))

    def duplicate_selected(self):
        selected = self.get_selected_paths()
        if not selected:
            return

        duplicated = []
        for p in selected:
            basename = os.path.basename(p)
            name, ext = os.path.splitext(basename)
            parent_dir = os.path.dirname(p)
            copy_name = f"{name}-copia{ext}"
            copy_path = os.path.join(parent_dir, copy_name)

            counter = 1
            while os.path.exists(copy_path):
                copy_name = f"{name}-copia ({counter}){ext}"
                copy_path = os.path.join(parent_dir, copy_name)
                counter += 1

            try:
                if os.path.isdir(p):
                    shutil.copytree(p, copy_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(p, copy_path)
                duplicated.append(copy_name)
            except Exception as e:  # noqa: BLE001
                logger.debug("Error duplicando %s: %s", p, e)

        if duplicated:
            self.refresh()

    def _setup_context_menus(self):
        for v in [self.tree, self.list, self.icon]:
            v.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            v.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, position):
        """Muestra el menú contextual nativo de Windows"""
        idx = self.current_view_widget.indexAt(position)

        is_background = False
        path_under_cursor = self.get_path_from_index(idx) if idx.isValid() else None

        if path_under_cursor:
            if not self.current_view_widget.selectionModel().isSelected(idx):
                self.current_view_widget.setSelection(
                    self.current_view_widget.visualRect(idx),
                    QItemSelectionModel.SelectionFlag.Select
                    | QItemSelectionModel.SelectionFlag.Clear,
                )
            selected_paths = [path_under_cursor]
        else:
            selected_paths = self.get_selected_paths()
            if not selected_paths:
                is_background = True
                selected_paths = [self.current_path]

        # Obtener coordenadas globales
        global_pos = self.current_view_widget.mapToGlobal(position)
        cursor_pos = QCursor.pos()
        logger.debug(
            f"Context menu - position: {position},"
            f" mapToGlobal: ({global_pos.x()}, {global_pos.y()}),"
            f" cursor: ({cursor_pos.x()}, {cursor_pos.y()})"
        )

        # Usar posición del cursor (más confiable)
        use_pos = cursor_pos

        # Obtener HWND
        hwnd = int(self.window().winId())

        # Importar e invocar el menú nativo
        try:
            from src.ui.native_menu import get_native_menu  # noqa: PLC0415

            # Procesar eventos pendientes de Qt antes de mostrar menú
            QApplication.processEvents()

            if is_background:
                get_native_menu().show_background_menu(
                    hwnd, self.current_path, use_pos.x(), use_pos.y(), self._create_new_item
                )
            else:
                get_native_menu().show_menu(hwnd, selected_paths, use_pos.x(), use_pos.y())

            # Procesar eventos después del menú
            QApplication.processEvents()
            # Refrescar después por si hubo cambios (borrado, renombrado)
            self.refresh()
        except Exception as e:
            logger.exception("Fallo al mostrar menú nativo: %s", e)  # noqa: TRY401
            # Fallback al menú básico de Qt si el nativo falla
            self._show_basic_menu(position, selected_paths)

    def _show_basic_menu(self, position, _paths):
        """Menú de respaldo en caso de error del nativo"""
        menu = QMenu(self)
        menu.addAction(
            "Abrir", lambda: self.on_item_double_clicked(self.current_view_widget.indexAt(position))
        )
        menu.addAction("Copiar ruta", self.copy_path_to_clipboard)
        menu.addSeparator()
        menu.addAction("Eliminar", lambda: self.delete_requested.emit())  # noqa: PLW0108
        menu.exec(self.current_view_widget.mapToGlobal(position))

    def eventFilter(self, obj, event):  # noqa: N802
        # Manejar clicks para emitir foco
        if event.type() == event.Type.MouseButtonPress:
            # Click on nav_frame - focus panel
            if obj == self.nav_frame:
                self.focused.emit(self)
                self.setFocus()
                return False

            for v in [self.tree, self.list, self.icon]:
                if obj == v.viewport():
                    idx = v.indexAt(event.pos())
                    if not idx.isValid():
                        self.focused.emit(self)
                    break

        # Manejar teclas - solo si este panel tiene el foco activo
        elif event.type() == event.Type.KeyPress:
            # Verificar si hay un diálogo modal abierto
            from PySide6.QtWidgets import QApplication  # noqa: PLC0415

            app = QApplication.instance()
            active_window = app.activeWindow()
            if active_window and active_window != self.window():
                # Hay un diálogo abierto, no interceptar
                return super().eventFilter(obj, event)

            # Manejar tecla Enter como doble clic
            if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                current_view = self.current_view_widget
                if current_view and current_view.hasFocus():
                    selected = current_view.selectedIndexes()
                    if selected:
                        self.on_item_double_clicked(selected[0])
                        return True

            # Nota: Las teclas '+' y '-' para selección por patrón se manejan
            # desde el eventFilter global en main.py para funcionar desde cualquier foco

            # Tancar filtre amb ESC (manejo local para respuesta más rápida)
            if event.key() == Qt.Key.Key_Escape and self.filter_input.isVisible():
                self.filter_input.clear()
                self.filter_input.hide()
                self.current_view_widget.setFocus()
                return True

        return super().eventFilter(obj, event)

    def go_back(self):
        path = self._path_history.back()
        if path:
            self._path_history.set_navigating(True)
            self.set_path(path)
            self._path_history.set_navigating(False)
            self._update_history_buttons()

    def go_forward(self):
        path = self._path_history.forward()
        if path:
            self._path_history.set_navigating(True)
            self.set_path(path)
            self._path_history.set_navigating(False)
            self._update_history_buttons()

    def _update_history_buttons(self):
        self.back_btn.setEnabled(self._path_history.can_back)
        self.forward_btn.setEnabled(self._path_history.can_forward)

    def _on_tab_path_changed(self, _index, path):
        self._tab_navigating = True
        self._path_history.set_navigating(True)
        self.set_path(path)
        self._path_history.set_navigating(False)
        self._tab_navigating = False

    def _on_tab_close(self, index):
        if self.tab_bar and self.tab_bar.count() > 1:
            self.tab_bar.removeTab(index)

    def _on_new_tab(self):
        if self.tab_bar:
            self.tab_bar.add_tab(self.current_path)

    def add_tab(self, path=None):
        if self.tab_bar:
            p = path or self.current_path
            self.tab_bar.add_tab(p)

    def show_inline_progress(self, percent: int):
        """Mostrar progress_bar + botó X in-line."""
        self.inline_progress.show()
        pct = max(0, min(100, percent))
        self.inline_progress_bar.setValue(pct)
        self.inline_cancel_btn.setEnabled(True)

    def hide_inline_progress(self):
        self.inline_progress.hide()
        self.inline_progress_bar.setValue(0)
        self.inline_cancel_btn.setEnabled(False)
