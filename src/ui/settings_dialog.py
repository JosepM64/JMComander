import logging
import os

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

try:
    from src.shortcuts_constants import SHORTCUTS_LIST
    from src.toolbar_constants import (
        TOOLBAR_DEFAULT_TOOLTIPS,
        TOOLBAR_DISPLAY_NAMES,
        TOOLBAR_MASTER_LAYOUT,
    )
except ImportError:
    try:
        from shortcuts_constants import SHORTCUTS_LIST
        from toolbar_constants import (
            TOOLBAR_DEFAULT_TOOLTIPS,
            TOOLBAR_DISPLAY_NAMES,
            TOOLBAR_MASTER_LAYOUT,
        )
    except ImportError:
        TOOLBAR_MASTER_LAYOUT = []
        TOOLBAR_DISPLAY_NAMES = {}
        TOOLBAR_DEFAULT_TOOLTIPS = {}
        SHORTCUTS_LIST = []


class SettingsDialog(QDialog):
    def __init__(self, config_manager, plugin_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración - JMComander")
        self.resize(850, 700)
        self.config = config_manager
        self.plugin_manager = plugin_manager
        self.main_window = parent
        self.tooltip_inputs = {}

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # --- Pestaña 1: Orden Barra ---
        tab_toolbar = QWidget()
        tb_layout = QVBoxLayout(tab_toolbar)
        tb_layout.addWidget(QLabel("Arrastra para reordenar botones de la barra principal:"))
        self.list_toolbar = QListWidget()
        self.list_toolbar.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_toolbar.setIconSize(QtCore.QSize(24, 24))

        current_layout = self.config.get_toolbar_layout()
        self.names = TOOLBAR_DISPLAY_NAMES

        for key in current_layout:
            if key in self.names:
                item = QListWidgetItem(self.names[key])
                item.setData(Qt.ItemDataRole.UserRole, key)
                if self.main_window and hasattr(self.main_window, "actions_map"):
                    obj = self.main_window.actions_map.get(key)
                    if (obj and isinstance(obj, QtWidgets.QToolButton)) or isinstance(
                        obj, QtGui.QAction
                    ):
                        item.setIcon(obj.icon())
                if key in ["separator", "spacer"]:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
                    item.setForeground(QColor(128, 128, 128))
                self.list_toolbar.addItem(item)
        tb_layout.addWidget(self.list_toolbar)
        tabs.addTab(tab_toolbar, "Orden Barra")

        # --- Pestaña 2: Textos Ayuda ---
        tab_tooltips = QWidget()
        tt_layout = QVBoxLayout(tab_tooltips)
        tt_layout.addWidget(QLabel("Personaliza los textos de ayuda (hover):"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        for key, default in TOOLBAR_DEFAULT_TOOLTIPS.items():
            if key in self.names:
                edit = QLineEdit(self.config.get_tooltip(key, default))
                edit.setPlaceholderText(default)
                self.tooltip_inputs[key] = edit
                form.addRow(f"{self.names[key]}:", edit)
        scroll.setWidget(content)
        tt_layout.addWidget(scroll)
        tabs.addTab(tab_tooltips, "Textos Ayuda")

        # --- Pestaña 3: Atajos ---
        tab_keys = QWidget()
        keys_layout = QVBoxLayout(tab_keys)
        keys_layout.addWidget(QLabel("Atajos de teclado implementados:"))
        self.table_keys = QTableWidget(len(SHORTCUTS_LIST), 2)
        self.table_keys.setHorizontalHeaderLabels(["Acción", "Teclas"])
        self.table_keys.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_keys.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_keys.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for i, item in enumerate(SHORTCUTS_LIST):
            self.table_keys.setItem(i, 0, QTableWidgetItem(item["action"]))
            self.table_keys.setItem(i, 1, QTableWidgetItem(item["key"]))
        keys_layout.addWidget(self.table_keys)
        tabs.addTab(tab_keys, "Atajos")

        # --- Pestaña 4: Plugins ---
        tab_plugins = QWidget()
        pl_layout = QVBoxLayout(tab_plugins)

        # Tabla de plugins
        self.pl_table = QTableWidget(0, 5)
        self.pl_table.setHorizontalHeaderLabels(
            ["Habilitado", "Nombre", "Versión", "Autor", "Tipo"]
        )
        self.pl_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.pl_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        # Cargar plugins
        self._load_plugins_table()

        pl_layout.addWidget(self.pl_table)

        # Botones
        btn_pl_layout = QHBoxLayout()
        self.btn_pl_enable = QPushButton("Habilitar")
        self.btn_pl_disable = QPushButton("Deshabilitar")
        self.btn_pl_config = QPushButton("⚙ Configurar")
        self.btn_pl_refresh = QPushButton("Recargar Plugins")

        self.btn_pl_enable.clicked.connect(self._enable_selected_plugin)
        self.btn_pl_disable.clicked.connect(self._disable_selected_plugin)
        self.btn_pl_config.clicked.connect(self._configure_selected_plugin)
        self.btn_pl_refresh.clicked.connect(self._reload_plugins)

        btn_pl_layout.addWidget(self.btn_pl_enable)
        btn_pl_layout.addWidget(self.btn_pl_disable)
        btn_pl_layout.addWidget(self.btn_pl_config)
        btn_pl_layout.addWidget(self.btn_pl_refresh)
        btn_pl_layout.addStretch()

        pl_layout.addLayout(btn_pl_layout)

        tabs.addTab(tab_plugins, "Plugins")

        # --- Pestaña 5: General ---
        tab_general = QWidget()
        gen_layout = QVBoxLayout(tab_general)
        gen_layout.addWidget(QLabel("Opciones generales:"))

        self.chk_background_ops = QCheckBox(
            "Ejecutar copiar/mover/eliminar en segundo plano por defecto"
        )
        self.chk_background_ops.setToolTip(
            "Cuando está activado, las operaciones de copiar, mover y eliminar se ejecutan en "
            "segundo plano mostrando el progreso en un pequeño panel "
            "en la parte inferior de la ventana. "
            "Puedes cancelar la operación en cualquier momento."
        )
        self.chk_background_ops.setChecked(self.config.get_background_operations())
        gen_layout.addWidget(self.chk_background_ops)

        work_dir_layout = QHBoxLayout()
        work_dir_layout.addWidget(QLabel("Directorio de trabajo (fallback al iniciar):"))
        self.work_dir_input = QLineEdit(self.config.get_work_directory())
        self.work_dir_input.setPlaceholderText("Dejar vacío para usar directorio de usuario")
        self.work_dir_input.setToolTip(
            "Si el último directori era un USB desconnectat, es canviarà a aquest directori. "
            "Si està buit, usarà el directori de l'usuari."
        )
        work_dir_layout.addWidget(self.work_dir_input)
        btn_browse_work = QPushButton("...")
        btn_browse_work.setFixedWidth(30)
        btn_browse_work.clicked.connect(self._browse_work_directory)
        work_dir_layout.addWidget(btn_browse_work)
        gen_layout.addLayout(work_dir_layout)

        gen_layout.addStretch()

        tabs.addTab(tab_general, "General")

        layout.addWidget(tabs)

        layout.addWidget(tabs)

        btn_box = QHBoxLayout()
        btn_reset = QPushButton("Restaurar Predeterminados")
        btn_reset.clicked.connect(self.reset_to_defaults)
        btn_save = QPushButton("Guardar y Aplicar")
        btn_save.clicked.connect(self.save_settings)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_reset)
        btn_box.addStretch()
        btn_box.addWidget(btn_save)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

    def _load_plugins_table(self):
        """Carga la tabla de plugins"""
        self.pl_table.setRowCount(0)
        self.plugins_data = self.plugin_manager.get_plugins()

        for _i, p in enumerate(self.plugins_data):
            row = self.pl_table.rowCount()
            self.pl_table.insertRow(row)

            # Checkbox habilitado
            chk = QCheckBox()
            chk.setChecked(True)
            chk.stateChanged.connect(
                lambda state, pid=p.id: self._on_plugin_enabled_changed(pid, state)
            )
            self.pl_table.setCellWidget(row, 0, chk)

            # Nombre
            self.pl_table.setItem(row, 1, QTableWidgetItem(p.name))

            # Versión
            self.pl_table.setItem(row, 2, QTableWidgetItem(p.version))

            # Autor
            self.pl_table.setItem(row, 3, QTableWidgetItem(p.author))

            # Tipo
            tipo = "Bundled" if p.bundled else "Usuario"
            self.pl_table.setItem(row, 4, QTableWidgetItem(tipo))

    def _on_plugin_enabled_changed(self, plugin_id, state):
        """Called when plugin checkbox changes"""
        # Por ahora solo informativo
        # En el futuro se podría implementar deshabilitación real

    def _enable_selected_plugin(self):
        """Habilita el plugin seleccionado"""
        row = self.pl_table.currentRow()
        if row >= 0 and row < self.pl_table.rowCount():
            chk = self.pl_table.cellWidget(row, 0)
            if isinstance(chk, QCheckBox):
                chk.setChecked(True)

    def _disable_selected_plugin(self):
        """Deshabilita el plugin seleccionado"""
        row = self.pl_table.currentRow()
        if row >= 0 and row < self.pl_table.rowCount():
            chk = self.pl_table.cellWidget(row, 0)
            if isinstance(chk, QCheckBox):
                chk.setChecked(False)

    def _reload_plugins(self):
        """Recarga todos los plugins"""
        from PySide6.QtWidgets import QMessageBox  # noqa: PLC0415

        QMessageBox.information(
            self,
            "Recargar Plugins",
            "Para recargar plugins, reinicia JMComander.\n\n"
            "Los plugins se cargan automáticamente al iniciar.",
        )

    def _configure_selected_plugin(self):
        """Abre el diálogo de configuración del plugin seleccionado"""
        from PySide6.QtWidgets import QMessageBox  # noqa: PLC0415

        row = self.pl_table.currentRow()
        if row < 0 or row >= self.pl_table.rowCount():
            QMessageBox.warning(
                self, "Configurar Plugin", "Por favor, selecciona un plugin de la lista."
            )
            return

        # Obtener el plugin seleccionado
        plugin = self.plugins_data[row]

        # Verificar si el plugin tiene diálogo de configuración
        logger.debug("Plugin %s config_dialog = %s", plugin, plugin)
        if plugin.config_dialog:
            try:
                # Obtener configuración actual del plugin
                current_config = self.config.get_plugin_config(plugin.id, {})
                logger.debug("Config actual = %s", current_config)

                # Crear y mostrar el diálogo de configuración
                dialog = plugin.config_dialog(current_config, self)
                logger.debug("Dialog creado = %s", dialog)

                if dialog.exec():
                    # Guardar la nueva configuración
                    new_config = dialog.get_config()
                    logger.debug("Nueva config = %s", new_config)
                    if new_config is not None:
                        self.config.set_plugin_config(plugin.id, new_config)
                        QMessageBox.information(
                            self,
                            "Configuración Guardada",
                            f"La configuración de '{plugin.name}' ha sido guardada.",
                        )
            except Exception as e:
                import traceback  # noqa: PLC0415

                logger.exception("Error abriendo config: %s", e)  # noqa: TRY401
                traceback.print_exc()
                QMessageBox.critical(
                    self, "Error", f"No se pudo abrir la configuración de '{plugin.name}':\n{e!s}"
                )
        else:
            QMessageBox.information(
                self,
                "Sin Configuración",
                f"El plugin '{plugin.name}' no tiene opciones de configuración disponibles.",
            )

    def reset_to_defaults(self):
        self.list_toolbar.clear()
        for key in TOOLBAR_MASTER_LAYOUT:
            if key in self.names:
                item = QListWidgetItem(self.names[key])
                item.setData(Qt.ItemDataRole.UserRole, key)
                self.list_toolbar.addItem(item)
        for key, edit in self.tooltip_inputs.items():
            edit.setText(TOOLBAR_DEFAULT_TOOLTIPS.get(key, ""))

    def _browse_work_directory(self):
        from PySide6.QtWidgets import QFileDialog  # noqa: PLC0415

        current = self.work_dir_input.text() or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(
            self, "Seleccionar directori de treball", current
        )
        if directory:
            self.work_dir_input.setText(directory)

    def save_settings(self):
        new_layout = []
        for i in range(self.list_toolbar.count()):
            new_layout.append(self.list_toolbar.item(i).data(Qt.ItemDataRole.UserRole))  # noqa: PERF401
        if "settings" not in new_layout:
            new_layout.append("settings")
        self.config.set_toolbar_layout(new_layout)
        new_tips = {k: e.text() for k, e in self.tooltip_inputs.items()}
        self.config.set_tooltips(new_tips)
        self.config.set_background_operations(self.chk_background_ops.isChecked())
        self.config.set_work_directory(self.work_dir_input.text().strip())
        self.accept()
