import hashlib
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import py7zr
import rarfile

logger = logging.getLogger(__name__)


@dataclass
class MountInfo:
    archive_path: Path
    mount_point: Path
    created_at: float
    last_access: float
    size: int


class ArchiveHandler:
    def __init__(self, temp_base: Path | None = None):
        self.temp_base = temp_base or Path(tempfile.gettempdir()) / "JMComander"
        self.mounted_archives: dict[str, MountInfo] = {}
        self._ensure_temp_dir()
        self.RAR_EXE = self._find_rar_exe()
        self.SEVEN_ZIP_EXE = self._find_7z_exe()
        self._configure_rarfile()

    def _ensure_temp_dir(self):
        try:
            if not self.temp_base.exists():
                self.temp_base.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.exception("Error creando directorio temporal: %s", e)  # noqa: TRY401

    @staticmethod
    def _get_assets_path() -> Path:
        if getattr(sys, "frozen", False):
            base = Path(sys._MEIPASS)  # noqa: SLF001
            for candidate in [base / "assets", base / "src" / "assets"]:
                if candidate.exists():
                    return candidate
        return Path(__file__).parent.parent / "assets"

    def _find_rar_exe(self) -> str | None:
        locations = ["UnRAR.exe", "unrar", "RAR.exe"]
        for loc in locations:
            if shutil.which(loc):
                logger.info("Found RAR executable: %s", loc)
                return loc
        assets = self._get_assets_path()
        for loc in locations:
            exe_path = assets / loc
            if exe_path.exists():
                logger.info("Found RAR in assets: %s", exe_path)
                return str(exe_path)
        return None

    def _find_7z_exe(self) -> str | None:
        locations = ["7z.exe", "7za.exe"]
        for loc in locations:
            if shutil.which(loc):
                logger.info("Found 7-Zip: %s", loc)
                return loc
        pf = os.environ.get("ProgramFiles", "C:\\Program Files")  # noqa: SIM112
        for loc in locations:
            exe_path = Path(pf) / "7-Zip" / loc
            if exe_path.exists():
                logger.info("Found 7-Zip in Program Files: %s", exe_path)
                return str(exe_path)
        pf_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")  # noqa: SIM112
        for loc in locations:
            exe_path = Path(pf_x86) / "7-Zip" / loc
            if exe_path.exists():
                logger.info("Found 7-Zip in Program Files x86: %s", exe_path)
                return str(exe_path)
        assets = self._get_assets_path()
        for loc in locations:
            exe_path = assets / loc
            if exe_path.exists():
                logger.info("Found 7-Zip in assets: %s", exe_path)
                return str(exe_path)
        return None

    def _configure_rarfile(self):
        try:
            if sys.platform == "win32":
                dll_path = self._find_unrar_dll()
                if dll_path:
                    rarfile.UNRAR_LIB = dll_path
                    logger.info("Configurado UnRAR DLL: %s", dll_path)
        except ImportError:
            pass

    def _find_unrar_dll(self) -> str | None:
        dll_names = ["UnRAR.dll", "UnRAR64.dll"]
        assets = self._get_assets_path()
        for name in dll_names:
            dll_path = assets / name
            if dll_path.exists():
                logger.info("Found UnRAR DLL: %s", dll_path)
                return str(dll_path)
        for name in dll_names:
            found = shutil.which(name.lower().replace(".dll", ""))
            if found:
                return found
        return None

    def is_archive(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path.lower())[1]
        return ext in [".zip", ".tar", ".gz", ".bz2", ".rar", ".7z"]

    def mount_archive(self, archive_path: str) -> str | None:
        path = Path(archive_path)
        if not path.exists():
            return None

        # Si ya está montado, retornar
        if str(path) in self.mounted_archives:
            self.mounted_archives[str(path)].last_access = time.time()
            return str(self.mounted_archives[str(path)].mount_point)

        # Crear punto de montaje
        hash_id = hashlib.md5(str(path).encode()).hexdigest()[:10]
        mount_point = self.temp_base / f"mnt_{hash_id}"

        try:
            if mount_point.exists():
                shutil.rmtree(mount_point)
            mount_point.mkdir(parents=True, exist_ok=True)

            if self._extract_archive(path, mount_point):
                self.mounted_archives[str(path)] = MountInfo(
                    archive_path=path,
                    mount_point=mount_point,
                    created_at=time.time(),
                    last_access=time.time(),
                    size=path.stat().st_size,
                )
                return str(mount_point)
        except Exception as e:
            logger.exception("Error montando archivo %s: %s", path, e)  # noqa: TRY401

        return None

    def _extract_archive(self, path: Path, dest: Path, password: str | None = None) -> bool:
        ext = path.suffix.lower()
        try:
            if ext == ".zip":
                with zipfile.ZipFile(path, "r") as z:
                    if password:
                        z.setpassword(password.encode())
                    z.extractall(dest)
                return True
            if ext in [".tar", ".gz", ".bz2"]:
                with tarfile.open(path, "r:*") as t:
                    t.extractall(dest)
                return True
            if ext == ".rar":
                return self._extract_rar(path, dest, password)
            if ext == ".7z":
                return self._extract_7z(path, dest, password)
        except Exception as e:
            logger.exception("Error extrayendo %s: %s", path, e)  # noqa: TRY401
        return False

    def _extract_rar(self, path: Path, dest: Path, password: str | None = None) -> bool:
        # Intentar rarfile primero con la DLL
        try:
            dll_path = self._find_unrar_dll()
            if dll_path:
                rarfile.UNRAR_LIB = dll_path
            with rarfile.RarFile(str(path)) as r:
                if password:
                    r.setpassword(password)
                r.extractall(str(dest))
            logger.info("Extracted RAR using rarfile: %s", path)
            return True  # noqa: TRY300
        except Exception as e:  # noqa: BLE001
            logger.warning("rarfile failed: %s", e)
            # Fallback: usar UnRAR.exe CLI
            if self.RAR_EXE:
                try:
                    cmd = [self.RAR_EXE, "x", "-y"]
                    if password:
                        cmd.extend([f"-p{password}"])
                    cmd.extend([str(path), str(dest)])
                    result = subprocess.run(cmd, capture_output=True, timeout=120)  # noqa: PLW1510
                    if result.returncode == 0:
                        logger.info("Extracted RAR using CLI: %s", path)
                        return True
                    logger.exception("UnRAR CLI failed: %s", result)
                except Exception as cli_e:
                    logger.exception("UnRAR CLI error: %s", cli_e)  # noqa: TRY401
        return False

    def _extract_7z(self, path: Path, dest: Path, password: str | None = None) -> bool:
        # Intentar py7zr primero
        try:
            with py7zr.SevenZipFile(str(path), mode="r", password=password) as z:
                z.extractall(str(dest))
            logger.info("Extracted 7z using py7zr: %s", path)
            return True  # noqa: TRY300
        except Exception as e:  # noqa: BLE001
            logger.warning("py7zr failed: %s", e)
            # Fallback: usar 7z.exe CLI
            if self.SEVEN_ZIP_EXE:
                try:
                    cmd = [self.SEVEN_ZIP_EXE, "x", "-y"]
                    if password:
                        cmd.extend([f"-p{password}"])
                    cmd.extend([str(path), f"-o{dest!s}"])
                    result = subprocess.run(cmd, capture_output=True, timeout=300)  # noqa: PLW1510
                    if result.returncode == 0:
                        logger.info("Extracted 7z using CLI: %s", path)
                        return True
                    logger.exception("7z CLI failed: %s", result)
                except Exception as cli_e:
                    logger.exception("7z CLI error: %s", cli_e)  # noqa: TRY401
        return False

    def unmount_archive(self, archive_path: str) -> bool:
        if archive_path in self.mounted_archives:
            mount = self.mounted_archives.pop(archive_path)
            try:
                if mount.mount_point.exists():
                    shutil.rmtree(mount.mount_point)
                return True  # noqa: TRY300
            except Exception:  # noqa: BLE001
                pass
        return False

    def get_mount_info(self, path: str) -> MountInfo | None:
        for mount in self.mounted_archives.values():
            if path.startswith(str(mount.mount_point)):
                return mount
        return None

    def get_display_path(self, mount_point: str) -> str:
        """Retorna la ruta del archivo original en lugar del punto de montaje"""
        info = self.get_mount_info(mount_point)
        if info:
            return f"{info.archive_path}►"
        return mount_point

    def is_inside_archive(self, path: str) -> bool:
        """Indica si la ruta está dentro de un archivo comprimido"""
        return self.get_mount_info(path) is not None


# Instancia global
archive_handler = ArchiveHandler()
