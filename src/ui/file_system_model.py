import datetime as _DT
import logging
import os
import re

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt

from src.core.file_constants import get_extension, get_file_category, get_file_type_display

logger = logging.getLogger(__name__)


def natural_sort_key(s):
    if not isinstance(s, str):
        s = str(s)
    return [int(chunk) if chunk.isdigit() else chunk.lower() for chunk in re.split(r"(\d+)", s)]


from PySide6.QtWidgets import QFileSystemModel  # noqa: E402


class ExtendedFileSystemModel(QFileSystemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._columns = ["Nombre", "Ext", "Tamaño", "Tipo", "Fecha", "Hora"]
        self._size_cache = {}
        self._mtime_cache = {}
        self.directoryLoaded.connect(self._on_directory_loaded)

    def _on_directory_loaded(self, path):
        self._size_cache.clear()
        self._mtime_cache.clear()

    def columnCount(self, _parent=QModelIndex()):  # noqa: N802
        return 6

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if role == Qt.ItemDataRole.DisplayRole and section < len(self._columns):
            return self._columns[section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):  # noqa: PLR0912
        if not index.isValid():
            return None

        column = index.column()
        file_path = self.filePath(index)

        if role == Qt.ItemDataRole.UserRole:
            if column == 0 and file_path:
                try:
                    name = os.path.basename(file_path)
                    if not os.path.isdir(file_path) and "." in name:
                        base, ext = os.path.splitext(name)
                        ext_clean = ext[1:] if ext else ""
                        if name.count(".") > 1 or (2 <= len(ext_clean) <= 4):
                            name = base
                    return name.lower()
                except Exception:  # noqa: BLE001
                    return ""
            if column == 1 and file_path:
                try:
                    return get_extension(file_path).lower()
                except Exception:  # noqa: BLE001
                    return ""
            if column == 2 and file_path:
                try:
                    if file_path not in self._size_cache:
                        self._size_cache[file_path] = os.path.getsize(file_path)
                    return self._size_cache[file_path]
                except Exception:  # noqa: BLE001
                    return 0
            if column == 3 and file_path:
                if os.path.isdir(file_path):
                    return "Dir"
                return get_file_type_display(file_path)
            if column in (4, 5) and file_path:
                try:
                    if file_path not in self._mtime_cache:
                        self._mtime_cache[file_path] = os.path.getmtime(file_path)
                    return self._mtime_cache[file_path]
                except Exception:  # noqa: BLE001
                    return 0

        if column == 0:
            if role == Qt.ItemDataRole.DisplayRole:
                file_path = self.filePath(index)
                if file_path:
                    name = os.path.basename(file_path)
                    if not os.path.isdir(file_path) and "." in name:
                        base, ext = os.path.splitext(name)
                        ext_clean = ext[1:] if ext else ""
                        if name.count(".") > 1 or (2 <= len(ext_clean) <= 4):
                            name = base
                    return name
            return super().data(index, role)

        if column == 1:
            if role == Qt.ItemDataRole.DisplayRole:
                file_path = self.filePath(index)
                if file_path:
                    return get_extension(file_path)
                return ""
            return super().data(index, role)

        if column == 2:
            source_column = column - 1
            source_index = self.index(index.row(), source_column, index.parent())
            return super().data(source_index, role)

        if column == 3:
            if role == Qt.ItemDataRole.DisplayRole:
                file_path = self.filePath(index)
                if file_path:
                    if os.path.isdir(file_path):
                        return "Dir"
                    return get_file_type_display(file_path)
                return ""
            return super().data(index, role)

        if column == 4:
            if role == Qt.ItemDataRole.DisplayRole:
                file_path = self.filePath(index)
                if file_path:
                    try:
                        mtime = self._get_mtime_cached(file_path)
                        if mtime:
                            dt = _DT.datetime.fromtimestamp(mtime, tz=_DT.UTC)
                            return dt.strftime("%d/%m/%Y")
                    except Exception:  # noqa: BLE001
                        pass
                return ""
            return super().data(index, role)

        if column == 5:
            if role == Qt.ItemDataRole.DisplayRole:
                file_path = self.filePath(index)
                if file_path:
                    try:
                        mtime = self._get_mtime_cached(file_path)
                        if mtime:
                            dt = _DT.datetime.fromtimestamp(mtime, tz=_DT.UTC)
                            return dt.strftime("%H:%M")
                    except Exception:  # noqa: BLE001
                        pass
                return ""
            return super().data(index, role)

        return super().data(index, role)

    def _get_mtime_cached(self, file_path):
        """mtime des de la caché — un stat() per fitxer i directori carregat,
        no un per cada repintat de cel·la."""
        if file_path not in self._mtime_cache:
            self._mtime_cache[file_path] = os.path.getmtime(file_path)
        return self._mtime_cache[file_path]


class FileSystemProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.folders_only = False
        self.current_root_source_index = None
        self._timestamp_cache = {}
        self._cache_valid = False
        self._extension_filter = None

    def columnCount(self, _parent=QModelIndex()):  # noqa: N802
        return 6

    def lessThan(self, left, right):  # noqa: N802, PLR0912
        source_model = self.sourceModel()
        if not source_model:
            return super().lessThan(left, right)

        if left.model() != self or right.model() != self:
            return super().lessThan(left, right)

        left_source = self.mapToSource(left)
        right_source = self.mapToSource(right)

        if not left_source.isValid() or not right_source.isValid():
            return super().lessThan(left, right)

        col = self.sortColumn()
        sort_order = self.sortOrder()

        left_is_dir = source_model.isDir(left_source)
        right_is_dir = source_model.isDir(right_source)

        if left_is_dir != right_is_dir:
            return not left_is_dir and right_is_dir

        try:
            left_data = source_model.data(left_source, Qt.ItemDataRole.UserRole)
            right_data = source_model.data(right_source, Qt.ItemDataRole.UserRole)

            if left_data is not None and right_data is not None:
                if col in (2, 4, 5):
                    if sort_order == Qt.SortOrder.AscendingOrder:
                        return left_data < right_data
                    return left_data > right_data
                left_str = str(left_data).lower()
                right_str = str(right_data).lower()
                if sort_order == Qt.SortOrder.AscendingOrder:
                    return left_str < right_str
                return left_str > right_str

            if col == 2:
                left_size = source_model.size(left_source)
                right_size = source_model.size(right_source)
                if sort_order == Qt.SortOrder.AscendingOrder:
                    return left_size < right_size
                return left_size > right_size

            if col == 4 or col == 5:  # noqa: PLR1714
                left_path = source_model.filePath(left_source)
                right_path = source_model.filePath(right_source)
                try:
                    if left_path not in self._timestamp_cache:
                        self._timestamp_cache[left_path] = os.path.getmtime(left_path)
                    if right_path not in self._timestamp_cache:
                        self._timestamp_cache[right_path] = os.path.getmtime(right_path)
                    left_ts = self._timestamp_cache[left_path]
                    right_ts = self._timestamp_cache[right_path]
                    if sort_order == Qt.SortOrder.AscendingOrder:
                        return left_ts < right_ts
                    return left_ts > right_ts  # noqa: TRY300
                except Exception:  # noqa: BLE001
                    return super().lessThan(left, right)

            if col == 0:
                left_name = source_model.fileName(left_source) or ""
                right_name = source_model.fileName(right_source) or ""
                if not left_name and not right_name:
                    return False
                if not left_name:
                    return True
                if not right_name:
                    return False
                left_key = natural_sort_key(left_name)
                right_key = natural_sort_key(right_name)
                if left_key != right_key:
                    if sort_order == Qt.SortOrder.AscendingOrder:
                        return left_key < right_key
                    return left_key > right_key
                return left_name.lower() < right_name.lower()

            if col == 1:
                left_path = source_model.filePath(left_source) or ""
                right_path = source_model.filePath(right_source) or ""
                if not left_path and not right_path:
                    return False
                if not left_path:
                    return True
                if not right_path:
                    return False
                left_ext = get_extension(left_path).lower()
                right_ext = get_extension(right_path).lower()
                if left_ext != right_ext:
                    if sort_order == Qt.SortOrder.AscendingOrder:
                        return left_ext < right_ext
                    return left_ext > right_ext
                if sort_order == Qt.SortOrder.AscendingOrder:
                    return left_path.lower() < right_path.lower()
                return left_path.lower() > right_path.lower()

            if col == 3:
                left_name = source_model.fileName(left_source) or ""
                right_name = source_model.fileName(right_source) or ""
                left_type = get_file_category(left_name)
                right_type = get_file_category(right_name)
                if left_type != right_type:
                    if sort_order == Qt.SortOrder.AscendingOrder:
                        return left_type < right_type
                    return left_type > right_type
                left_key = natural_sort_key(left_name)
                right_key = natural_sort_key(right_name)
                if sort_order == Qt.SortOrder.AscendingOrder:
                    return left_key < right_key
                return left_key > right_key
        except Exception as e:  # noqa: BLE001
            logger.debug("lessThan error: %s", e)

        return super().lessThan(left, right)

    def _is_descendant_of(self, index, ancestor):
        if not index.isValid() or not ancestor.isValid():
            logger.debug("_is_descendant_of: invalid index or ancestor")
            return False

        if index == ancestor:
            logger.debug("_is_descendant_of: index equals ancestor")
            return True

        current = index
        source_model = self.sourceModel()
        while current.isValid():
            current = current.parent()
            if current == ancestor:
                if source_model and hasattr(source_model, "filePath"):
                    index_path = source_model.filePath(index) if index.isValid() else "invalid"
                    ancestor_path = (
                        source_model.filePath(ancestor) if ancestor.isValid() else "invalid"
                    )
                    current_path = (
                        source_model.filePath(current) if current.isValid() else "invalid"
                    )
                    logger.debug(
                        f"_is_descendant_of: FOUND descendant:"
                        f" index='{index_path}',"
                        f" ancestor='{ancestor_path}',"
                        f" current parent='{current_path}'"
                    )
                return True

        if source_model and hasattr(source_model, "filePath"):
            index_path = source_model.filePath(index) if index.isValid() else "invalid"
            ancestor_path = source_model.filePath(ancestor) if ancestor.isValid() else "invalid"
            logger.debug(
                f"_is_descendant_of: NOT descendant:"
                f" index='{index_path}', ancestor='{ancestor_path}'"
            )
        return False

    def filterAcceptsRow(self, source_row, source_parent):  # noqa: N802, PLR0912
        source_model = self.sourceModel()
        if not source_model:
            return super().filterAcceptsRow(source_row, source_parent)

        child_idx = source_model.index(source_row, 0, source_parent)
        child_name = source_model.data(child_idx)

        if (
            self.current_root_source_index
            and self.current_root_source_index.isValid()
            and child_idx.isValid()
        ):
            if child_idx == self.current_root_source_index:
                return True
            if hasattr(source_model, "filePath"):
                child_path = source_model.filePath(child_idx)
                root_path = source_model.filePath(self.current_root_source_index)
                if child_path == root_path:
                    return True

        has_filter = (
            self.filterRegularExpression().isValid() and self.filterRegularExpression().pattern()
        )

        if not self.current_root_source_index or not self.current_root_source_index.isValid():
            if has_filter:
                return super().filterAcceptsRow(source_row, source_parent)
            return True

        is_descendant = self._is_descendant_of(child_idx, self.current_root_source_index)
        is_ancestor = self._is_descendant_of(self.current_root_source_index, child_idx)
        is_current_root = child_idx == self.current_root_source_index
        is_child_of_current = is_descendant and (
            source_parent == self.current_root_source_index
            or (
                hasattr(source_model, "filePath")
                and source_model.filePath(source_parent)
                == source_model.filePath(self.current_root_source_index)
            )
        )

        if is_ancestor and not is_current_root:
            return True

        if not is_descendant and not is_ancestor and not is_current_root:
            return False

        if has_filter:
            if is_child_of_current:
                filter_result = super().filterAcceptsRow(source_row, source_parent)
                logger.debug(
                    f"filterAcceptsRow [CHILD FILTER]:"
                    f" row={source_row}, filename='{child_name}',"
                    f" match={filter_result}"
                )
                return filter_result
            if is_current_root:
                return True
            if is_descendant:
                return self._has_filtered_children(child_idx)

        if (
            self.folders_only
            and not is_current_root
            and hasattr(source_model, "isDir")
            and not source_model.isDir(child_idx)
        ):
            return False

        if (
            self._extension_filter
            and hasattr(source_model, "isDir")
            and not source_model.isDir(child_idx)
        ):
            child_path = (
                source_model.filePath(child_idx) if hasattr(source_model, "filePath") else ""
            )
            _, ext = os.path.splitext(child_path)
            if ext.lower() not in self._extension_filter:
                return False

        return True

    def _has_filtered_children(self, parent_idx):
        source_model = self.sourceModel()
        if not source_model or not parent_idx.isValid():
            return False

        for row in range(source_model.rowCount(parent_idx)):
            child_idx = source_model.index(row, 0, parent_idx)
            if not child_idx.isValid():
                continue

            if super().filterAcceptsRow(row, parent_idx):
                return True

            if self._has_filtered_children(child_idx):
                return True

        return False

    def set_current_root_source_index(self, source_index):
        self.current_root_source_index = source_index

    def set_extension_filter(self, extensions):
        self._extension_filter = extensions if extensions else None
        self.invalidateFilter()
        source_model = self.sourceModel()
        source_index = self.current_root_source_index
        if source_model and source_index and source_index.isValid():
            filepath = (
                source_model.filePath(source_index)
                if hasattr(source_model, "filePath")
                else "unknown"
            )
            logger.debug(
                f"ProxyModel: set_current_root_source_index:"
                f" path='{filepath}',"
                f" isValid={source_index.isValid()},"
                f" internalId={source_index.internalId()}"
            )
        else:
            logger.debug("ProxyModel: set_current_root_source_index: invalid")
        self.invalidateFilter()
