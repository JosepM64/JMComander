import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_PATHS = {
    "home": str(Path.home()),
    "desktop": str(Path.home() / "Desktop"),
    "documents": str(Path.home() / "Documents"),
    "downloads": str(Path.home() / "Downloads"),
}


class JsonStore:
    def __init__(self, filepath, items_key="items"):
        self.filepath = filepath
        self._items_key = items_key
        self._items = []
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, encoding="utf-8") as f:
                    data = json.load(f)
                self._items = data if isinstance(data, list) else data.get(self._items_key, [])
            except Exception:  # noqa: BLE001
                self._items = []
        return self._items

    def save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._items, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.exception("Error guardando %s: %s", self, e)  # noqa: TRY401

    def get_all(self):
        return self._items

    def add(self, item, unique_key=None):
        if unique_key:
            for existing in self._items:
                if isinstance(existing, dict) and existing.get(unique_key) == item.get(unique_key):
                    return False
        self._items.append(item)
        self.save()
        return True

    def remove(self, index):
        if 0 <= index < len(self._items):
            self._items.pop(index)
            self.save()
            return True
        return False

    def update(self, index, item):
        if 0 <= index < len(self._items):
            self._items[index] = item
            self.save()
            return True
        return False

    def move_up(self, index):
        if index > 0:
            self._items[index], self._items[index - 1] = self._items[index - 1], self._items[index]
            self.save()
            return True
        return False

    def move_down(self, index):
        if index < len(self._items) - 1:
            self._items[index], self._items[index + 1] = self._items[index + 1], self._items[index]
            self.save()
            return True
        return False

    def set_items(self, items):
        self._items = items
        self.save()
