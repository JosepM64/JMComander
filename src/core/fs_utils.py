import ctypes
import logging
import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Mantener import para compatibilidad
import send2trash  # noqa: E402

ERROR_SHARING_VIOLATION = 32
ERROR_LOCK_VIOLATION = 33

OPTIMAL_BUFFER_SIZE = 4 * 1024 * 1024  # 4MB — millor rendiment a USB lent
PARALLEL_COPY_WORKERS = 2  # Fitxers per directori copiats en paral·lel

# Noms reservats Windows (+ .git que copytree ha de saltar) — font única a utils
from src.core.utils import WINDOWS_RESERVED_NAMES as _WIN_RESERVED  # noqa: E402

RESERVED_NAMES = set(_WIN_RESERVED) | {".git"}


def is_file_locked(path):
    """
    Verifica si un archivo o carpeta está en uso por otro proceso.
    Returns True si está bloqueado, False si se puede acceder.
    """
    if not os.path.exists(path):
        return False

    abs_path = os.path.abspath(path)

    if os.path.isdir(abs_path):
        return _is_dir_locked(abs_path)
    return _is_file_locked_windows(abs_path)


def _is_file_locked_windows(filepath):
    """Intenta abrir un archivo en modo exclusivo para verificar si está bloqueado."""
    try:
        handle = ctypes.windll.kernel32.CreateFileW(
            filepath,
            0x00000001,  # GENERIC_READ
            0,  # No sharing - wants exclusive access
            None,
            3,  # OPEN_EXISTING
            0x00000080,  # FILE_ATTRIBUTE_NORMAL
            None,
        )
        if handle in (-1, 0):
            error = ctypes.get_last_error()
            return error in (ERROR_SHARING_VIOLATION, ERROR_LOCK_VIOLATION)
        ctypes.windll.kernel32.CloseHandle(handle)
        return False
    except Exception:  # noqa: BLE001
        return False


def _is_dir_locked(dirpath):
    """Verifica si una carpeta está en uso por otro proceso."""
    try:
        test_file = os.path.join(dirpath, ".jmcomander_lock_test_" + str(os.getpid()))
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return False
    except (PermissionError, OSError):
        try:
            os.scandir(dirpath)
            return False
        except (PermissionError, OSError):
            return True


def get_locked_paths(paths):
    """Devuelve una lista de paths que están bloqueados/en uso."""
    return [path for path in paths if is_file_locked(path)]


def send_to_trash(path):
    """Envía archivos a la papelera. Si falla devuelve False — NUNCA escala
    a borrado permanente (destrucción irreversible sin consentimiento)."""
    abs_path = os.path.normpath(os.path.abspath(path))
    try:
        send2trash.send2trash(abs_path)
        return True  # noqa: TRY300
    except Exception as e:
        logger.warning("No se pudo mover a la papelera %s: %s", abs_path, e)
        return False


def safe_delete(path, use_trash=True):
    """Borrado robusto: Papelera vs Permanente"""
    abs_path = os.path.normpath(os.path.abspath(path))

    if use_trash:
        send_to_trash(abs_path)
    elif os.path.isdir(abs_path):
        shutil.rmtree(abs_path)
    else:
        os.remove(abs_path)


def should_overwrite_file(src_file, dst_file, action=None):
    """Determine if file should be overwritten based on action."""
    if action is None or action == "overwrite":
        return True

    if not os.path.exists(dst_file):
        return True

    try:
        src_mtime = os.path.getmtime(src_file)
        dst_mtime = os.path.getmtime(dst_file)

        if action == "overwrite_if_newer":
            return src_mtime > dst_mtime
        if action == "overwrite_if_older":
            return src_mtime < dst_mtime
        if action == "skip_if_newer":
            return src_mtime <= dst_mtime
    except OSError:
        pass

    return False


def copytree_with_progress(
    src, dst, progress_callback=None, cancel_flag=None, action=None, dirs_exist_ok=True
):
    """Copy directory with progress and cancellation support.
    Returns (success, bytes_copied).
    """
    logger.info(f"[copytree_with_progress] START: src={src}, dst={dst}, action={action}")

    if not os.path.exists(src):
        logger.error(f"[copytree_with_progress] Source does not exist: {src}")
        return False, 0

    try:
        os.makedirs(dst, exist_ok=True)
    except Exception as e:
        logger.exception(f"[copytree_with_progress] Error creating destination: {e}")
        return False, 0

    total_copied = 0
    files_copied = 0
    files_skipped = 0
    last_emit_bytes = 0  # throttle: només emet cada ~1MB copiat
    stats_lock = threading.Lock()
    cancelled_by_worker = False

    def _copy_single_file(src_file, dst_file):
        """Copia un fitxer i retorna bytes copiats, o None si s'ha cancel·lat."""
        nonlocal cancelled_by_worker, total_copied, last_emit_bytes, files_copied

        if cancel_flag and cancel_flag():
            cancelled_by_worker = True
            return None

        try:
            file_size = os.path.getsize(src_file)

            if file_size == 0:
                open(dst_file, "wb").close()
            else:
                with open(src_file, "rb") as fsrc, open(dst_file, "wb") as fdst:
                    # Pre-allocar espai NOMÉS per fitxers petits (a grans, truncate
                    # escriu zeros i bloqueja la còpia durant minuts)
                    if file_size <= 64 * 1024 * 1024:  # 64MB
                        try:
                            fdst.truncate(file_size)
                        except OSError:
                            pass  # FS sense suport de truncate previ
                    while True:
                        if cancel_flag and cancel_flag():
                            cancelled_by_worker = True
                            return None
                        buf = fsrc.read(OPTIMAL_BUFFER_SIZE)
                        if not buf:
                            break
                        fdst.write(buf)
                        with stats_lock:
                            total_copied += len(buf)
                            # Throttle callback: només cada ~1MB o al final del fitxer
                            if progress_callback and (total_copied - last_emit_bytes) >= (1024 * 1024):
                                progress_callback(total_copied)
                                last_emit_bytes = total_copied

            shutil.copystat(src_file, dst_file)
            with stats_lock:
                files_copied += 1
            return True

        except Exception as e:
            logger.warning(f"Error copying {src_file}: {e}")
            return False

    try:
        # Un sol executor per TOTA la còpia — crear/destruir un pool per
        # directori era overhead pur en arbres amb moltes carpetes
        with ThreadPoolExecutor(max_workers=PARALLEL_COPY_WORKERS) as executor:
            for root, dirs, files in os.walk(src):
                if cancel_flag and cancel_flag():
                    return False, total_copied

                if any(name in RESERVED_NAMES for name in root.split(os.sep)):
                    continue

                rel_root = os.path.relpath(root, src)
                dst_root = dst if rel_root == "." else os.path.join(dst, rel_root)

                os.makedirs(dst_root, exist_ok=True)

                for dir_name in dirs:
                    dst_dir = os.path.join(dst_root, dir_name)
                    os.makedirs(dst_dir, exist_ok=True)

                # Copiar fitxers del directori actual en paral·lel
                tasks = []
                for file_name in files:
                    if file_name in RESERVED_NAMES:
                        continue
                    src_file = os.path.join(root, file_name)
                    dst_file = os.path.join(dst_root, file_name)

                    if not should_overwrite_file(src_file, dst_file, action):
                        files_skipped += 1
                        continue

                    tasks.append((src_file, dst_file))

                if not tasks:
                    continue

                futures = {executor.submit(_copy_single_file, s, d): s for s, d in tasks}
                for future in as_completed(futures):
                    if cancel_flag and cancel_flag():
                        cancelled_by_worker = True
                        break
                    future.result()  # propaga excepcions
                    if progress_callback:
                        with stats_lock:
                            progress_callback(total_copied)
                            last_emit_bytes = total_copied

                if cancelled_by_worker:
                    return False, total_copied

        return True, total_copied

    except Exception as e:
        logger.exception(f"Error in copytree_with_progress: {e}")
        return False, total_copied


def get_tree_size(path, progress_callback=None, cancel_flag=None, timeout_s=1.5):
    """Calculate total size of a file or directory recursively (iterative, no recursion limit).
    Returns 0 if timeout_s is exceeded, to avoid blocking on slow drives."""
    import time
    start_time = time.monotonic()
    total = 0
    if os.path.isfile(path):
        try:
            total = os.path.getsize(path)
        except OSError:
            pass
    elif os.path.isdir(path):
        stack = [path]
        while stack:
            if time.monotonic() - start_time > timeout_s:
                return 0  # USB lent — saltar estimació
            if cancel_flag and cancel_flag():
                return 0
            current = stack.pop()
            try:
                with os.scandir(current) as it:
                    for entry in it:
                        if entry.is_file(follow_symlinks=False):
                            try:
                                total += entry.stat(follow_symlinks=False).st_size
                            except OSError:
                                pass
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
            except (PermissionError, OSError):
                pass
    return total
