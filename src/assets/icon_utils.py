from PySide6.QtGui import QIcon  # noqa: INP001
from PySide6.QtWidgets import QApplication

"""
Utilitats per a la càrrega d'icones SVG a JMComander.
Consolida la lògica de càrrega per evitar duplicació de codi (DRY).
"""

import logging  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402

logger = logging.getLogger(__name__)


def get_base_path():
    """
    Retorna el path base per accedir a recursos (assets).
    Funciona tant en mode desenvolupament com en mode frozen (PyInstaller).
    """
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # noqa: SLF001
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def load_icon(icon_name, fallback_pixmap=None):
    """
    Carrega una icona SVG des de src/assets/icons/.

    Args:
        icon_name: Nom del fitxer SVG (ex: "mdi-arrow-up.svg")
        fallback_pixmap: QStyle.StandardPixmap a usar si falla la càrrega

    Returns:
        QIcon amb la icona carregada o el fallback
    """

    base_path = get_base_path()
    icon_path = os.path.join(base_path, "src", "assets", "icons", icon_name)

    if os.path.exists(icon_path):
        return QIcon(icon_path)

    logger.warning("Icona no trobada: %s, usant fallback", icon_path)
    if fallback_pixmap is not None:
        style = QApplication.style()
        return style.standardIcon(fallback_pixmap)
    return QIcon()


def load_icon_from_path(icon_path, fallback_pixmap=None):
    """
    Carrega una icona des d'un path absolut.

    Args:
        icon_path: Path absolut al fitxer d'icona
        fallback_pixmap: QStyle.StandardPixmap a usar si falla

    Returns:
        QIcon amb la icona carregada o el fallback
    """

    if icon_path and os.path.exists(icon_path):
        return QIcon(icon_path)

    if fallback_pixmap is not None:
        style = QApplication.style()
        return style.standardIcon(fallback_pixmap)
    return QIcon()
