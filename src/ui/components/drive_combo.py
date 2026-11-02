import logging
import os

import win32api
import win32file
from PySide6.QtCore import QDir, Signal
from PySide6.QtWidgets import QComboBox

from src.core.mtp_handler import get_iphone_storage_path

try:
    _HAS_WIN32 = True
except ImportError:
    _HAS_WIN32 = False

logger = logging.getLogger(__name__)


class DriveCombo(QComboBox):
    drive_activated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(80)
        self.activated.connect(self._on_activated)

    def _on_activated(self, index):
        path = self.itemData(index)
        if path:
            self.drive_activated.emit(path)

    def update_drives(self, current_path, shell_current_path=None, force_refresh=False, include_iphone=False):  # noqa: PLR0912
        current_drive = os.path.splitdrive(current_path)[0].upper()
        if not current_drive.endswith("/") and not current_drive.endswith("\\"):
            current_drive += "/"
        current_drive = current_drive.replace("\\", "/")

        # Early exit: mateixa unitat i llista ja construïda -> res a fer.
        # (GetVolumeInformation per unitat a cada navegació pot blocar amb USB lent)
        if (
            not force_refresh
            and self.count() > 0
            and getattr(self, "_last_drive", None) == current_drive
        ):
            return False
        self._last_drive = current_drive

        self.blockSignals(True)
        self.clear()

        for d in QDir.drives():
            path = d.path()
            norm_path = path.upper().replace("\\", "/")
            label = path
            try:
                if _HAS_WIN32:
                    win_path = os.path.normpath(path) + os.sep
                    dtype = win32file.GetDriveType(win_path)
                    if dtype == win32file.DRIVE_REMOVABLE:
                        try:
                            vol_name, _, _, _, _ = win32api.GetVolumeInformation(win_path)
                            if vol_name and "iPhone" in vol_name:
                                label = (
                                    f"[iPhone] {vol_name} ({path})"
                                    if vol_name.strip()
                                    else f"[iPhone] {path}"
                                )
                            else:
                                label = f"[USB] {path}"
                        except Exception:  # noqa: BLE001
                            label = f"[USB] {path}"
                    elif dtype == win32file.DRIVE_FIXED:
                        label = f"[Local] {path}"
                    elif dtype == win32file.DRIVE_REMOTE:
                        label = f"[Xarxa] {path}"
                    elif dtype == win32file.DRIVE_CDROM:
                        label = f"[CD] {path}"
            except Exception:  # noqa: BLE001
                pass

            self.addItem(label, path)

            if norm_path == current_drive:
                self.setCurrentIndex(self.count() - 1)

        # Detecció d'iPhone opcional: per defecte NO es fa en navegar ni en
        # canviar d'unitat (evita enumeracions COM al camí crític). Només
        # s'activa explícitament en obrir el desplegable (showPopup) o quan
        # ja estem dins d'una ruta Shell/MTP.
        found = False
        if include_iphone:
            found = self._add_iphone_entry(shell_current_path, force_refresh)

        self.blockSignals(False)
        return found

    def _add_iphone_entry(self, shell_current_path=None, force_refresh=False):
        iphone_info = get_iphone_storage_path(force_refresh)
        if not iphone_info:
            return False

        if isinstance(iphone_info, tuple) and len(iphone_info) == 2:
            iphone_shell_path, iphone_name = iphone_info
            label = f"[iPhone] {iphone_name}"
        elif isinstance(iphone_info, str):
            iphone_shell_path = iphone_info
            label = "[iPhone] iPhone"
        else:
            return False

        for i in range(self.count()):
            if self.itemData(i) == iphone_shell_path:
                return False

        self.addItem(label, iphone_shell_path)
        if shell_current_path and iphone_shell_path == shell_current_path:
            self.setCurrentIndex(self.count() - 1)
        return True


    def showPopup(self):  # noqa: N802
        """Detecta l'iPhone/MTP en obrir el desplegable d'unitats.

        Des de la v6.9.39 no hi ha botó dedicat a la barra: la detecció es
        fa aquí, de manera transparent per a l'usuari. És l'únic punt on es
        fa la comprovació (a més de quan ja estem dins d'una ruta Shell).
        """
        try:
            self._add_iphone_entry()
        except Exception:
            logger.debug("No s'ha pogut detectar l'iPhone en obrir el combo", exc_info=True)
        super().showPopup()
