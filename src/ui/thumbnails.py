"""Miniatures d'imatges per a les vistes d'icones (Iconos P / G / XL).

Les miniatures es descodegen en un pool de fils amb QImageReader.setScaledSize
(decodeix només els pixels necessaris, no la imatge sencera) i es desenen en un
QPixmapCache compartit per tots els panells. El model rep el senyal
'thumbnail_ready' i refresca només la fila corresponent, de manera que la
interfície no es congela mai.
"""

import logging
import os
import threading

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, QSize, QThreadPool, Signal
from PySide6.QtGui import QImage, QImageReader, QPixmap, QPixmapCache

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_SUPPORT = True
except ImportError:
    pillow_heif = None
    HEIF_SUPPORT = False

logger = logging.getLogger(__name__)

# Extensions amb imatge que sabem decodificar (QImageReader / plugins Qt).
IMAGE_EXTENSIONS = frozenset({
    ".jpg",
    ".jpeg",
    ".jpe",
    ".jfif",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".tif",
    ".tiff",
    ".svg",
    ".svgz",
    ".heic",
    ".heif",
    ".avif",
})

# Qt 6 no sap llegir HEIC/HEIF/AVIF -> es fan amb pillow-heif (libheif).
PIL_FALLBACK_EXTENSIONS = frozenset({".heic", ".heif", ".avif"})

# Per damunt d'aquesta mida no es genera miniatura (fitxers RAW/PSD enormes).
MAX_SOURCE_BYTES = 96 * 1024 * 1024

# Mida de la cache de pixmaps (KiB) -> 128 MiB.
CACHE_LIMIT_KIB = 128 * 1024

# Registra el decodificador HEIF de Pillow un sol cop.
_pil_ready = False


def _ensure_pillow_heif() -> bool:
    """Indica si Pillow pot llegir HEIC/HEIF/AVIF."""
    return HEIF_SUPPORT


def is_image_file(path) -> bool:
    """True si el fitxer te una extensio d'imatge coneguda."""
    try:
        return os.path.splitext(str(path))[1].lower() in IMAGE_EXTENSIONS
    except (TypeError, ValueError):
        return False


def _decode_with_pillow(path, size):
    """Descodifica HEIC/HEIF/AVIF amb pillow-heif i retorna un QImage."""
    if not _ensure_pillow_heif():
        return None
    try:
        with Image.open(path) as handle:
            image = handle.convert("RGBA")
            image.thumbnail((size, size), Image.Resampling.LANCZOS)
            width, height = image.size
            data = image.tobytes()
    except Exception as exc:  # noqa: BLE001
        logger.debug("No s'ha pogut decodificar (pillow) %s: %s", path, exc)
        return None
    if width <= 0 or height <= 0:
        return None
    # .copy() fa que la QImage tingui la seva propia memoria (el buffer PIL
    # es pot alliberar immediatament).
    return QImage(data, width, height, width * 4, QImage.Format.Format_RGBA8888).copy()


def _decode_image(path, size):
    """Descodifica la imatge a com a maxim 'size' px conservant la proporcio.

    Retorna un QImage o None. Es pot cridar des d'un fil que no sigui el GUI
    (QImage no te restriccions de fil, a diferencia de QPixmap).
    """
    try:
        if os.path.getsize(path) > MAX_SOURCE_BYTES:
            return None
    except OSError:
        return None

    if os.path.splitext(str(path))[1].lower() in PIL_FALLBACK_EXTENSIONS:
        return _decode_with_pillow(path, size)

    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    original = reader.size()
    if original.isValid() and not original.isEmpty():
        width = original.width()
        height = original.height()
        # Escala només si cal reduir; aixi no fem upscale de miniatures.
        if width > size or height > size:
            factor = min(size / width, size / height)
            reader.setScaledSize(QSize(max(1, int(width * factor)), max(1, int(height * factor))))
    image = reader.read()
    if image.isNull():
        logger.debug("No s'ha pogut decodificar la imatge %s", path)
        return None
    return image


class _DecodeTask(QRunnable):
    """Descodifica una imatge en segon pla."""

    def __init__(self, provider, path, size):
        super().__init__()
        self._provider = provider
        self._path = path
        self._size = size
        self.setAutoDelete(True)

    def run(self):
        image = None
        mtime = None
        try:
            mtime = os.path.getmtime(self._path)
            image = _decode_image(self._path, self._size)
        except OSError:
            mtime = None
        except Exception as exc:  # noqa: BLE001
            logger.debug("Miniatura fallida per a %s: %s", self._path, exc)
        self._provider._deliver(self._path, self._size, image, mtime)  # noqa: SLF001


class ThumbnailProvider(QObject):
    """Genera i cacheja miniatures d'imatges en segon pla."""

    thumbnail_ready = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache = QPixmapCache()
        self._cache.setCacheLimit(CACHE_LIMIT_KIB)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(max(2, min(6, (os.cpu_count() or 4) // 2)))
        self._lock = threading.Lock()
        self._scheduled = set()
        self._images = {}
        # path -> mtime dels fitxers que NO s'han pogut decodificar.
        # Evita el bucle infinit de reintent (un .avif sense support de Qt
        # es tornava a demanar cada 400 ms).
        self._failed = {}

    def pixmap(self, path, size):
        """Retorna la miniatura si ja esta disponible; altrament la demana.

        Retorna None fins que la miniatura no estigui llesta (mentre es mostra
        la icona estatica de l'extensio).
        """
        key = self._key(path, size)
        cached = self._cache.find(key)
        if cached is not None and not cached.isNull():
            return cached
        # Potser el fil de treball ja ha acabat i la imatge espera: la recollim
        # i la posem al cache (QPixmap només es pot crear al thread GUI).
        with self._lock:
            pending = self._images.pop((path, size), None)
        if pending is not None:
            pixmap = QPixmap.fromImage(pending)
            if not pixmap.isNull():
                self._cache.insert(key, pixmap)
                return pixmap
        if self._is_failed(path):
            return None
        self._schedule(path, size)
        return None

    def store(self, path, size, image):
        """Guarda la miniatura al cache. S'ha de cridar al thread GUI."""
        if image is None:
            return
        self._cache.insert(self._key(path, size), QPixmap.fromImage(image))

    def take_image(self, path, size):
        """Recupera la imatge ja descodificada (l'ha deixat el fil de treball)."""
        with self._lock:
            return self._images.pop((path, size), None)

    def clear(self):
        """Buida la cache de miniatures."""
        self._cache.clear()
        with self._lock:
            self._images.clear()
            self._scheduled.clear()
            self._failed.clear()

    @staticmethod
    def _key(path, size):
        return f"{path}\x00{size}"

    def _is_failed(self, path) -> bool:
        """True si ja hem intentat (i fallat) decodificar aquest fitxer.

        Si el fitxer ha canviat (mtime diferent) es torna a intentar.
        """
        with self._lock:
            mtime = self._failed.get(path)
        if mtime is None:
            return False
        try:
            return os.path.getmtime(path) == mtime
        except OSError:
            return True

    def _schedule(self, path, size):
        marker = (path, size)
        with self._lock:
            if marker in self._scheduled:
                return
            self._scheduled.add(marker)
        self._pool.start(_DecodeTask(self, path, size))

    def _deliver(self, path, size, image, mtime=None):
        with self._lock:
            self._scheduled.discard((path, size))
            if image is not None:
                self._images[(path, size)] = image
            elif mtime is not None:
                self._failed[path] = mtime
        # Senyal encolat: s'executa al thread GUI.
        try:
            self.thumbnail_ready.emit(path, size)
        except RuntimeError:
            # L'objecte ja ha estat destruït (tancament de l'aplicació).
            logger.debug("Proveidor de miniatures destruït, es descarta %s", path)


_provider = None


def get_thumbnail_provider():
    """Proveidor compartit per tots els panells (la cache es comparteix)."""
    global _provider  # noqa: PLW0603
    if _provider is None:
        _provider = ThumbnailProvider()
    return _provider
