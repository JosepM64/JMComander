import logging

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QSizePolicy, QToolButton, QWidget

from src.toolbar_constants import TOOLBAR_MASTER_LAYOUT

logger = logging.getLogger(__name__)


def is_widget_valid(obj):
    """Verifica si un objeto de Qt sigue siendo válido sin usar sip ni shiboken"""
    if obj is None:
        return False
    try:
        # En PySide6, si el objeto C++ ha sido eliminado,
        # intentar acceder a un método lanzará una excepción.
        obj.parent()
        return True  # noqa: TRY300
    except Exception:  # noqa: BLE001
        return False


class ToolbarManager(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.special_widgets = {}

    def register_special_widget(self, key, widget):
        self.special_widgets[key] = widget

    def refresh_toolbar(self):  # noqa: PLR0912
        toolbar = self.main_window.main_toolbar
        toolbar.clear()

        # Intentar recuperar widgets si fallan
        self._recreate_if_needed()

        layout = self.main_window.config.get_toolbar_layout()
        if not layout:
            layout = TOOLBAR_MASTER_LAYOUT

        # Mapa de funciones de actualización para asegurar que los menús funcionen
        menu_updaters = {
            "view_mode": self.main_window.update_view_mode_menu,
            "recent_paths": self.main_window.update_recent_paths_menu,
            "plugins": self.main_window.update_plugins_menu,
            "bookmarks": self.main_window.update_bookmarks_menu,
        }

        for key in layout:
            if key == "separator":
                toolbar.addSeparator()
            elif key == "spacer":
                spacer = QWidget()
                spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                toolbar.addWidget(spacer)
            elif key in self.special_widgets:
                w = self.special_widgets[key]
                if is_widget_valid(w):
                    w.setVisible(True)
                    w.setEnabled(True)

                    if isinstance(w, QToolButton):
                        w.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

                    # Llamar al actualizador de menú para que se genere el QMenu
                    if key in menu_updaters:
                        try:
                            menu_updaters[key]()
                        except Exception as e:  # noqa: BLE001
                            logger.debug("Error actualizando menú %s: %s", key, e)

                    # Aplicar tooltip personalizado
                    tip = self.main_window.config.get_tooltip(key)
                    if tip:
                        w.setToolTip(tip)

                    toolbar.addWidget(w)
            elif key in self.main_window.actions_map:
                item = self.main_window.actions_map[key]
                tip = self.main_window.config.get_tooltip(key)
                if tip and hasattr(item, "setToolTip"):
                    item.setToolTip(tip)

                if isinstance(item, QWidget):
                    toolbar.addWidget(item)
                else:
                    toolbar.addAction(item)

    def _recreate_if_needed(self):
        """Recrea los botones si han sido destruidos por el sistema de Qt"""
        creators = {
            "settings": self.main_window._create_settings_button,  # noqa: SLF001
            "view_mode": self.main_window._create_view_mode_button,  # noqa: SLF001
            "recent_paths": self.main_window._create_recent_paths_button,  # noqa: SLF001
            "plugins": self.main_window._create_plugins_button,  # noqa: SLF001
            "bookmarks": self.main_window._create_bookmarks_button,  # noqa: SLF001
        }
        for key, func in creators.items():
            w = self.special_widgets.get(key)
            if not is_widget_valid(w):
                new_w = func()
                self.special_widgets[key] = new_w
                # Actualizar ref en MainWindow para métodos internos
                attr_name = f"btn_{key if key != 'bookmarks' else 'bookmarks_menu'}"
                setattr(self.main_window, attr_name, new_w)
                self.main_window.actions_map[key] = new_w

                # Reconectar señales especiales que se pierden al recrear
                if key == "settings":
                    new_w.clicked.connect(self.main_window.open_settings)
                elif key == "plugins":
                    new_w.clicked.connect(self.main_window.show_plugins_menu)
