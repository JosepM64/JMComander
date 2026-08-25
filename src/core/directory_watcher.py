import logging
import os

from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)


class DirectoryWatcher(QObject):
    directory_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtCore import QFileSystemWatcher

        self._file_watcher = QFileSystemWatcher(self)
        self._file_watcher.directoryChanged.connect(self._on_directory_changed)

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._do_refresh)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(10000)
        self._poll_timer.timeout.connect(self._poll_for_changes)

        self._last_poll_files: set = set()
        self._poll_timer_started = False
        self._refresh_in_progress = False
        self._watched_path: str | None = None

    def watch(self, path: str, force_watcher_reset: bool = False):
        if not path or not os.path.isdir(path):
            self._poll_timer.stop()
            self._poll_timer_started = False
            return

        if not force_watcher_reset:
            watched = self._file_watcher.directories()
            if watched and watched[0] == path:
                if self._file_watcher.files() or self._file_watcher.directories():
                    return

        self._poll_timer.stop()
        watcher_failed = False

        try:
            watched = self._file_watcher.directories()
            if watched:
                self._file_watcher.removePaths(watched)
            if self._file_watcher.addPath(path):
                logger.debug("File watcher added: %s", path)
            else:
                logger.debug("File watcher addPath returned False")
                watcher_failed = True
        except Exception as e:
            logger.debug("Could not watch directory: %s", e)
            watcher_failed = True

        self._update_poll_cache(path)
        self._watched_path = path

        if watcher_failed or (self._need_polling(path) and not self._poll_timer_started):
            self._poll_timer.start()
            self._poll_timer_started = True

    def unwatch(self):
        self._poll_timer.stop()
        self._poll_timer_started = False
        try:
            watched = self._file_watcher.directories()
            if watched:
                self._file_watcher.removePaths(watched)
        except Exception:
            pass
        self._watched_path = None

    def _need_polling(self, path: str) -> bool:
        if not path:
            return False
        if path.startswith("::") or path.startswith("\\\\?\\") or "shell::" in path.lower():
            return True
        return path.startswith("\\\\") and not path.startswith("\\\\?\\")

    def _update_poll_cache(self, path: str):
        try:
            if path and os.path.isdir(path):
                self._last_poll_files = set(os.listdir(path))
            else:
                self._last_poll_files = set()
        except Exception:
            self._last_poll_files = set()

    def _poll_for_changes(self):
        try:
            if not self._watched_path or not os.path.isdir(self._watched_path):
                return
            if self._file_watcher.directories():
                return
            current_files = set(os.listdir(self._watched_path))
            if current_files != self._last_poll_files:
                self._last_poll_files = current_files
                self._do_refresh()
        except Exception as e:
            logger.debug("Error polling for changes: %s", e)

    def _on_directory_changed(self, path):
        logger.debug("Directory changed detected: %s", path)
        self._debounce_timer.start()

    def _do_refresh(self):
        logger.debug("DirectoryWatcher._do_refresh START")
        if self._refresh_in_progress:
            logger.debug("Refresh already in progress, queueing deferred refresh")
            QTimer.singleShot(100, self._do_refresh)
            return
        self._refresh_in_progress = True
        try:
            if self._watched_path and os.path.exists(self._watched_path):
                self._update_poll_cache(self._watched_path)
                self.directory_changed.emit(self._watched_path)
        except Exception as e:
            logger.debug("Error during auto-refresh: %s", e)
        finally:
            self._refresh_in_progress = False
