import logging
import os
import shutil
import threading
import time

from PySide6.QtCore import QObject, QRunnable, Signal

from src.core.fs_utils import copytree_with_progress, get_tree_size

from .fs_utils import send_to_trash
from .secure_delete import SecureDelete

logger = logging.getLogger(__name__)


class JobSignals(QObject):
    progress = Signal(str, int)
    started = Signal(str)
    finished = Signal()
    error = Signal(str)
    cancelled = Signal()
    conflict = Signal(object, str, str, int, int)
    file_started = Signal(str, int, int)
    file_finished = Signal(str, bool)
    # qint64: PySide6 Signal(int) és int de C++ 32-bit — overflow amb fitxers >2GB
    total_size = Signal("qint64")


class BaseJob(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = JobSignals()
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True
        self.signals.cancelled.emit()

    def _emit_progress(self, text, percent):
        self.signals.progress.emit(text, percent)

    def _emit_progress_for_item(self, action, filename, i, total):
        percent = int(((i + 1) * 100) / total) if total > 0 else 0
        self._emit_progress(f"{action}: {filename} ({i + 1}/{total})...", percent)

    def _check_cancelled(self):
        if self.is_cancelled:
            self.signals.cancelled.emit()
            return True
        return False

    def _finish_or_cancel(self, action="Completado"):
        if not self.is_cancelled:
            self._emit_progress(action, 100)
            self.signals.finished.emit()
        else:
            self.signals.cancelled.emit()


class ConflictMixin:
    def _init_conflict(self):
        self._conflict_event = threading.Event()
        self._conflict_decision = None
        self._apply_all_decision = None

    def resolve_conflict(self, action, apply_all):
        self._conflict_decision = (action, apply_all)
        if apply_all:
            self._apply_all_decision = action
        self._conflict_event.set()

    def get_unique_dst(self, dst):
        if not os.path.exists(dst):
            return dst
        base, ext = os.path.splitext(dst)
        i = 1
        while os.path.exists(f"{base} ({i}){ext}"):
            i += 1
        return f"{base} ({i}){ext}"

    def _apply_action_to_conflict(self, action, src, dst):  # noqa: PLR0912
        if action == "skip":
            return False, dst
        if action == "rename":
            return True, self.get_unique_dst(dst)
        if action == "overwrite":
            return True, dst
        if action == "overwrite_if_newer":
            if os.path.isdir(src) and os.path.isdir(dst):
                return True, dst
            if (
                os.path.exists(src)
                and os.path.exists(dst)
                and os.path.getmtime(src) > os.path.getmtime(dst)
            ):
                return True, dst
            return False, dst
        if action == "overwrite_if_older":
            if os.path.isdir(src) and os.path.isdir(dst):
                return True, dst
            if (
                os.path.exists(src)
                and os.path.exists(dst)
                and os.path.getmtime(src) < os.path.getmtime(dst)
            ):
                return True, dst
            return False, dst
        if action == "skip_if_newer":
            if os.path.isdir(src) and os.path.isdir(dst):
                return True, dst
            if (
                os.path.exists(src)
                and os.path.exists(dst)
                and os.path.getmtime(src) > os.path.getmtime(dst)
            ):
                return False, dst
            return True, dst
        if action == "cancel":
            self.is_cancelled = True
            return False, dst
        return False, dst

    def check_conflicts(self, src, dst, index, total):
        if not os.path.exists(dst):
            return True, dst

        if self._apply_all_decision:
            return self._apply_action_to_conflict(self._apply_all_decision, src, dst)

        self._conflict_event.clear()
        self._conflict_decision = None
        self.signals.conflict.emit(self, src, dst, index, total)

        while not self._conflict_event.wait(timeout=0.1):
            if self.is_cancelled:
                return False, dst

        if self.is_cancelled:
            return False, dst

        action, apply_all = self._conflict_decision or ("skip", False)

        if apply_all:
            self._apply_all_decision = action

        return self._apply_action_to_conflict(action, src, dst)


class CopyJob(BaseJob, ConflictMixin):
    def __init__(self, src_list, dst_folder):
        BaseJob.__init__(self)
        ConflictMixin._init_conflict(self)  # noqa: SLF001
        self.src_list = src_list
        self.dst_folder = dst_folder
        # Src copiats amb èxit — MoveJob només esborra els originals d'aquesta llista
        self.copied_ok = []

    def cancel(self):
        self.is_cancelled = True
        self._conflict_event.set()
        self.signals.cancelled.emit()

    def run(self):  # noqa: PLR0912
        total = len(self.src_list)
        if total == 0:
            self.signals.finished.emit()
            return

        self._emit_progress("Calculando tamaño total...", 0)
        sizes = []

        def cancel_check():
            return self.is_cancelled

        for i, src in enumerate(self.src_list):
            if self._check_cancelled():
                return

            progress_percent = int((i / total) * 100) if total > 0 else 0
            self._emit_progress(f"Calculando tamaño: {os.path.basename(src)}", progress_percent)

            try:
                size = get_tree_size(src, cancel_flag=cancel_check)
                sizes.append(size)
            except Exception as e:  # noqa: BLE001
                logger.warning("[CopyJob] Cannot get tree size of %s: %s", src, e)
                sizes.append(0)

        total_size = sum(sizes) if sizes else 1
        logger.info("[CopyJob] Total size to copy: %s bytes", total_size)
        self.signals.total_size.emit(total_size)

        if self._check_cancelled():
            return

        completed_size = 0

        for i, src in enumerate(self.src_list):
            if self._check_cancelled():
                return

            filename = os.path.basename(src)
            raw_dst = os.path.join(self.dst_folder, filename)
            dst = self.get_unique_dst(raw_dst)

            start_progress = int((completed_size / total_size) * 100) if total_size > 0 else 0
            self._emit_progress(f"Copiando {filename} ({i + 1}/{total})...", start_progress)
            self.signals.file_started.emit(filename, i + 1, total)

            proceed, dst = self.check_conflicts(src, raw_dst, i, total)

            if self._check_cancelled():
                return

            if not proceed:
                logger.warning("[CopyJob] NOT proceeding with copy: src=%s, dst=%s", src, dst)
                self.signals.file_finished.emit(filename, False)
                continue

            dst_existed_before = os.path.exists(dst)

            try:
                if os.path.isdir(src):
                    last_percent = [-1]
                    last_emit_time = [0.0]
                    progress_lock = threading.Lock()
                    base_completed = completed_size

                    def progress_callback(total_copied):
                        with progress_lock:  # noqa: B023
                            if total_size > 0:
                                global_percent = (
                                    int(((base_completed + total_copied) / total_size) * 100)  # noqa: B023
                                    if total_size > 0
                                    else 100
                                )
                            else:
                                # USB lent (timeout a get_tree_size): progrés estable per temps
                                now = time.monotonic()
                                if now - last_emit_time[0] >= 0.5:  # noqa: B023
                                    last_emit_time[0] = now  # noqa: B023
                                    global_percent = last_percent[0] + 1  # noqa: B023
                                else:
                                    global_percent = last_percent[0]  # noqa: B023
                            if global_percent != last_percent[0] and 0 <= global_percent <= 100:  # noqa: B023
                                last_percent[0] = min(global_percent, 99)  # noqa: B023
                                current_file = os.path.join(filename, "...")  # noqa: B023
                                self._emit_progress(
                                    f"Copiant {current_file} ({global_percent}%)", global_percent
                                )

                    def cancel_check():
                        return self.is_cancelled

                    success, bytes_copied = copytree_with_progress(
                        src,
                        dst,
                        progress_callback=progress_callback,
                        cancel_flag=cancel_check,
                        action=self._apply_all_decision,
                        dirs_exist_ok=True,
                    )

                    logger.info(
                        f"[CopyJob] After directory copy,"
                        f" success={success}, bytes_copied={bytes_copied}"
                    )

                    completed_size += bytes_copied

                    if not success:
                        if not dst_existed_before and os.path.exists(dst):
                            shutil.rmtree(dst)
                        self.signals.cancelled.emit()
                        return

                    self.copied_ok.append(src)
                    self.signals.file_finished.emit(filename, True)
                else:
                    size = os.path.getsize(src)

                    if size == 0:
                        open(dst, "wb").close()
                        if self._check_cancelled():
                            if not dst_existed_before and os.path.exists(dst):
                                os.remove(dst)
                            self.signals.cancelled.emit()
                            return
                        self.copied_ok.append(src)
                        self.signals.file_finished.emit(filename, True)
                    else:
                        fsrc = None
                        fdst = None
                        try:
                            fsrc = open(src, "rb")
                            fdst = open(dst, "wb")
                            # Pre-allocar espai NOMÉS per fitxers petits (a grans, truncate
                            # escriu zeros i bloqueja la còpia durant minuts)
                            if size <= 64 * 1024 * 1024:  # 64MB
                                try:
                                    fdst.truncate(size)
                                except OSError:
                                    pass  # FS sense suport de truncate previ
                            copied = 0
                            buffer_size = 4 * 1024 * 1024  # 4MB buffer (consistent amb fs_utils)
                            last_emit_percent = -1
                            while True:
                                if self.is_cancelled:
                                    break
                                buf = fsrc.read(buffer_size)
                                if not buf:
                                    break
                                fdst.write(buf)
                                copied += len(buf)
                                percent = int((copied / size) * 100) if size > 0 else 100
                                if percent != last_emit_percent:
                                    global_copied = completed_size + copied
                                    total_percent = (
                                            int((global_copied / total_size) * 100)
                                            if total_size > 0
                                            else int(((i + 1) * 100) / total)
                                        )
                                    self._emit_progress(
                                        f"Copiando {filename} ({percent}%) [{i + 1}/{total}]",
                                        total_percent,
                                    )
                                    last_emit_percent = percent

                            if self.is_cancelled:
                                if not dst_existed_before and os.path.exists(dst):
                                    os.remove(dst)
                                self.signals.cancelled.emit()
                                return

                            shutil.copystat(src, dst)
                            completed_size += sizes[i]
                            self.copied_ok.append(src)
                            self.signals.file_finished.emit(filename, True)
                        finally:
                            if fdst:
                                fdst.close()
                            if fsrc:
                                fsrc.close()

            except Exception as e:  # noqa: BLE001
                try:
                    if not dst_existed_before:
                        if os.path.isfile(dst) and os.path.exists(dst):
                            os.remove(dst)
                        elif os.path.isdir(dst) and os.path.exists(dst):
                            shutil.rmtree(dst)
                except Exception:  # noqa: BLE001
                    pass

                if not self.is_cancelled:
                    self.signals.error.emit(f"Error copiando {src}: {e}")
                self.signals.file_finished.emit(filename, False)

            end_progress = int((completed_size / total_size) * 100) if total_size > 0 else 0
            self._emit_progress(f"Copiando {filename} ({i + 1}/{total})...", min(end_progress, 100))

        self._finish_or_cancel()


class MoveJob(BaseJob, ConflictMixin):
    def __init__(self, src_list, dst_folder):
        BaseJob.__init__(self)
        ConflictMixin._init_conflict(self)  # noqa: SLF001
        self.src_list = src_list
        self.dst_folder = dst_folder
        self._copy_job = None

    def cancel(self):
        self.is_cancelled = True
        self._conflict_event.set()
        # Propagar la cancel·lació al CopyJob intern (si està actiu)
        if self._copy_job is not None:
            self._copy_job.cancel()
        self.signals.cancelled.emit()

    def run(self):
        total = len(self.src_list)
        if total == 0:
            self.signals.finished.emit()
            return

        self._emit_progress("Calculando tamaño total...", 0)
        sizes = []

        def cancel_check():
            return self.is_cancelled

        for i, src in enumerate(self.src_list):
            if self._check_cancelled():
                return
            progress_percent = int((i / total) * 100) if total > 0 else 0
            self._emit_progress(f"Calculando tamaño: {os.path.basename(src)}", progress_percent)
            try:
                size = get_tree_size(src, cancel_flag=cancel_check)
                sizes.append(size)
            except Exception:  # noqa: BLE001
                sizes.append(0)

        total_size = sum(sizes) if sizes else 1
        self.signals.total_size.emit(total_size)

        # Reutilitzar CopyJob: còpia amb progrés, cancel·lació i paral·lelisme
        # (shutil.move entre unitats faria la còpia a cegues, sense progrés ni cancel)
        copy_job = CopyJob(self.src_list, self.dst_folder)
        self._copy_job = copy_job
        copy_job._apply_all_decision = self._apply_all_decision  # noqa: SLF001
        copy_job.signals.progress.connect(self.signals.progress.emit)
        copy_job.signals.total_size.connect(self.signals.total_size.emit)
        copy_job.signals.file_started.connect(self.signals.file_started.emit)
        copy_job.signals.file_finished.connect(self.signals.file_finished.emit)
        copy_job.signals.error.connect(self.signals.error.emit)
        copy_job.signals.cancelled.connect(self.signals.cancelled.emit)
        # CRÍTIC: reemetre conflictes a través del MoveJob perquè l'engine els resolgui
        # (sense això, un destí existent penjaria la còpia esperant una decisió que mai arriba)
        copy_job.signals.conflict.connect(self.signals.conflict.emit)
        copy_job.run()

        if self.is_cancelled or copy_job.is_cancelled:
            return

        # Eliminar originals NOMÉS dels ítems copiats amb èxit.
        # Un "Ometre" al conflicte o un error de còpia NO ha d'esborrar l'original.
        for src in self.src_list:
            if src not in copy_job.copied_ok:
                continue
            if not os.path.exists(src):
                continue
            try:
                if os.path.isdir(src):
                    shutil.rmtree(src)
                else:
                    os.remove(src)
            except Exception as e:
                logger.warning(f"[MoveJob] No se pudo eliminar original {src}: {e}")  # noqa: G004

        self._finish_or_cancel()


class DeleteJob(BaseJob):
    def __init__(self, src_list, permanent=False):
        super().__init__()
        self.src_list = src_list
        self.permanent = permanent

    def _safe_remove(self, path):
        if self.is_cancelled:
            return False
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return True  # noqa: TRY300
        except Exception as e:
            logger.error(f"[SafeRemove] Error al eliminar {path}: {e}", exc_info=True)
            return False

    def run(self):
        total = len(self.src_list)
        if total == 0:
            self.signals.finished.emit()
            return

        for i, src in enumerate(self.src_list):
            if self._check_cancelled():
                return

            if not os.path.exists(src):
                continue

            filename = os.path.basename(src)
            action = "Eliminando" if self.permanent else "Moviendo a papelera"
            start_progress = int((i * 100) / total) if total > 0 else 0
            self._emit_progress(f"{action}: {filename} ({i + 1}/{total})...", start_progress)
            self.signals.file_started.emit(filename, i + 1, total)

            try:
                success = False
                if self.permanent:
                    success = self._safe_remove(src)
                    if not success:
                        self.signals.error.emit(f"No se pudo eliminar: {filename}")
                else:
                    success = send_to_trash(src)
                    if not success:
                        # NO escalar a borrado permanente: solo informar del error
                        self.signals.error.emit(f"No se pudo mover a papelera: {filename}")

                self.signals.file_finished.emit(filename, success)
            except Exception as e:  # noqa: BLE001
                self.signals.error.emit(f"Error: {e}")
                self.signals.file_finished.emit(filename, False)

            self._emit_progress_for_item(action, filename, i, total)

        self._finish_or_cancel()


class SecureDeleteJob(BaseJob):
    def __init__(self, src_list, secure_params):
        super().__init__()
        self.src_list = src_list
        self.secure_params = secure_params

    def run(self):
        logger.info(
            f"[SecureDeleteJob] Iniciando borrado seguro de"
            f" {len(self.src_list)} elementos,"
            f" method={self.secure_params.get('method')}"
        )
        try:
            total = len(self.src_list)
            if total == 0:
                self.signals.finished.emit()
                return

            method = self.secure_params.get("method", "auto")
            passes = self.secure_params.get("passes", 3)

            for i, src in enumerate(self.src_list):
                if self._check_cancelled():
                    return

                filename = os.path.basename(src)
                start_progress = int((i * 100) / total) if total > 0 else 0
                self._emit_progress(
                    f"Borrado seguro: {filename} ({i + 1}/{total})...", start_progress
                )
                self.signals.file_started.emit(filename, i + 1, total)

                try:

                    def progress_callback(p):
                        overall = int(((i + p) / total) * 100)  # noqa: B023
                        self._emit_progress(f"Borrando {filename}...", overall)  # noqa: B023

                    success = SecureDelete.delete(
                        src, method=method, passes=passes, progress_callback=progress_callback
                    )

                    if success:
                        self.signals.file_finished.emit(filename, True)
                    else:
                        self.signals.error.emit(f"Error en borrado seguro de {src}")
                        self.signals.file_finished.emit(filename, False)

                except Exception as e:  # noqa: BLE001
                    if not self.is_cancelled:
                        self.signals.error.emit(f"Error borrando {src}: {e}")
                    self.signals.file_finished.emit(filename, False)

            self._finish_or_cancel()
        except Exception as e:
            logger.error(f"[SecureDeleteJob] Excepción no capturada: {e}", exc_info=True)
            raise
