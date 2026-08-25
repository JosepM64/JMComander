import logging

logger = logging.getLogger(__name__)


class PathHistory:
    MAX_HISTORY = 50

    def __init__(self):
        self._history = []
        self._index = -1
        self._navigating = False

    @property
    def current(self):
        if 0 <= self._index < len(self._history):
            return self._history[self._index]
        return None

    def push(self, path):
        if self._navigating:
            return
        if self._history and self._history[self._index] == path:
            return
        self._history = self._history[: self._index + 1]
        self._history.append(path)
        if len(self._history) > self.MAX_HISTORY:
            self._history.pop(0)
        else:
            self._index += 1
        while len(self._history) > self.MAX_HISTORY:
            self._history.pop(0)
            self._index -= 1

    def back(self):
        if self._index > 0:
            self._index -= 1
            return self.current
        return None

    def forward(self):
        if self._index < len(self._history) - 1:
            self._index += 1
            return self.current
        return None

    @property
    def can_back(self):
        return self._index > 0

    @property
    def can_forward(self):
        return self._index < len(self._history) - 1

    def set_navigating(self, value):
        self._navigating = value
