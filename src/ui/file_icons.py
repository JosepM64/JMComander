"""Icones del shell de Windows (les mateixes que l'Explorador).

Les icones s'extreuen amb ``SHGetFileInfo`` / ``SHGetImageList`` a partir de
l'extensió del fitxer (o del path real, per a les carpetes especials) i es
converteixen a ``QPixmap``. El resultat es cacheja per clau, de manera que cada
extensió només es consulta una vegada per procés.

Si l'extracció no està disponible (per exemple, un build sense pywin32), es fa
servir el mapa d'icones estàndard de Qt com a alternativa.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import uuid
from ctypes import wintypes
from functools import lru_cache

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QStyle

logger = logging.getLogger(__name__)

# Mides que demanem al shell. 16/32/48 cobreixen les vistes de detall i de
# llista; 256 (SHIL_JUMBO) només s'extreu quan la vista d'icones el necessita.
_SIZE_SMALL = 16
_SIZE_LARGE = 32
_SIZE_EXTRA = 48
_SIZE_JUMBO = 256
_JUMBO_THRESHOLD = 64
_JUMBO_MIN_CONTENT_RATIO = 0.4

_SHIL_SMALL = 0
_SHIL_LARGE = 1
_SHIL_EXTRALARGE = 2
_SHIL_JUMBO = 4
_SIZE_TO_SHIL = {
    _SIZE_SMALL: _SHIL_SMALL,
    _SIZE_LARGE: _SHIL_LARGE,
    _SIZE_EXTRA: _SHIL_EXTRALARGE,
}

_SHGFI_ICON = 0x000000100
_SHGFI_SMALLICON = 0x000000001
_SHGFI_LARGEICON = 0x000000000
_SHGFI_SYSICONINDEX = 0x000004000
_SHGFI_USEFILEATTRIBUTES = 0x000000010
_ILD_TRANSPARENT = 0x00000001
_FILE_ATTRIBUTE_NORMAL = 0x80
_FILE_ATTRIBUTE_DIRECTORY = 0x10
_IID_IIMAGELIST = uuid.UUID("{46EB5926-582E-4017-9FDF-E8998DAA0950}")
# SHGetImageList només s'exporta per ordinal.
_SHGETIMAGELIST_ORDINAL = 727

_FAKE_FILE = "C:\\__jmcomander_icon__"
_FAKE_FOLDER = "C:\\__jmcomander_icon_dir__"

# Carpetes conegudes de Windows (Descargas, Escritorio...). Es comprova el
# path real, així que no hi ha falsos positius amb carpetes que es diguin igual.
_KNOWN_FOLDERS = (
    ("desktop", QStandardPaths.StandardLocation.DesktopLocation),
    ("documents", QStandardPaths.StandardLocation.DocumentsLocation),
    ("downloads", QStandardPaths.StandardLocation.DownloadLocation),
    ("pictures", QStandardPaths.StandardLocation.PicturesLocation),
    ("music", QStandardPaths.StandardLocation.MusicLocation),
    ("videos", QStandardPaths.StandardLocation.MoviesLocation),
)


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _SHFILEINFOW(ctypes.Structure):
    _fields_ = [
        ("hIcon", wintypes.HICON),
        ("iIcon", ctypes.c_int),
        ("dwAttributes", wintypes.DWORD),
        ("szDisplayName", wintypes.WCHAR * 260),
        ("szTypeName", wintypes.WCHAR * 80),
    ]


class _ShellIconExtractor:
    """Extreu icones de Windows i les converteix a ``QPixmap``."""

    def __init__(self) -> None:
        self.available = False
        self._shell32 = None
        self._user32 = None
        self._win32con = None
        self._win32gui = None
        self._win32ui = None
        self._get_image_list = None
        self._get_icon_proto = None
        self._iid = None
        self._lists: dict[int, object | None] = {}
        self._setup()

    # ------------------------------------------------------------------ setup
    def _setup(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import win32con  # noqa: PLC0415
            import win32gui  # noqa: PLC0415
            import win32ui  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            logger.warning("Icones del shell no disponibles (pywin32): %s", exc)
            return

        try:
            shell32 = ctypes.WinDLL("shell32", use_last_error=True)
            shell32.SHGetFileInfoW.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                ctypes.POINTER(_SHFILEINFOW),
                wintypes.UINT,
                wintypes.UINT,
            ]
            shell32.SHGetFileInfoW.restype = ctypes.c_void_p

            get_image_list = shell32[_SHGETIMAGELIST_ORDINAL]
            get_image_list.argtypes = [
                ctypes.c_int,
                ctypes.POINTER(_GUID),
                ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
            ]
            get_image_list.restype = ctypes.c_long

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.DrawIconEx.argtypes = [
                wintypes.HDC,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.HICON,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.UINT,
                wintypes.HBRUSH,
                wintypes.UINT,
            ]
            user32.DrawIconEx.restype = wintypes.BOOL
            user32.DestroyIcon.argtypes = [wintypes.HICON]
            user32.DestroyIcon.restype = wintypes.BOOL
        except Exception as exc:  # noqa: BLE001
            logger.warning("Icones del shell no disponibles: %s", exc)
            return

        self._shell32 = shell32
        self._user32 = user32
        self._win32con = win32con
        self._win32gui = win32gui
        self._win32ui = win32ui
        self._get_image_list = get_image_list
        self._get_icon_proto = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.POINTER(wintypes.HICON),
        )
        self._iid = _GUID.from_buffer_copy(_IID_IIMAGELIST.bytes_le)
        self.available = True
        logger.debug("Icones del shell de Windows disponibles")

    # --------------------------------------------------------------- extracció
    def _index_for(self, name: str, attributes: int, use_attributes: bool) -> int:
        info = _SHFILEINFOW()
        flags = _SHGFI_SYSICONINDEX
        if use_attributes:
            flags |= _SHGFI_USEFILEATTRIBUTES
        self._shell32.SHGetFileInfoW(
            name, attributes, ctypes.byref(info), ctypes.sizeof(info), flags
        )
        return info.iIcon

    def _image_list(self, shil: int):
        if shil in self._lists:
            return self._lists[shil]
        pointer = ctypes.POINTER(ctypes.c_void_p)()
        result = self._get_image_list(shil, ctypes.byref(self._iid), ctypes.byref(pointer))
        self._lists[shil] = pointer if result == 0 and pointer else None
        return self._lists[shil]

    def _hicon_from_list(self, shil: int, index: int):
        image_list = self._image_list(shil)
        if not image_list:
            return None
        vtable = ctypes.cast(
            image_list, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        hicon = wintypes.HICON()
        result = self._get_icon_proto(vtable[10])(
            image_list, index, _ILD_TRANSPARENT, ctypes.byref(hicon)
        )
        if result != 0 or not hicon or not hicon.value:
            return None
        return hicon

    def _hicon_from_file_info(
        self, name: str, attributes: int, use_attributes: bool, large: bool
    ):
        info = _SHFILEINFOW()
        flags = _SHGFI_ICON | (_SHGFI_LARGEICON if large else _SHGFI_SMALLICON)
        if use_attributes:
            flags |= _SHGFI_USEFILEATTRIBUTES
        self._shell32.SHGetFileInfoW(
            name, attributes, ctypes.byref(info), ctypes.sizeof(info), flags
        )
        if not info.hIcon or not info.hIcon.value:
            return None
        return info.hIcon

    def _hicon(
        self, index: int, size: int, name: str, attributes: int, use_attributes: bool
    ):
        hicon = self._hicon_from_list(_SIZE_TO_SHIL[size], index)
        if hicon is not None:
            return hicon
        return self._hicon_from_file_info(
            name, attributes, use_attributes, large=size >= _SIZE_LARGE
        )

    def _to_image(self, hicon, size: int) -> QImage | None:
        hdc_screen = 0
        source_dc = memory_dc = bitmap = None
        try:
            hdc_screen = self._win32gui.GetDC(0)
            source_dc = self._win32ui.CreateDCFromHandle(hdc_screen)
            memory_dc = source_dc.CreateCompatibleDC()
            bitmap = self._win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(source_dc, size, size)
            memory_dc.SelectObject(bitmap)
            memory_dc.FillSolidRect((0, 0, size, size), 0)
            self._user32.DrawIconEx(
                memory_dc.GetSafeHdc(),
                0,
                0,
                hicon,
                size,
                size,
                0,
                None,
                self._win32con.DI_NORMAL,
            )
            bits = bitmap.GetBitmapBits(True)
            return QImage(bits, size, size, QImage.Format.Format_ARGB32).copy()
        except Exception as exc:  # noqa: BLE001
            logger.debug("No s'ha pogut convertir la icona del shell (%spx): %s", size, exc)
            return None
        finally:
            if memory_dc is not None:
                memory_dc.DeleteDC()
            if source_dc is not None:
                source_dc.DeleteDC()
            if bitmap is not None:
                try:
                    self._win32gui.DeleteObject(bitmap.GetHandle())
                except Exception:  # noqa: BLE001
                    pass
            if hdc_screen:
                self._win32gui.ReleaseDC(0, hdc_screen)

    # ------------------------------------------------------------------- API
    def build_icon(self, name: str, attributes: int, use_attributes: bool) -> QIcon | None:
        if not self.available:
            return None
        try:
            index = self._index_for(name, attributes, use_attributes)
        except Exception as exc:  # noqa: BLE001
            logger.debug("SHGetFileInfo ha fallat per '%s': %s", name, exc)
            return None

        icon = QIcon()
        for size in (_SIZE_SMALL, _SIZE_LARGE, _SIZE_EXTRA):
            hicon = self._hicon(index, size, name, attributes, use_attributes)
            if hicon is None:
                continue
            try:
                image = self._to_image(hicon, size)
            finally:
                self._user32.DestroyIcon(hicon)
            if image is not None:
                icon.addPixmap(QPixmap.fromImage(image))
        return None if icon.isNull() else icon

    def jumbo_pixmap(self, name: str, attributes: int, use_attributes: bool) -> QPixmap | None:
        """Icona de 256 px, només si el shell en té una de real (no una de petita)."""
        if not self.available:
            return None
        try:
            index = self._index_for(name, attributes, use_attributes)
            hicon = self._hicon_from_list(_SHIL_JUMBO, index)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Icona jumbo no disponible per '%s': %s", name, exc)
            return None
        if hicon is None:
            return None
        try:
            image = self._to_image(hicon, _SIZE_JUMBO)
        finally:
            self._user32.DestroyIcon(hicon)
        if image is None or _content_ratio(image) < _JUMBO_MIN_CONTENT_RATIO:
            # El shell no té una icona gran: n'ha tornat una de petita en una
            # cantonada. Val més escalar la de 48 px, que quedaria centrada.
            return None
        return QPixmap.fromImage(image)


def _content_ratio(image: QImage) -> float:
    """Relació entre el costat més gran del contingut i la mida del llenç.

    Es mostreja la imatge (no cal mirar els 65 536 píxels) perquè només
    interessa distingir una icona gran de veritat d'una de 48 px posada en una
    cantonada del llenç de 256 px.
    """
    width = image.width()
    height = image.height()
    step = max(1, width // 32)
    min_x, min_y, max_x, max_y = width, height, -1, -1
    for y in range(0, height, step):
        for x in range(0, width, step):
            if (image.pixel(x, y) >> 24) & 0xFF > 8:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x < 0 or max_y < 0:
        return 0.0
    content = max(max_x - min_x + step, max_y - min_y + step)
    return content / float(width)


# Icones de recanvi (si el shell no està disponible). Es construeixen a partir
# de les icones estàndard de Qt.
_FALLBACK_ICONS = {
    ".jpg": "SP_FileDialogContentsView",
    ".jpeg": "SP_FileDialogContentsView",
    ".png": "SP_FileDialogContentsView",
    ".gif": "SP_FileDialogContentsView",
    ".bmp": "SP_FileDialogContentsView",
    ".webp": "SP_FileDialogContentsView",
    ".heic": "SP_FileDialogContentsView",
    ".heif": "SP_FileDialogContentsView",
    ".avif": "SP_FileDialogContentsView",
    ".svg": "SP_FileDialogContentsView",
    ".ico": "SP_FileDialogContentsView",
    ".tif": "SP_FileDialogContentsView",
    ".tiff": "SP_FileDialogContentsView",
    ".mp4": "SP_MediaVolume",
    ".mkv": "SP_MediaVolume",
    ".avi": "SP_MediaVolume",
    ".mov": "SP_MediaVolume",
    ".wmv": "SP_MediaVolume",
    ".webm": "SP_MediaVolume",
    ".mpg": "SP_MediaVolume",
    ".mpeg": "SP_MediaVolume",
    ".mp3": "SP_MediaPlay",
    ".wav": "SP_MediaPlay",
    ".flac": "SP_MediaPlay",
    ".aac": "SP_MediaPlay",
    ".ogg": "SP_MediaPlay",
    ".m4a": "SP_MediaPlay",
    ".wma": "SP_MediaPlay",
    ".zip": "SP_FileDialogStart",
    ".rar": "SP_FileDialogStart",
    ".7z": "SP_FileDialogStart",
    ".gz": "SP_FileDialogStart",
    ".tar": "SP_FileDialogStart",
    ".bz2": "SP_FileDialogStart",
    ".xz": "SP_FileDialogStart",
    ".iso": "SP_FileDialogStart",
    ".pdf": "SP_FileDialogDetailedView",
    ".doc": "SP_FileDialogDetailedView",
    ".docx": "SP_FileDialogDetailedView",
    ".odt": "SP_FileDialogDetailedView",
    ".xls": "SP_FileDialogDetailedView",
    ".xlsx": "SP_FileDialogDetailedView",
    ".ods": "SP_FileDialogDetailedView",
    ".ppt": "SP_FileDialogDetailedView",
    ".pptx": "SP_FileDialogDetailedView",
    ".txt": "SP_FileDialogDetailedView",
    ".log": "SP_FileDialogDetailedView",
    ".md": "SP_FileDialogDetailedView",
    ".rtf": "SP_FileDialogDetailedView",
    ".exe": "SP_ComputerIcon",
    ".msi": "SP_ComputerIcon",
    ".bat": "SP_ComputerIcon",
    ".cmd": "SP_ComputerIcon",
    ".py": "SP_FileIcon",
    ".js": "SP_FileIcon",
    ".ts": "SP_FileIcon",
    ".html": "SP_FileIcon",
    ".css": "SP_FileIcon",
    ".json": "SP_FileIcon",
    ".xml": "SP_FileIcon",
}


def _fallback_icon(ext: str) -> QIcon:
    app = QApplication.instance()
    if app is None:
        return QIcon()
    name = _FALLBACK_ICONS.get(ext, "SP_FileIcon")
    standard = getattr(QStyle.StandardPixmap, name, QStyle.StandardPixmap.SP_FileIcon)
    return QIcon(app.style().standardIcon(standard))


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


class ShellIconProvider:
    """Cacheja les icones del shell per extensió i per carpeta especial."""

    def __init__(self) -> None:
        self._extractor = _ShellIconExtractor()
        self._cache: dict[str, QIcon] = {}
        self._jumbo_checked: set[str] = set()
        self._known_folders: dict[str, str] | None = None

    @property
    def available(self) -> bool:
        return self._extractor.available

    def file_icon(self, ext: str, size: int = _SIZE_SMALL) -> QIcon:
        ext = (ext or "").lower()
        name = f"{_FAKE_FILE}{ext}"
        return self._cached(
            key=f"file:{ext}",
            size=size,
            name=name,
            attributes=_FILE_ATTRIBUTE_NORMAL,
            use_attributes=True,
            fallback=lambda: _fallback_icon(ext),
        )

    def folder_icon(self, path: str | None = None, size: int = _SIZE_SMALL) -> QIcon:
        special = self._special_folder(path)
        if special is not None:
            return self._cached(
                key=f"folder:{special}",
                size=size,
                name=str(path),
                attributes=_FILE_ATTRIBUTE_DIRECTORY,
                use_attributes=False,
                fallback=lambda: _fallback_icon(""),
            )
        return self._cached(
            key="folder",
            size=size,
            name=_FAKE_FOLDER,
            attributes=_FILE_ATTRIBUTE_DIRECTORY,
            use_attributes=True,
            fallback=lambda: _fallback_icon(""),
        )

    # -------------------------------------------------------------- internals
    def _cached(
        self,
        key: str,
        size: int,
        *,
        name: str,
        attributes: int,
        use_attributes: bool,
        fallback,
    ) -> QIcon:
        icon = self._cache.get(key)
        if icon is None:
            icon = self._extractor.build_icon(name, attributes, use_attributes)
            if icon is None or icon.isNull():
                icon = fallback()
            self._cache[key] = icon

        if (
            size >= _JUMBO_THRESHOLD
            and self._extractor.available
            and key not in self._jumbo_checked
        ):
            self._jumbo_checked.add(key)
            pixmap = self._extractor.jumbo_pixmap(name, attributes, use_attributes)
            if pixmap is not None:
                icon.addPixmap(pixmap)
        return icon

    def _special_folder(self, path: str | None) -> str | None:
        if not path:
            return None
        if self._known_folders is None:
            known: dict[str, str] = {}
            for key, location in _KNOWN_FOLDERS:
                value = QStandardPaths.writableLocation(location)
                if value:
                    known[_norm(value)] = key
            self._known_folders = known
        return self._known_folders.get(_norm(path))



@lru_cache(maxsize=1)
def get_icon_provider() -> ShellIconProvider:
    """Retorna el proveïdor compartit d'icones del shell."""
    return ShellIconProvider()


