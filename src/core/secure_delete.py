"""
Módulo de borrado seguro con detección SSD/HDD
Versión 1.5 - JMComander
"""

import logging
import os
import platform
import subprocess
from collections.abc import Callable

logger = logging.getLogger(__name__)


class SecureDelete:
    """Manejador de borrado seguro con detección de tipo de disco"""

    @staticmethod
    def is_ssd(path: str) -> bool:
        """
        Detecta si la ruta está en un SSD (Windows).
        """
        if platform.system() != "Windows":
            return False  # Por defecto asumir HDD en Linux/Mac

        try:
            drive = os.path.splitdrive(path)[0].upper()

            # Configurar para ocultar ventana de consola en Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE

            # Usar PowerShell para detectar tipo de disco
            try:
                ps_command = (
                    "Get-PhysicalDisk"
                    f" | Where-Object {{$_.DeviceID -eq"
                    f" (Get-Partition -DriveLetter '{drive[0]}').DiskNumber}}"
                    " | Select-Object -ExpandProperty MediaType"
                )
                result = subprocess.run(  # noqa: PLW1510
                    ["powershell", "-WindowStyle", "Hidden", "-Command", ps_command],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    startupinfo=startupinfo,
                )
                if "SSD" in result.stdout.upper():
                    return True
            except Exception as _e:  # noqa: BLE001
                pass

            # Método alternativo: verificar si es disco duro vs SSD
            try:
                ps_command2 = (
                    "(Get-WmiObject -Class Win32_DiskDrive"
                    " | Where-Object {{$_.Index -eq"
                    " (Get-WmiObject -Class Win32_LogicalDisk"
                    f" | Where-Object {{$_.DeviceID -eq '{drive}'}}}}"
                    ").VolumeSerialNumber}}).Model"
                )
                result2 = subprocess.run(  # noqa: PLW1510
                    ["powershell", "-WindowStyle", "Hidden", "-Command", ps_command2],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    startupinfo=startupinfo,
                )
                model = result2.stdout.strip()
                if "SSD" in model.upper() or "SOLID" in model.upper():
                    return True
            except Exception as _e:  # noqa: BLE001
                pass

            return False  # noqa: TRY300

        except Exception as _e:  # noqa: BLE001
            # Si no podemos detectar, asumir HDD por seguridad
            return False

    @staticmethod
    def overwrite_file_hdd(
        filepath: str, passes: int = 3, progress_callback: Callable | None = None
    ) -> bool:
        """
        Sobrescribe archivo en HDD con múltiples pasadas.
        Patrones: Ceros, Unos, Aleatorio
        """
        try:
            file_size = os.path.getsize(filepath)

            patterns = [
                b"\x00" * 4096,  # Ceros
                b"\xff" * 4096,  # Unos
                os.urandom(4096),  # Aleatorio
            ]

            with open(filepath, "r+b", buffering=0) as f:
                for pass_num in range(passes):
                    pattern = patterns[min(pass_num, len(patterns) - 1)]
                    pattern_len = len(pattern)

                    bytes_written = 0
                    f.seek(0)

                    while bytes_written < file_size:
                        chunk_size = min(pattern_len, file_size - bytes_written)
                        f.write(pattern[:chunk_size])
                        bytes_written += chunk_size

                        # Reportar progreso
                        if progress_callback:
                            progress = (pass_num * file_size + bytes_written) / (passes * file_size)
                            progress_callback(progress)

                    # Forzar escritura a disco
                    f.flush()
                    os.fsync(f.fileno())

            return True  # noqa: TRY300

        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error sobrescribiendo archivo: {e}")  # noqa: G004
            return False

    @classmethod
    def delete(
        cls,
        path: str,
        method: str = "auto",
        passes: int = 3,
        progress_callback: Callable | None = None,
    ) -> bool:
        """
        Borrado seguro principal.

        Args:
            path: Ruta al archivo/directorio
            method: "auto", "hdd", "ssd", "quick"
            passes: Número de pasadas (solo HDD)
            progress_callback: Función para reportar progreso (0-1)
        """
        try:
            # Determinar método
            if method == "auto":
                is_ssd = cls.is_ssd(path)
                method = "ssd" if is_ssd else "hdd"

            # Si es directorio, procesar recursivamente
            if os.path.isdir(path):
                success = True
                items = list(os.scandir(path))
                total_items = len(items)

                for i, entry in enumerate(items):
                    # Reportar progreso del directorio
                    if progress_callback and total_items > 0:
                        dir_progress = i / total_items
                        progress_callback(dir_progress * 0.9)

                    if entry.is_dir(follow_symlinks=False):
                        success = cls.delete(entry.path, method, passes, None) and success
                    else:
                        success = cls._delete_file(entry.path, method, passes, None) and success

                # Eliminar directorio vacío
                if success:
                    os.rmdir(path)

                if progress_callback:
                    progress_callback(1.0)

                return success

            return cls._delete_file(path, method, passes, progress_callback)

        except Exception as e:
            logger.debug(f"Error en borrado seguro: {e}")  # noqa: G004
            logger.error(
                f"[SecureDelete] Fallo en delete({path},"
                f" method={method}): {e}",
                exc_info=True,
            )
            return False

    @classmethod
    def _delete_file(
        cls, filepath: str, method: str, passes: int, progress_callback: Callable | None
    ) -> bool:
        """Borrado seguro para un solo archivo"""

        if method == "quick":
            # Solo eliminar (para archivos no confidenciales en SSD)
            os.remove(filepath)
            return True

        if method == "hdd":
            # Sobrescribir + eliminar
            success = cls.overwrite_file_hdd(filepath, passes, progress_callback)
            if success:
                os.remove(filepath)
            return success

        if method == "ssd":
            # En SSDs modernos, sobrescribir no es efectivo por wear-leveling
            # La mejor práctica es cifrar + eliminar
            try:
                with open(filepath, "r+b") as f:
                    data = f.read()
                    # Sobrescribir con aleatorio (aunque no sea perfecto en SSD)
                    f.seek(0)
                    f.write(os.urandom(len(data)))
                os.remove(filepath)
                return True  # noqa: TRY300
            except Exception as e:
                logger.error(
                    f"[SecureDelete] Error en borrado SSD"
                    f" ({filepath}): {e}",
                    exc_info=True,
                )
                return False

        else:
            raise ValueError(f"Método desconocido: {method}")  # noqa: EM102, TRY003
