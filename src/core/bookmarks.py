import logging

from src.core.json_store import _DEFAULT_PATHS, JsonStore

logger = logging.getLogger(__name__)


class BookmarkManager:
    def __init__(self, filepath="bookmarks.json"):
        self._store = JsonStore(filepath)
        if not self._store.get_all():
            self._store.set_items(
                [
                    {"name": "Inicio", "path": _DEFAULT_PATHS["home"]},
                    {"name": "Escritorio", "path": _DEFAULT_PATHS["desktop"]},
                    {"name": "Documentos", "path": _DEFAULT_PATHS["documents"]},
                    {"name": "Descargas", "path": _DEFAULT_PATHS["downloads"]},
                ]
            )

    def load(self):
        return self._store.load()

    def save(self):
        self._store.save()

    def add_bookmark(self, name, path):
        return self._store.add({"name": name, "path": path}, unique_key="path")

    def remove_bookmark(self, index):
        return self._store.remove(index)

    def update_bookmark(self, index, name, path):
        return self._store.update(index, {"name": name, "path": path})

    def move_up(self, index):
        return self._store.move_up(index)

    def move_down(self, index):
        return self._store.move_down(index)

    def get_all(self):
        return self._store.get_all()
